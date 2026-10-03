---
name: eeg-report
description: "Build a self-contained HTML report (mne.Report) and a Markdown summary from all stage outputs: methods, sample, exclusions, per-claim results with figures, full statistical reporting. Use after eeg-stats and eeg-figure complete."
argument-hint: "[project-dir] [— format: html|md|both] [— cobidas: strict|normal]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-report: auto-generate HTML/Markdown report

## Context: $ARGUMENTS

## Constants

- **HTML_BACKEND = `mne.Report`** — self-contained HTML, embeds all figures/topomaps/PSD.
- **MARKDOWN_BACKEND = custom builder** — concatenates stage reports with figures linked.
- **REPORTING_STANDARD = `COBIDAS-MEEG`** — Pernet et al. 2020, Nature Neuroscience.
- **OUTPUT_DIR = `report-stage/`** — Create if missing.
- **REPRO_RECEIPT = `report-stage/REPRO_RECEIPT.md`**.
- **REPORT_HTML = `report-stage/report.html`**.
- **REPORT_MD = `report-stage/REPORT.md`**.

## Required Inputs

Before building the report, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with claim table filled. **Stop if missing or unfrozen.**
2. `DATASET_BRIEF.md` — acquisition parameters, participant info, task description.
3. At least one stage output directory: `preprocess-stage/`, `ica-stage/`, `erp-stage/`, `tfr-stage/`, `stats-stage/`, `figure-stage/`.
4. `FINDINGS.md` — per-claim verdicts from eeg-stats.
5. `ENVIRONMENT.json` — software versions and backend info.
6. `figure-stage/*.svg` and `figure-stage/*.png` — rendered figures from eeg-figure.

Optional:
- `channel_mapping.json` — for reporting channel name conventions.
- `stats-stage/BACKEND_RESOLUTION.md` — backend selection rationale.

## Phase A — Collect stage outputs

Scan the project directory and inventory all available stage outputs:

```python
stages = {
    'dataset': 'DATASET_BRIEF.md',
    'plan': 'ANALYSIS_PLAN.md',
    'environment': 'ENVIRONMENT.json',
    'preprocess': 'preprocess-stage/',
    'ica': 'ica-stage/',
    'epoch': 'epoch-stage/',
    'erp': 'erp-stage/',
    'tfr': 'tfr-stage/',
    'stats': 'stats-stage/',
    'figures': 'figure-stage/',
    'decoding': 'decoding-stage/',
    'connectivity': 'connectivity-stage/',
    'source': 'source-stage/',
    'findings': 'FINDINGS.md',
}
```

For each stage, record:
- Whether it exists.
- File count and total size.
- Key metadata (e.g., N subjects processed, N epochs retained).

Write `report-stage/STAGE_INVENTORY.json`.

## Phase B — Build HTML report via mne.Report

### B.1 — Initialize report

```python
import mne
report = mne.Report(title="EEG Analysis Report", verbose=True)
report.add_html(title="Analysis Overview", html=overview_html, tags=('overview',))
```

### B.2 — Acquisition info section

Extract from `DATASET_BRIEF.md` and render as HTML:

- Recording system (manufacturer, model, serial)
- Sampling rate, online filters, reference
- Number of channels, channel type breakdown (EEG, EOG, EMG, etc.)
- Electrode placement standard (10-20, 10-10, custom)
- Impedance targets
- Task description, trial structure, timing

```python
report.add_html(title="Acquisition", html=acquisition_html, tags=('methods',))
```

### B.3 — Preprocessing summary section

From `preprocess-stage/` logs:

- Resampling (original → target rate)
- Filtering (highpass, lowpass, notch — filter type, order, transition bandwidth)
- Bad channel detection and interpolation (method, N interpolated, which channels)
- Re-referencing (scheme: average, linked mastoid, REST, etc.)
- Artifact rejection criteria

```python
# Embed the preprocessed raw for interactive scrolling
report.add_raw(raw, title="Preprocessed continuous data", psd=True, tags=('preprocess',))
```

### B.4 — ICA results section

From `ica-stage/`:

- ICA method (fastica, infomax, picard), number of components
- Variance explained
- Component classification (brain, eye blink, saccade, heart, muscle, channel noise, other)
- N components rejected, with justification

```python
# Add ICA component maps and properties
report.add_ica(ica, title="ICA decomposition",
               inst=raw,  # or epochs
               picks=range(min(20, ica.n_components_)),
               tags=('ica',))
```

### B.5 — Epoching summary

From `epoch-stage/`:

- Epoch time window (tmin, tmax)
- Baseline correction window and method
- Rejection criteria (peak-to-peak threshold, flat threshold)
- N epochs per condition: created, rejected, retained
- Rejection rate per subject (flag if >30%)

```python
report.add_epochs(epochs, title="Epochs summary", psd=True, tags=('epochs',))
```

### B.6 — ERP/TFR results sections

From `erp-stage/` and `tfr-stage/`:

```python
# Add grand-average evokeds
report.add_evokeds(evokeds, titles=condition_names,
                   noise_cov=None, tags=('erp',))

# Add TFR as custom figures
for fig_path in tfr_figures:
    report.add_image(fig_path, title=fig_title, tags=('tfr',))
```

### B.7 — Statistical results section

For each claim in `ANALYSIS_PLAN.md`:

1. Load `stats-stage/<claim_id>_cluster_perm.json`.
2. Render a summary block:
   - Claim text
   - Test used, N permutations, seed, alpha
   - Cluster p-value, effect size (Cohen's d)
   - Verdict: supports / does_not_support / partial
3. Embed the corresponding figure from `figure-stage/`.
4. Link to the raw arrays file (`stats-stage/<claim_id>_arrays.npz`).

```python
for claim in claims:
    stat_html = render_claim_result(claim)
    report.add_html(title=f"Claim {claim['id']}: {claim['text'][:60]}",
                    html=stat_html, tags=('stats',))
    if claim['figure_path']:
        report.add_image(claim['figure_path'],
                        title=f"Figure for {claim['id']}",
                        tags=('stats', 'figures'))
```

### B.7b — Multiverse / specification-curve robustness panel (optional)

A single frozen pipeline reports one verdict with no sense of how fragile it is. If the upstream stages re-ran the same contrast across a small a-priori fork set, embed a specification-curve panel summarizing robustness across defensible analytic choices.

```python
# multiverse_results: list of dicts, one per fork, each with the analytic
# choices and the resulting effect size / p-value for the SAME contrast.
spec_html = render_specification_curve(
    multiverse_results,
    forks=['highpass', 'reference', 'measure'],  # e.g. {0.1,0.5 Hz}x{average,mastoid}x{mean-amp,peak}
)
report.add_html(title="Multiverse robustness", html=spec_html, tags=('stats', 'robustness'))
```

Report the distribution of effect sizes and p-values across forks and the **fraction of pipelines that support the claim**, not just the frozen pipeline's number. Only **defensible** forks belong in the grid — do not pad it with choices no analyst would make. When the full grid is combinatorially large, sample a representative subset and report robustness over that sample (Bartlett et al. 2025). Frame the result against the documented magnitude of analyst-to-analyst divergence: in EEGManyPipelines, 168 teams analyzing one dataset reached materially divergent conclusions (Trubutschek et al. 2024), so a claim that survives only one fork should be reported as fragile.

- Cite: Clayson, P. E., Baldwin, S. A., & Larson, M. J. (2021). The importance of preprocessing and analytic choices in ERP research: a multiverse perspective. NeuroImage, 245, 118712.
- Cite: Bartlett, J. E., et al. (2025). Sampling the specification space for tractable multiverse EEG analysis. bioRxiv 2025.04.08.647779.
- Cite: Trubutschek, D., et al. (2024). EEGManyPipelines: a large-scale analysis of analytic flexibility in EEG. Journal of Cognitive Neuroscience, 36(2), 217–224.

### B.8 — COBIDAS self-check section

Generate a checklist verifying COBIDAS-MEEG compliance (Pernet et al. 2020):

| Item | Status | Details |
|---|---|---|
| Sample size and exclusions reported | ✅/❌ | N = X enrolled, N = Y analyzed |
| Recording system specified | ✅/❌ | [system name] |
| Sampling rate reported | ✅/❌ | [rate] Hz |
| Filter parameters reported | ✅/❌ | [highpass]-[lowpass] Hz, [type] |
| Reference scheme reported | ✅/❌ | [scheme] |
| Epoch window and baseline reported | ✅/❌ | [tmin, tmax], baseline [bmin, bmax] |
| Artifact rejection criteria reported | ✅/❌ | [criteria] |
| ICA method and N components reported | ✅/❌ | [method], N = [n] |
| Statistical test fully specified | ✅/❌ | [test], N_perm, seed, alpha, tail |
| Effect size reported | ✅/❌ | Cohen's d = [value] |
| Multiple comparisons correction reported | ✅/❌ | [method] |
| Cluster-forming threshold reported | ✅/❌ | t = [value] |
| Channel adjacency definition reported | ✅/❌ | [method] |

```python
cobidas_html = render_cobidas_checklist(stage_inventory)
report.add_html(title="COBIDAS-MEEG Compliance Check",
                html=cobidas_html, tags=('cobidas',))
```

### B.9 — Save HTML report

```python
report.save(str(output_dir / "report.html"), overwrite=True, open_browser=False)
```

## Phase C — Build Markdown report

Generate `report-stage/REPORT.md` with all sections as Markdown:

```markdown
# EEG Analysis Report
Generated: [date]
Project: [project name]

## 1. Acquisition
[from DATASET_BRIEF.md]

## 2. Preprocessing
[from preprocess-stage logs]

## 3. ICA
[from ica-stage logs]

## 4. Epoching
[from epoch-stage logs]

## 5. Results
### Claim C1: [claim text]
- Test: [test name], N_perm = [N], seed = [S], alpha = [α]
- Result: cluster p = [value], Cohen's d = [value]
- Verdict: [supports / does_not_support / partial]
- Figure: ![F1](../figure-stage/F1_name.png)

[repeat for each claim]

## 6. Exploratory
[from FINDINGS.md exploratory section, if any]

## 7. COBIDAS Compliance
[checklist table]
```

## Phase D — Generate REPRO_RECEIPT.md

The reproducibility receipt documents everything needed to reproduce the analysis.

```markdown
# Reproducibility Receipt
Generated: [ISO 8601 timestamp]

## Software Versions
| Package | Version |
|---|---|
| Python | [version] |
| MNE-Python | [version] |
| NumPy | [version] |
| SciPy | [version] |
| matplotlib | [version] |
| scikit-learn | [version] |
| pandas | [version] |

## Git Information
- Repository: [repo URL or local path]
- Commit SHA: [full SHA]
- Branch: [branch name]
- Clean working tree: [yes/no]
- Uncommitted changes: [list if any]

## RNG Seeds
| Stage | Seed |
|---|---|
| ICA | [seed] |
| Cluster permutation | [seed] |
| Cross-validation | [seed] |
| Bootstrap | [seed] |

## Input File Hashes (SHA-256)
| File | SHA-256 |
|---|---|
| ANALYSIS_PLAN.md | [hash] |
| [raw data file 1] | [hash] |
| [raw data file 2] | [hash] |
| ... | ... |

## Output File Hashes (SHA-256)
| File | SHA-256 |
|---|---|
| stats-stage/C1_cluster_perm.json | [hash] |
| figure-stage/F1_name.svg | [hash] |
| report-stage/report.html | [hash] |
| ... | ... |

## Analysis Plan Frozen At
- Timestamp: [mtime of ANALYSIS_PLAN.md]
- SHA-256: [hash]

## Environment
- OS: [os.uname()]
- CPU: [platform.processor()]
- RAM: [total GB]
- GPU: [if used, nvidia-smi output]
- BLAS/threading backend: [MKL | OpenBLAS | ...] (from `numpy.show_config()`), thread count: [OMP_NUM_THREADS / threadpoolctl]
- Environment lockfile: [conda environment.yml export | uv.lock | pip-freeze.txt] (attach alongside the receipt)
- Container image: [Docker/Singularity image + digest, if used] — **the only guarantee of numerical reproducibility**

> **Bit-level reproducibility is NOT guaranteed across OS/BLAS backends without a container.** Single-precision math-library differences (MKL vs OpenBLAS, thread count, OS) accumulate over a long pipeline, so byte-identical code and data can diverge numerically on another machine (Glatard et al. 2015). All results here are **MNE-Python-specific** — re-deriving them in a different package will not reproduce them exactly because cross-package defaults differ (Kabbara et al. 2023).

## BIDS Provenance (if applicable)
- Dataset: [BIDS dataset name]
- BIDS version: [version]
- Derivatives pipeline: [pipeline name and version]
```

### REPRO_RECEIPT generation code

```python
import hashlib, subprocess, json, platform, datetime

receipt = {}

# Git SHA
try:
    receipt['git_sha'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    receipt['git_branch'] = subprocess.check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True).strip()
    receipt['git_clean'] = subprocess.check_output(
        ['git', 'status', '--porcelain'], text=True).strip() == ''
except subprocess.CalledProcessError:
    receipt['git_sha'] = 'NOT_A_GIT_REPO'

# Software versions
import mne, numpy, scipy, matplotlib, sklearn
receipt['versions'] = {
    'python': platform.python_version(),
    'mne': mne.__version__,
    'numpy': numpy.__version__,
    'scipy': scipy.__version__,
    'matplotlib': matplotlib.__version__,
    'sklearn': sklearn.__version__,
}

# File hashes
def sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# Seeds from ANALYSIS_PLAN.md
# Parse and record all RNG seeds

# Numerical-reproducibility provenance: lockfile + BLAS backend
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    numpy.show_config()
receipt['blas_backend'] = buf.getvalue()  # MKL vs OpenBLAS shows here
try:
    import threadpoolctl
    receipt['threadpools'] = threadpoolctl.threadpool_info()
except ImportError:
    pass
# Export a full lockfile next to the receipt (prefer conda/uv over a bare pip freeze)
try:
    receipt['pip_freeze'] = subprocess.check_output(
        ['python', '-m', 'pip', 'freeze'], text=True)
except subprocess.CalledProcessError:
    pass
# Flag that bit-level reproducibility is not guaranteed without a container.
receipt['bitlevel_reproducible_without_container'] = False
```

## Phase E — Sanity checks

All must pass before declaring success:

- [ ] `report-stage/report.html` exists and is >10 KB (not empty/broken).
- [ ] `report-stage/REPORT.md` exists with all sections populated.
- [ ] `report-stage/REPRO_RECEIPT.md` exists with git SHA, seeds, and file hashes.
- [ ] `report-stage/STAGE_INVENTORY.json` exists.
- [ ] Every claim in ANALYSIS_PLAN has a corresponding section in both HTML and MD reports.
- [ ] Every figure referenced in FIGURE_PLAN is embedded in the HTML report.
- [ ] COBIDAS checklist has no ❌ items — or if it does, they are flagged for user attention.
- [ ] REPRO_RECEIPT has no placeholder values (no `[TODO]`, `[FILL]`, etc.).
- [ ] All file hashes in REPRO_RECEIPT are valid SHA-256 (64 hex characters).

## Critical Rules

- **Never** fabricate data or statistics in the report. Every number must trace to a stage output file.
- **Never** omit exclusions or failed subjects — transparency is mandatory.
- **Never** modify ANALYSIS_PLAN.md during report generation.
- **Never** embed raw data files in the HTML report (size risk). Embed only figures and summary statistics.
- **Always** include the COBIDAS checklist — even if some items fail.
- **Always** generate REPRO_RECEIPT.md — it is not optional.
- **Always** record actual seeds used, not planned seeds, by reading from stage output logs.
- **Never** report microstate clinical effect directions (e.g., SCZ → increased C, AD → shortened durations) as a per-subject diagnosis or classifier — present them only as group-level literature context with citations, against published healthy-adult norm bands.

## Domain Knowledge (distilled from reporting methodology literature)

### COBIDAS-MEEG (Pernet et al. 2020, Nature Neuroscience)

The OHBM Committee on Best Practices in Data Analysis and Sharing (COBIDAS) published MEEG-specific guidelines requiring:

- Complete description of recording parameters (system, channels, sampling rate, filters, reference).
- Preprocessing pipeline with exact parameters (filter type, cutoff, order, transition bandwidth).
- Artifact handling: criteria, N rejected, method (manual, automatic, ICA).
- Epoching: time window, baseline, rejection thresholds.
- Statistical analysis: test, implementation, permutations, seed, threshold, adjacency, alpha, tail, effect size.
- The report must enable exact replication by an independent lab.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nature Neuroscience, 23(12), 1473–1483.

### BIDS-style provenance (Gorgolewski et al. 2016, Scientific Data)

- Organize derivatives following BIDS derivatives specification.
- Include `dataset_description.json` with pipeline name, version, and parameters.
- Record provenance: which input files produced which output files.
- Use stable identifiers (file hashes, git SHAs) for traceability.
- The REPRO_RECEIPT serves as a lightweight provenance record when full BIDS derivatives are not used. **It is a provenance record, not a guarantee of numerical reproduction** — see the caveat below.
- Cite: Gorgolewski, K. J., et al. (2016). The brain imaging data structure, a format for organizing and describing outputs of neuroimaging experiments. Scientific Data, 3, 160044.

### Reproducibility in EEG research

- Record all random seeds explicitly — permutation tests, ICA initialization, cross-validation splits.
- Pin software versions in a requirements file or conda environment export.
- Hash input files to detect silent data corruption or version changes.
- A clean git SHA proves the analysis code was version-controlled at execution time.
- If the git working tree was dirty, log the diff for full traceability.

#### Numerical reproducibility across machines (beyond git SHA + version pins)

Git SHA, seeds, file hashes, and a top-level package list pin *what code ran*, but they do **not** guarantee the same numbers on another machine. Single-precision math-library differences across operating systems and BLAS backends (MKL vs OpenBLAS, and thread count) accumulate over a long pipeline, so byte-identical code and data can diverge numerically elsewhere (Glatard et al. 2015). Strengthen the receipt accordingly:

- Capture a **full environment lockfile** (conda `environment.yml` export, or `pip freeze` / `uv.lock`) — not just the handful of top-level packages in the versions table.
- Record the **BLAS/threading backend** (MKL vs OpenBLAS via `numpy.show_config()`, plus the thread count) — it materially affects floating-point results.
- Recommend a **container** (Docker/Singularity image hash) as the only real guarantee of numerical reproducibility, and explicitly flag in the receipt that bit-level reproducibility is **not** guaranteed across OS/BLAS without one.
- Note that all reported numbers are **MNE-Python-specific**: differing cross-package defaults are a known source of non-reproduction, so a re-analysis in a different toolbox will not match exactly (Kabbara et al. 2023).
- Cite: Glatard, T., et al. (2015). Reproducibility of neuroimaging analyses across operating systems. Frontiers in Neuroinformatics, 9, 12.
- Cite: Kabbara, A., et al. (2023). The impact of EEG software/pipeline choice on connectivity results. NeuroImage: Reports, 3, 100169.

### Microstate reporting norms and clinical directions (report only if microstate-stage outputs exist)

When the project contains microstate outputs (`microstate-stage/`), the report should table the four canonical metrics per class (mean duration, occurrence/frequency, time coverage, GEV) and sanity-check them against published healthy-adult norms. Flag — do not silently drop — values outside these bands. The per-class parameters come from `pycrostates` segmentation `.compute_parameters()` outputs; transition structure comes from `pycrostates.segmentation.compute_transition_matrix` / `compute_expected_transition_matrix`.

**Typical healthy-adult values (eyes-closed resting EEG, canonical 4-map solution A/B/C/D):**

| Metric | Typical range / value | Note |
|---|---|---|
| Mean duration (per class) | 80–120 ms | Khanna 2014 lifespans ≈94–102 ms for A–D; the wider 40–200 ms band is a hard plausibility bound, not a norm |
| Occurrence (per class) | ~2–6 /s | Khanna: A≈2.3, B≈2.5, C≈2.65, D≈2.6 /s |
| Total occurrence (all classes) | ~10 /s | Sum across the four maps |
| Time coverage | A≈21%, B≈25%, C≈27%, D≈27% | Sums to ~100%; report as a split, not just per-class |
| Global Explained Variance (GEV) | ~70% for K=4 | If a 4-map solution explains far less, the segmentation or map quality is suspect |
| Duration vs. frequency | R≈−0.72 | Duration and occurrence are inversely correlated; both increasing together is a red flag |

**Known clinical effect directions** (report descriptively for context only — do not infer diagnosis):

- **Schizophrenia:** increased class C occurrence/coverage; shortened class D (and class B) duration; altered A→D transition syntax (Khanna 2015 Table 1; Rieger 2016 meta-analysis).
- **Frontotemporal dementia:** shortened class C.
- **Alzheimer's disease:** globally shortened durations (notably class D).
- **Panic disorder:** longer class A, reduced class C. **Tourette syndrome:** more frequent class A.

These directions are study-level associations with substantial overlap with healthy controls; the report must frame them as literature context, never as a per-subject classifier.

- Cite: Koenig, T., et al. (2002). Millisecond by millisecond, year by year: normative EEG microstates and developmental stages. NeuroImage, 16, 41–48.
- Cite: Khanna, A., Pascual-Leone, A., Michel, C. M., & Farzan, F. (2014/2015). Microstates in resting-state EEG: current status and future directions. Neuroscience & Biobehavioral Reviews, 49, 105–113.
- Cite: Rieger, K., Diaz Hernandez, L., Baenninger, A., & Koenig, T. (2016). 15 years of microstate research in schizophrenia — where are we? A meta-analysis. Frontiers in Psychiatry, 7, 22.

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing | Stop. Cannot build report without the analysis plan. |
| No stage outputs found | Stop. At least one analysis stage must have run. |
| FINDINGS.md missing | Warn. Build report without verdict section, flag for user. |
| Figure files missing | Warn. Build report with placeholder "[Figure not yet rendered]". |
| ENVIRONMENT.json missing | Warn. Collect versions at report-generation time instead. |
| HTML report >100 MB | Reduce embedded figure resolution or link instead of embed. |
| Git not available | Record "NOT_A_GIT_REPO" in REPRO_RECEIPT. Continue. |
| Microstate metric outside norm band (duration <40 or >200 ms, GEV ≪70% for K=4, duration and occurrence both rising) | Report the value but annotate it as "outside published healthy-adult range" with the expected band; do not drop or clip silently. |
| Microstate coverage does not sum to ~100% | Flag in the report — indicates a backfitting/labeling error upstream, not a reportable result. |
| Microstate clinical interpretation requested per subject | Refuse. Report group-level effect directions as literature context only; never assign a diagnosis or per-subject label. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `DATASET_BRIEF.md`, `FINDINGS.md`, `ENVIRONMENT.json`, all `*-stage/` directories, `figure-stage/*.svg`, `figure-stage/*.png`, `channel_mapping.json`
- Outputs: `report-stage/report.html`, `report-stage/REPORT.md`, `report-stage/REPRO_RECEIPT.md`, `report-stage/STAGE_INVENTORY.json`
- Previous: `eeg-stats` and `eeg-figure` must complete before report generation.
- Next: `eeg-audit` verifies report completeness. `eeg-methods-text` may draw from the report for manuscript methods section.
