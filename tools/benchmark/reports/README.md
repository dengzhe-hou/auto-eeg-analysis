# Benchmark reports

These scripts and committed outputs are the canonical sources for the AEA manuscript's
certification figures, comparison table, and supporting summaries. They were relocated from
`paper/figures/` without changing the numerical calculations or plotted values. The local
manuscript keeps relative symlinks at its original figure paths.

| Script | Committed inputs | Output in this directory |
|---|---|---|
| `fig1_chain.py` | Certification workflow encoded in the script | `fig1_chain.pdf` |
| `fig2_pinning.py` | `../CROSS_TOOLBOX_RESULT.json`, `../cluster_cert/*.json` | `fig2_pinning.pdf` |
| `fig3_levels.py` | `skill_levels.json`, checked against `docs/CERTIFICATION_LEVELS.md` | `fig3_levels.pdf` |
| `tab1_crosstoolbox.py` | `../CROSS_TOOLBOX_RESULT.json`, `../cross_toolbox_results/*.json`, `tools/validation/*_results.json` | `tab1_crosstoolbox.tex` |
| `run_manifest.py` | `../RECIPE_GENERATION_SPECLEVEL.json`, `../RECIPE_GENERATION_RESULT.json`, `../RECIPE_GENERATION_RESULT_MMN_codex.json`, `../OPEN_MODEL_RESULT.json` | `run_manifest.json` |
| `attenuation.py` | `../cross_toolbox_results/*.json`, `tools/validation/*_results.json` | `attenuation.json` |

Paths beginning with `../` are relative to this directory; paths beginning with `docs/` or
`tools/` are relative to the repository root. `latex_includes.tex` records the manuscript's
figure and table include paths as comments. The archived JSON, PDF, and TeX files are unchanged by this move;
the source annotation in `skill_levels.json` therefore retains the former test filename.

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
