"""AEA numerical regression pipeline.

A *deterministic*, self-contained ERP + cluster-permutation pipeline on the
freely-downloadable MNE sample dataset (auditory vs. visual). Its only job is
to produce a small dict of key numbers that a regression test pins against a
committed baseline (``tools/baselines/sample_pipeline.json``), so that:

  * the "reproducible / validated" claim becomes *falsifiable*, and
  * a silent MNE / NumPy / SciPy API change that shifts the numbers is caught
    on every CI run instead of in someone's paper.

Scope note — why no ICA here:
  ICA (extended Infomax) + ICLabel (ONNX) is the *least* bit-reproducible and
  slowest part of the pipeline; pinning its floats across BLAS / onnxruntime
  versions would make the test flaky. The numbers that are actually *claimed*
  (ERP amplitudes, cluster p / t_sum / Cohen's d) are computed by the
  deterministic filter -> epoch -> average -> cluster-perm chain and are what we
  regress on. A separate, tolerance-only ICA *smoke* check lives in
  ``tools/tests/test_regression.py``.

Usage::

    python tools/regression_pipeline.py                 # print metrics
    python tools/regression_pipeline.py --write-baseline # (re)generate baseline
    python tools/regression_pipeline.py --check          # compare to baseline
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

BASELINE_PATH = Path(__file__).parent / "baselines" / "sample_pipeline.json"

# --- Fixed, deterministic analysis configuration -------------------------------
# A fixed frontocentral ROI of always-present, non-bad sample EEG channels.
# (Sample marks only 'EEG 053' bad; all of these exist and are good.)
ROI = ["EEG 003", "EEG 004", "EEG 005", "EEG 010", "EEG 011", "EEG 012"]
N100_WINDOW = (0.08, 0.15)      # auditory N100 amplitude window (s)
STATS_WINDOW = (0.05, 0.20)     # cluster-permutation search window (s)
REJECT_UV = 150e-6
SEED = 42
N_PERMUTATIONS = 1000


def resolve_raw_path(data_path: str | None = None, download: bool = True) -> Path:
    """Return the sample auditory/visual raw file, fetching the dataset if needed."""
    import mne

    if data_path is not None:
        base = Path(data_path)
    else:
        base = Path(mne.datasets.sample.data_path(download=download))
    raw_path = base / "MEG" / "sample" / "sample_audvis_filt-0-40_raw.fif"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Sample raw not found at {raw_path}. "
            "Run `python -c \"import mne; mne.datasets.sample.data_path()\"` to fetch it."
        )
    return raw_path


def run_pipeline(
    data_path: str | None = None,
    n_permutations: int = N_PERMUTATIONS,
    download: bool = True,
) -> dict:
    """Run the deterministic ERP + cluster-perm pipeline; return key metrics."""
    import mne
    from scipy import stats as scipy_stats

    mne.set_log_level("ERROR")
    raw_path = resolve_raw_path(data_path, download=download)

    # --- Preprocess: EEG only, drop bads, average reference (data is 0-40 Hz) ---
    raw = mne.io.read_raw_fif(raw_path, preload=True)
    raw.pick_types(meg=False, eeg=True, stim=True, exclude="bads")
    raw.set_eeg_reference("average", projection=False)
    n_eeg = len(mne.pick_types(raw.info, eeg=True))

    # --- Epoch: auditory (1,2) vs visual (3,4) -------------------------------
    events = mne.find_events(raw, stim_channel="STI 014")
    event_id = {"aud/l": 1, "aud/r": 2, "vis/l": 3, "vis/r": 4}
    epochs = mne.Epochs(
        raw, events, event_id=event_id, tmin=-0.2, tmax=0.5,
        baseline=(-0.2, 0), preload=True, reject=dict(eeg=REJECT_UV),
    )
    aud = epochs["aud/l", "aud/r"]
    vis = epochs["vis/l", "vis/r"]
    n_aud, n_vis = len(aud), len(vis)

    # --- ERP: auditory N100 amplitude at ROI ---------------------------------
    evk_aud, evk_vis = aud.average(), vis.average()
    roi = [c for c in ROI if c in evk_aud.ch_names]
    roi_idx = [evk_aud.ch_names.index(c) for c in roi]
    t_mask = (evk_aud.times >= N100_WINDOW[0]) & (evk_aud.times <= N100_WINDOW[1])

    aud_n100 = float(evk_aud.data[roi_idx][:, t_mask].mean() * 1e6)
    vis_n100 = float(evk_vis.data[roi_idx][:, t_mask].mean() * 1e6)

    # Auditory peak latency (most negative ROI-mean sample) within the window
    aud_roi_tc = evk_aud.data[roi_idx].mean(axis=0)
    win_times = evk_aud.times[t_mask]
    peak_lat = float(win_times[np.argmin(aud_roi_tc[t_mask])] * 1000)

    # --- Stats: paired spatio-temporal cluster permutation (aud - vis) -------
    n_min = min(n_aud, n_vis)
    X_aud = aud.get_data(copy=True)[:n_min]
    X_vis = vis.get_data(copy=True)[:n_min]
    X_diff = X_aud - X_vis  # (trials, channels, times)

    ch_idx = [epochs.ch_names.index(c) for c in roi]
    s_mask = (epochs.times >= STATS_WINDOW[0]) & (epochs.times <= STATS_WINDOW[1])
    X_stat = X_diff[:, ch_idx, :][:, :, s_mask].transpose(0, 2, 1)  # (trials, times, ch)

    roi_info = mne.pick_info(epochs.info, ch_idx)
    adjacency, _ = mne.channels.find_ch_adjacency(roi_info, ch_type="eeg")

    df = X_stat.shape[0] - 1
    t_thr = scipy_stats.t.ppf(1 - 0.025, df)  # two-sided 0.05
    t_obs, clusters, cluster_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        X_stat, n_permutations=n_permutations, threshold=t_thr, tail=0,
        seed=SEED, adjacency=adjacency, out_type="mask", n_jobs=1, verbose=False,
    )
    sig = [p for p in cluster_p if p < 0.05]
    t_sums = [float(t_obs[clusters[i]].sum()) for i in range(len(clusters))]
    max_abs_t_sum = float(max((abs(t) for t in t_sums), default=0.0))
    min_p = float(min(cluster_p)) if len(cluster_p) else 1.0

    roi_mean_diff = X_diff[:, ch_idx, :][:, :, s_mask].mean(axis=(1, 2))
    cohens_d = float(roi_mean_diff.mean() / roi_mean_diff.std())

    return {
        "dataset": "mne.datasets.sample (sample_audvis_filt-0-40_raw.fif)",
        "config": {
            "roi": roi, "n100_window_s": list(N100_WINDOW),
            "stats_window_s": list(STATS_WINDOW), "reject_uV": REJECT_UV * 1e6,
            "seed": SEED, "n_permutations": n_permutations,
        },
        "n_eeg_channels": int(n_eeg),
        "n_epochs": {"auditory": int(n_aud), "visual": int(n_vis), "paired": int(n_min)},
        "erp": {
            "aud_n100_uV": round(aud_n100, 4),
            "vis_n100_uV": round(vis_n100, 4),
            "diff_uV": round(aud_n100 - vis_n100, 4),
            "aud_peak_latency_ms": round(peak_lat, 1),
        },
        "stats": {
            "threshold_t": round(float(t_thr), 4),
            "n_clusters": int(len(clusters)),
            "n_significant": int(len(sig)),
            "min_cluster_p": round(min_p, 4),
            "max_abs_t_sum": round(max_abs_t_sum, 2),
            "cohens_d": round(cohens_d, 4),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-baseline", action="store_true",
                    help="run the pipeline and overwrite the committed baseline JSON")
    ap.add_argument("--check", action="store_true",
                    help="run the pipeline and diff against the committed baseline")
    ap.add_argument("--data-path", default=None,
                    help="MNE sample data_path root (default: auto-resolve/download)")
    args = ap.parse_args()

    metrics = run_pipeline(data_path=args.data_path)
    print(json.dumps(metrics, indent=2))

    if args.write_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        print(f"\nBaseline written: {BASELINE_PATH}")
    elif args.check:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8-sig"))
        same = metrics == baseline
        print(f"\nMatches baseline exactly: {same}")
        if not same:
            raise SystemExit("Metrics differ from baseline (use the pytest test for tolerant comparison).")


if __name__ == "__main__":
    main()
