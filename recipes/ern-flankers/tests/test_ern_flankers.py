"""Numerical regression guard for the `ern-flankers` recipe.

This is the reference exemplar of the recipe-acceptance gate the ROADMAP
requires ("numerical regression test passes"). It re-runs the recipe's two
*supported* claims on ERP CORE Subject-001 Flankers and pins their qualitative
verdicts plus bounded magnitudes against the validated results (RECIPE.md):

    C2 (ERN):   incompatible - compatible diff ~= -1.15 uV  (more negative)
    C3 (theta): incompatible - compatible diff ~= +0.12 dB  (more positive)

Bounds are deliberately wide, not bit-exact: extended-Infomax ICA + ICLabel are
not reproducible across BLAS / onnxruntime builds, so the guard catches sign
flips and gross drift (the failure modes that matter) without flaking on
platform-level float jitter.

ERP CORE is NOT fetchable via mne.datasets, so this test SKIPS unless the data
is present. To run it::

    # place ERP-CORE_Subject-001_Task-Flankers_eeg.fif under <MNE_DATA>/MNE-ERP-CORE-data/
    # (Kappenman et al. 2021, https://doi.org/10.18115/D5JW4R), or:
    export AEA_ERP_CORE_FLANKERS=/path/to/ERP-CORE_Subject-001_Task-Flankers_eeg.fif
    pytest recipes/ern-flankers/tests/ -v
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

SEED = 42
ROI = ["FCz", "Fz", "Cz"]


def _resolve_flankers() -> Path | None:
    import mne

    cands = []
    env = os.environ.get("AEA_ERP_CORE_FLANKERS")
    if env:
        cands.append(Path(env))
    mne_data = os.environ.get("MNE_DATA") or mne.get_config("MNE_DATA") or str(Path.home() / "mne_data")
    cands.append(Path(mne_data) / "MNE-ERP-CORE-data" / "ERP-CORE_Subject-001_Task-Flankers_eeg.fif")
    for c in cands:
        if c.exists():
            return c
    return None


@pytest.fixture(scope="module")
def results() -> dict:
    path = _resolve_flankers()
    if path is None:
        pytest.skip(
            "ERP CORE Flankers data not found (not auto-downloadable). "
            "Set AEA_ERP_CORE_FLANKERS or place it under <MNE_DATA>/MNE-ERP-CORE-data/."
        )
    import mne
    from mne_icalabel import label_components

    mne.set_log_level("ERROR")
    np.random.seed(SEED)

    # --- Preprocess (0.1-30 FIR, 60 Hz notch, average ref) ---
    raw = mne.io.read_raw_fif(path, preload=True).pick_types(eeg=True)
    raw.filter(0.1, 30.0, n_jobs=1).notch_filter(60.0, n_jobs=1)
    raw.set_eeg_reference("average", projection=False)

    # --- ICA + ICLabel ---
    raw_hp = raw.copy().filter(l_freq=1.0, h_freq=None)
    ica = mne.preprocessing.ICA(n_components=15, method="infomax", random_state=SEED,
                                max_iter="auto", fit_params=dict(extended=True))
    ica.fit(raw_hp)
    labels = label_components(raw_hp, ica, method="iclabel")["labels"]
    ica.exclude = [i for i, l in enumerate(labels)
                   if l in {"eye blink", "muscle artifact", "heart beat"}]
    raw_clean = raw.copy()
    ica.apply(raw_clean)

    # --- Events: stim codes 3-6, response codes 1-2 (ERP CORE Flankers) ---
    events, _ = mne.events_from_annotations(raw)
    stim = events[np.isin(events[:, 2], [3, 4, 5, 6])]
    resp = events[np.isin(events[:, 2], [1, 2])]

    # Response-locked epochs (C2): label each response by its preceding stimulus
    comp_resp, incomp_resp = [], []
    for r in resp:
        prior = stim[stim[:, 0] < r[0]]
        if not len(prior):
            continue
        code = int(prior[-1, 2])
        rr = r.copy()
        if code in (3, 4):
            rr[2] = 201
            comp_resp.append(rr)
        elif code in (5, 6):
            rr[2] = 202
            incomp_resp.append(rr)
    resp_events = np.vstack([comp_resp, incomp_resp])
    resp_events = resp_events[resp_events[:, 0].argsort()]
    epochs_resp = mne.Epochs(raw_clean, resp_events, event_id={"comp": 201, "incomp": 202},
                             tmin=-0.4, tmax=0.6, baseline=(-0.4, -0.2),
                             preload=True, reject=dict(eeg=150e-6))

    roi_idx = [epochs_resp.ch_names.index(c) for c in ROI]
    t_ern = (epochs_resp.times >= 0.0) & (epochs_resp.times <= 0.1)
    comp_ern = epochs_resp["comp"].average().data[roi_idx][:, t_ern].mean() * 1e6
    incomp_ern = epochs_resp["incomp"].average().data[roi_idx][:, t_ern].mean() * 1e6
    c2_diff = float(incomp_ern - comp_ern)

    # Stimulus-locked theta (C3)
    stim_ev = stim.copy()
    stim_ev[np.isin(stim_ev[:, 2], [3, 4]), 2] = 101
    stim_ev[np.isin(stim_ev[:, 2], [5, 6]), 2] = 102
    epochs_stim = mne.Epochs(raw_clean, stim_ev, event_id={"comp": 101, "incomp": 102},
                             tmin=-0.2, tmax=0.8, baseline=(-0.2, 0),
                             preload=True, reject=dict(eeg=150e-6))
    freqs = np.arange(4, 30, 1)
    n_cycles = freqs / 3
    kw = dict(freqs=freqs, n_cycles=n_cycles, return_itc=False, decim=4, average=True, verbose=False)
    tfr_comp = epochs_stim["comp"].compute_tfr(method="morlet", **kw).apply_baseline((-0.2, 0), mode="logratio")
    tfr_incomp = epochs_stim["incomp"].compute_tfr(method="morlet", **kw).apply_baseline((-0.2, 0), mode="logratio")
    theta = (freqs >= 4) & (freqs <= 8)
    t_theta = (tfr_comp.times >= 0.2) & (tfr_comp.times <= 0.5)
    roi_tfr = [tfr_comp.ch_names.index(c) for c in ROI]
    comp_theta = tfr_comp.data[roi_tfr][:, theta][:, :, t_theta].mean()
    incomp_theta = tfr_incomp.data[roi_tfr][:, theta][:, :, t_theta].mean()
    c3_diff = float(incomp_theta - comp_theta)

    return {"c2_ern_diff_uV": c2_diff, "c3_theta_diff_dB": c3_diff,
            "n_comp_resp": len(epochs_resp["comp"]), "n_incomp_resp": len(epochs_resp["incomp"])}


def test_c2_ern_more_negative_for_incompatible(results):
    # Validated diff = -1.15 uV. Guard against sign flips / gross drift.
    diff = results["c2_ern_diff_uV"]
    assert diff < 0, f"ERN should be more negative for incompatible, got {diff:+.2f} uV"
    assert -3.0 < diff < -0.2, f"ERN diff {diff:+.2f} uV outside expected band [-3.0, -0.2]"


def test_c3_theta_greater_for_incompatible(results):
    # Validated diff = +0.12 dB. Frontal theta enhanced by conflict.
    diff = results["c3_theta_diff_dB"]
    assert diff > 0, f"Frontal theta should be greater for incompatible, got {diff:+.3f} dB"
    assert diff < 0.6, f"Theta diff {diff:+.3f} dB implausibly large (>0.6)"


def test_trial_counts_sane(results):
    assert results["n_comp_resp"] >= 40
    assert results["n_incomp_resp"] >= 40
