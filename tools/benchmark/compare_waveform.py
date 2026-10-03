"""Per-sample waveform agreement: AEA recipe vs MNE-BIDS-Pipeline, any benchmarked component.

The scalar benchmark (compare_mmn.py) shows the ROI-window mean agrees; a single window-averaged
number can hide per-sample disagreement. This compares the FULL difference *waveform* (all 30 EEG
channels x every sample) between the two pipelines, per subject, and reports per-sample RMSE and
max-abs deviation. Reuses each component's own AEA-side and gold-side difference-wave builders.

  python tools/benchmark/compare_waveform.py --component MMN     # or P3 / N170 / ERN / N400

Component config: (AEA validate module, gold extract module, ROI, task, deriv dir, AEA json).
Both subject_* functions return the difference Evoked (AEA at [0], gold at [-1]).
"""
from __future__ import annotations
import argparse, importlib, json
from pathlib import Path
import numpy as np
import mne

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo/tools on path
mne.set_log_level("ERROR")

# component -> (aea module, aea fn, gold module, gold fn, ROI, task, deriv subdir, aea results json)
COMPONENTS = {
    "MMN":  ("validation.validate_mmn_group",  "subject_mmn",  "benchmark.extract_bidspipe_mmn",  "subject_mmn",
             ["Fz", "FCz", "Cz"], "MMN", "erpcore_mmn_bench_deriv", "tools/validation/mmn_group_results.json"),
    "P3":   ("validation.validate_p3_group",   "subject_p3",   "benchmark.extract_bidspipe_p3",   "subject_p3",
             ["Fz", "Cz", "Pz", "CPz"], "P3", "erpcore_p3_bench_deriv", "tools/validation/p3_group_results.json"),
    "N170": ("validation.validate_n170_erpcore_group", "subject_n170", "benchmark.extract_bidspipe_n170", "subject_n170",
             ["PO7", "PO8", "P7", "P8"], "N170", "erpcore_n170_bench_deriv", "tools/validation/n170_erpcore_results.json"),
    "ERN":  ("validation.validate_ern_erpcore_group", "subject_ern", "benchmark.extract_bidspipe_ern", "subject_ern",
             ["FCz", "Fz", "Cz"], "ERN", "erpcore_ern_bench_deriv", "tools/validation/ern_erpcore_results.json"),
    "N400": ("validation.validate_n400_erpcore_group", "subject_n400", "benchmark.extract_bidspipe_n400", "subject_n400",
             ["CPz", "Cz", "Pz"], "N400", "erpcore_n400_bench_deriv", "tools/validation/n400_erpcore_results.json"),
}


def aligned(aea_evk, gold_evk):
    common = [c for c in aea_evk.ch_names if c in gold_evk.ch_names]
    a_idx = [aea_evk.ch_names.index(c) for c in common]
    g_idx = [gold_evk.ch_names.index(c) for c in common]
    n = min(aea_evk.data.shape[1], gold_evk.data.shape[1])
    if not np.allclose(aea_evk.times[:n], gold_evk.times[:n], atol=1e-6):
        raise RuntimeError("time grids differ beyond tolerance")
    return aea_evk.data[a_idx][:, :n] * 1e6, gold_evk.data[g_idx][:, :n] * 1e6, common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", default="MMN", choices=list(COMPONENTS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    amod, afn, gmod, gfn, roi, task, deriv_sub, aea_json = COMPONENTS[args.component]
    out = args.out or f"tools/benchmark/{args.component}_WAVEFORM_RESULT.json"
    deriv = Path.home() / "mne_data" / deriv_sub

    aea_subject = getattr(importlib.import_module(amod), afn)
    gold_subject = getattr(importlib.import_module(gmod), gfn)
    subs = [p["subject"] for p in json.load(open(aea_json, encoding="utf-8-sig"))["per_subject"]]

    per = []
    for s in subs:
        ave = deriv / s / "eeg" / f"{s}_task-{task}_ave.fif"
        if not ave.exists():
            print(f"  {s}: SKIP (no gold ave.fif)"); continue
        aea_res = aea_subject(s)          # (diff, scalar, n1, n2)
        gold_res = gold_subject(ave)      # (scalar, n1, n2, diff)
        a, g, ch = aligned(aea_res[0], gold_res[-1])
        d = a - g                          # (ch, time) µV
        per.append({
            "subject": s,
            "rmse_allch_nV": round(float(np.sqrt((d ** 2).mean())) * 1000, 3),
            "maxabs_allch_nV": round(float(np.abs(d).max()) * 1000, 3),
            "scalar_delta_nV": round((aea_res[1] - gold_res[0]) * 1000, 3),
        })
        print(f"  {s}: waveform RMSE(all-ch)={per[-1]['rmse_allch_nV']:.2f} nV  "
              f"max-abs={per[-1]['maxabs_allch_nV']:.2f} nV", flush=True)

    rmse = np.array([p["rmse_allch_nV"] for p in per])
    maxabs = np.array([p["maxabs_allch_nV"] for p in per])
    summary = {
        "comparison": f"AEA vs MNE-BIDS-Pipeline 1.10.1 — full {args.component} difference waveform",
        "component": args.component, "roi": roi,
        "scope": "all 30 EEG channels x every sample",
        "n_subjects": len(per),
        "waveform_rmse_allch_nV": {"median": round(float(np.median(rmse)), 3),
                                   "mean": round(float(rmse.mean()), 3),
                                   "max": round(float(rmse.max()), 3),
                                   "worst_subject": per[int(rmse.argmax())]["subject"]},
        "waveform_maxabs_allch_nV": {"mean": round(float(maxabs.mean()), 3),
                                     "max": round(float(maxabs.max()), 3),
                                     "worst_subject": per[int(maxabs.argmax())]["subject"]},
        "per_subject": per,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(out, "w", encoding="utf-8"), indent=2)
    print(f"\n  {args.component} N={len(per)}: waveform RMSE median={np.median(rmse):.2f} "
          f"mean={rmse.mean():.2f} max={rmse.max():.2f} nV  saved {out}")


if __name__ == "__main__":
    main()
