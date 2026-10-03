"""Extract the per-subject N400 metric from MNE-BIDS-Pipeline derivatives (ERP CORE N400).

Forms unrelated-related with the same weights AEA uses; mean over CPz/Cz/Pz in 300-500 ms.

  python tools/benchmark/extract_bidspipe_n400.py --deriv ~/mne_data/erpcore_n400_bench_deriv
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import mne

mne.set_log_level("ERROR")
ROI = ["CPz", "Cz", "Pz"]
N400_WIN = (0.30, 0.50)


def _find_cond(evokeds, name):
    for ev in evokeds:
        if re.search(rf"\b{name}\b", (ev.comment or "").lower()):
            return ev
    return None


def subject_n400(ave_fif):
    evokeds = mne.read_evokeds(ave_fif, verbose="ERROR")
    unrel = _find_cond(evokeds, "unrelated")
    rel = _find_cond(evokeds, "related")
    if unrel is None or rel is None:
        raise RuntimeError(f"missing condition evoked (have {[e.comment for e in evokeds]})")
    diff = mne.combine_evoked([unrel, rel], weights=[1, -1])
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= N400_WIN[0]) & (diff.times <= N400_WIN[1])
    n400_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return n400_uV, unrel.nave, rel.nave, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deriv", default=str(Path.home() / "mne_data" / "erpcore_n400_bench_deriv"))
    ap.add_argument("--out", default="tools/benchmark/bidspipe_n400_results.json")
    args = ap.parse_args()
    deriv = Path(args.deriv)

    per = []
    for ave in sorted(deriv.glob("sub-*/eeg/*ave.fif")):
        m = re.search(r"(sub-\d+)", ave.name)
        if not m:
            continue
        sub = m.group(1)
        try:
            n400_uV, nunrel, nrel, _ = subject_n400(ave)
            per.append({"subject": sub, "n400_uV": round(n400_uV, 3),
                        "n_dev": int(nunrel), "n_std": int(nrel)})
            print(f"  {sub}: N400={n400_uV:+.3f} uV (unrel_nave={nunrel}, rel_nave={nrel})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    ns = np.array([p["n400_uV"] for p in per]) if per else np.array([])
    out = {
        "tool": "mne-bids-pipeline", "dataset": "ERP CORE N400, unrelated - related, harmonized",
        "roi": ROI, "n400_window_s": list(N400_WIN), "n_subjects": len(per),
        "grand_mean_n400_uV": round(float(ns.mean()), 3) if len(ns) else None,
        "per_subject": per,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    if len(ns):
        print(f"\nN={len(per)}  grand-mean N400 = {ns.mean():+.3f} uV   saved {args.out}")


if __name__ == "__main__":
    main()
