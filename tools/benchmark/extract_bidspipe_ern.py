"""Extract the per-subject ERN metric from MNE-BIDS-Pipeline derivatives (ERP CORE ERN).

Forms error-correct with the same weights AEA uses and measures the mean amplitude over
FCz/Fz/Cz in 0-100 ms post-response — the identical metric validate_ern_erpcore_group.py reports.

  python tools/benchmark/extract_bidspipe_ern.py --deriv ~/mne_data/erpcore_ern_bench_deriv
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import mne

mne.set_log_level("ERROR")
ROI = ["FCz", "Fz", "Cz"]
ERN_WIN = (0.0, 0.1)


def _find_cond(evokeds, name):
    for ev in evokeds:
        if re.search(rf"\b{name}\b", (ev.comment or "").lower()):
            return ev
    return None


def subject_ern(ave_fif):
    evokeds = mne.read_evokeds(ave_fif, verbose="ERROR")
    err = _find_cond(evokeds, "error")
    cor = _find_cond(evokeds, "correct")
    if err is None or cor is None:
        raise RuntimeError(f"missing condition evoked (have {[e.comment for e in evokeds]})")
    diff = mne.combine_evoked([err, cor], weights=[1, -1])
    roi = [c for c in ROI if c in diff.ch_names]
    roi_idx = [diff.ch_names.index(c) for c in roi]
    tmask = (diff.times >= ERN_WIN[0]) & (diff.times <= ERN_WIN[1])
    ern_uV = float(diff.data[roi_idx][:, tmask].mean() * 1e6)
    return ern_uV, err.nave, cor.nave, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deriv", default=str(Path.home() / "mne_data" / "erpcore_ern_bench_deriv"))
    ap.add_argument("--out", default="tools/benchmark/bidspipe_ern_results.json")
    args = ap.parse_args()
    deriv = Path(args.deriv)

    per = []
    for ave in sorted(deriv.glob("sub-*/eeg/*ave.fif")):
        m = re.search(r"(sub-\d+)", ave.name)
        if not m:
            continue
        sub = m.group(1)
        try:
            ern_uV, nerr, ncor, _ = subject_ern(ave)
            per.append({"subject": sub, "ern_uV": round(ern_uV, 3),
                        "n_dev": int(nerr), "n_std": int(ncor)})
            print(f"  {sub}: ERN={ern_uV:+.3f} uV (err_nave={nerr}, cor_nave={ncor})", flush=True)
        except Exception as e:
            print(f"  {sub}: SKIP {type(e).__name__}: {str(e)[:70]}", flush=True)

    es = np.array([p["ern_uV"] for p in per]) if per else np.array([])
    out = {
        "tool": "mne-bids-pipeline", "dataset": "ERP CORE ERN, error - correct (response-locked), harmonized",
        "roi": ROI, "ern_window_s": list(ERN_WIN), "n_subjects": len(per),
        "grand_mean_ern_uV": round(float(es.mean()), 3) if len(es) else None,
        "per_subject": per,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    if len(es):
        print(f"\nN={len(per)}  grand-mean ERN = {es.mean():+.3f} uV   saved {args.out}")


if __name__ == "__main__":
    main()
