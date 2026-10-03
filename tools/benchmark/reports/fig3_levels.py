#!/usr/bin/env python
"""Figure 3 — the honest coverage map: certification level of each of the 22 skills."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORDER = ["L3", "L2", "L1", "L0"]
COLOR = {"L3": "#1b5e20", "L2": "#4c8f3a", "L1": "#b8860b", "L0": "#c8c8c8"}
LABEL = {"L3": "L3 cross-toolbox certified (end-to-end output)", "L2": "L2 cross-implementation certified",
         "L1": "L1 behaviourally evaluated", "L0": "L0 API-tested only"}


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    levels = json.loads((Path(__file__).resolve().parent / "skill_levels.json")
                        .read_text(encoding="utf-8-sig"))["levels"]
    skills = sorted(levels, key=lambda s: (ORDER.index(levels[s]), s))

    fig, ax = plt.subplots(figsize=(7.0, 5.4))
    xpos = {"L3": 3, "L2": 2, "L1": 1, "L0": 0}
    for i, s in enumerate(skills):
        lv = levels[s]
        ax.barh(i, xpos[lv] + 1, color=COLOR[lv], edgecolor="white", height=0.78)
        ax.annotate(s.replace("eeg-", ""), (-0.15, i), va="center", ha="right", fontsize=10, color="#111111")
        ax.annotate(lv, (xpos[lv] + 1.1, i), va="center", ha="left", fontsize=10, color="#111111")
    ax.set_yticks([]); ax.invert_yaxis()
    ax.set_xlim(-2.2, 5.2); ax.set_xticks([1, 2, 3, 4]); ax.set_xticklabels(["L0", "L1", "L2", "L3"], fontsize=10)
    ax.set_xlabel("certification level (categorical)", fontsize=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    counts = {l: sum(1 for v in levels.values() if v == l) for l in ORDER}
    ax.legend(handles=[Patch(color=COLOR[l], label=f"{LABEL[l]} (n={counts[l]})") for l in ORDER],
              loc="upper center", bbox_to_anchor=(0.45, -0.10), ncol=2, fontsize=9, frameon=False)
    fig.tight_layout()
    return fig, ax, levels


if __name__ == "__main__":
    fig, _, _ = build()
    out = Path(__file__).resolve().parent / "fig3_levels.pdf"
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")
