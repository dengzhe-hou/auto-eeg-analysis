"""N>1 group ERP validation: the N170 face-selectivity effect on OpenNeuro ds000117
(Wakeman & Henson 2015 face-recognition study; EEG embedded in the Elekta MEG .fif).

The N170 is a face-selective occipito-temporal negativity ~130-200 ms: faces elicit a
LARGER (more negative) N170 than non-face control images. Here we contrast faces
(Famous + Unfamiliar) vs Scrambled faces and test the difference across subjects with a
second-level spatiotemporal cluster test — a genuine population-level ERP result, this
time on the canonical public face dataset (the source-mining top recipe candidate).

  python tools/validation/validate_n170_faces.py --subjects 16
"""
from __future__ import annotations
import argparse, json, warnings
from pathlib import Path
import numpy as np

warnings.filterwarnings("ignore")
DATA = Path.home() / "mne_data" / "ds000117"
N170_WIN = (0.13, 0.20)
FACE_CODES = {5, 6, 7, 13, 14, 15}      # Famous + Unfamiliar (initial/immediate/delayed)
SCRAMBLED_CODES = {17, 18, 19}


def posterior_lateral_roi(info, n_per_hemi=4):
    """Pick occipito-temporal channels geometrically: posterior (y<0) and lateral (|x| large)."""
    import mne
    picks = mne.pick_types(info, meg=False, eeg=True, exclude="bads")
    pos = np.array([info["chs"][p]["loc"][:3] for p in picks])    # (n, xyz) head coords
    names = [info["ch_names"][p] for p in picks]
    # posterior third by y; among those take the most lateral per hemisphere
    y, x = pos[:, 1], pos[:, 0]
    post = y < np.percentile(y, 40)
    roi = []
    for side in (x > 0, x < 0):                                   # right, left
        cand = [i for i in range(len(names)) if post[i] and side[i] and np.isfinite(pos[i]).all()]
        cand = sorted(cand, key=lambda i: -abs(x[i]))[:n_per_hemi]
        roi += cand
    return [names[i] for i in roi]


def subject_n170(sub):
    import mne
    f = DATA / sub / "ses-meg" / "meg" / f"{sub}_ses-meg_task-facerecognition_run-01_meg.fif"
    raw = mne.io.read_raw_fif(f, preload=True, verbose="ERROR")
    events = mne.find_events(raw, stim_channel="STI101", shortest_event=1, verbose="ERROR")  # before pick
    raw.pick_types(meg=False, eeg=True, eog=False, ecg=False, exclude="bads", verbose="ERROR")
    # drop channels without a valid scalp position (EOG/ECG carried as EEG0xx)
    bad_pos = [raw.ch_names[i] for i in range(len(raw.ch_names))
               if not np.isfinite(raw.info["chs"][i]["loc"][:3]).all()
               or np.allclose(raw.info["chs"][i]["loc"][:3], 0)]
    raw.drop_channels(bad_pos)
    raw.filter(0.1, 40.0, n_jobs=1, verbose="ERROR")
    # ds000117 carries HEOG/VEOG/ECG as EEG0xx channels; they have positions so the
    # position check above misses them. Drop by extreme variance (>>scalp) BEFORE the
    # average reference, else they corrupt the reference and the ±reject kills every trial.
    stds = raw.get_data().std(axis=1)
    med = np.median(stds)
    hi = [raw.ch_names[i] for i in range(len(stds)) if stds[i] > 4 * med]
    raw.drop_channels(hi)
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    if raw.info["sfreq"] > 300:
        raw, events = raw.resample(250.0, events=events, verbose="ERROR")  # keep events in sync
    ev = events.copy()
    ev = ev[np.isin(ev[:, 2], list(FACE_CODES | SCRAMBLED_CODES))]
    ev[np.isin(ev[:, 2], list(FACE_CODES)), 2] = 1
    ev[np.isin(ev[:, 2], list(SCRAMBLED_CODES)), 2] = 2
    epochs = mne.Epochs(raw, ev, event_id={"face": 1, "scrambled": 2}, tmin=-0.2, tmax=0.5,
                        baseline=(-0.2, 0.0), preload=True, reject=dict(eeg=150e-6), verbose="ERROR")
    if len(epochs["face"]) < 30 or len(epochs["scrambled"]) < 15:
        raise RuntimeError(f"too few epochs (face={len(epochs['face'])}, scr={len(epochs['scrambled'])})")
    evk_face, evk_scr = epochs["face"].average(), epochs["scrambled"].average()
    diff = mne.combine_evoked([evk_face, evk_scr], weights=[1, -1])     # face - scrambled
    roi = posterior_lateral_roi(diff.info)
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= N170_WIN[0]) & (diff.times <= N170_WIN[1])
    n170 = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return diff, n170, roi, len(epochs["face"]), len(epochs["scrambled"])


def main():
    import mne
    from scipy import stats as sstats
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=16)
    ap.add_argument("--out", default="tools/validation/n170_faces_results.json")
    args = ap.parse_args()

    subs = sorted([p.name for p in DATA.glob("sub-*") if p.is_dir()])[: args.subjects]
    per, evokeds = [], []
    for sub in subs:
        try:
            diff, n170, roi, nf, ns = subject_n170(sub)
            per.append({"subject": sub, "n170_uV": round(n170, 3), "n_face": nf, "n_scrambled": ns, "roi": roi})
            evokeds.append(diff)
            print(f"  {sub}: N170(face-scr)={n170:+.3f} uV (face={nf}, scr={ns})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    # Subjects can drop different numbers of bad/EOG channels — restrict to the channels
    # COMMON to all subjects (in a consistent order) before stacking for the group test.
    common = set(evokeds[0].ch_names)
    for e in evokeds[1:]:
        common &= set(e.ch_names)
    order = [c for c in evokeds[0].ch_names if c in common]
    X = np.array([e.copy().pick_channels(order, ordered=True).data for e in evokeds])  # (subj, ch, times)
    info_ref = evokeds[0].copy().pick_channels(order, ordered=True).info
    times_ref = evokeds[0].times
    roi_ref = posterior_lateral_roi(info_ref)                       # group ROI on common channels
    tmask = (times_ref >= N170_WIN[0]) & (times_ref <= N170_WIN[1])
    Xw = X[:, :, tmask].transpose(0, 2, 1)                           # (subj, times, ch)
    adj, _ = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    df = Xw.shape[0] - 1
    t_thr = -sstats.t.ppf(1 - 0.05, df)
    t_obs, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        Xw, n_permutations=5000, threshold=t_thr, tail=-1, seed=42,
        adjacency=adj, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    n170s = np.array([p["n170_uV"] for p in per])
    t1, p1 = sstats.ttest_1samp(n170s, 0)
    results = {
        "dataset": "OpenNeuro ds000117 (Wakeman & Henson 2015), EEG from MEG .fif, faces - scrambled",
        "n_subjects": len(per), "n170_window_s": list(N170_WIN), "roi_example": roi_ref,
        "grand_mean_n170_uV": round(float(n170s.mean()), 3),
        "n170_sem_uV": round(float(n170s.std(ddof=1) / np.sqrt(len(n170s))), 3),
        "one_sample_t": round(float(t1), 2), "one_sample_p": float(p1),
        "cohens_dz": round(float(n170s.mean() / n170s.std(ddof=1)), 3),
        "second_level_cluster": {"n_clusters": int(len(clusters)), "n_significant": len(sig),
                                 "min_p": float(min(cl_p)) if len(cl_p) else 1.0, "significant": sig},
        "PASS": bool(n170s.mean() < 0 and p1 < 0.05 and len(sig) >= 1),
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ga = X.mean(0)
        roi_idx = [info_ref["ch_names"].index(c) for c in roi_ref]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        ax[0].plot(times_ref * 1000, ga[roi_idx].mean(0) * 1e6, "k", lw=2)
        ax[0].axvspan(N170_WIN[0]*1000, N170_WIN[1]*1000, color="orange", alpha=0.2)
        ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(0, color="k", ls="--", lw=0.6)
        ax[0].set(xlabel="ms", ylabel="µV", xlim=(-200, 500),
                  title=f"A) Grand-avg N170 (face-scrambled) occipito-temporal\nN={len(per)}, p={p1:.1e}")
        ax[1].bar(range(len(n170s)), n170s, color=["C3" if v < 0 else "C0" for v in n170s])
        ax[1].axhline(n170s.mean(), color="k", ls="--", label=f"mean={n170s.mean():.2f}µV")
        ax[1].set(xlabel="subject", ylabel="N170 µV", title="B) Per-subject face−scrambled N170")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        plt.savefig("tools/validation/figures/n170_faces.png", dpi=140, bbox_inches="tight"); plt.close()
        print("Figure: tools/validation/figures/n170_faces.png")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print(f"\n==== N170 FACE-SELECTIVITY (N={len(per)}) ====")
    print(f"grand-mean N170(face-scr) = {n170s.mean():+.3f} µV (SEM {results['n170_sem_uV']}), "
          f"t={t1:.2f} p={p1:.2e} dz={results['cohens_dz']}")
    print(f"cluster: {results['second_level_cluster']['n_significant']} sig, "
          f"min_p={results['second_level_cluster']['min_p']:.4f} -> PASS={results['PASS']}")
    print(f"ROI (geometric posterior-lateral): {roi_ref}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
