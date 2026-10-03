"""Score LLM-generated pipelines against the certified benchmark (BENCHMARK.md §6f).

Every benchmark so far compared a HAND-WRITTEN reference implementation of a recipe spec
(`tools/validation/validate_*_group.py`) against MNE-BIDS-Pipeline. That certifies the *spec's
reference implementation*, not the thing AEA actually sells: **an LLM reading `RECIPE.md` and
generating the pipeline**. This scores that generation step.

Protocol: blind agents get the recipe spec + a dataset brief (and are forbidden from reading
`tools/`), write a pipeline from scratch, run it on the real data, and emit per-subject µV. This
script compares each generation to the committed, gold-verified per-subject values.

Two conditions:
  A = recipe spec only (agent chooses optional steps)  -> tests SPEC SUFFICIENCY
  B = pinned harmonized-minimal config                 -> tests CODE-GENERATION CORRECTNESS

  python tools/benchmark/score_recipe_generation.py --gen-dir <dir> --labels A1 A2 B1 B2
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TOL = 0.10   # µV — same gate as tools/tests/test_benchmark.py

# component -> (gold-verified reference json, per-subject key, grand-mean key)
COMPONENTS = {
    "MMN":  ("tools/validation/mmn_group_results.json",    "mmn_uV",  "grand_mean_mmn_uV"),
    "P3":   ("tools/validation/p3_group_results.json",     "p3_uV",   "grand_mean_p3_uV"),
    "N170": ("tools/validation/n170_erpcore_results.json", "n170_uV", "grand_mean_n170_uV"),
}


def load_reference(component):
    rel, key, gm_key = COMPONENTS[component]
    d = json.load(open(ROOT / rel, encoding="utf-8-sig"))
    return {p["subject"]: p[key] for p in d["per_subject"]}, d[gm_key], key, rel


def score(gen_path: Path, ref: dict):
    g = json.load(open(gen_path, encoding="utf-8-sig"))
    per = g.get("per_subject", {})
    common = sorted(set(per) & set(ref))
    if not common:
        return {"error": "no common subjects"}
    a = np.array([float(per[s]) for s in common])
    b = np.array([ref[s] for s in common])
    d = a - b
    return {
        "n_common": len(common),
        "n_analyzed_gen": g.get("n_analyzed"),
        "excluded_gen": g.get("excluded", []),
        "grand_mean_gen": g.get("grand_mean_uV"),
        "max_abs_delta_uV": round(float(np.abs(d).max()), 4),
        "mean_abs_delta_uV": round(float(np.abs(d).mean()), 4),
        "median_abs_delta_uV": round(float(np.median(np.abs(d))), 4),
        "pearson_r": round(float(np.corrcoef(a, b)[0, 1]), 5) if len(common) > 2 else None,
        "n_within_tol": int((np.abs(d) <= TOL).sum()),
        "frac_within_tol": round(float((np.abs(d) <= TOL).mean()), 3),
        # PASS means the generated program reproduced the certified ANALYSIS: the intended cohort
        # and the numbers. Agreement on an intersected subset is reported separately -- the
        # Round-1 reviewer found L0_6 awarded PASS on 34 of 38 subjects under the old rule.
        "cohort_complete": bool(len(common) == len(ref) and len(per) == len(ref)),
        "missing_subjects": sorted(set(ref) - set(per)),
        "numerical_agreement_on_common": bool(np.abs(d).max() <= TOL),
        "grand_mean_gen_on_common_uV": float(np.mean([per[k] for k in common])),
        "grand_mean_ref_on_common_uV": float(np.mean([ref[k] for k in common])),
        "PASS": bool(np.abs(d).max() <= TOL and len(common) == len(ref) and len(per) == len(ref)),
        "choices": g.get("choices", {}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-dir", required=True)
    ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--component", default="MMN", choices=list(COMPONENTS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    ref, ref_mean, key, ref_rel = load_reference(args.component)
    if args.out is None:
        args.out = f"tools/benchmark/RECIPE_GENERATION_RESULT_{args.component}.json"
    gen_dir = Path(args.gen_dir)

    results, gens = {}, {}
    for lab in args.labels:
        p = gen_dir / lab / "result.json"
        if not p.exists():
            results[lab] = {"error": "no result.json (generation failed)"}
            print(f"  {lab}: FAILED to produce result.json")
            continue
        r = score(p, ref)
        results[lab] = r
        gens[lab] = {s: float(v) for s, v in json.load(open(p, encoding="utf-8-sig"))["per_subject"].items()}
        print(f"  {lab}: n={r.get('n_common')} max|Δ|={r.get('max_abs_delta_uV')} µV "
              f"mean|Δ|={r.get('mean_abs_delta_uV')} within±{TOL}: {r.get('n_within_tol')}/{r.get('n_common')} "
              f"PASS={r.get('PASS')}", flush=True)

    # generation-to-generation reproducibility (same condition, independent runs)
    repro = {}
    groups = sorted({l.split("_")[0] if "_" in l else l[0] for l in gens})
    for c in groups:
        labs = sorted(l for l in gens if (l.split("_")[0] if "_" in l else l[0]) == c)
        if len(labs) >= 2:
            s = sorted(set(gens[labs[0]]) & set(gens[labs[1]]))
            if s:
                dd = np.array([gens[labs[0]][x] for x in s]) - np.array([gens[labs[1]][x] for x in s])
                repro[c] = {"pair": labs[:2], "n": len(s),
                            "max_abs_delta_uV": round(float(np.abs(dd).max()), 4),
                            "mean_abs_delta_uV": round(float(np.abs(dd).mean()), 4),
                            "identical": bool(np.abs(dd).max() < 1e-9)}

    out = {
        "evaluation": "BENCHMARK.md §6f — LLM recipe-generation vs the certified benchmark",
        "component": args.component,
        "reference": ref_rel, "reference_grand_mean_uV": ref_mean,
        "tolerance_uV": TOL,
        "conditions": {"A": "recipe spec only (spec sufficiency)",
                       "B": "pinned harmonized-minimal config (code-generation correctness)"},
        "per_generation": results,
        "generation_reproducibility": repro,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"\nreference grand-mean = {ref_mean} µV")
    for c, v in repro.items():
        print(f"  condition {c} run-to-run: max|Δ|={v['max_abs_delta_uV']} µV identical={v['identical']}")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
