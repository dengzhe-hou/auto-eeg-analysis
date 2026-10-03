"""Extract the per-subject P3b metric from MNE-BIDS-Pipeline derivatives (ERP CORE P3).

Reads the gold pipeline's per-condition evokeds, forms target-standard with the same
mne.combine_evoked weights AEA uses, and measures the mean amplitude over Fz/Cz/Pz/CPz in
300-500 ms — the identical metric tools/validation/validate_p3_group.py reports.

  python tools/benchmark/extract_bidspipe_p3.py --deriv ~/mne_data/erpcore_p3_bench_deriv
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import mne

mne.set_log_level("ERROR")
ROI = ["Fz", "Cz", "Pz", "CPz"]
P3_WIN = (0.30, 0.50)


def _find_cond(evokeds, name):
    for ev in evokeds:
        if re.search(rf"\b{name}\b", (ev.comment or "").lower()):
            return ev
    return None


def subject_p3(ave_fif: Path):
    evokeds = mne.read_evokeds(ave_fif, verbose="ERROR")
    tgt = _find_cond(evokeds, "target")
    std = _find_cond(evokeds, "standard")
    if tgt is None or std is None:
        raise RuntimeError(f"missing condition evoked (have {[e.comment for e in evokeds]})")
    diff = mne.combine_evoked([tgt, std], weights=[1, -1])
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= P3_WIN[0]) & (diff.times <= P3_WIN[1])
    p3_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return p3_uV, tgt.nave, std.nave, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deriv", default=str(Path.home() / "mne_data" / "erpcore_p3_bench_deriv"))
    ap.add_argument("--out", default="tools/benchmark/bidspipe_p3_results.json")
    args = ap.parse_args()
    deriv = Path(args.deriv)

    per = []
    for ave in sorted(deriv.glob("sub-*/eeg/*ave.fif")):
        m = re.search(r"(sub-\d+)", ave.name)
        if not m:
            continue
        sub = m.group(1)
        try:
            p3_uV, ntgt, nstd, _ = subject_p3(ave)
            per.append({"subject": sub, "p3_uV": round(p3_uV, 3),
                        "n_dev": int(ntgt), "n_std": int(nstd)})
            print(f"  {sub}: P3={p3_uV:+.3f} uV (tgt_nave={ntgt}, std_nave={nstd})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    p3s = np.array([p["p3_uV"] for p in per]) if per else np.array([])
    out = {
        "tool": "mne-bids-pipeline", "dataset": "ERP CORE P3, target - standard, harmonized config",
        "roi": ROI, "p3_window_s": list(P3_WIN), "n_subjects": len(per),
        "grand_mean_p3_uV": round(float(p3s.mean()), 3) if len(p3s) else None,
        "per_subject": per,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    if len(p3s):
        print(f"\nN={len(per)}  grand-mean P3 = {p3s.mean():+.3f} uV   saved {args.out}")


if __name__ == "__main__":
    main()
