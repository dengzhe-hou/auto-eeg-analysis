"""N>1 group ERP validation: Error-Related Negativity (ERN) on ERP CORE (Kappenman 2021).

Arrow-flankers task. The ERN is a RESPONSE-locked frontocentral negativity peaking ~0-100 ms
after an ERROR response (Gehring 1993). This is the canonical error-minus-correct ERN — the
ERP CORE ERN primary contrast. (The `ern-flankers` recipe's C2 frames ERN as
incompatible-vs-compatible responses, a different, weaker conflict effect that needs per-response
stimulus derivation; here we benchmark the standard error-vs-correct ERN, which also exercises a
RESPONSE-locked pipeline — the first non-stimulus-locked component in the benchmark.)

Response `value` is 3 digits: d1=response side (1=L,2=R), d2=flanker compat, d3=target side.
CORRECT iff d1==d3 (responded to the correct side); ERROR iff d1!=d3.

  python tools/validation/validate_ern_erpcore_group.py --subjects 20
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _certified_output import guard_certified_output  # noqa: E402

warnings.filterwarnings("ignore")

ROI = ["FCz", "Fz", "Cz"]
ERN_WIN = (0.0, 0.1)                 # 0-100 ms post-response
ERROR, CORRECT = 1, 2
MIN_ERR, MIN_COR = 15, 15
DATA = Path.home() / "mne_data" / "erpcore-ERN"


def _ern_events(ev_tsv, sfreq):
    import pandas as pd
    ev = pd.read_csv(ev_tsv, sep="\t")
    v = ev["value"]
    resp = ev[(v >= 111) & (v <= 222) & (v.astype("Int64").astype(str).str.len() == 3)].copy()
    d1 = resp["value"] // 100
    d3 = resp["value"] % 10
    codes = np.where(d1.to_numpy() == d3.to_numpy(), CORRECT, ERROR).astype(int)
    samples = np.round(resp["onset"].to_numpy() * sfreq).astype(int)
    return np.c_[samples, np.zeros_like(samples), codes]


def load_subject(sub, sfreq=256.0):
    import mne
    eeg = DATA / sub / "eeg"
    raw = mne.io.read_raw_eeglab(eeg / f"{sub}_task-ERN_eeg.set", preload=True, verbose="ERROR")
    raw.drop_channels([c for c in ["HEOG_left", "HEOG_right", "VEOG_lower"] if c in raw.ch_names])
    raw.pick_types(eeg=True, verbose="ERROR")
    raw.set_montage("standard_1020", match_case=False, on_missing="warn", verbose="ERROR")
    raw.filter(0.1, 30.0, n_jobs=1, verbose="ERROR")
    if sfreq and abs(raw.info["sfreq"] - sfreq) > 1:
        raw.resample(sfreq, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    events = _ern_events(eeg / f"{sub}_task-ERN_events.tsv", raw.info["sfreq"])
    events = events[(events[:, 0] > 0) & (events[:, 0] < raw.n_times)]
    return raw, events


def subject_ern(sub):
    import mne
    raw, events = load_subject(sub)
    # response-locked; pre-response baseline (-0.4, -0.2); reject=None (identical trial set both tools)
    epochs = mne.Epochs(raw, events, event_id={"correct": CORRECT, "error": ERROR},
                        tmin=-0.4, tmax=0.6, baseline=(-0.4, -0.2), preload=True,
                        reject=None, verbose="ERROR")
    if len(epochs["error"]) < MIN_ERR or len(epochs["correct"]) < MIN_COR:
        raise RuntimeError(f"too few epochs (err={len(epochs['error'])}, cor={len(epochs['correct'])})")
    evk_err = epochs["error"].average()
    evk_cor = epochs["correct"].average()
    diff = mne.combine_evoked([evk_err, evk_cor], weights=[1, -1])   # error - correct (ERN)
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= ERN_WIN[0]) & (diff.times <= ERN_WIN[1])
    ern_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return diff, ern_uV, len(epochs["error"]), len(epochs["correct"])


def main():
    import mne
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--out", default="tools/validation/ern_erpcore_results.json")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting the certified baseline with a different N")
    args = ap.parse_args()

    subs = sorted([p.name for p in DATA.glob("sub-*")])[: args.subjects]
    per, diffs, info_ref, times_ref = [], [], None, None
    for sub in subs:
        try:
            diff, ern_uV, nerr, ncor = subject_ern(sub)
            per.append({"subject": sub, "ern_uV": round(ern_uV, 3), "n_dev": nerr, "n_std": ncor})
            diffs.append(diff.data)
            if info_ref is None:
                info_ref, times_ref = diff.info, diff.times
            print(f"  {sub}: ERN={ern_uV:+.3f} uV (err={nerr}, cor={ncor})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    from scipy import stats as sstats
    X = np.array(diffs)
    tmask = (times_ref >= ERN_WIN[0]) & (times_ref <= ERN_WIN[1])
    Xw = X[:, :, tmask].transpose(0, 2, 1)
    adj, _ = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    df = Xw.shape[0] - 1
    t_thr = -sstats.t.ppf(1 - 0.05, df)                       # one-sided (ERN negative)
    _, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        Xw, n_permutations=5000, threshold=t_thr, tail=-1, seed=42,
        adjacency=adj, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    es = np.array([p["ern_uV"] for p in per])
    t1, p1 = sstats.ttest_1samp(es, 0)

    results = {
        "dataset": "ERP CORE ERN (Kappenman 2021), error - correct, response-locked",
        "n_subjects": len(per), "roi": ROI, "ern_window_s": list(ERN_WIN),
        "grand_mean_ern_uV": round(float(es.mean()), 3),
        "ern_sem_uV": round(float(es.std(ddof=1) / np.sqrt(len(es))), 3),
        "one_sample_t": round(float(t1), 2), "one_sample_p": float(p1),
        "cohens_dz": round(float(es.mean() / es.std(ddof=1)), 3),
        "second_level_cluster": {
            "n_clusters": int(len(clusters)), "n_significant": len(sig),
            "min_p": float(min(cl_p)) if len(cl_p) else 1.0, "significant": sig,
        },
        "PASS": bool(es.mean() < 0 and p1 < 0.05 and len(sig) >= 1),
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    guard_certified_output(args.out, "tools/validation/ern_erpcore_results.json", len(per), args.force)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ga = X.mean(0)
        roi_idx = [info_ref["ch_names"].index(c) for c in ROI if c in info_ref["ch_names"]]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        ax[0].plot(times_ref * 1000, ga[roi_idx].mean(0) * 1e6, "k", lw=2)
        ax[0].axvspan(ERN_WIN[0] * 1000, ERN_WIN[1] * 1000, color="orange", alpha=0.2)
        ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", ls="--", lw=0.6)
        ax[0].set(xlabel="ms (rel. response)", ylabel="µV", xlim=(-400, 600),
                  title=f"A) Grand-avg ERN (error-correct) @ {'/'.join(ROI)}\nN={len(per)}, p={p1:.1e}")
        ax[1].bar(range(len(es)), es, color=["C3" if m < 0 else "C0" for m in es])
        ax[1].axhline(es.mean(), color="k", ls="--", label=f"mean={es.mean():.2f}µV")
        ax[1].set(xlabel="subject", ylabel="ERN µV", title="B) Per-subject ERN (error-correct)")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        figp = "tools/validation/figures/ern_erpcore_group.png"
        Path(figp).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        print(f"Figure: {figp}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print(f"\n==== ERN GROUP (N={len(per)}) ====")
    print(f"grand-mean ERN = {es.mean():+.3f} µV (SEM {results['ern_sem_uV']}), "
          f"t={t1:.2f} p={p1:.2e} dz={results['cohens_dz']}")
    print(f"second-level cluster: {results['second_level_cluster']['n_significant']} sig, "
          f"min_p={results['second_level_cluster']['min_p']:.4f} -> PASS={results['PASS']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
