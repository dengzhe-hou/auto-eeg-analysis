"""Draw the AEA library workflow using the shared print-size figure style."""
from __future__ import annotations

import argparse
from pathlib import Path

from plot_style import CONDITION_A, MM_PER_INCH, figure_style

ROOT = Path(__file__).resolve().parents[2]


def render(output_dir: Path) -> list[Path]:
    """Export an editable SVG, a vector PDF, and a 600 dpi PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle

    output_dir.mkdir(parents=True, exist_ok=True)
    text_color = "#202B33"
    border_color = "#687780"
    with plt.rc_context(figure_style()):
        fig = plt.figure(figsize=(180 / MM_PER_INCH, 82 / MM_PER_INCH))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set(xlim=(0, 180), ylim=(0, 82), aspect="equal")
        ax.set_axis_off()

        def box(x: float, y: float, width: float, height: float,
                title: str, lines: list[str], *, fill: str = "white",
                border: str = border_color) -> None:
            ax.add_patch(Rectangle((x, y), width, height, facecolor=fill,
                                   edgecolor=border, linewidth=1.0))
            ax.text(x + width / 2, y + height - 5.1, title,
                    ha="center", va="center", color=text_color,
                    fontsize=7.5, fontweight="bold")
            for index, line in enumerate(lines):
                ax.text(x + width / 2, y + height - 10.2 - 4.5 * index,
                        line, ha="center", va="center", color=text_color,
                        fontsize=7)

        def arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
            ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>",
                                         mutation_scale=7, linewidth=1.0,
                                         color=border_color, shrinkA=1,
                                         shrinkB=1))

        box(44, 61, 94, 17, "AEA skills + recipes",
            ["Inputs · Parameters · Templates · Outputs · Checks"],
            fill="#F0F5FA", border=CONDITION_A)
        box(4, 32, 44, 22, "Researcher",
            ["Study design + data", "Approves analysis plan"])
        box(69, 32, 44, 22, "LLM coding client",
            ["Adapts code templates", "Runs saved scripts"])
        box(136, 32, 40, 22, "MNE-Python",
            ["Computes EEG results", "Primary backend"])
        box(69, 5, 107, 17, "Saved workflow artifacts",
            ["Code · Results · Figures · Methods · Review records"])

        arrow((48, 43), (69, 43))
        ax.text(58.5, 46.5, "Approved plan", ha="center", va="bottom",
                color=text_color, fontsize=5.8)
        arrow((113, 43), (136, 43))
        ax.text(124.5, 46.5, "Analysis script", ha="center", va="bottom",
                color=text_color, fontsize=5.8)
        arrow((91, 61), (91, 54))
        arrow((91, 32), (91, 22))
        arrow((156, 32), (156, 22))

        paths = []
        for suffix in ("pdf", "svg", "png"):
            path = output_dir / f"library-overview.{suffix}"
            fig.savefig(path, dpi=600)
            paths.append(path)
        plt.close(fig)
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "projects/library-overview")
    args = parser.parse_args()
    print("\n".join(str(path) for path in render(args.output_dir)))
