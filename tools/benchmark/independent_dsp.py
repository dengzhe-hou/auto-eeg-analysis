"""Kernel-independence check: MNE DSP vs an independent SciPy DSP — MMN (passive) + P3 (active).

The MNE-BIDS-Pipeline benchmark bounds *composition* error but not *kernel* error — both sit on MNE's
numerical primitives. This computes each subject's ERP TWO ways from the SAME raw file:

  (A) MNE DSP:   raw.filter / raw.resample / set_eeg_reference / Epochs.average
  (B) SciPy DSP: butter+sosfiltfilt (zero-phase) / resample_poly / mean-subtract / manual epoch+average

Only the numerical kernels differ (MNE's EEGLAB *reader* is shared I/O, not a kernel; every numerical
op in (B) is re-implemented in SciPy/NumPy). reject=None on both → identical trial sets, no
epoch-selection confound, so the residual is pure kernel/implementation sensitivity. This is a
non-MNE-kernel bound the MNE-vs-MNE-BIDS-Pipeline agreement (nanovolts, same kernels) could not give.

  python tools/benchmark/independent_dsp.py --component MMN     # or P3
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from scipy import signal, stats
import mne, pandas as pd

mne.set_log_level("ERROR")
EOG = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# component -> (data dir, task, ROI, window, epoch (tmin,tmax), band (l,h), condition-label fn)
CFG = {
    "MMN": dict(dir="MNE-erpcoremmn2021-data", task="MMN", roi=["Fz", "FCz", "Cz"],
                win=(0.10, 0.25), epoch=(-0.2, 0.5), band=(0.1, 30.0)),
    "P3":  dict(dir="erpcore-P3", task="P3", roi=["Fz", "Cz", "Pz", "CPz"],
                win=(0.30, 0.50), epoch=(-0.2, 0.8), band=(0.1, 30.0)),
}


def _events(component, ev):
    """Return (onsets_series, code_array) with code 1 = 'signal' cond, 2 = 'reference' cond;
    the difference wave is (cond1 - cond2)."""
    v = ev["value"]
    if component == "MMN":                       # deviant(70) - standard(80)
        e = ev[v.isin([70, 80])]
        return e["onset"], np.where(e["value"].to_numpy() == 70, 1, 2)
    if component == "P3":                          # target - standard (tens==units => target)
        e = ev[(v >= 11) & (v <= 55)]
        is_t = (e["value"] // 10) == (e["value"] % 10)
        return e["onset"], np.where(is_t.to_numpy(), 1, 2)
    raise ValueError(component)


def _read(component, sub):
    c = CFG[component]
    eeg = Path.home() / "mne_data" / c["dir"] / sub / "eeg"
    raw = mne.io.read_raw_eeglab(eeg / f"{sub}_task-{c['task']}_eeg.set", preload=True, verbose="ERROR")
    raw.drop_channels([x for x in EOG if x in raw.ch_names])
    raw.pick_types(eeg=True, verbose="ERROR")
    ev = pd.read_csv(eeg / f"{sub}_task-{c['task']}_events.tsv", sep="\t")
    return raw, ev


def _roi_mean(diff, ch_names, times, roi, win):
    idx = [ch_names.index(x) for x in roi if x in ch_names]
    tm = (times >= win[0]) & (times <= win[1])
    return float(diff[idx][:, tm].mean() * 1e6)


def erp_mne(component, sub):
    c = CFG[component]
    raw, ev = _read(component, sub)
    raw.set_montage("standard_1020", match_case=False, on_missing="ignore", verbose="ERROR")
    raw.filter(*c["band"], verbose="ERROR").resample(256.0, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    onsets, codes = _events(component, ev)
    samp = np.round(onsets.to_numpy() * raw.info["sfreq"]).astype(int)
    events = np.c_[samp, np.zeros_like(samp), codes]
    events = events[(events[:, 0] > 0) & (events[:, 0] < raw.n_times)]
    ep = mne.Epochs(raw, events, {"c1": 1, "c2": 2}, tmin=c["epoch"][0], tmax=c["epoch"][1],
                    baseline=(c["epoch"][0], 0.0), reject=None, preload=True, verbose="ERROR")
    diff = mne.combine_evoked([ep["c1"].average(), ep["c2"].average()], [1, -1])
    return _roi_mean(diff.data, diff.ch_names, diff.times, c["roi"], c["win"])


def erp_scipy(component, sub):
    c = CFG[component]
    raw, ev = _read(component, sub)
    x = raw.get_data()                                    # (ch, n) V — shared I/O
    ch, sf = list(raw.ch_names), raw.info["sfreq"]
    x = signal.sosfiltfilt(signal.butter(4, c["band"][0], "highpass", fs=sf, output="sos"), x, axis=1)
    x = signal.sosfiltfilt(signal.butter(4, c["band"][1], "lowpass", fs=sf, output="sos"), x, axis=1)
    x = signal.resample_poly(x, up=1, down=int(round(sf / 256.0)), axis=1)
    sf2 = sf / int(round(sf / 256.0))
    x = x - x.mean(axis=0, keepdims=True)
    pre = int(round(-c["epoch"][0] * sf2)); post = int(round(c["epoch"][1] * sf2))
    onsets, codes = _events(component, ev)
    ons = np.round(onsets.to_numpy() * sf2).astype(int)
    c1, c2 = [], []
    for o, k in zip(ons, codes):
        a, b = o - pre, o + post
        if a < 0 or b > x.shape[1]:
            continue
        seg = x[:, a:b].copy()
        seg = seg - seg[:, :pre].mean(axis=1, keepdims=True)
        (c1 if k == 1 else c2).append(seg)
    diff = np.array(c1).mean(0) - np.array(c2).mean(0)
    times = (np.arange(diff.shape[1]) - pre) / sf2
    return _roi_mean(diff, ch, times, c["roi"], c["win"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", default="MMN", choices=list(CFG))
    ap.add_argument("--subjects", type=int, default=12)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or f"tools/benchmark/{args.component}_KERNEL_INDEP_RESULT.json"
    ddir = Path.home() / "mne_data" / CFG[args.component]["dir"]
    subs = sorted(p.name for p in ddir.glob("sub-*"))[: args.subjects]
    per = []
    for s in subs:
        try:
            a, b = erp_mne(args.component, s), erp_scipy(args.component, s)
            per.append({"subject": s, "mne_uV": round(a, 3), "scipy_uV": round(b, 3), "delta_uV": round(a - b, 3)})
            print(f"  {s}: MNE={a:+.3f}  SciPy={b:+.3f}  Δ={a-b:+.3f} µV", flush=True)
        except Exception as e:
            print(f"  {s}: SKIP {type(e).__name__}: {str(e)[:60]}", flush=True)
    A = np.array([p["mne_uV"] for p in per]); B = np.array([p["scipy_uV"] for p in per]); d = A - B
    r = stats.pearsonr(A, B)[0]
    summ = {
        "check": "kernel independence — MNE DSP vs independent SciPy DSP (same data, same spec, reject=None)",
        "component": args.component, "roi": CFG[args.component]["roi"], "window_s": list(CFG[args.component]["win"]),
        "n_subjects": len(per),
        "mne_grand_mean_uV": round(float(A.mean()), 3), "scipy_grand_mean_uV": round(float(B.mean()), 3),
        "group_mean_delta_uV": round(float(A.mean() - B.mean()), 3),
        "per_subject_max_abs_uV": round(float(np.abs(d).max()), 3),
        "per_subject_mean_abs_uV": round(float(np.abs(d).mean()), 3),
        "pearson_r": round(float(r), 4), "per_subject": per,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(summ, open(out, "w", encoding="utf-8"), indent=2)
    print(f"\n{args.component} N={len(per)}: MNE={A.mean():+.3f} SciPy={B.mean():+.3f} "
          f"Δgroup={A.mean()-B.mean():+.3f} max|Δ|={np.abs(d).max():.3f} r={r:.4f} µV  saved {out}")


if __name__ == "__main__":
    main()
