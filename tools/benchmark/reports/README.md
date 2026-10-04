# Benchmark reports

These builders derive certification figures, the comparison table and supporting summaries
from committed numerical results. The calculations and checked values remain in the library.
Rendered manuscript PDFs, the workflow illustration and manuscript include notes are
preserved in the [public report snapshot](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/reports).
The [complete benchmark snapshot](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark)
also retains historical evaluation reports and generated programs, including unsuccessful
runs and the original limitations.

| Script | Committed inputs | Generated output in this directory |
|---|---|---|
| `fig2_pinning.py` | `../CROSS_TOOLBOX_RESULT.json`, `../cluster_cert/*.json` | `fig2_pinning.pdf` |
| `fig3_levels.py` | `skill_levels.json`, checked against `docs/CERTIFICATION_LEVELS.md` | `fig3_levels.pdf` |
| `tab1_crosstoolbox.py` | `../CROSS_TOOLBOX_RESULT.json`, `../cross_toolbox_results/*.json`, `tools/validation/*_results.json` | `tab1_crosstoolbox.tex` |
| `run_manifest.py` | `../RECIPE_GENERATION_SPECLEVEL.json`, `../RECIPE_GENERATION_RESULT.json`, `../RECIPE_GENERATION_RESULT_MMN_codex.json`, `../OPEN_MODEL_RESULT.json` | `run_manifest.json` |
| `attenuation.py` | `../cross_toolbox_results/*.json`, `tools/validation/*_results.json` | `attenuation.json` |

Paths beginning with `../` are relative to this directory; paths beginning with `docs/` or
`tools/` are relative to the repository root. The builders originated in `paper/figures/`;
the source annotation in `skill_levels.json` retains the former test filename.
Generated PDFs need not be committed to use or validate these builders.

Run an individual builder from the repository root in the documented environment:

```bash
conda run -n aeais python tools/benchmark/reports/fig2_pinning.py
```

This rebuilds a report from committed results; it does not rerun the underlying EEG experiment.
To check the plotted values, table cells, certification map, and generation manifest:

```bash
conda run -n aeais python -m pytest tools/tests/test_benchmark_reports.py tools/tests/test_generation_scoring.py
```

The seven figure and table checks formerly in `test_paper_figures.py` remain in
`test_benchmark_reports.py`, including inspection of the actual plot artists. The library's
full test command also runs these checks.
