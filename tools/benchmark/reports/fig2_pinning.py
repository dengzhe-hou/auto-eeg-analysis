#!/usr/bin/env python
"""Figure 2 — divergence before vs after pinning one word of the specification.

Panel (a): FieldTrip-vs-certified max per-subject |Δ|, toolbox default -> fully pinned filter
(cutoff convention AND transition width change together; the cutoff-only step is 0.8023 -> 0.0496 µV for P3),
five components, with the ±0.1 µV certification tolerance marked.
Panel (b): the cluster-forming tail. Before-pinning data exist for N400 only (the original
alpha=0.05 run); after pinning, all four tested components have exactly identical partitions.

Every plotted value is read from committed JSONs; tools/tests/test_benchmark_reports.py re-derives
the expectations independently and checks the artists (contract E17).
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BM = ROOT / "tools" / "benchmark"
COMPONENTS = ["P3", "N400", "ERN", "N170", "MMN"]


def load_pairs() -> dict[str, tuple[float, float]]:
    rows = json.loads((BM / "CROSS_TOOLBOX_RESULT.json").read_text(encoding="utf-8-sig"))
    by_src = {r["source"]: r for r in rows}
    out = {}
    for c in COMPONENTS:
        out[c] = (by_src[f"fieldtrip_{c}.json"]["max_abs_diff_uV"],
                  by_src[f"fieldtrip_{c}_cutmatch.json"]["max_abs_diff_uV"])
    return out


def _p3_width_only():
    rows = json.loads((BM / "CROSS_TOOLBOX_RESULT.json").read_text(encoding="utf-8-sig"))
    for r in rows:
        if r["source"] == "fieldtrip_P3_df0.1.json":
            return r["max_abs_diff_uV"]
    return None


def load_cluster() -> dict:
    cc = BM / "cluster_cert"
    j = lambda n: json.loads((cc / n).read_text(encoding="utf-8-sig"))
    mne, ft05, ft025 = j("mne_N400.json"), j("fieldtrip_N400.json"), j("fieldtrip_N400_a025.json")
    lead = lambda d: max(d["clusters"], key=lambda c: abs(c["t_sum"]))
    return {"n_mne": mne["n_clusters"], "n_ft_unpinned": ft05["n_clusters"],
            "n_ft_pinned": ft025["n_clusters"],
            "ext_mne": lead(mne)["n_points"], "ext_ft_unpinned": lead(ft05)["n_points"],
            "ext_ft_pinned": lead(ft025)["n_points"]}


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker

    pairs, clu = load_pairs(), load_cluster()
    fig = plt.figure(figsize=(7.6, 3.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[3, 2], height_ratios=[1, 1], hspace=0.12, wspace=0.42)
    ax_a = fig.add_subplot(gs[:, 0]); ax_b = fig.add_subplot(gs[0, 1]); axe = fig.add_subplot(gs[1, 1], sharex=ax_b)

    styles = {"P3": ("-", "o"), "N400": ("--", "s"), "ERN": ("-.", "^"), "N170": (":", "D"), "MMN": ("-", "v")}
    for i, c in enumerate(COMPONENTS):
        un, pi = pairs[c]
        ls, mk = styles[c]
        ax_a.plot([0, 1], [un, pi], ls=ls, marker=mk, ms=5, lw=1.5, label=c)
    # the intermediate P3b configuration carries the causal argument: transition width pinned alone
    # (0.8023 uV, worse) before the cutoff convention is changed at that fixed width
    mid = _p3_width_only()
    if mid is not None:
        ax_a.plot([0.5], [mid], marker="o", ms=5, color="C0", ls="none")
        ax_a.annotate("P3b, transition\nwidth only", (0.5, mid), textcoords="offset points", xytext=(8, -24), fontsize=8.5)
    # Right-edge labels, dodged: with several pinned values near 0.05 the naive placement
    # overprints them (P3 and N400 collided in the first render).
    import numpy as np
    order = sorted(COMPONENTS, key=lambda c: pairs[c][1])
    ys = [pairs[c][1] for c in order]
    placed = []
    for c, y in zip(order, ys):
        yy = y
        while placed and yy / placed[-1] < 1.22:      # log-scale spacing
            yy = placed[-1] * 1.22
        placed.append(yy)
        ax_a.annotate({"P3": "P3b"}.get(c, c), (1.05, yy), fontsize=8.5, va="center")
    ax_a.axhline(0.1, color="0.4", ls="--", lw=0.9)
    ax_a.annotate("0.1 µV tolerance", (0.05, 0.088), fontsize=8.5, color="0.35")
    ax_a.set_yscale("log")
    ax_a.set_xticks([0, 0.5, 1], ["FieldTrip\ndefault", "width\npinned", "cutoff convention\n+ width pinned"], fontsize=8.5)
    ax_a.set_xlim(-0.15, 1.35)
    ax_a.set_ylabel("max per-subject |Δ| vs reference (µV)", fontsize=9.5)
    ax_a.set_yticks([0.05, 0.1, 0.2, 0.5, 1.0]); ax_a.set_yticklabels(["0.05", "0.1", "0.2", "0.5", "1"], fontsize=8.5)
    ax_a.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax_a.set_title("(a) FieldTrip filter specification", fontsize=9.5)

    x = [0, 1, 2]
    n_vals = [clu["n_mne"], clu["n_ft_unpinned"], clu["n_ft_pinned"]]
    e_vals = [clu["ext_mne"], clu["ext_ft_unpinned"], clu["ext_ft_pinned"]]
    ax_b.bar(x, n_vals, width=0.55, color="C0")
    axe.bar(x, e_vals, width=0.55, color="C1")
    for i, (n, e) in enumerate(zip(n_vals, e_vals)):
        ax_b.annotate(str(n), (i, n), ha="center", va="bottom", fontsize=8.5)
        axe.annotate(str(e), (i, e), ha="center", va="bottom", fontsize=8.5)
    ax_b.set_ylabel("suprathreshold\nclusters", fontsize=9); axe.set_ylabel("leading-cluster\nextent (samples)", fontsize=9)
    ax_b.set_ylim(0, 22); axe.set_ylim(0, 1750)
    ax_b.tick_params(axis="y", labelsize=8.5); axe.tick_params(axis="y", labelsize=8.5)
    plt.setp(ax_b.get_xticklabels(), visible=False)
    axe.set_xticks(x); axe.set_xticklabels(["MNE-Python\n$t_{0.975}$", "FieldTrip\n$t_{0.95}$", "FieldTrip\n$t_{0.975}$ (matched)"], fontsize=8.5)
    ax_b.set_title("(b) cluster-forming threshold (N400, full epoch)", fontsize=9.5)

    return fig, (ax_a, ax_b, axe), {"pairs": pairs, "cluster": clu}


if __name__ == "__main__":
    fig, _, _ = build()
    out = Path(__file__).resolve().parent / "fig2_pinning.pdf"
    fig.savefig(out)
    print(f"wrote {out}")
