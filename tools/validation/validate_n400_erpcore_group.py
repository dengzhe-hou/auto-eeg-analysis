"""N>1 group ERP validation: N400 semantic priming on ERP CORE (Kappenman 2021).

Word-pair semantic priming: a prime word then a target word that is semantically related or
unrelated. The N400 is a centro-parietal negativity ~300-500 ms that is LARGER (more negative)
for UNRELATED targets (Kutas & Federmeier 2011). Event `value` is 3 digits: d1=word type
(1=prime, 2=target), d2=relatedness (1=related, 2=unrelated), d3=list. This uses target words
only (d1=2): unrelated (221/222) - related (211/212).

  python tools/validation/validate_n400_erpcore_group.py --subjects 20
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _certified_output import guard_certified_output  # noqa: E402

warnings.filterwarnings("ignore")

ROI = ["CPz", "Cz", "Pz"]
N400_WIN = (0.30, 0.50)
UNRELATED, RELATED = 1, 2
MIN_PER_COND = 30
DATA = Path.home() / "mne_data" / "erpcore-N400"


def _n400_events(ev_tsv, sfreq):
    import pandas as pd
    ev = pd.read_csv(ev_tsv, sep="\t")
    v = ev["value"]
    rel = ev[v.isin([211, 212])].copy();   rel_s = np.round(rel["onset"].to_numpy() * sfreq).astype(int)
    unrel = ev[v.isin([221, 222])].copy(); unrel_s = np.round(unrel["onset"].to_numpy() * sfreq).astype(int)
    arr = np.r_[
        np.c_[rel_s, np.zeros_like(rel_s), np.full(len(rel_s), RELATED)],
        np.c_[unrel_s, np.zeros_like(unrel_s), np.full(len(unrel_s), UNRELATED)],
    ]
    return arr[np.argsort(arr[:, 0])]


def load_subject(sub, sfreq=256.0):
    import mne
    eeg = DATA / sub / "eeg"
    raw = mne.io.read_raw_eeglab(eeg / f"{sub}_task-N400_eeg.set", preload=True, verbose="ERROR")
    raw.drop_channels([c for c in ["HEOG_left", "HEOG_right", "VEOG_lower"] if c in raw.ch_names])
    raw.pick_types(eeg=True, verbose="ERROR")
    raw.set_montage("standard_1020", match_case=False, on_missing="warn", verbose="ERROR")
    raw.filter(0.1, 30.0, n_jobs=1, verbose="ERROR")
    if sfreq and abs(raw.info["sfreq"] - sfreq) > 1:
        raw.resample(sfreq, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    events = _n400_events(eeg / f"{sub}_task-N400_events.tsv", raw.info["sfreq"])
    events = events[(events[:, 0] > 0) & (events[:, 0] < raw.n_times)]
    return raw, events


def subject_n400(sub):
    import mne
    raw, events = load_subject(sub)
    epochs = mne.Epochs(raw, events, event_id={"related": RELATED, "unrelated": UNRELATED},
                        tmin=-0.2, tmax=0.8, baseline=(-0.2, 0.0), preload=True,
                        reject=None, verbose="ERROR")
    if len(epochs["unrelated"]) < MIN_PER_COND or len(epochs["related"]) < MIN_PER_COND:
        raise RuntimeError(f"too few epochs (unrel={len(epochs['unrelated'])}, rel={len(epochs['related'])})")
    evk_unrel = epochs["unrelated"].average()
    evk_rel = epochs["related"].average()
    diff = mne.combine_evoked([evk_unrel, evk_rel], weights=[1, -1])   # unrelated - related (N400)
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= N400_WIN[0]) & (diff.times <= N400_WIN[1])
    n400_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return diff, n400_uV, len(epochs["unrelated"]), len(epochs["related"])


def main():
    import mne
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--out", default="tools/validation/n400_erpcore_results.json")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting the certified baseline with a different N")
    args = ap.parse_args()

    subs = sorted([p.name for p in DATA.glob("sub-*")])[: args.subjects]
    per, diffs, info_ref, times_ref = [], [], None, None
    for sub in subs:
        try:
            diff, n400_uV, nunrel, nrel = subject_n400(sub)
            per.append({"subject": sub, "n400_uV": round(n400_uV, 3), "n_dev": nunrel, "n_std": nrel})
            diffs.append(diff.data)
            if info_ref is None:
                info_ref, times_ref = diff.info, diff.times
            print(f"  {sub}: N400={n400_uV:+.3f} uV (unrel={nunrel}, rel={nrel})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    from scipy import stats as sstats
    X = np.array(diffs)
    tmask = (times_ref >= N400_WIN[0]) & (times_ref <= N400_WIN[1])
    Xw = X[:, :, tmask].transpose(0, 2, 1)
    adj, _ = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    df = Xw.shape[0] - 1
    t_thr = -sstats.t.ppf(1 - 0.05, df)                       # one-sided (N400 negative)
    _, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        Xw, n_permutations=5000, threshold=t_thr, tail=-1, seed=42,
        adjacency=adj, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    ns = np.array([p["n400_uV"] for p in per])
    t1, p1 = sstats.ttest_1samp(ns, 0)

    results = {
        "dataset": "ERP CORE N400 (Kappenman 2021), unrelated - related (target words)",
        "n_subjects": len(per), "roi": ROI, "n400_window_s": list(N400_WIN),
        "grand_mean_n400_uV": round(float(ns.mean()), 3),
        "n400_sem_uV": round(float(ns.std(ddof=1) / np.sqrt(len(ns))), 3),
        "one_sample_t": round(float(t1), 2), "one_sample_p": float(p1),
        "cohens_dz": round(float(ns.mean() / ns.std(ddof=1)), 3),
        "second_level_cluster": {
            "n_clusters": int(len(clusters)), "n_significant": len(sig),
            "min_p": float(min(cl_p)) if len(cl_p) else 1.0, "significant": sig,
        },
        "PASS": bool(ns.mean() < 0 and p1 < 0.05 and len(sig) >= 1),
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    guard_certified_output(args.out, "tools/validation/n400_erpcore_results.json", len(per), args.force)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ga = X.mean(0)
        roi_idx = [info_ref["ch_names"].index(c) for c in ROI if c in info_ref["ch_names"]]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        ax[0].plot(times_ref * 1000, ga[roi_idx].mean(0) * 1e6, "k", lw=2)
        ax[0].axvspan(N400_WIN[0] * 1000, N400_WIN[1] * 1000, color="orange", alpha=0.2)
        ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", ls="--", lw=0.6)
        ax[0].set(xlabel="ms", ylabel="µV", xlim=(-200, 800),
                  title=f"A) Grand-avg N400 (unrel-rel) @ {'/'.join(ROI)}\nN={len(per)}, p={p1:.1e}")
        ax[1].bar(range(len(ns)), ns, color=["C3" if m < 0 else "C0" for m in ns])
        ax[1].axhline(ns.mean(), color="k", ls="--", label=f"mean={ns.mean():.2f}µV")
        ax[1].set(xlabel="subject", ylabel="N400 µV", title="B) Per-subject N400 (unrel-rel)")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        figp = "tools/validation/figures/n400_erpcore_group.png"
        Path(figp).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        print(f"Figure: {figp}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print(f"\n==== N400 GROUP (N={len(per)}) ====")
    print(f"grand-mean N400 = {ns.mean():+.3f} µV (SEM {results['n400_sem_uV']}), "
          f"t={t1:.2f} p={p1:.2e} dz={results['cohens_dz']}")
    print(f"second-level cluster: {results['second_level_cluster']['n_significant']} sig, "
          f"min_p={results['second_level_cluster']['min_p']:.4f} -> PASS={results['PASS']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
