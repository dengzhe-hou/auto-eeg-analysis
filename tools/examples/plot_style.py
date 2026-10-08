"""Shared print-size figure style retained from the worked-example plotter."""

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
