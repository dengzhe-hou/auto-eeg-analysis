"""Paper figures must show the numbers their sources hold (acceptance contract E17/E18).

The generic figure-fidelity checks were validated on synthetic figures; the contract reviewer was
right that this does not verify the PAPER's figures. These tests re-derive every plotted value
independently from the committed JSONs and read the artists of the actual Figure 2 / Figure 3 /
Table 1 builders.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "tools" / "benchmark" / "reports"
sys.path.insert(0, str(FIG))


def _result_rows():
    rows = json.loads((ROOT / "tools" / "benchmark" / "CROSS_TOOLBOX_RESULT.json")
                      .read_text(encoding="utf-8-sig"))
    return {r["source"]: r for r in rows}


# --- Figure 2 (contract E17) --------------------------------------------------------------------

def test_fig2_slopes_match_the_json():
    """Every unpinned->pinned pair drawn in panel (a) equals the committed comparison rows."""
    import fig2_pinning
    fig, (ax_a, _, _), _ = fig2_pinning.build()
    by_src = _result_rows()
    expected = {}
    for c in fig2_pinning.COMPONENTS:
        expected[c] = (by_src[f"fieldtrip_{c}.json"]["max_abs_diff_uV"],
                       by_src[f"fieldtrip_{c}_cutmatch.json"]["max_abs_diff_uV"])
    drawn = [tuple(np.asarray(ln.get_ydata(), dtype=float))
             for ln in ax_a.get_lines() if len(ln.get_xdata()) == 2]
    for c, pair in expected.items():
        assert any(np.allclose(d, pair, rtol=0, atol=1e-12) for d in drawn), \
            f"{c}: {pair} not drawn in panel (a)"
    matplotlib.pyplot.close(fig)


def test_fig2_has_the_tolerance_line_and_units():
    import fig2_pinning
    fig, (ax_a, _, _), _ = fig2_pinning.build()
    hlines = [ln for ln in ax_a.get_lines()
              if len(set(np.asarray(ln.get_ydata()))) == 1
              and np.isclose(float(np.asarray(ln.get_ydata())[0]), 0.1)]
    assert hlines, "the ±0.1 µV certification-tolerance line is missing"
    assert "µV" in ax_a.get_ylabel(), f"y-label lacks units: {ax_a.get_ylabel()!r}"
    matplotlib.pyplot.close(fig)


def test_fig2_cluster_panel_matches_the_json():
    import fig2_pinning
    fig, (_, ax_b, axe), _ = fig2_pinning.build()
    cc = ROOT / "tools" / "benchmark" / "cluster_cert"
    j = lambda n: json.loads((cc / n).read_text(encoding="utf-8-sig"))
    lead = lambda d: max(d["clusters"], key=lambda c: abs(c["t_sum"]))
    exp_n = [j("mne_N400.json")["n_clusters"], j("fieldtrip_N400.json")["n_clusters"],
             j("fieldtrip_N400_a025.json")["n_clusters"]]
    exp_e = [lead(j("mne_N400.json"))["n_points"], lead(j("fieldtrip_N400.json"))["n_points"],
             lead(j("fieldtrip_N400_a025.json"))["n_points"]]
    got_n = sorted(p.get_height() for p in ax_b.patches)
    got_e = sorted(p.get_height() for p in axe.patches)
    assert got_n == sorted(exp_n), f"cluster counts drawn {got_n} != {sorted(exp_n)}"
    assert got_e == sorted(exp_e), f"extents drawn {got_e} != {sorted(exp_e)}"
    matplotlib.pyplot.close(fig)


# --- Figure 3 (contract E18): per-skill, not just totals ----------------------------------------

def _levels_from_doc() -> dict[str, str]:
    doc = (ROOT / "docs" / "CERTIFICATION_LEVELS.md").read_text(encoding="utf-8-sig")
    out = {}
    for m in re.finditer(r"^\| `([a-z-]+)` \| \*?\*?(L[0-3])\*?\*?", doc, re.M):
        out[m.group(1)] = m.group(2)
    return out


def test_fig3_source_matches_certification_levels_doc_per_skill():
    levels = json.loads((FIG / "skill_levels.json").read_text(encoding="utf-8-sig"))["levels"]
    doc = _levels_from_doc()
    assert doc, "could not parse docs/CERTIFICATION_LEVELS.md"
    assert levels == doc, (
        "per-skill mismatch between the figure's source and the doc:\n"
        + "\n".join(f"  {k}: fig={levels.get(k)} doc={doc.get(k)}"
                    for k in sorted(set(levels) | set(doc)) if levels.get(k) != doc.get(k)))


def test_fig3_totals_are_4_1_3_14():
    levels = json.loads((FIG / "skill_levels.json").read_text(encoding="utf-8-sig"))["levels"]
    counts = {l: sum(1 for v in levels.values() if v == l) for l in ("L3", "L2", "L1", "L0")}
    # eeg-recipe was L2 on the strength of the historical generation pilot alone; the claims gate
    # (2026-09-13) reclassified it to L0.
    assert counts == {"L3": 4, "L2": 1, "L1": 3, "L0": 14}, counts


def test_fig3_draws_one_bar_per_skill():
    import fig3_levels
    fig, ax, levels = fig3_levels.build()
    assert len(ax.patches) == len(levels) == 22
    matplotlib.pyplot.close(fig)


# --- Table 1 (contract E18): cells from the ten named rows --------------------------------------

def test_tab1_cells_match_the_json():
    import tab1_crosstoolbox
    tex = (FIG / "tab1_crosstoolbox.tex").read_text(encoding="utf-8-sig")
    for tb, c, r in tab1_crosstoolbox.rows():
        needle = (f"{tb} & {'P3b' if c == 'P3' else c} & {r['n_shared']} & {r['grand_mean_diff_pct']:.3f} & {r['max_abs_diff_uV']:.3f} & "
                  f"{r['ccc']:.4f} & {r['within_0p1uV']}/{r['n_shared']}")
        assert needle in tex, f"row not found or drifted: {needle}"
    assert len(tab1_crosstoolbox.rows()) == 10
