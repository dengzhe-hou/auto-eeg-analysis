"""Numerical regression tests for the AEA deterministic pipeline.

Run::

    pytest tools/tests/test_regression.py -v

The first run downloads the MNE sample dataset (~1.5 GB, cached afterwards).

These tests turn AEA's "reproducible / validated" claim into something
*falsifiable*: if an MNE / NumPy / SciPy upgrade silently shifts an ERP
amplitude or a cluster statistic, CI fails here instead of in a paper.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from regression_pipeline import BASELINE_PATH, resolve_raw_path, run_pipeline  # noqa: E402

VALID_ICLABEL = {
    "brain", "muscle artifact", "eye blink", "heart beat",
    "line noise", "channel noise", "other",
}

# These tests need the MNE sample dataset (~1.5 GB). On a machine that does not already have it,
# every one of them used to fail with a raw FileNotFoundError -- so anyone trying AEA for the first
# time saw a wall of red and could reasonably conclude the project was broken. Skip cleanly
# instead, and make fetching an explicit opt-in.
FETCH = os.environ.get("AEA_FETCH_DATA") == "1"


def _sample_present() -> bool:
    try:
        resolve_raw_path(download=False)
        return True
    except Exception:                       # noqa: BLE001 — absent, unreadable, either way: skip
        return False


pytestmark = pytest.mark.skipif(
    not (_sample_present() or FETCH),
    reason="MNE sample dataset (~1.5 GB) not present. Set AEA_FETCH_DATA=1 to download and run.",
)


@pytest.fixture(scope="module")
def metrics() -> dict:
    """Run the deterministic pipeline once for the whole module."""
    return run_pipeline(download=FETCH)


@pytest.fixture(scope="module")
def baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8-sig"))


# --- Exact structural invariants ----------------------------------------------

def test_channel_count(metrics, baseline):
    assert metrics["n_eeg_channels"] == baseline["n_eeg_channels"]


def test_epoch_counts(metrics, baseline):
    assert metrics["n_epochs"] == baseline["n_epochs"]


# --- ERP amplitudes (deterministic; allow tiny cross-version float drift) -----

def test_erp_amplitudes(metrics, baseline):
    m, b = metrics["erp"], baseline["erp"]
    assert m["aud_n100_uV"] == pytest.approx(b["aud_n100_uV"], abs=0.05)
    assert m["vis_n100_uV"] == pytest.approx(b["vis_n100_uV"], abs=0.05)
    assert m["diff_uV"] == pytest.approx(b["diff_uV"], abs=0.05)
    # Auditory N100 is genuinely more negative than visual at the ROI:
    assert m["diff_uV"] < 0


def test_erp_peak_latency(metrics, baseline):
    # Within one sample (~6.7 ms at the sample sfreq) of the baseline peak.
    assert metrics["erp"]["aud_peak_latency_ms"] == pytest.approx(
        baseline["erp"]["aud_peak_latency_ms"], abs=7.0
    )


# --- Cluster-permutation statistics -------------------------------------------

def test_cluster_significance(metrics, baseline):
    # The number of *significant* clusters is the load-bearing claim; pin it.
    assert metrics["stats"]["n_significant"] == baseline["stats"]["n_significant"]
    assert metrics["stats"]["n_significant"] >= 1


def test_cluster_statistics(metrics, baseline):
    m, b = metrics["stats"], baseline["stats"]
    assert m["min_cluster_p"] == pytest.approx(b["min_cluster_p"], abs=0.02)
    assert m["max_abs_t_sum"] == pytest.approx(b["max_abs_t_sum"], rel=0.05)
    assert m["cohens_d"] == pytest.approx(b["cohens_d"], abs=0.02)


# --- ICA / ICLabel smoke test (tolerance-only: guards API drift, not floats) --

def test_ica_iclabel_smoke():
    """ICA + ICLabel must *run* and return a sane, correctly-shaped labeling.

    Deliberately does NOT pin float outputs: extended-Infomax + ONNX ICLabel are
    not bit-reproducible across BLAS / onnxruntime builds. This only catches the
    API breaking (the failure mode the strict numeric test cannot see because it
    excludes ICA on purpose).
    """
    pytest.importorskip("onnxruntime", reason="onnxruntime required by mne-icalabel")
    # onnxruntime is a popular standalone package, so having it does not imply mne-icalabel.
    pytest.importorskip("mne_icalabel")
    import mne
    from mne_icalabel import label_components

    mne.set_log_level("ERROR")
    from regression_pipeline import resolve_raw_path

    raw = mne.io.read_raw_fif(resolve_raw_path(), preload=True)
    raw.pick_types(meg=False, eeg=True, exclude="bads")
    raw.crop(tmax=60.0)  # keep the smoke test fast
    raw.set_eeg_reference("average", projection=False)
    raw_hp = raw.copy().filter(l_freq=1.0, h_freq=None)

    n_req = 15
    ica = mne.preprocessing.ICA(
        n_components=n_req, method="infomax", random_state=42,
        max_iter="auto", fit_params=dict(extended=True),
    )
    ica.fit(raw_hp)
    assert ica.n_components_ == n_req

    labels = label_components(raw_hp, ica, method="iclabel")
    label_list = labels["labels"]
    assert len(label_list) == ica.n_components_
    assert set(label_list).issubset(VALID_ICLABEL)

    excluded = [i for i, l in enumerate(label_list)
                if l in {"eye blink", "muscle artifact", "heart beat"}]
    assert 0 <= len(excluded) <= ica.n_components_
