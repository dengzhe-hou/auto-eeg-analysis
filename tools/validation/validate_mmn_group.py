"""N>1 group ERP validation: Mismatch Negativity (MMN) on ERP CORE (Kappenman 2021).

A genuine across-subject ERP grand-average + second-level cluster test — the canonical
"retire N=1" analysis. ERP CORE MMN is a passive auditory oddball: frequent 80 dB
standards (value 80) and rare 70 dB deviants (value 70). The MMN is the
deviant-minus-standard frontocentral negativity ~100-250 ms (Naatanen et al. 2007).

  python tools/validation/validate_mmn_group.py --subjects 40
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _certified_output import guard_certified_output  # noqa: E402

warnings.filterwarnings("ignore")

ROI = ["Fz", "FCz", "Cz"]
MMN_WIN = (0.10, 0.25)
STD_VAL, DEV_VAL = 80, 70
DATA = Path.home() / "mne_data" / "MNE-erpcoremmn2021-data"


def load_subject(sub: str, sfreq=256.0):
    import mne, pandas as pd
    eeg = DATA / sub / "eeg"
    setf = eeg / f"{sub}_task-MMN_eeg.set"
    raw = mne.io.read_raw_eeglab(setf, preload=True, verbose="ERROR")
    # ERP CORE .set types the EOG channels as EEG; drop them by name so they don't
    # pollute the average reference or the channel adjacency (overlapping positions).
    raw.drop_channels([c for c in ["HEOG_left", "HEOG_right", "VEOG_lower"] if c in raw.ch_names])
    raw.pick_types(eeg=True, verbose="ERROR")
    # Set a clean standard montage on the 30 EEG channels (match_case=False so ERP CORE's
    # 'FP1'/'FP2' match standard 'Fp1'/'Fp2'; this also replaces the .set's 33-point dig).
    raw.set_montage("standard_1020", match_case=False, on_missing="warn", verbose="ERROR")
    raw.filter(0.1, 30.0, n_jobs=1, verbose="ERROR")
    if sfreq and abs(raw.info["sfreq"] - sfreq) > 1:
        raw.resample(sfreq, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    ev = pd.read_csv(eeg / f"{sub}_task-MMN_events.tsv", sep="\t")
    ev = ev[ev["value"].isin([STD_VAL, DEV_VAL])]
    # rescale sample index to the (possibly resampled) rate
    orig_sf = 1024.0
    samples = np.round(ev["onset"].to_numpy() * raw.info["sfreq"]).astype(int)
    events = np.c_[samples, np.zeros_like(samples), ev["value"].to_numpy().astype(int)]
    events = events[(events[:, 0] > 0) & (events[:, 0] < raw.n_times)]
    return raw, events


def subject_mmn(sub):
    import mne
    raw, events = load_subject(sub)
    epochs = mne.Epochs(raw, events, event_id={"standard": STD_VAL, "deviant": DEV_VAL},
                        tmin=-0.2, tmax=0.5, baseline=(-0.2, 0.0), preload=True,
                        reject=dict(eeg=100e-6), verbose="ERROR")
    # Minimum trial counts per recipes/mmn-oddball/RECIPE.md (min_trials_per_condition: 50;
    # "≥ 50 deviants and ≥ 150 standards per subject after artifact rejection").
    if len(epochs["deviant"]) < 50 or len(epochs["standard"]) < 150:
        raise RuntimeError(f"too few epochs (dev={len(epochs['deviant'])}, std={len(epochs['standard'])})")
    evk_std = epochs["standard"].average()
    evk_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([evk_dev, evk_std], weights=[1, -1])  # deviant - standard
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= MMN_WIN[0]) & (diff.times <= MMN_WIN[1])
    mmn_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return diff, mmn_uV, len(epochs["deviant"]), len(epochs["standard"])


def main():
    import mne
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--out", default="tools/validation/mmn_group_results.json")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting the certified baseline with a different N")
    args = ap.parse_args()

    subs = sorted([p.name for p in DATA.glob("sub-*")])[: args.subjects]
    per, diffs, info_ref = [], [], None
    for sub in subs:
        try:
            diff, mmn_uV, ndev, nstd = subject_mmn(sub)
            per.append({"subject": sub, "mmn_uV": round(mmn_uV, 3), "n_dev": ndev, "n_std": nstd})
            diffs.append(diff.data)            # (ch, times)
            if info_ref is None:
                info_ref, times_ref = diff.info, diff.times
            print(f"  {sub}: MMN={mmn_uV:+.3f} uV (dev={ndev}, std={nstd})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    # --- Second-level spatiotemporal cluster test (deviant-standard, MMN window) ---
    from scipy import stats as sstats
    X = np.array(diffs)                                   # (subj, ch, times)
    tmask = (times_ref >= MMN_WIN[0]) & (times_ref <= MMN_WIN[1])
    Xw = X[:, :, tmask].transpose(0, 2, 1)               # (subj, times, ch)
    adj, _ = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    df = Xw.shape[0] - 1
    t_thr = -sstats.t.ppf(1 - 0.05, df)                  # one-sided (MMN negative)
    t_obs, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        Xw, n_permutations=5000, threshold=t_thr, tail=-1, seed=42,
        adjacency=adj, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    mmns = np.array([p["mmn_uV"] for p in per])
    t1, p1 = sstats.ttest_1samp(mmns, 0)

    results = {
        "dataset": "ERP CORE MMN (mne erpcoremmn2021), deviant(70dB) - standard(80dB)",
        "n_subjects": len(per), "roi": ROI, "mmn_window_s": list(MMN_WIN),
        "grand_mean_mmn_uV": round(float(mmns.mean()), 3),
        "mmn_sem_uV": round(float(mmns.std(ddof=1) / np.sqrt(len(mmns))), 3),
        "one_sample_t": round(float(t1), 2), "one_sample_p": float(p1),
        "cohens_dz": round(float(mmns.mean() / mmns.std(ddof=1)), 3),
        "second_level_cluster": {
            "n_clusters": int(len(clusters)), "n_significant": len(sig),
            "min_p": float(min(cl_p)) if len(cl_p) else 1.0,
            "significant": sig,
        },
        "PASS": bool(mmns.mean() < 0 and p1 < 0.05 and len(sig) >= 1),
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    guard_certified_output(args.out, "tools/validation/mmn_group_results.json", len(per), args.force)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    # Figure: grand-average MMN at ROI + per-subject MMN
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ga = X.mean(0)                                    # (ch, times)
        roi_idx = [info_ref["ch_names"].index(c) for c in ROI if c in info_ref["ch_names"]]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        ax[0].plot(times_ref * 1000, ga[roi_idx].mean(0) * 1e6, "k", lw=2)
        ax[0].axvspan(MMN_WIN[0] * 1000, MMN_WIN[1] * 1000, color="orange", alpha=0.2)
        ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", ls="--", lw=0.6)
        ax[0].set(xlabel="ms", ylabel="µV", xlim=(-200, 500),
                  title=f"A) Grand-avg MMN (dev-std) @ {'/'.join(ROI)}\nN={len(per)}, p={p1:.1e}")
        ax[1].bar(range(len(mmns)), mmns, color=["C3" if m < 0 else "C0" for m in mmns])
        ax[1].axhline(mmns.mean(), color="k", ls="--", label=f"mean={mmns.mean():.2f}µV")
        ax[1].set(xlabel="subject", ylabel="MMN µV", title="B) Per-subject MMN amplitude")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        figp = "tools/validation/figures/mmn_group.png"
        Path(figp).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        results_fig = figp
        print(f"Figure: {figp}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print(f"\n==== MMN GROUP (N={len(per)}) ====")
    print(f"grand-mean MMN = {mmns.mean():+.3f} µV (SEM {results['mmn_sem_uV']}), "
          f"t={t1:.2f} p={p1:.2e} dz={results['cohens_dz']}")
    print(f"second-level cluster: {results['second_level_cluster']['n_significant']} sig, "
          f"min_p={results['second_level_cluster']['min_p']:.4f} -> PASS={results['PASS']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
