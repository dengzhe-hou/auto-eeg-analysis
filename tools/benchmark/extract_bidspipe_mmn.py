"""Extract the per-subject MMN metric from MNE-BIDS-Pipeline derivatives.

Reads the gold-standard pipeline's per-condition evokeds, forms the deviant-standard
difference with the SAME mne.combine_evoked weights AEA uses, and measures the mean
amplitude over Fz/FCz/Cz in 100-250 ms — the identical metric AEA reports. The only
thing that differs between the two numbers is the pipeline that produced the evokeds.

  python tools/benchmark/extract_bidspipe_mmn.py --deriv ~/mne_data/erpcore_mmn_bench_deriv
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import mne

mne.set_log_level("ERROR")
ROI = ["Fz", "FCz", "Cz"]
MMN_WIN = (0.10, 0.25)


def _find_cond(evokeds, name):
    # match by Evoked.comment, tolerant to "deviant", "deviant (N=...)", case, etc.
    for ev in evokeds:
        c = (ev.comment or "").lower()
        if re.search(rf"\b{name}\b", c):
            return ev
    return None


def subject_mmn(ave_fif: Path):
    evokeds = mne.read_evokeds(ave_fif, verbose="ERROR")
    dev = _find_cond(evokeds, "deviant")
    std = _find_cond(evokeds, "standard")
    if dev is None or std is None:
        raise RuntimeError(f"missing condition evoked (have {[e.comment for e in evokeds]})")
    diff = mne.combine_evoked([dev, std], weights=[1, -1])   # deviant - standard, same as AEA
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= MMN_WIN[0]) & (diff.times <= MMN_WIN[1])
    mmn_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return mmn_uV, dev.nave, std.nave, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deriv", default=str(Path.home() / "mne_data" / "erpcore_mmn_bench_deriv"))
    ap.add_argument("--out", default="tools/benchmark/bidspipe_mmn_results.json")
    args = ap.parse_args()
    deriv = Path(args.deriv)

    per = []
    for ave in sorted(deriv.glob("sub-*/eeg/*ave.fif")):
        m = re.search(r"(sub-\d+)", ave.name)
        if not m:
            continue   # skip sub-average group file
        sub = m.group(1)
        try:
            mmn_uV, ndev, nstd, _ = subject_mmn(ave)
            per.append({"subject": sub, "mmn_uV": round(mmn_uV, 3),
                        "n_dev": int(ndev), "n_std": int(nstd)})
            print(f"  {sub}: MMN={mmn_uV:+.3f} uV (dev_nave={ndev}, std_nave={nstd})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    mmns = np.array([p["mmn_uV"] for p in per]) if per else np.array([])
    out = {
        "tool": "mne-bids-pipeline",
        "dataset": "ERP CORE MMN, deviant(70) - standard(80), harmonized config",
        "roi": ROI, "mmn_window_s": list(MMN_WIN), "n_subjects": len(per),
        "grand_mean_mmn_uV": round(float(mmns.mean()), 3) if len(mmns) else None,
        "per_subject": per,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    if len(mmns):
        print(f"\nN={len(per)}  grand-mean MMN = {mmns.mean():+.3f} uV   saved {args.out}")


if __name__ == "__main__":
    main()
