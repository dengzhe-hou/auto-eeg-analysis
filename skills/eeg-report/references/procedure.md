## Final JSON and interpretation

Use `tools/check_analysis_outputs.py`'s `write_outputs` on actual computed values
and metadata. It returns the same complete object saved in `result.json`.
Include that object in the final report, with its nonempty `explanation` field.
Do not manually create a shorter JSON after writing the file. Construct channel
counts, sample counts and labels from the selected data, not guessed variables.

Answer the requested interpretation in the saved explanation as well as the
human-readable report. For a hemispheric comparison give each measured
left-minus-right value, its direction and whether directions agree across bands.
For GFP state the requested absolute peak times and saved interval. A methods
description alone does not answer a question about the results. Undefined
quantities and unresolved choices remain explicit; do not invent a conclusion.

The MNE [continuous-plan runner](../../../docs/PRELOADED_SKILLS.md#execute-and-check-a-complete-continuous-plan)
saves `FINAL_SUBMISSION.md` from this same object and runs source-data checks.
When checking an actual final message separately, pass that report to
`check_analysis_outputs.py --report FINAL_SUBMISSION.md`; the parser retains
which fields were present inside its JSON rather than importing nearby prose.

For external semantic review, preserve the saved explanation, final JSON
explanation and complete final submission as separate inputs. The
[review-context builder](../../../tools/prepare_analysis_review.py) prepares
these inputs without calling a model or changing any score. Missing required
structured fields remain objective delivery failures. Plot review should also
receive the checked channel range when channel curves are allowed, not just a
mean that can differ greatly from an actual channel curve. Inspect the actual
image for a disputed rejection; record uncertainty instead of modifying the
scientific output to match a judge.

## Constants

- **HTML_BACKEND = `mne.Report`** — self-contained HTML, embeds all figures/topomaps/PSD.
- **MARKDOWN_BACKEND = custom builder** — concatenates stage reports with figures linked.
- **REPORTING_STANDARD = `COBIDAS-MEEG`** — Pernet et al. 2020, Nature Neuroscience.
- **OUTPUT_DIR = `report-stage/`** — Create if missing.
- **REPRO_RECEIPT = `report-stage/REPRO_RECEIPT.md`**.
- **REPORT_HTML = `report-stage/report.html`**.
- **REPORT_MD = `report-stage/REPORT.md`**.

## Phase A — Collect stage outputs

Use the approved plan and actual execution ledger to identify planned stages
and their required file paths/patterns. Do not infer the analysis design from
which directories happen to exist. Inventory all supported stages, including
spectral, complexity, microstate, QC and behavior, even when not applicable.

```python
# AEA example: report-stage-inventory
import json
import runpy
from pathlib import Path
input_helpers = runpy.run_path(str(Path(AEA_ROOT) / 'skills/eeg-report/scripts/inputs.py'))
stage_inventory = input_helpers['collect_stage_inputs'](
    run_dir, planned_stages=approved_reporting_stages,
    required_sources=recorded_required_stage_sources)
report_dir = Path(run_dir) / 'report-stage'
report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / 'STAGE_INVENTORY.json').write_text(json.dumps(stage_inventory, indent=2))
```

Each planned stage needs explicit actual sources, not a universal
`*_cluster_perm.json` filename. The helper records file names/counts/bytes and
which required patterns match. `available` means input files are present, not
that execution/verification passed; retain actual saved execution/check states.
Unplanned stages are `not_applicable`, even if old directories exist (their
presence is still inventoried). Planned missing sources are `unavailable` and
must be named in an explicitly incomplete/partial report; never claim completion
or fabricate outputs. Report numerical participant/epoch counts from the stage
records, not file count. Core plan, dataset brief and environment provenance are
collected separately from the analysis-stage inventory.

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

### B.5 — Epoching summary (only for a planned event/trial route)

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

For each statistical claim in `ANALYSIS_PLAN.md` (skip this statistical panel
for a purely descriptive workflow):

1. Load the recorded output of that claim's approved test. `stats-stage/<claim_id>_cluster_perm.json` applies only to a cluster-permutation route.
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

### B.7a — Optional deterministic ERP cluster result section

For an already approved **participant-level, one-sided, one-sample ERP cluster test**, `tools/render_statistical_report.py` can check and render a bounded numerical section. It supports arithmetic participant-mean amplitudes with an explicitly approved descriptive two-sided 95% Student t interval. It does not select that estimator or interval for the researcher. If the plan uses another test, tail, estimator or interval, the utility reports `UnsupportedReport`; retain the approved analysis and use the existing reporting route without claiming this check covers it.

Read the [machine-readable input contract](../../../tools/erp_cluster_report.schema.json) when using this route. `eeg-stats` supplies the approved report contract, recorded result fields and participant-level arrays. From the AEA repository root:

```bash
python tools/render_statistical_report.py \
  --contract projects/my-study/stats-stage/C1_report_contract.json \
  --results projects/my-study/stats-stage/C1_report_results.json \
  --arrays projects/my-study/stats-stage/C1_arrays.npz \
  --output-dir projects/my-study/report-stage/C1
```

The utility recomputes the mean, sample SD, SEM and interval from arrays; checks contrast, units, cohort accounting, ROI/window, threshold, recorded cluster p values and permutation counts; and writes `RESULT_STATEMENT.json`, `RESULTS.md` and `REPORT_CHECK.json`. Insert the accepted `RESULTS.md` unchanged into the report's numerical results section. To check an actual exported section, pass it with `--report <result-section.md>`; comparison is exact UTF-8 text. Failed checks keep a failed receipt and must not be presented as accepted results.

A descriptive ROI interval can include zero while a cluster is significant: these concern different statistics. The fixed section reports both without inventing a scalar hypothesis test or a `supports` verdict. General scientific interpretation and the researcher's claim decisions remain outside this automated check. It does not certify the upstream preprocessing, the permutation implementation or the biological conclusion. Other sections of the report remain governed by the existing workflow.

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

### B.7c — Continuous and descriptive analysis sections

For planned spectral/connectivity/complexity/microstate analyses, render their
actual numerical outputs, channel/ROI identities, retained recording duration,
windowing, fitted-template source where relevant, and saved checks. Include the
QC and behavior outputs when those stages were planned. Reuse saved figures;
do not recompute analyses while composing the report. Keep missing planned
stages visible. A descriptive microstate report can be complete without event
epochs, ERP or cluster statistics, and must not imply those stages ran.

### B.8 — COBIDAS self-check section

Generate a checklist for the applicable executed/planned methods. Mark
unplanned trial/ICA/source/statistical items not_applicable; an applicable missing
record remains missing/unavailable. Do not claim compliance from a directory
listing alone (Pernet et al. 2020):

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
