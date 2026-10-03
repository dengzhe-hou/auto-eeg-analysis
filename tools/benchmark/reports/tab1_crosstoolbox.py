#!/usr/bin/env python
"""Table 1 — five components x two independent toolboxes, unpinned arms, vs certified values."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENTS = ["MMN", "P3", "N170", "ERN", "N400"]


def _arm_test(r, tb, c):
    """Two-sided one-sample t-test of the toolbox arm's amplitudes against zero on the SHARED subjects.

    Round-2 review caught the first version testing every subject the arm retained (EEGLAB kept 39
    MMN participants where the certified set has 38), so its p-values matched n = 39, not the
    shared cohort the rest of the row describes.
    """
    import numpy as np
    from scipy import stats
    src = f"{'eeglab' if tb == 'EEGLAB' else 'fieldtrip'}_{c}{'_p2p' if (tb, c) == ('EEGLAB', 'MMN') else ''}.json"
    d = json.loads((ROOT / "tools" / "benchmark" / "cross_toolbox_results" / src).read_text(encoding="utf-8-sig"))
    ref_file = {"MMN": "mmn_group_results", "P3": "p3_group_results", "N170": "n170_erpcore_results",
                "ERN": "ern_erpcore_results", "N400": "n400_erpcore_results"}[c]
    ref = {x["subject"] for x in json.loads((ROOT / "tools" / "validation" / f"{ref_file}.json").read_text(encoding="utf-8-sig"))["per_subject"]}
    v = np.array([float(val) for sub, val in d["per_subject"].items() if sub in ref])
    t, pval = stats.ttest_1samp(v, 0.0)            # two-sided, as in the validation scripts
    return float(t), float(pval), len(v)


def rows():
    data = json.loads((ROOT / "tools" / "benchmark" / "CROSS_TOOLBOX_RESULT.json")
                      .read_text(encoding="utf-8-sig"))
    by_src = {r["source"]: r for r in data}
    out = []
    for tb, pref in (("EEGLAB", "eeglab"), ("FieldTrip", "fieldtrip")):
        for c in COMPONENTS:
            src = f"{pref}_{c}_p2p.json" if (pref, c) == ("eeglab", "MMN") else f"{pref}_{c}.json"
            r = by_src[src]
            out.append((tb, c, r))
    return out


def main() -> int:
    lines = [
        r"\begin{table}[t]", r"\centering", r"\small",
        r"\caption{Per-subject agreement of two independently implemented toolboxes with the "
        r"certified values at each toolbox's own defaults (before pinning; MMN uses the peak-to-peak "
        r"criterion matched to the reference). $|$grand $\Delta|$ is the absolute difference between "
        r"the toolbox and certified grand means over the $n$ shared subjects, as a percentage of the "
        r"certified grand mean; $t$ and $p$ are the toolbox arm's two-sided one-sample test of the "
        r"$n$ shared subjects' amplitudes against zero ($n-1$ degrees of freedom); same conclusion "
        r"means that the effect direction and the $p<0.05$ decision equal the reference's.}",
        r"\label{tab:crosstoolbox}",
        r"\resizebox{\linewidth}{!}{\begin{tabular}{llrrrrrrrc}", r"\toprule",
        r"toolbox & component & $n$ & $|$grand $\Delta|$ (\%) & max $|\Delta|$ (µV) & CCC & "
        r"$\leq$0.1\,µV & $t$ & $p$ (two-sided) & same conclusion \\",
        r"\midrule",
    ]
    for tb, c, r in rows():
        t, pval, n = _arm_test(r, tb, c)
        assert n == r["n_shared"], (tb, c, n, r["n_shared"])
        m, e = f"{pval:.1e}".split("e"); pstr = f"${m}\\times10^{{{int(e)}}}$"   # uniform scientific notation
        lines.append(
            f"{tb} & {'P3b' if c == 'P3' else c} & {n} & {r['grand_mean_diff_pct']:.3f} & {r['max_abs_diff_uV']:.3f} & "
            f"{r['ccc']:.4f} & {r['within_0p1uV']}/{r['n_shared']} & {t:.2f} & {pstr} & "
            f"{'yes' if r['same_conclusion'] else 'no'} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    out = Path(__file__).resolve().parent / "tab1_crosstoolbox.tex"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(rows())} data rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
