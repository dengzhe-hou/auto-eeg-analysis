#!/usr/bin/env python
"""Enumerate every committed MMN generation and compute what is actually computable.

Contract C9. Two evidence files tabulated the generation runs differently — CONSEQUENCE_EVAL.md
says 10 L0 + 10 L1 + 3 L2 = 23, SPEC_PRECISION_EVAL.md says 9 L0 + 12 L1 + 3 L2 (+Qwen) — and the
committed records settle it: the CONSEQUENCE tabulation cannot be reproduced from the committed
JSONs. This script derives the manifest from the JSONs alone, and states plainly which quantities
are computable from committed data (the direction of every grand mean) and which are not
(per-generation significance: per-subject values were never committed, so those verdicts exist
only as CONSEQUENCE_EVAL's reported output).

The paper may print: the enumeration, and the 24/24 negative-direction count. It may cite the
significance verdicts only as "as evaluated at run time (CONSEQUENCE_EVAL.md)", and must not
print "23/23" as if it were derivable.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
B = ROOT / "tools" / "benchmark"


def main() -> int:
    runs = []

    spec = json.loads((B / "RECIPE_GENERATION_SPECLEVEL.json").read_text(encoding="utf-8-sig"))
    for gid, r in sorted(spec["per_generation"].items()):
        runs.append({"id": gid, "source": "RECIPE_GENERATION_SPECLEVEL.json",
                     "condition": "L0" if gid.startswith("L0") else "L1",
                     "family": "Claude", "grand_mean_uV": r.get("grand_mean_gen"),
                     "n_common": r.get("n_common"), "n_analyzed": r.get("n_analyzed_gen")})

    res = json.loads((B / "RECIPE_GENERATION_RESULT.json").read_text(encoding="utf-8-sig"))
    for gid, r in sorted(res["per_generation"].items()):
        runs.append({"id": gid, "source": "RECIPE_GENERATION_RESULT.json",
                     "condition": "L1" if gid.startswith("A") else "L2",
                     "family": "Claude", "grand_mean_uV": r.get("grand_mean_gen"),
                     "n_common": r.get("n_common"), "n_analyzed": r.get("n_analyzed_gen")})

    cdx = json.loads((B / "RECIPE_GENERATION_RESULT_MMN_codex.json").read_text(encoding="utf-8-sig"))
    for gid, r in sorted(cdx["per_generation"].items()):
        runs.append({"id": f"codex_{gid}", "source": "RECIPE_GENERATION_RESULT_MMN_codex.json",
                     "condition": "L2", "family": "GPT/Codex",
                     "grand_mean_uV": r.get("grand_mean_gen"), "n_common": r.get("n_common"),
                     "n_analyzed": r.get("n_analyzed_gen")})

    qwn = json.loads((B / "OPEN_MODEL_RESULT.json").read_text(encoding="utf-8-sig"))
    for gid, r in sorted(qwn["per_generation"].items()):
        runs.append({"id": gid, "source": "OPEN_MODEL_RESULT.json", "condition": "L2",
                     "family": "open-weight (executed only after 3 author-classified "
                               "output-handling repairs)",
                     "grand_mean_uV": r.get("grand_mean_gen"), "n_common": r.get("n_common"), "n_analyzed": r.get("n_analyzed_gen")})

    for r in runs:                        # the committed summaries predate the cohort rule
        # Two different notions, kept apart (Round-2 review): did the generation COVER the reference
        # cohort (all 38 reference subjects present), and did it analyse EXACTLY that cohort (no
        # extra subjects -- 19 records analysed 39-40 because they did not apply the reference's
        # exclusions). The revised scorer's PASS requires the second.
        r["reference_coverage_complete"] = (r["n_common"] == 38)
        r["cohort_matches_reference"] = (r["n_common"] == 38 and r.get("n_analyzed") == 38)
    frontier = [r for r in runs if not r["source"].startswith("OPEN_MODEL")]
    by_cond = {c: sum(1 for r in frontier if r["condition"] == c) for c in ("L0", "L1", "L2")}
    neg = sum(1 for r in frontier if (r["grand_mean_uV"] or 0) < 0)

    out = {
        "component": "MMN",
        "enumerated_frontier_runs": len(frontier),
        "by_condition": by_cond,
        "plus_open_weight_repaired": len(runs) - len(frontier),
        "negative_direction": f"{neg}/{len(frontier)}",
        "partial_cohort_runs": [r["id"] for r in frontier if not r["reference_coverage_complete"]],
        "cohort_mismatch_runs": [r["id"] for r in frontier if not r["cohort_matches_reference"]],
        "cohort_note": "partial_cohort_runs = reference subjects missing; cohort_mismatch_runs = "
                       "analysed cohort != reference cohort (extra or missing subjects). The retained "
                       "summaries satisfy neither the revised scorer's PASS condition nor independent "
                       "recomputation; they are readable scores, not reconstructable evidence.",
        "computable_from_committed_data": [
            "the enumeration itself",
            "grand-mean direction per run (all negative)",
        ],
        "readable_from_retained_summaries_only": [
            "per-run agreement metrics (max|Δ|, within-tolerance count, Pearson r) -- scores written "
            "at run time from per-subject vectors that were not retained (exception: MMN B1 in "
            "RECIPE_GENERATION_RESULT.json embeds its 38 values and recomputes); they can be read, "
            "not independently recomputed",
        ],
        "NOT_computable_from_committed_data": [
            "per-generation group-significance tests: per-subject values per generation were not "
            "committed; the 'all significant' verdicts exist only as CONSEQUENCE_EVAL.md's "
            "reported output",
        ],
        "reconciliation": "CONSEQUENCE_EVAL.md's 10+10+3=23 tabulation is not reproducible from "
                          "the committed records, which enumerate 9 L0 + 12 L1 + 3 L2 = 24 "
                          "frontier generations (+1 repaired open-weight). The paper uses the "
                          "24-run enumeration and does not print 23/23.",
        "runs": runs,
    }
    p = Path(__file__).resolve().parent / "run_manifest.json"
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{len(frontier)} frontier runs ({by_cond}) + {len(runs)-len(frontier)} repaired; "
          f"direction {neg}/{len(frontier)} negative")
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
