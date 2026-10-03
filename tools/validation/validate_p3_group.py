"""N>1 group ERP validation: P3b (target vs standard) on ERP CORE (Kappenman 2021).

Active visual oddball: 5 letters, one is the block target. Event `value` is two digits —
tens = block target letter, units = trial stimulus letter — so a TARGET trial is value
with tens==units (11,22,33,44,55; ~20%), a STANDARD is tens!=units (~80%). The P3b is the
target-minus-standard centro-parietal positivity ~300-500 ms (Polich 2007).

  python tools/validation/validate_p3_group.py --subjects 20
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _certified_output import guard_certified_output  # noqa: E402

warnings.filterwarnings("ignore")

ROI = ["Fz", "Cz", "Pz", "CPz"]
P3_WIN = (0.30, 0.50)
TARGET, STANDARD = 1, 2
# minimum retained trials per recipes/p300-oddball/RECIPE.md (>=30 target, >=100 standard)
MIN_TARGET, MIN_STANDARD = 30, 100
DATA = Path.home() / "mne_data" / "erpcore-P3"


def _p3_events(ev_tsv, sfreq):
    import pandas as pd
    ev = pd.read_csv(ev_tsv, sep="\t")
    stim = ev[(ev["value"] >= 11) & (ev["value"] <= 55)].copy()
    is_target = (stim["value"] // 10) == (stim["value"] % 10)
    codes = np.where(is_target, TARGET, STANDARD).astype(int)
    samples = np.round(stim["onset"].to_numpy() * sfreq).astype(int)
    return np.c_[samples, np.zeros_like(samples), codes]


def load_subject(sub, sfreq=256.0):
    import mne
    eeg = DATA / sub / "eeg"
    raw = mne.io.read_raw_eeglab(eeg / f"{sub}_task-P3_eeg.set", preload=True, verbose="ERROR")
    raw.drop_channels([c for c in ["HEOG_left", "HEOG_right", "VEOG_lower"] if c in raw.ch_names])
    raw.pick_types(eeg=True, verbose="ERROR")
    raw.set_montage("standard_1020", match_case=False, on_missing="warn", verbose="ERROR")
    raw.filter(0.1, 30.0, n_jobs=1, verbose="ERROR")
    if sfreq and abs(raw.info["sfreq"] - sfreq) > 1:
        raw.resample(sfreq, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    events = _p3_events(eeg / f"{sub}_task-P3_events.tsv", raw.info["sfreq"])
    events = events[(events[:, 0] > 0) & (events[:, 0] < raw.n_times)]
    return raw, events


def subject_p3(sub):
    import mne
    raw, events = load_subject(sub)
    # No peak-to-peak rejection: the active P3 task over a 1 s epoch without ICA would lose
    # most trials to blinks/EMG at 100 uV. Averaging all epochs keeps N and — since BOTH
    # pipelines then average the identical trial set — removes any epoch-selection divergence,
    # the cleanest possible cross-tool numeric comparison (see docs/BENCHMARK.md).
    epochs = mne.Epochs(raw, events, event_id={"standard": STANDARD, "target": TARGET},
                        tmin=-0.2, tmax=0.8, baseline=(-0.2, 0.0), preload=True,
                        reject=None, verbose="ERROR")
    if len(epochs["target"]) < MIN_TARGET or len(epochs["standard"]) < MIN_STANDARD:
        raise RuntimeError(f"too few epochs (tgt={len(epochs['target'])}, std={len(epochs['standard'])})")
    evk_std = epochs["standard"].average()
    evk_tgt = epochs["target"].average()
    diff = mne.combine_evoked([evk_tgt, evk_std], weights=[1, -1])   # target - standard
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= P3_WIN[0]) & (diff.times <= P3_WIN[1])
    p3_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return diff, p3_uV, len(epochs["target"]), len(epochs["standard"])


def main():
    import mne
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--out", default="tools/validation/p3_group_results.json")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting the certified baseline with a different N")
    args = ap.parse_args()

    subs = sorted([p.name for p in DATA.glob("sub-*")])[: args.subjects]
    per, diffs, info_ref, times_ref = [], [], None, None
    for sub in subs:
        try:
            diff, p3_uV, ntgt, nstd = subject_p3(sub)
            per.append({"subject": sub, "p3_uV": round(p3_uV, 3), "n_dev": ntgt, "n_std": nstd})
            diffs.append(diff.data)
            if info_ref is None:
                info_ref, times_ref = diff.info, diff.times
            print(f"  {sub}: P3={p3_uV:+.3f} uV (tgt={ntgt}, std={nstd})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    from scipy import stats as sstats
    X = np.array(diffs)
    tmask = (times_ref >= P3_WIN[0]) & (times_ref <= P3_WIN[1])
    Xw = X[:, :, tmask].transpose(0, 2, 1)
    adj, _ = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    df = Xw.shape[0] - 1
    t_thr = sstats.t.ppf(1 - 0.05, df)                        # one-sided (P3 positive)
    _, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        Xw, n_permutations=5000, threshold=t_thr, tail=1, seed=42,
        adjacency=adj, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    p3s = np.array([p["p3_uV"] for p in per])
    t1, p1 = sstats.ttest_1samp(p3s, 0)

    results = {
        "dataset": "ERP CORE P3 (Kappenman 2021), target - standard (visual oddball)",
        "n_subjects": len(per), "roi": ROI, "p3_window_s": list(P3_WIN),
        "grand_mean_p3_uV": round(float(p3s.mean()), 3),
        "p3_sem_uV": round(float(p3s.std(ddof=1) / np.sqrt(len(p3s))), 3),
        "one_sample_t": round(float(t1), 2), "one_sample_p": float(p1),
        "cohens_dz": round(float(p3s.mean() / p3s.std(ddof=1)), 3),
        "second_level_cluster": {
            "n_clusters": int(len(clusters)), "n_significant": len(sig),
            "min_p": float(min(cl_p)) if len(cl_p) else 1.0, "significant": sig,
        },
        "PASS": bool(p3s.mean() > 0 and p1 < 0.05 and len(sig) >= 1),
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    guard_certified_output(args.out, "tools/validation/p3_group_results.json", len(per), args.force)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ga = X.mean(0)
        roi_idx = [info_ref["ch_names"].index(c) for c in ROI if c in info_ref["ch_names"]]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        ax[0].plot(times_ref * 1000, ga[roi_idx].mean(0) * 1e6, "k", lw=2)
        ax[0].axvspan(P3_WIN[0] * 1000, P3_WIN[1] * 1000, color="orange", alpha=0.2)
        ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", ls="--", lw=0.6)
        ax[0].set(xlabel="ms", ylabel="µV", xlim=(-200, 800),
                  title=f"A) Grand-avg P3 (target-standard) @ {'/'.join(ROI)}\nN={len(per)}, p={p1:.1e}")
        ax[1].bar(range(len(p3s)), p3s, color=["C0" if m > 0 else "C3" for m in p3s])
        ax[1].axhline(p3s.mean(), color="k", ls="--", label=f"mean={p3s.mean():.2f}µV")
        ax[1].set(xlabel="subject", ylabel="P3 µV", title="B) Per-subject P3 amplitude")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        figp = "tools/validation/figures/p3_group.png"
        Path(figp).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        print(f"Figure: {figp}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print(f"\n==== P3 GROUP (N={len(per)}) ====")
    print(f"grand-mean P3 = {p3s.mean():+.3f} µV (SEM {results['p3_sem_uV']}), "
          f"t={t1:.2f} p={p1:.2e} dz={results['cohens_dz']}")
    print(f"second-level cluster: {results['second_level_cluster']['n_significant']} sig, "
          f"min_p={results['second_level_cluster']['min_p']:.4f} -> PASS={results['PASS']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
