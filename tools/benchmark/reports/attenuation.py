#!/usr/bin/env python
"""Toolbox choice as measurement error: two ILLUSTRATIVE scenarios, not a bound and not a range.

Contract A3, tightened by the Round-1 reviewer. Paired differences identify the DISAGREEMENT
variance between two implementations; they do not identify either implementation's error
variance, any shared error, or the latent signal variance, and they say nothing about
error-signal correlation. So the two allocations below do not bracket the truth -- they are two
scenarios under a classical measurement-error model, reported alongside the quantities that ARE
observed (signed bias and dispersion of the differences):

  equal-split : sd_err = sd(diff)/sqrt(2)   (each arm half the variance)
  one-sided   : sd_err = sd(diff)           (all variance assigned to the candidate arm)

reliability = var_between / (var_between + var_err); extra N = 1/reliability - 1.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "tools" / "benchmark" / "cross_toolbox_results"
KEY = {"MMN": "mmn_uV", "P3": "p3_uV", "N170": "n170_uV", "ERN": "ern_uV", "N400": "n400_uV"}
REF = {"MMN": "mmn_group_results", "P3": "p3_group_results", "N170": "n170_erpcore_results",
       "ERN": "ern_erpcore_results", "N400": "n400_erpcore_results"}


def main() -> int:
    cert = {c: {r["subject"]: float(r[KEY[c]]) for r in json.loads(
        (ROOT / "tools" / "validation" / f"{f}.json").read_text(encoding="utf-8-sig"))["per_subject"]}
        for c, f in REF.items()}

    rows = []
    for f in sorted(D.glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8-sig"))
        c = j.get("component")
        # unpinned arms only, and skip the EEGLAB abs-criterion variant (specification mismatch,
        # not implementation noise)
        if not c or "cutmatch" in f.stem or "df0.1" in f.stem or j.get("reject_mode") == "abs":
            continue
        got = {k: float(v) for k, v in j["per_subject"].items()}
        s = sorted(set(got) & set(cert[c]))
        a = np.array([got[k] for k in s]); b = np.array([cert[c][k] for k in s])
        sd_b = float(b.std(ddof=1)); sd_d = float((a - b).std(ddof=1))
        row = {"component": c, "toolbox": "EEGLAB" if f.stem.startswith("eeglab") else "FieldTrip",
               "n": len(s), "sd_between_uV": round(sd_b, 4),
               "bias_uV": round(float((a - b).mean()), 4),          # observed: signed mean difference
               "sd_diff_uV": round(sd_d, 4)}                          # observed: dispersion of differences
        for name, sd_err in (("equal_split", sd_d / np.sqrt(2)), ("one_sided", sd_d)):
            rel = sd_b**2 / (sd_b**2 + sd_err**2)
            row[name] = {"sd_err_uV": round(float(sd_err), 4),
                         "reliability": round(float(rel), 6),
                         "extra_n_pct": round(float((1 / rel - 1) * 100), 3)}
        rows.append(row)

    worst = {k: max(r[k]["extra_n_pct"] for r in rows) for k in ("equal_split", "one_sided")}
    out = {
        "estimand": "sample-size inflation needed to recover power lost to toolbox-choice "
                    "measurement error, per component x toolbox (unpinned arms)",
        "assumption_note": "ILLUSTRATIVE SCENARIOS under a classical measurement-error model: "
                           "equal_split assumes equal independent error in both arms (sd/sqrt2); "
                           "one_sided assigns all paired-difference variance to the candidate arm. "
                           "Neither is established, and the two do NOT bracket the truth: paired "
                           "differences identify disagreement variance only (not each arm's error "
                           "variance, shared error, or error-signal correlation), and systematic "
                           "bias is reported separately. Do not call this a bound or a range.",
        "rows": rows,
        "worst_extra_n_pct": worst,
        "headline": f"illustrative extra-N scenarios: {worst['equal_split']:.2f}% (equal split) and "
                    f"{worst['one_sided']:.2f}% (one-sided), worst component x toolbox; "
                    f"observed bias range {min(r['bias_uV'] for r in rows):+.3f}..{max(r['bias_uV'] for r in rows):+.3f} µV",
    }
    outp = Path(__file__).resolve().parent / "attenuation.json"
    outp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"worst extra-N: equal-split {worst['equal_split']:.3f}%  one-sided {worst['one_sided']:.3f}%")
    print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
