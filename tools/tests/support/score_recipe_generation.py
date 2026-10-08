"""Numerical comparison support for library regression tests."""
import json
from pathlib import Path

import numpy as np

TOL = 0.10


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
