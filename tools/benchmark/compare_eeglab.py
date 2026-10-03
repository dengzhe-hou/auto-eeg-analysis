#!/usr/bin/env python
"""Compare EEGLAB/Octave per-subject values against the certified AEA reference values.

The EEGLAB arm (``tools/benchmark/erpcore_eeglab.m``) is the *independent toolbox* leg of
the benchmark: different language, reader, FIR design, resampler and rejection routine.
The contrast is held identical, so a difference here is an implementation difference —
or, as the MMN case showed, a *specification* ambiguity that the two toolboxes resolve
differently.

Usage:
    python tools/benchmark/compare_eeglab.py --component N170 \
        --eeglab /tmp/eeglab_bench/eeglab_N170.json
    python tools/benchmark/compare_eeglab.py --all --out tools/benchmark/EEGLAB_RESULT_ALL.json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]

# component -> (certified JSON, per-subject value key)
COMPONENTS = {
    "MMN":  ("tools/validation/mmn_group_results.json",     "mmn_uV"),
    "P3":   ("tools/validation/p3_group_results.json",      "p3_uV"),
    "N170": ("tools/validation/n170_erpcore_results.json",  "n170_uV"),
    "ERN":  ("tools/validation/ern_erpcore_results.json",   "ern_uV"),
    "N400": ("tools/validation/n400_erpcore_results.json",  "n400_uV"),
}


def lin_ccc(x: np.ndarray, y: np.ndarray) -> float:
    """Lin's concordance correlation coefficient."""
    mx, my = x.mean(), y.mean()
    vx, vy = x.var(), y.var()
    cov = ((x - mx) * (y - my)).mean()
    return float(2 * cov / (vx + vy + (mx - my) ** 2))


def load_certified(component: str) -> dict[str, float]:
    rel, key = COMPONENTS[component]
    d = json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))
    return {r["subject"]: float(r[key]) for r in d["per_subject"]}


def compare(component: str, eeglab_path: Path) -> dict:
    eeg = json.loads(eeglab_path.read_text(encoding="utf-8-sig"))
    got = {k: float(v) for k, v in eeg["per_subject"].items()}
    ref = load_certified(component)
    shared = sorted(set(got) & set(ref))
    if not shared:
        raise SystemExit(f"{component}: no shared subjects between EEGLAB and reference")

    a = np.array([got[s] for s in shared])      # EEGLAB
    b = np.array([ref[s] for s in shared])      # certified (MNE)
    d = a - b

    t_e, p_e = stats.ttest_1samp(a, 0.0)
    t_r, p_r = stats.ttest_1samp(b, 0.0)

    # how often does the two toolboxes' retained-trial count differ? (0 when reject is off)
    n_trials = eeg.get("n_trials", {})
    ref_full = json.loads((ROOT / COMPONENTS[component][0]).read_text(encoding="utf-8-sig"))["per_subject"]
    ref_n = {r["subject"]: (int(r.get("n_dev", -1)), int(r.get("n_std", -1))) for r in ref_full}
    trial_mismatch = sum(
        1 for s in shared
        if s in n_trials and s in ref_n and tuple(n_trials[s]) != ref_n[s]
    )

    return {
        "component": component,
        "reject_mode": eeg.get("reject_mode"),
        "n_shared": len(shared),
        "n_eeglab": eeg.get("n_analyzed"),
        "n_certified": len(ref),
        "grand_mean_eeglab_uV": round(float(a.mean()), 4),
        "grand_mean_certified_uV": round(float(b.mean()), 4),
        "grand_mean_abs_diff_uV": round(float(abs(a.mean() - b.mean())), 4),
        "max_abs_diff_uV": round(float(np.abs(d).max()), 4),
        "mean_abs_diff_uV": round(float(np.abs(d).mean()), 4),
        # Components differ ~6x in amplitude (ERN -5.4 uV vs MMN -0.84 uV), so a fixed
        # +/-0.1 uV tolerance is far stricter for some than others. Report the per-subject
        # difference relative to the certified grand-mean magnitude as well.
        "max_abs_diff_pct_of_grand": round(float(np.abs(d).max() / abs(b.mean()) * 100), 2),
        "mean_abs_diff_pct_of_grand": round(float(np.abs(d).mean() / abs(b.mean()) * 100), 2),
        "grand_mean_diff_pct": round(float(abs(a.mean() - b.mean()) / abs(b.mean()) * 100), 3),
        "ccc": round(lin_ccc(a, b), 6),
        "pearson_r": round(float(stats.pearsonr(a, b)[0]), 4),
        "spearman_rho": round(float(stats.spearmanr(a, b)[0]), 4),
        "within_0p1uV": int((np.abs(d) <= 0.10).sum()),
        "subjects_with_differing_trial_counts": trial_mismatch,
        "conclusion_eeglab": {"t": round(float(t_e), 3), "p": float(p_e)},
        "conclusion_certified": {"t": round(float(t_r), 3), "p": float(p_r)},
        "same_conclusion": bool((np.sign(a.mean()) == np.sign(b.mean())) and (p_e < 0.05) == (p_r < 0.05)),
        "worst_subject": max(shared, key=lambda s: abs(got[s] - ref[s])),
    }


def fmt(r: dict) -> str:
    return (
        f"{r['component']:5s} rej={str(r['reject_mode']):4s} n={r['n_shared']:2d} | "
        f"grand {r['grand_mean_eeglab_uV']:+8.4f} vs {r['grand_mean_certified_uV']:+8.4f} "
        f"(Δ {r['grand_mean_abs_diff_uV']:.4f} = {r['grand_mean_diff_pct']:.2f}%) | "
        f"max|Δ| {r['max_abs_diff_uV']:.4f} ({r['max_abs_diff_pct_of_grand']:.0f}%) "
        f"mean|Δ| {r['mean_abs_diff_uV']:.4f} | CCC {r['ccc']:.4f} r {r['pearson_r']:.4f} "
        f"ρ {r['spearman_rho']:.4f} | ≤0.1µV {r['within_0p1uV']}/{r['n_shared']} | "
        f"trial-count mismatches {r['subjects_with_differing_trial_counts']} | "
        f"same conclusion {r['same_conclusion']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", choices=sorted(COMPONENTS))
    ap.add_argument("--eeglab", type=Path)
    ap.add_argument("--all", action="store_true",
                    help="compare every toolbox result JSON found in --glob-dir")
    ap.add_argument("--glob-dir", type=Path, default=Path("/tmp/eeglab_bench"))
    ap.add_argument("--pattern", default="*.json",
                    help="filename glob within --glob-dir (default: *.json)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    results = []
    if args.all:
        for f in sorted(args.glob_dir.glob(args.pattern)):
            try:
                comp = json.loads(f.read_text(encoding="utf-8-sig"))["component"]
            except Exception as e:                        # noqa: BLE001
                print(f"skip {f.name}: {e}", file=sys.stderr)
                continue
            if comp not in COMPONENTS:
                continue
            r = compare(comp, f)
            r["source"] = f.name
            results.append(r)
            print(fmt(r))
    else:
        if not (args.component and args.eeglab):
            ap.error("need --component and --eeglab, or --all")
        r = compare(args.component, args.eeglab)
        results.append(r)
        print(fmt(r))

    if args.out:
        args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
