"""Render all F1 panels required by the v0.3.2 N400 recipe from saved ERP arrays."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from gen_case_study_figures import (CONDITION_A, CONDITION_B, DIFFERENCE,
                                   MM_PER_INCH, figure_style)


def render(run_dir: Path, figure_data: Path | None = None,
           summary_path: Path | None = None) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mne

    if figure_data is None:
        arrays = np.load(run_dir / "erp-stage/group_arrays.npz")
        summary = json.loads((run_dir / "stats-stage/summary.json").read_text(encoding="utf-8-sig"))
        info = mne.io.read_info(run_dir / "erp-stage/group-info.fif", verbose="ERROR")
        related, unrelated = arrays["related"], arrays["unrelated"]
        idx = [info["ch_names"].index(name) for name in summary["roi"]]
        roi_related = related[:, idx].mean(1) * 1e6
        roi_unrelated = unrelated[:, idx].mean(1) * 1e6
        grand_difference = (unrelated-related).mean(0) * 1e6
    else:
        arrays = np.load(figure_data)
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))["results"]
        info = mne.create_info(arrays["all_ch_names"].tolist(), 256, "eeg")
        info.set_montage(mne.channels.make_dig_montage(
            ch_pos=dict(zip(info["ch_names"], arrays["positions_m"])), coord_frame="head"))
        roi_related = arrays["related_roi_uV"].mean(1)
        roi_unrelated = arrays["unrelated_roi_uV"].mean(1)
        grand_difference = arrays["grand_average_difference_uV"]
    times = arrays["times"]
    roi_difference = roi_unrelated - roi_related
    window = (times >= 0.3) & (times <= 0.5)
    peak_index = np.flatnonzero(window)[np.argmin(roi_difference.mean(0)[window])]
    peak_map = grand_difference[:, peak_index]
    subject_uv = roi_difference[:, window].mean(1)
    output = run_dir / "figure-stage"
    output.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(figure_style()):
        fig, axes = plt.subplots(1, 3, figsize=(180 / MM_PER_INCH, 71 / MM_PER_INCH))
        fig.subplots_adjust(left=0.075, right=0.985, bottom=0.25, top=0.82, wspace=0.53)
        titles = ["N400 at CPz/Cz/Pz", f"Difference at {times[peak_index] * 1000:.0f} ms",
                  "Participant N400 amplitudes"]
        for ax, label, title in zip(axes, "abc", titles):
            ax.set_title(title, loc="left")
            ax.text(-0.17, 1.17, label, transform=ax.transAxes, fontsize=8.5,
                    fontweight="bold", va="top")
        ax = axes[0]
        ax.axvspan(300, 500, color="0.92", zorder=0)
        for values, color, label in [(roi_related, CONDITION_A, "Related"),
                                      (roi_unrelated, CONDITION_B, "Unrelated"),
                                      (roi_difference, DIFFERENCE, "Difference")]:
            mean = values.mean(0)
            sem = values.std(0, ddof=1) / np.sqrt(len(values))
            ax.plot(times * 1000, mean, color=color, label=label)
            ax.fill_between(times * 1000, mean-sem, mean+sem, color=color,
                            alpha=0.12, linewidth=0)
        ax.axhline(0, color="0.5", linewidth=0.5)
        ax.axvline(0, color="0.5", linewidth=0.5, linestyle="--")
        ax.set(xlabel="Time from target (ms)", ylabel="Amplitude (µV)", xlim=(-200, 800))
        ax.legend(loc="lower left", bbox_to_anchor=(0, -0.40), ncol=2,
                  fontsize=5.5, borderaxespad=0)
        ax = axes[1]
        limit = float(np.abs(peak_map).max())
        im, _ = mne.viz.plot_topomap(peak_map, info, axes=ax, show=False,
                                    cmap="RdBu_r", vlim=(-limit, limit), contours=0)
        cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.06)
        cb.set_label("Difference (µV)", fontsize=7)
        ax = axes[2]
        xs = np.arange(1, len(subject_uv) + 1)
        ax.scatter(xs, subject_uv, s=12, color=DIFFERENCE, linewidth=0)
        ax.axhline(0, color="0.5", linewidth=0.5)
        ax.axhline(subject_uv.mean(), color=CONDITION_B, linewidth=1.2, label="Group mean")
        ax.set(xlabel="Participant", ylabel="Unrelated − related (µV)",
               xticks=[1, 5, 10, 15, 20], xlim=(0, 21))
        ax.legend(loc="lower left", bbox_to_anchor=(0, -0.40), fontsize=6)
        files = []
        for suffix in ("pdf", "svg", "png"):
            path = output / f"F1_n400_recipe.{suffix}"
            fig.savefig(path, dpi=600)
            files.append(path)
        plt.close(fig)
    caption = (
        f"N400 recipe case (N={len(subject_uv)} participants). (a) Grand-average related, "
        "unrelated, and unrelated-minus-related ERPs averaged over CPz/Cz/Pz. Shading is "
        "±1 SEM across participants for each curve; the grey area is the prespecified "
        "300–500 ms inferential window. (b) Descriptive full-scalp difference topomap at "
        f"{times[peak_index]*1000:.2f} ms, the most negative grand-average ROI sample in "
        "that window. (c) All participants' mean ROI differences in 300–500 ms; the line "
        "is their group mean. The sole primary inferential test uses the three-channel "
        "ROI over the complete 300–500 ms window, negative tail, 5000 permutations, seed 42; "
        f"minimum cluster p={summary['min_cluster_p']}. Cluster-level inference does not "
        "localize individual electrodes or samples. The explicitly documented benchmark "
        "branch omits ICA and amplitude-based trial rejection."
    )
    (output / "F1_n400_recipe.caption.txt").write_text(caption + "\n", encoding="utf-8")
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "projects/n400-recipe-case")
    parser.add_argument("--figure-data", type=Path,
                        help="Replot the compact public NPZ without participant EEG files")
    parser.add_argument("--summary", type=Path, default=ROOT / "tools/validation/recipe_case_results.json")
    args = parser.parse_args()
    print("\n".join(str(p) for p in render(args.run_dir, args.figure_data, args.summary)))
