#!/usr/bin/env python
"""Figure 1 — the certification chain, with the independent implementation at each link.

Deterministic vector diagram (matplotlib). Contrast waveforms branch into the ROI amplitude and the
cluster statistic (the cluster test takes channel-by-time contrast waves, not scalar amplitudes).
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 5.2); ax.axis("off")

    def box(x, y, w, h, name, fs=9.0):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08", fc="#eef3fa", ec="#33507a", lw=1.2))
        ax.text(x + w / 2, y + h / 2, name, ha="center", va="center", fontsize=fs, fontweight="bold")

    def arrow(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=13, color="#33507a", lw=1.2))

    def note(x, y, text):
        ax.text(x, y, text, ha="center", va="top", fontsize=8.0, color="#222222")

    # column 1: raw data
    box(0.3, 2.3, 1.7, 1.0, "raw EEG\n(ERP CORE, BIDS)")
    note(1.15, 2.0, "public data;\nper-condition trial\ncounts matched across\narms (MMN: rejection\ndiffers by arm)")
    # column 2: contrast waveforms
    box(2.75, 2.3, 1.8, 1.0, "per-subject\ncontrast\nwaveforms")
    note(3.65, 2.0, "filter, reference,\nepoch, baseline,\naverage (Table 1)")
    arrow(2.05, 2.8, 2.7, 2.8)
    # column 3: two outputs
    box(5.3, 3.5, 1.9, 0.95, "ROI amplitude")
    box(5.3, 1.35, 1.9, 0.95, "cluster statistic\n(t-map,\npartitions)")
    arrow(4.6, 2.95, 5.25, 3.95); arrow(4.6, 2.65, 5.25, 1.85)
    note(6.25, 4.75 + 0.35, "")
    ax.text(6.25, 4.98, "reference pipeline: 112/112 within 0.1 µV;\nEEGLAB, FieldTrip arms", ha="center", va="bottom", fontsize=8.0, color="#222222")
    ax.text(6.25, 1.05, "FieldTrip: identical partitions,\nt-maps to floating-point precision", ha="center", va="top", fontsize=8.0, color="#222222")
    # column 4: figure
    box(7.95, 2.3, 1.7, 1.0, "figure")
    arrow(7.25, 3.95, 7.9, 3.0); arrow(7.25, 1.85, 7.9, 2.6)
    note(8.8, 2.0, "plotted values read\nback and checked\nagainst the source\narrays")
    ax.text(5.0, 0.2, "each output compared with an independent implementation; committed artifacts tested on every change",
            ha="center", fontsize=8.5, style="italic", color="#33507a")
    fig.tight_layout()
    return fig, ax


if __name__ == "__main__":
    fig, _ = build()
    out = Path(__file__).resolve().parent / "fig1_chain.pdf"
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")
