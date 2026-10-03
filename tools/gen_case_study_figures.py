"""Render the repaired case studies from their retained analysis outputs.

Run ``python tools/gen_case_study_figures.py --run-dir RUN`` after a case-study
runner has written ``summary.json`` and ``plot_arrays.npz``. The plotting input
arrays contain the analysis means, uncertainty and electrode positions; this
module performs no statistical tests or preprocessing. Figures are designed at
180 mm width and saved as PDF, editable-text SVG and 600 dpi PNG, alongside a
caption that identifies the statistical unit and the descriptive panels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


CONDITION_A = "#0072B2"
CONDITION_B = "#D55E00"
DIFFERENCE = "#333333"
WINDOW = "#e7e7e7"
MM_PER_INCH = 25.4


def figure_style() -> dict:
    """Use the same print-size typography and condition colors for both cases."""
    from matplotlib import font_manager

    installed = {font.name for font in font_manager.fontManager.ttflist}
    font = next((name for name in ("Arial", "Helvetica") if name in installed), None)
    if font is None:
        raise RuntimeError("Install Arial or Helvetica before exporting these figures.")
    return {
        "font.family": "sans-serif",
        "font.sans-serif": [font],
        "mathtext.fontset": "custom",
        "mathtext.rm": font,
        "mathtext.it": f"{font}:italic",
        "mathtext.bf": f"{font}:bold",
        "mathtext.sf": font,
        "mathtext.default": "regular",
        "font.size": 7,
        "axes.labelsize": 7.5,
        "axes.titlesize": 7.5,
        "axes.titlepad": 7,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "legend.fontsize": 6.5,
        "legend.frameon": False,
        "legend.handlelength": 1.5,
        "lines.linewidth": 1.2,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }


def _panel(ax, letter: str, title: str) -> None:
    ax.set_title(title, loc="left")
    ax.text(
        -0.19, 1.04, letter, transform=ax.transAxes, fontsize=8.5,
        fontweight="bold", va="bottom", ha="left",
    )


def _time_axes(ax, times_s, window_s, ylabel: str, response: bool = False) -> None:
    ax.axvspan(*np.asarray(window_s) * 1000, facecolor=WINDOW, zorder=0)
    ax.axvline(0, color="0.55", linestyle="--", linewidth=0.65, zorder=0)
    ax.axhline(0, color="0.65", linewidth=0.55, zorder=0)
    ax.set(
        xlabel="Time from response (ms)" if response else "Time (ms)",
        ylabel=ylabel,
        xlim=(times_s[0] * 1000, times_s[-1] * 1000),
    )


def _cluster_note(ax, claim: dict) -> None:
    p = claim["min_p"]
    text = "No supra-threshold cluster" if p is None else f"Minimum cluster p = {p:.4f}"
    ax.text(
        0.98, 0.98, text, transform=ax.transAxes, ha="right", va="top",
        fontsize=5.5, color="0.25",
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none", "pad": 1.2},
    )


def _two_conditions(ax, times_s, a, b, a_label: str, b_label: str,
                    sem_a=None, sem_b=None) -> None:
    times_ms = np.asarray(times_s) * 1000
    for values, error, color, label in (
        (a, sem_a, CONDITION_A, a_label), (b, sem_b, CONDITION_B, b_label),
    ):
        ax.plot(times_ms, values, color=color, label=label)
        if error is not None:
            ax.fill_between(times_ms, values - error, values + error, color=color,
                            alpha=0.16, linewidth=0)


def _milliseconds(window) -> str:
    return f"{window[0] * 1000:g}–{window[1] * 1000:g} ms"


def _cluster_caption(claim: dict) -> str:
    p = claim["min_p"]
    minimum = "no supra-threshold clusters" if p is None else f"minimum cluster p = {p:.6g}"
    return (f"{claim['claim_id']}: {minimum}; {claim['n_sig']} clusters pass "
            f"the cluster-level threshold p < {claim['cluster_alpha']:.6g}.")


def _n100_figure(summary: dict, arrays: dict):
    import matplotlib.pyplot as plt

    claim = summary["claims"][0]
    fig, axes = plt.subplots(1, 3, figsize=(180 / MM_PER_INCH, 80 / MM_PER_INCH))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.30, top=0.86, wspace=0.53)
    times = arrays["times"]
    window = arrays["window_s"]
    a_name, b_name = summary["condition_a_name"], summary["condition_b_name"]

    ax = axes[0]
    _panel(ax, "a", "N100 at the selected ROI")
    _time_axes(ax, times, window, "Amplitude (µV)")
    _two_conditions(ax, times, arrays["condition_a_uv"], arrays["condition_b_uv"],
                    a_name, b_name, arrays["condition_a_sem_uv"], arrays["condition_b_sem_uv"])
    ax.legend(loc="best")

    ax = axes[1]
    _panel(ax, "b", f"{a_name} − {b_name}")
    _time_axes(ax, times, window, "Difference (µV)")
    difference = arrays["difference_uv"]
    sem = arrays["difference_sem_uv"]
    ax.plot(times * 1000, difference, color=DIFFERENCE)
    ax.fill_between(times * 1000, difference - sem, difference + sem,
                    color=DIFFERENCE, alpha=0.16, linewidth=0)
    _cluster_note(ax, claim)

    ax = axes[2]
    _panel(ax, "c", "ROI electrode locations")
    sensors = arrays["all_sensor_positions_m"] * 1000
    positions = arrays["roi_positions_m"] * 1000
    targets = arrays["target_positions_m"] * 1000
    ax.scatter(sensors[:, 0], sensors[:, 1], s=4, c="0.78", linewidths=0,
               zorder=1)
    for actual, target, label in zip(positions, targets, arrays["roi_targets"]):
        ax.plot([actual[0], target[0]], [actual[1], target[1]], color="0.45",
                linewidth=0.65, zorder=2)
        offset = (-12, -9) if str(label) == "Cz" else (3, 4)
        ax.annotate(str(label), xy=target[:2], xytext=offset, textcoords="offset points",
                    fontsize=5.5, color="0.2")
    ax.scatter(positions[:, 0], positions[:, 1], c=CONDITION_A, s=13,
               edgecolors="white", linewidths=0.35, label="Selected electrodes", zorder=3)
    ax.scatter(targets[:, 0], targets[:, 1], c=CONDITION_B, marker="+", s=22,
               linewidths=0.8, label="10–20 targets", zorder=4)
    ax.set(xlabel="Head x (mm)", ylabel="Head y (mm)", aspect="equal")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.26), fontsize=5.5)

    caption = (
        "Auditory and visual responses in the repaired N100 example. "
        "(a) Condition means over the six selected ROI electrodes. "
        "(b) Auditory minus visual mean. Shading around the curves in a and b is ±1 SEM "
        f"across {claim['n_cycles']} complete stimulus cycles; the difference SEM uses "
        "the within-cycle differences. Grey backgrounds show the planned "
        f"{_milliseconds(window)} analysis window, not significance at individual time points. "
        "(c) Measured sensor locations and the six intended 10–20 targets, projected onto "
        "the x–y plane of head coordinates. Lines connect each selected electrode with its "
        "target; distances in this projection are not the three-dimensional matching distances. "
        + _cluster_caption(claim) + " Cluster-level inference does not localize significance "
        "to each time point or electrode. This is a single-participant analysis."
    )
    return fig, "F1_auditory_vs_visual_N100", caption


def _flankers_figure(summary: dict, arrays: dict):
    import matplotlib.pyplot as plt
    import mne

    claims = {claim["claim_id"]: claim for claim in summary["claims"]}
    fig, axes = plt.subplots(2, 3, figsize=(180 / MM_PER_INCH, 133 / MM_PER_INCH),
                             layout="constrained")
    fig.get_layout_engine().set(w_pad=0.055, h_pad=0.07, wspace=0.08, hspace=0.12)
    roi = arrays["roi_indices"].astype(int)

    for col, prefix, claim_id, title in (
        (0, "stim", "C1", "Stimulus-locked ERP"),
        (1, "resp", "C2", "Response-locked ERP"),
    ):
        ax = axes[0, col]
        times = arrays[f"{prefix}_times"]
        _panel(ax, chr(ord("a") + col), title)
        _time_axes(ax, times, claims[claim_id]["spec"]["window_s"], "Amplitude (µV)",
                   response=prefix == "resp")
        _two_conditions(ax, times, arrays[f"{prefix}_comp_uV"][roi].mean(axis=0),
                        arrays[f"{prefix}_incomp_uV"][roi].mean(axis=0),
                        "Compatible", "Incompatible")
        _cluster_note(ax, claims[claim_id])
        ax.legend(loc="upper right", bbox_to_anchor=(1, 0.86))

    ax = axes[0, 2]
    _panel(ax, "c", "Stimulus difference map")
    names = [str(name) for name in arrays["channel_names"]]
    montage = mne.channels.make_dig_montage(
        ch_pos=dict(zip(names, arrays["channel_pos_head_m"])), coord_frame="head")
    info = mne.create_info(names, sfreq=1, ch_types="eeg")
    info.set_montage(montage)
    topography = arrays["stim_topomap_uV"]
    limit = float(np.max(np.abs(topography)))
    im, _ = mne.viz.plot_topomap(topography, info, axes=ax, show=False, contours=0,
                               cmap="RdBu_r", vlim=(-limit, limit), sensors=True)
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.05, shrink=0.8)
    cbar.set_label("µV", fontsize=7)
    cbar.ax.tick_params(labelsize=6, width=0.5, length=2)
    ax.text(0.5, -0.09, _milliseconds(arrays["topomap_window_s"]),
            transform=ax.transAxes, ha="center", fontsize=6)

    ax = axes[1, 0]
    _panel(ax, "d", "Time–frequency difference")
    tfr_difference = arrays["tfr_diff_db"].mean(axis=0)
    limit = float(np.max(np.abs(tfr_difference)))
    im = ax.pcolormesh(arrays["tfr_times"] * 1000, arrays["tfr_freqs"], tfr_difference,
                       cmap="RdBu_r", vmin=-limit, vmax=limit, shading="auto", rasterized=True)
    ax.axvline(0, color="0.35", linestyle="--", linewidth=0.65)
    ax.set(xlabel="Time (ms)", ylabel="Frequency (Hz)",
           xlim=(arrays["tfr_times"][0] * 1000, arrays["tfr_times"][-1] * 1000))
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.05)
    cbar.set_label("dB", fontsize=7)
    cbar.ax.tick_params(labelsize=6, width=0.5, length=2)

    ax = axes[1, 1]
    frequencies = claims["C3"]["spec"]["freq_range_hz"]
    _panel(ax, "e", f"Theta power ({frequencies[0]:g}–{frequencies[1]:g} Hz)")
    _time_axes(ax, arrays["tfr_times"], claims["C3"]["spec"]["window_s"], "Power (dB)")
    _two_conditions(ax, arrays["tfr_times"], arrays["theta_comp_db"], arrays["theta_incomp_db"],
                    "Compatible", "Incompatible")
    _cluster_note(ax, claims["C3"])
    ax.legend(loc="lower right")

    ax = axes[1, 2]
    _panel(ax, "f", "Power spectral density")
    ax.semilogy(arrays["psd_freqs"], arrays["psd_comp_roi"],
                color=CONDITION_A, label="Compatible")
    ax.semilogy(arrays["psd_freqs"], arrays["psd_incomp_roi"],
                color=CONDITION_B, label="Incompatible")
    ax.set(xlabel="Frequency (Hz)", ylabel="PSD (V²/Hz)",
           xlim=(arrays["psd_freqs"][0], arrays["psd_freqs"][-1]))
    ax.legend(loc="upper right")

    sample_sizes = "; ".join(
        f"{claim_id}: {claims[claim_id]['n_per_condition']['compatible']} compatible, "
        f"{claims[claim_id]['n_per_condition']['incompatible']} incompatible trials"
        for claim_id in ("C1", "C2", "C3")
    )
    caption = (
        "Compatible and incompatible responses in the repaired Flankers example. "
        f"{sample_sizes}. (a,b) Condition means over the "
        f"{', '.join(str(name) for name in arrays['roi_names'])} ROI for stimulus- and "
        "response-locked epochs. The response-locked contrast compares compatibility, "
        "not errors against correct responses. (c) Incompatible minus compatible ERP, "
        f"averaged over {_milliseconds(arrays['topomap_window_s'])} at each electrode. "
        "(d) ROI mean time–frequency difference, incompatible minus compatible. "
        "(e) Theta power averaged over the stated frequency band and ROI. Panels d and e "
        "use per-trial baseline-normalized power, 10 log10(power / baseline power), in dB. "
        "(f) ROI mean power spectral density. Curves show condition means without error bands. "
        "Grey backgrounds show the planned windows, not pointwise significance. "
        + " ".join(_cluster_caption(claims[key]) for key in ("C1", "C2", "C3"))
        + " C3 inference uses joint frequency × time × electrode clusters; its averaged "
        "theta curve is descriptive. Cluster-level p values do not identify significant "
        "individual time points, frequencies or electrodes. These are trial-level "
        "within-participant comparisons, not population inference."
    )
    return fig, "F1_flankers_full", caption


def generate_figures(run_dir: str | Path, out: str | Path | None = None) -> list[Path]:
    """Generate the case's figure and caption from one completed run directory."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    run_dir = Path(run_dir)
    out_dir = Path(out) if out is not None else run_dir / "figure-stage"
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8-sig"))
    with np.load(run_dir / "plot_arrays.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    renderers = {"n100": _n100_figure, "flankers": _flankers_figure}
    out_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(figure_style()):
        fig, stem, caption = renderers[summary["case"]](summary, arrays)
        outputs = []
        for suffix in ("pdf", "svg", "png"):
            path = out_dir / f"{stem}.{suffix}"
            fig.savefig(path, dpi=600)
            outputs.append(path)
        plt.close(fig)
    caption_path = out_dir / f"{stem}.caption.txt"
    caption_path.write_text(caption + "\n", encoding="utf-8")
    outputs.append(caption_path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="Output directory (default: RUN/figure-stage)")
    args = parser.parse_args()
    for path in generate_figures(args.run_dir, args.out):
        print(path)


if __name__ == "__main__":
    main()
