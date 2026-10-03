"""N>1 group ERP validation: N170 face selectivity on ERP CORE (Kappenman 2021).

ERP CORE N170 shows faces, cars, and scrambled versions. The canonical face-selective
contrast is faces vs cars (a matched non-face object control): the N170 is a lateral
occipito-temporal negativity ~130-200 ms that is LARGER (more negative) for faces
(Bentin 1996). Event `value`: 1-40 = faces, 41-80 = cars, 101-180 = scrambled, 201/202 =
responses. This uses face (1-40) - car (41-80), matching recipes/n170-faces.

  python tools/validation/validate_n170_erpcore_group.py --subjects 20
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _certified_output import guard_certified_output  # noqa: E402

warnings.filterwarnings("ignore")

ROI = ["PO7", "PO8", "P7", "P8"]
N170_WIN = (0.13, 0.20)
FACE, NONFACE = 1, 2
MIN_PER_COND = 30
DATA = Path.home() / "mne_data" / "erpcore-N170"


def _n170_events(ev_tsv, sfreq):
    import pandas as pd
    ev = pd.read_csv(ev_tsv, sep="\t")
    v = ev["value"]
    face = ev[(v >= 1) & (v <= 40)].copy();  face_s = np.round(face["onset"].to_numpy() * sfreq).astype(int)
    car = ev[(v >= 41) & (v <= 80)].copy();  car_s = np.round(car["onset"].to_numpy() * sfreq).astype(int)
    ev_arr = np.r_[
        np.c_[face_s, np.zeros_like(face_s), np.full(len(face_s), FACE)],
        np.c_[car_s, np.zeros_like(car_s), np.full(len(car_s), NONFACE)],
    ]
    return ev_arr[np.argsort(ev_arr[:, 0])]


def load_subject(sub, sfreq=256.0):
    import mne
    eeg = DATA / sub / "eeg"
    raw = mne.io.read_raw_eeglab(eeg / f"{sub}_task-N170_eeg.set", preload=True, verbose="ERROR")
    raw.drop_channels([c for c in ["HEOG_left", "HEOG_right", "VEOG_lower"] if c in raw.ch_names])
    raw.pick_types(eeg=True, verbose="ERROR")
    raw.set_montage("standard_1020", match_case=False, on_missing="warn", verbose="ERROR")
    raw.filter(0.1, 40.0, n_jobs=1, verbose="ERROR")
    if sfreq and abs(raw.info["sfreq"] - sfreq) > 1:
        raw.resample(sfreq, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    events = _n170_events(eeg / f"{sub}_task-N170_events.tsv", raw.info["sfreq"])
    events = events[(events[:, 0] > 0) & (events[:, 0] < raw.n_times)]
    return raw, events


def subject_n170(sub):
    import mne
    raw, events = load_subject(sub)
    # reject=None: keep every trial so both pipelines average the identical set (see docs/BENCHMARK.md)
    epochs = mne.Epochs(raw, events, event_id={"face": FACE, "car": NONFACE},
                        tmin=-0.2, tmax=0.5, baseline=(-0.2, 0.0), preload=True,
                        reject=None, verbose="ERROR")
    if len(epochs["face"]) < MIN_PER_COND or len(epochs["car"]) < MIN_PER_COND:
        raise RuntimeError(f"too few epochs (face={len(epochs['face'])}, car={len(epochs['car'])})")
    evk_face = epochs["face"].average()
    evk_car = epochs["car"].average()
    diff = mne.combine_evoked([evk_face, evk_car], weights=[1, -1])   # face - car (more negative)
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= N170_WIN[0]) & (diff.times <= N170_WIN[1])
    n170_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return diff, n170_uV, len(epochs["face"]), len(epochs["car"])


def main():
    import mne
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--out", default="tools/validation/n170_erpcore_results.json")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting the certified baseline with a different N")
    args = ap.parse_args()

    subs = sorted([p.name for p in DATA.glob("sub-*")])[: args.subjects]
    per, diffs, info_ref, times_ref = [], [], None, None
    for sub in subs:
        try:
            diff, n170_uV, nface, ncar = subject_n170(sub)
            per.append({"subject": sub, "n170_uV": round(n170_uV, 3), "n_dev": nface, "n_std": ncar})
            diffs.append(diff.data)
            if info_ref is None:
                info_ref, times_ref = diff.info, diff.times
            print(f"  {sub}: N170={n170_uV:+.3f} uV (face={nface}, car={ncar})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    from scipy import stats as sstats
    X = np.array(diffs)
    tmask = (times_ref >= N170_WIN[0]) & (times_ref <= N170_WIN[1])
    Xw = X[:, :, tmask].transpose(0, 2, 1)
    adj, _ = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    df = Xw.shape[0] - 1
    t_thr = -sstats.t.ppf(1 - 0.05, df)                       # one-sided (N170 negative)
    _, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        Xw, n_permutations=5000, threshold=t_thr, tail=-1, seed=42,
        adjacency=adj, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    ns = np.array([p["n170_uV"] for p in per])
    t1, p1 = sstats.ttest_1samp(ns, 0)

    results = {
        "dataset": "ERP CORE N170 (Kappenman 2021), face - car (occipito-temporal)",
        "n_subjects": len(per), "roi": ROI, "n170_window_s": list(N170_WIN),
        "grand_mean_n170_uV": round(float(ns.mean()), 3),
        "n170_sem_uV": round(float(ns.std(ddof=1) / np.sqrt(len(ns))), 3),
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
    guard_certified_output(args.out, "tools/validation/n170_erpcore_results.json", len(per), args.force)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ga = X.mean(0)
        roi_idx = [info_ref["ch_names"].index(c) for c in ROI if c in info_ref["ch_names"]]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        ax[0].plot(times_ref * 1000, ga[roi_idx].mean(0) * 1e6, "k", lw=2)
        ax[0].axvspan(N170_WIN[0] * 1000, N170_WIN[1] * 1000, color="orange", alpha=0.2)
        ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", ls="--", lw=0.6)
        ax[0].set(xlabel="ms", ylabel="µV", xlim=(-200, 500),
                  title=f"A) Grand-avg N170 (face-car) @ {'/'.join(ROI)}\nN={len(per)}, p={p1:.1e}")
        ax[1].bar(range(len(ns)), ns, color=["C3" if m < 0 else "C0" for m in ns])
        ax[1].axhline(ns.mean(), color="k", ls="--", label=f"mean={ns.mean():.2f}µV")
        ax[1].set(xlabel="subject", ylabel="N170 µV", title="B) Per-subject N170 (face-car)")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        figp = "tools/validation/figures/n170_erpcore_group.png"
        Path(figp).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        print(f"Figure: {figp}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print(f"\n==== N170 GROUP (N={len(per)}) ====")
    print(f"grand-mean N170 = {ns.mean():+.3f} µV (SEM {results['n170_sem_uV']}), "
          f"t={t1:.2f} p={p1:.2e} dz={results['cohens_dz']}")
    print(f"second-level cluster: {results['second_level_cluster']['n_significant']} sig, "
          f"min_p={results['second_level_cluster']['min_p']:.4f} -> PASS={results['PASS']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
