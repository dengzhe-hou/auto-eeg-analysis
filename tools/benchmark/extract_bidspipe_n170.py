"""Extract the per-subject N170 metric from MNE-BIDS-Pipeline derivatives (ERP CORE N170).

Forms face-car with the same weights AEA uses and measures the mean amplitude over
PO7/PO8/P7/P8 in 130-200 ms — the identical metric validate_n170_erpcore_group.py reports.

  python tools/benchmark/extract_bidspipe_n170.py --deriv ~/mne_data/erpcore_n170_bench_deriv
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import mne

mne.set_log_level("ERROR")
ROI = ["PO7", "PO8", "P7", "P8"]
N170_WIN = (0.13, 0.20)


def _find_cond(evokeds, name):
    for ev in evokeds:
        if re.search(rf"\b{name}\b", (ev.comment or "").lower()):
            return ev
    return None


def subject_n170(ave_fif):
    evokeds = mne.read_evokeds(ave_fif, verbose="ERROR")
    face = _find_cond(evokeds, "face")
    car = _find_cond(evokeds, "car")
    if face is None or car is None:
        raise RuntimeError(f"missing condition evoked (have {[e.comment for e in evokeds]})")
    diff = mne.combine_evoked([face, car], weights=[1, -1])
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= N170_WIN[0]) & (diff.times <= N170_WIN[1])
    n170_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return n170_uV, face.nave, car.nave, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deriv", default=str(Path.home() / "mne_data" / "erpcore_n170_bench_deriv"))
    ap.add_argument("--out", default="tools/benchmark/bidspipe_n170_results.json")
    args = ap.parse_args()
    deriv = Path(args.deriv)

    per = []
    for ave in sorted(deriv.glob("sub-*/eeg/*ave.fif")):
        m = re.search(r"(sub-\d+)", ave.name)
        if not m:
            continue
        sub = m.group(1)
        try:
            n170_uV, nface, ncar, _ = subject_n170(ave)
            per.append({"subject": sub, "n170_uV": round(n170_uV, 3),
                        "n_dev": int(nface), "n_std": int(ncar)})
            print(f"  {sub}: N170={n170_uV:+.3f} uV (face_nave={nface}, car_nave={ncar})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    ns = np.array([p["n170_uV"] for p in per]) if per else np.array([])
    out = {
        "tool": "mne-bids-pipeline", "dataset": "ERP CORE N170, face - car, harmonized config",
        "roi": ROI, "n170_window_s": list(N170_WIN), "n_subjects": len(per),
        "grand_mean_n170_uV": round(float(ns.mean()), 3) if len(ns) else None,
        "per_subject": per,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    if len(ns):
        print(f"\nN={len(per)}  grand-mean N170 = {ns.mean():+.3f} uV   saved {args.out}")


if __name__ == "__main__":
    main()
