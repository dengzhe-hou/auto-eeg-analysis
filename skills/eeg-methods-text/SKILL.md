---
name: eeg-methods-text
description: "Auto-generate a submission-ready EEG methods paragraph that satisfies the COBIDAS-MEEG checklist (Pernet et al. 2020). Reads DATASET_BRIEF.md, every stage's BACKEND_RESOLUTION.md and *_summary.json, ANALYSIS_PLAN.md, and stats-stage outputs to produce a paragraph users can paste into their paper. Reviewers love it. Authors love it more. Use when the user says \"write methods\", \"generate methods text\", \"COBIDAS paragraph\", or after the pipeline finishes."
argument-hint: "[project-dir] [— venue: NeurIPS|JNeurosci|NeuroImage|FrontiersHumanNeuro|CerebralCortex|generic] [— format: md|tex|both] [— bibtex]"
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# eeg-methods-text: COBIDAS-MEEG methods paragraph generator

A truly novel skill: no existing EEG pipeline emits a methods paragraph. Authors copy-paste from past papers and miss details that reviewers catch.

## Context: $ARGUMENTS

## Constants

- **CHECKLIST = `COBIDAS-MEEG`** (Pernet et al. 2020, "Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research").
- **VENUE_DEFAULT = `generic`** — paragraph adapts to venue style (NeurIPS more terse, JNeurosci more detailed, etc.).
- **OUTPUT_MD = `report-stage/methods.md`**.
- **OUTPUT_TEX = `report-stage/methods.tex`** (LaTeX-ready).
- **OUTPUT_BIB = `report-stage/methods_references.bib`** (auto-collected BibTeX).
- **OUTPUT_ARTEMIS = `report-stage/methods_artemis.json`** (machine-readable structured methods, ARTEM-IS schema).
- **OUTPUT_DEVIATIONS = `report-stage/preregistration_deviations.md`** (executed-vs-planned diff).

## What goes into the paragraph

The COBIDAS-MEEG checklist's required EEG reporting items, gathered from the project's own logs (no manual input needed):

### Sample (from DATASET_BRIEF.md + epoch-stage exclusion log)
- N enrolled, N analyzed, N excluded with reasons.
- Demographics (age, handedness, sex if reported).

### Acquisition (from DATASET_BRIEF.md)
- System, channel count + montage, online filter, sampling rate, online reference.

### Preprocessing (from preprocess-stage/preprocess_summary.json + BACKEND_RESOLUTION.md)
- Backend + version (MNE 1.7.1).
- Bandpass (l_freq, h_freq, filter type, zero-phase y/n).
- Notch frequencies.
- Resample (if applied).
- Reference scheme.
- Bad-channel detection rule + tool version + seed.
- Bad channels per subject (mean, range).

### ICA (from ica-stage/ica_summary.json)
- Method (extended Infomax, etc.), n_components, seed.
- Pre-fit HP filter cutoff (best-practice 1 Hz copy).
- Auto-labeling tool + version (mne-icalabel 0.6).
- Component classes rejected, mean count per subject.
- Subjects with manual review.

### Epoching (from epoch-stage)
- Window, baseline, AR mode, AR tool version, seed.
- Min trials per condition rule and subjects excluded.

### Statistics (from stats-stage/*_cluster_perm.json + ANALYSIS_PLAN.md)
- Per claim: contrast, channels/ROI, time/freq window, test, n_permutations, RNG seed, cluster-forming threshold, adjacency definition, alpha.
- Multiple-comparisons strategy across claims.
- Effect-size metric (Cohen's dz / partial eta²).

### Source analysis (from source-stage/source_summary.json, if a source-localization stage ran)
- Head/forward model: BEM (n layers) or template (fsaverage), conductivities, and how the source space was built (surface oct6 / volumetric grid spacing).
- Inverse method (dSPM / sLORETA / eLORETA / MNE / LCMV beamformer) and the regularization actually used: `lambda2 = 1 / SNR**2` (state the assumed SNR, default SNR=3 → lambda2≈0.111) for minimum-norm methods, or the noise-covariance regularization for beamformers.
- Noise-covariance and (for beamformers) data-covariance estimation windows, the estimator, and rank handling.
- Whether individual source estimates were morphed to a common template (fsaverage) before group statistics / display.
- Atlas used to name peaks/clusters (Desikan-Killiany or Destrieux via `read_labels_from_annot`, or AAL for volumetric STCs) and the reported coordinate system (MNI).

### Reporting standard
- Cluster-level p, t_obs sum, channels involved, time window, peak channel/time, effect size.

## Phases

### A. Gather

Read every required source. If anything is missing, stop and tell the user *what file* needs to exist.

Required files:
- `DATASET_BRIEF.md`
- `ANALYSIS_PLAN.md`
- `preprocess-stage/preprocess_summary.json`
- `preprocess-stage/BACKEND_RESOLUTION.md`
- `ica-stage/ica_summary.json`
- `ica-stage/BACKEND_RESOLUTION.md`
- `epoch-stage/epoch_summary.json`
- `epoch-stage/BACKEND_RESOLUTION.md`
- `stats-stage/*_cluster_perm.json`
- `stats-stage/BACKEND_RESOLUTION.md`
- `ENVIRONMENT.json`

### B. COBIDAS checklist auto-audit

Before composing the paragraph, run through the full COBIDAS-MEEG checklist and flag any items that cannot be filled from the gathered data. This catches gaps BEFORE output rather than after.

**COBIDAS-MEEG Required Items Checklist**:

| # | Item | Source file | Status |
|---|------|------------|--------|
| 1 | Sample size (enrolled, analyzed, excluded) | DATASET_BRIEF + epoch exclusion | |
| 2 | Demographics (age, sex, handedness) | DATASET_BRIEF | |
| 3 | Acquisition system + model | DATASET_BRIEF | |
| 4 | Channel count + montage name | DATASET_BRIEF | |
| 5 | Online reference | DATASET_BRIEF | |
| 6 | Online filter settings | DATASET_BRIEF | |
| 7 | Sampling rate | DATASET_BRIEF | |
| 8 | Offline bandpass (type, cutoffs, zero-phase) | preprocess_summary | |
| 9 | Notch filter (frequencies) | preprocess_summary | |
| 10 | Re-reference scheme | preprocess_summary | |
| 11 | Bad-channel method + tool version | preprocess_summary | |
| 12 | Bad-channel stats (mean, range) | preprocess_summary | |
| 13 | ICA method + n_components + seed | ica_summary | |
| 14 | ICA pre-fit HP cutoff | ica_summary | |
| 15 | Auto-label tool + version | ica_summary | |
| 16 | Rejected component classes + mean count | ica_summary | |
| 17 | Epoch window + baseline | epoch_summary | |
| 18 | Artifact rejection method + tool version | epoch_summary | |
| 19 | Min trial rule + exclusions | epoch_summary | |
| 20 | Statistical test + implementation | stats JSON | |
| 21 | N permutations + seed | stats JSON | |
| 22 | Cluster-forming threshold derivation | stats JSON | |
| 23 | Adjacency definition | stats JSON | |
| 24 | Alpha + MC correction | stats JSON | |
| 25 | Effect size metric + formula | stats JSON | |
| 26 | Tail + justification | stats JSON | |
| 27 | Source head/forward model (BEM or template) | source_summary | |
| 28 | Inverse method + lambda2/SNR or beamformer reg | source_summary | |
| 29 | Noise (and data) covariance windows | source_summary | |
| 30 | Morph-to-fsaverage before group/display | source_summary | |
| 31 | Atlas for labeling + coordinate system (MNI) | source_summary | |

Rows 27-31 are **conditional**: skip them (mark `n/a`, not `missing`) when no source-stage ran. Only treat them as `unavailable` if `ANALYSIS_PLAN.md` declares a source-localization claim but `source-stage/source_summary.json` is absent.

For each item:
- `filled` — value extracted successfully.
- `missing` — source file exists but field not found. Flag as warning.
- `unavailable` — source file missing entirely. Flag as error.

If any item is `unavailable`, **stop and tell the user which stage needs to run first**.
If items are `missing`, proceed but include warnings in the self-check output.

### C. Resolve venue style

Each venue has specific word count targets and style expectations:

| Venue | Target words | Style notes |
|---|---|---|
| `NeurIPS` | ~200 | Terse. Defer preprocessing details to supplementary. Focus on statistical approach. No subheadings in methods. |
| `ICML` / `ICLR` | ~200 | Similar to NeurIPS. Emphasize reproducibility via code/data availability statement. |
| `JNeurosci` | ~500 | Full detail required. Reviewers expect every COBIDAS item. Subheadings encouraged. |
| `NeuroImage` | ~400 | Moderate detail. COBIDAS compliance expected. Include software versions inline. |
| `Cerebral Cortex` | ~400 | Similar to NeuroImage. Emphasize effect sizes and power considerations. |
| `FrontiersHumanNeuro` | ~400 | Standard with reproducibility emphasis. Include data/code availability. |
| `generic` | ~300–400 | Paragraph form, covers all COBIDAS items. Default when no venue specified. |

When venue is `NeurIPS` or `ICML`/`ICLR`:
- Main methods: acquisition system, key preprocessing steps (1 sentence), statistical test + parameters.
- Generate a separate `report-stage/methods_supplementary.md` with full COBIDAS detail for appendix.

### D. Compose

Build the paragraph by template-interpolating values into the COBIDAS structure:

1. **Markdown output** (`report-stage/methods.md`):
   - Structured prose following venue style.
   - All numerical values interpolated from stage JSONs.
   - Verify every `<placeholder>` is resolved before outputting; if any unresolved, abort.

2. **LaTeX output** (`report-stage/methods.tex`):
   - Proper LaTeX formatting: `\textit{}` for software names, `\SI{}{}` for units (if siunitx available).
   - Citation commands using `\citep{}` / `\citet{}` with keys from BibTeX file.
   - Escape special characters (`%`, `&`, `_`, `#`, `$`).
   - Wrap in `\subsection{EEG Recording and Analysis}` or appropriate venue section command.
   - Example:
     ```latex
     \subsection{EEG Recording and Analysis}
     EEG was recorded from \num{64} Ag/AgCl electrodes arranged in the
     international 10--20 system (actiCHamp Plus, Brain Products GmbH)
     at a sampling rate of \SI{512}{\hertz}, referenced online to FCz.
     ...
     ```

3. **Machine-readable ARTEM-IS artifact** (`report-stage/methods_artemis.json`):
   - Every field already harvested for the COBIDAS prose (montage, online/offline filters, epoch window, baseline, ICA settings, component-measurement window, stats parameters) is also serialized into an ARTEM-IS-shaped JSON. The COBIDAS paragraph is a human-readable prose checklist; the ARTEM-IS JSON is the complementary structured schema that makes a reported methods section cross-study searchable and machine-diffable. Emit both from the same interpolation pass so the prose and JSON never drift apart.
   - Cite: Šoškić et al. (2025), Psychophysiology e70187 (ARTEM-IS structured EEG-methods schema).

4. **Preregistration-deviation section** (`report-stage/preregistration_deviations.md`):
   - Because AEA freezes and timestamps `ANALYSIS_PLAN.md`, that file functions as a de-facto preregistration. Diff the executed analysis (the stage `*_summary.json` values actually used) against the frozen plan and enumerate every decision that is NOT in the plan — an added covariate, a changed time/ROI window, an extra exclusion criterion, a swapped test. Label each such decision exploratory/post-hoc in the output. Hand-written methods sections systematically omit these silent departures; surfacing them is what keeps the confirmatory/exploratory line honest.
   - Cite: Paul, Govaart & Schettino (2021), Int. J. Psychophysiol. 164:52 (reporting preregistration deviations).

5. **Source-analysis sentence template** (emit only if a source-stage ran):
   > "Cortical sources were estimated using {{method}} with the inverse operator regularized at lambda2 = 1/SNR^2 (assumed SNR = {{snr}}; lambda2 = {{lambda2}}). The forward model used a {{n_layer}}-layer BEM (conductivities {{cond}}) / the fsaverage template, with the noise covariance estimated from the {{noise_cov_window}} interval. Individual source estimates were morphed to fsaverage before group analysis. Peaks were labeled using the {{atlas}} atlas and are reported in MNI coordinates."
   For an LCMV beamformer, replace the lambda2 clause with the data-covariance window and the covariance regularization (e.g. `reg=0.05`).

6. **ERP group-statistics sentence template** — state which of the two routes was used so the paragraph is internally consistent with the stats stage:
   - Hypothesis-driven (a-priori ROI + window): "Mean amplitude was averaged over {{roi_channels}} in the {{tmin}}-{{tmax}} ms window (or peak latency/amplitude extracted with `Evoked.get_peak(mode='{{mode}}', tmin, tmax)`) per participant and entered into a single {{test}}; no mass-univariate correction was required."
   - Data-driven 'when'/'where': defer to the cluster-permutation sentence already emitted from the stats stage, and say the time window/channel set was determined data-drivenly rather than pre-specified (so cluster boundaries are NOT interpreted as effect onset/offset — see Sassenhagen & Draschkow 2019).
   Prefer reporting **mean amplitude** over peak amplitude for noise robustness, and state that the window was pre-registered when the route is hypothesis-driven.

### E. Automatic BibTeX collection

Scan all stage `BACKEND_RESOLUTION.md` files and the tools used. Collect BibTeX entries for every software and method referenced:

**Core entries to always include**:
- MNE-Python: Gramfort et al. (2013), Frontiers in Neuroscience
- COBIDAS-MEEG: Pernet et al. (2020), Nature Neuroscience

**Conditional entries** (include only if used):
- autoreject: Jas et al. (2017), NeuroImage
- mne-icalabel: Li et al. (2022), Journal of Open Source Software
- MNE-BIDS: Appelhoff et al. (2019), JOSS
- ICLabel: Pion-Tonachini et al. (2019), NeuroImage
- LIMO EEG: Pernet et al. (2011), Computational Intelligence and Neuroscience
- Cluster permutation methodology: Maris & Oostenveld (2007), Journal of Neuroscience Methods
- FDR control: Benjamini & Hochberg (1995), JRSS-B; Genovese et al. (2002), NeuroImage (cite when `mne.stats.fdr_correction` was used).
- SciPy (cluster-forming threshold via `scipy.stats.t.ppf` / `f.ppf`): Virtanen et al. (2020), Nature Methods.
- Source localization: Hämäläinen & Ilmoniemi (1994), Med Biol Eng Comput (MNE); Dale et al. (2000), Neuron (dSPM); Van Veen et al. (1997), IEEE TBME (LCMV beamformer) — include only the one(s) matching the inverse method in source_summary.
- Atlas for source labeling: Desikan et al. (2006), NeuroImage (Desikan-Killiany) or Tzourio-Mazoyer et al. (2002), NeuroImage (AAL).
- ERP technique reference: Luck (2014), An Introduction to the ERP Technique, MIT Press; Chaumon et al. (2015), J Neurosci Methods (ICA artifact handling).
- Microstates: Koenig et al. (2002) / Michel & Koenig (2018), NeuroImage (cite when a microstate stage ran).
- Structured machine-readable methods: Šoškić et al. (2025), Psychophysiology e70187 (ARTEM-IS) — include when the ARTEM-IS JSON is emitted.
- Preregistration-deviation reporting: Paul, Govaart & Schettino (2021), Int. J. Psychophysiol. 164:52 — include when a deviation section is emitted.

Write collected entries to `report-stage/methods_references.bib`.

If running on a recipe, also include the recipe's own `citation.bib` entries.

### F. Output + self-check

Write output files, then append the COBIDAS self-check:

```markdown
# COBIDAS-MEEG self-check

filled  Sample size + exclusions reported
filled  Acquisition system + montage + online filter + reference declared
filled  Preprocessing: bandpass, notch, resample, re-reference, bad-channel rule
filled  ICA: method, n_components, seed, auto-label tool, rejected classes
filled  Epoching: window, baseline, AR tool, seed, min-trial rule
filled  Statistics per claim: contrast, channels, window, test, perms, seed, threshold, adjacency, MC strategy
filled  Reporting standard: cluster p, t_obs, channels, time, effect size
warning Issue: <if any check could not be filled from logs, list here>
```

Use `filled` / `missing` / `unavailable` status markers (no emoji — plain text labels).

### G. Cross-reference suggestions

- Suggest BibTeX entries to cite for each method (mne-python, autoreject, mne-icalabel, COBIDAS guideline).
- If running on a recipe, append the recipe's reference papers to suggest citations.
- Print a "Suggested citations" summary to the user listing what to cite and why.

## Critical Rules

- **Never** write "significant" next to an uncorrected mass-univariate p < 0.05 map. Every cluster/point reported as significant must carry its multiple-comparison method (cluster permutation, FDR, or Bonferroni) in the same sentence.
- **Never** report a cluster's temporal/spatial extent as the effect's onset, offset, or peak location (Sassenhagen & Draschkow 2019); the methods text must phrase cluster bounds as "a cluster spanning ...", not "the effect began at ...".
- **Never** state a cluster-forming threshold as a bare number (e.g. "t = 2.0") without its derivation; report it as the critical t at the chosen alpha and design df (`scipy.stats.t.ppf(1 - alpha/2, df)`, two-tailed) or note `threshold=None` (MNE default) explicitly.
- **Never** invent demographics, filter cutoffs, or trial counts to fill a `missing` checklist item; emit "not recorded" and warn in the self-check.
- **Never** fabricate a citation. Only emit BibTeX for tools/methods actually present in a stage `BACKEND_RESOLUTION.md`.
- Always report **retained trial counts per condition** (mean and range across subjects), since ERP/TFR SNR scales with sqrt(n_trials); a paragraph that reports rejection percentage but not surviving counts is incomplete.

## Domain Knowledge

### Pernet et al. 2020: COBIDAS-MEEG checklist
- The Committee on Best Practices in Data Analysis and Sharing (COBIDAS) for MEEG provides a comprehensive checklist for reproducible EEG/MEG research.
- Key principle: every analysis decision must be reported with enough detail that an independent researcher can reproduce the results.
- The checklist covers: participants, task, acquisition, preprocessing, time-domain analysis, frequency-domain analysis, source analysis, statistics, and data sharing.
- Common reviewer complaints addressed by COBIDAS: missing filter specifications, unclear re-referencing, unreported artifact rejection criteria, missing effect sizes.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee. Nature Neuroscience, 23, 1473–1483.

### What reviewers look for in EEG methods sections
- **Filter specs**: Reviewers at JNeurosci and NeuroImage specifically check for filter type (FIR/IIR), order, zero-phase vs causal, and transition bandwidth. "Bandpass filtered 0.1–30 Hz" without these details will trigger a revision request.
- **ICA details**: Number of components, algorithm, seed, and automatic vs manual labeling. Reviewers want to know how many components were rejected and by what criteria.
- **Statistical robustness**: Permutation count (< 1000 raises eyebrows), seed for reproducibility, cluster-forming threshold justification (not just "p < 0.05"), adjacency definition.
- **Effect sizes**: Mandatory at most venues since ~2020. Cohen's d or dz for t-tests, partial eta-squared for ANOVAs. Reviewers reject "significant" without effect size.
- **Software versions**: Exact version numbers, not just "MNE-Python". Pin to the version used.
- **Sample size justification**: Increasingly expected. Power analysis or reference to similar published studies.

### Common methods section mistakes (from reviewer perspective)
1. Reporting cluster boundaries as precise effect onset/offset (Sassenhagen & Draschkow 2019).
2. Not reporting online reference electrode.
3. Saying "artifact rejection" without specifying threshold, method, or percentage rejected.
4. Using ANOVA on ERP amplitudes without acknowledging sphericity violations.
5. Not reporting whether filters were applied before or after epoching.
6. Missing the distinction between online and offline reference.

### Multiple-comparison policy to verbalize (Bonferroni vs FDR vs cluster permutation)
- Three corrections, three control targets: **Bonferroni** controls FWER but is over-conservative for autocorrelated EEG time/frequency points — reserve it for a small, pre-specified set of channels/windows. **FDR** (Benjamini-Hochberg, `mne.stats.fdr_correction(pvals, alpha=0.05, method='indep')`) controls the false-discovery rate and is the lightweight default for sparse/non-contiguous point tests. **Cluster-based permutation** (Maris & Oostenveld 2007) is the EEG default when the effect is contiguous in time/space/frequency, and is itself nonparametric (distribution-free inference + MC control in one step).
- The methods paragraph must name which one was used and what it controls; "corrected for multiple comparisons" alone is not COBIDAS-compliant.
- Flag tiny-N group analyses (n < ~12) as underpowered in the self-check; do not silently omit the correction the way demo notebooks sometimes do for small N.
- Cite: Maris & Oostenveld (2007), J Neurosci Methods 164:177-190; Benjamini & Hochberg (1995), JRSS-B 57:289-300; Genovese et al. (2002), NeuroImage 15:870-878.

### Deriving and reporting the cluster-forming threshold
- The cluster-forming t-threshold is the critical t at the chosen alpha and the design-specific df, not a generic 2.0: `threshold = scipy.stats.t.ppf(1 - alpha/2, df)` for a two-tailed test (note the alpha/2), with df = n_subjects-1 for a within-subject/paired design and df = nA+nB-2 for an independent-samples design. For F-based (ANOVA) cluster tests use `scipy.stats.f.ppf(1 - alpha, dfn, dfd)`.
- `threshold=None` lets MNE pick a default, but to *report* a specific cluster-forming alpha the threshold must be derived from df. The methods text should state both the alpha and the resulting t (or that the TFCE / hat-variance default was used).

### Reporting retained trials and the correction-over-rejection principle
- ERP/TFR averaging cancels random noise and reveals the time- and phase-locked signal; SNR scales with sqrt(n_trials), so trial count is a first-class methods item. Report retained trials per condition (mean + range across subjects), not just the rejection percentage.
- Best practice is **correction over rejection**: stereotyped artifacts (blinks, saccades, line noise) are corrected with ICA to preserve trial count, and trial rejection is reserved for non-correctable segments (movement, swallowing, channel pops). The methods text should make this division explicit, and over-aggressive IC removal is itself a reviewer flag because it can erase evoked signal (Chaumon et al. 2015).
- Cite: Luck (2014), An Introduction to the ERP Technique, 2nd ed.; Chaumon, Bishop & Busch (2015), J Neurosci Methods 250:47-63.

### Microstate methods boilerplate and healthy-adult norms (if a microstate stage ran)
- Report: clustering method (modified k-means / AAHC), number of maps K and the GEV they explain, fitting/backfitting with polarity ignored, and the temporal-smoothing window. State the per-class metrics reported: mean duration, occurrence/coverage, and transition probabilities.
- Healthy-adult sanity bands to sanity-check (not to assert) outputs: mean duration ~80-120 ms per class, occurrence ~2-6 /s per class (~10 /s total), coverage roughly A~21% / B~25% / C~27% / D~27%, and K=4 canonical maps explaining ~70% GEV; duration and frequency are inversely correlated (R~-0.72).
- Cite: Koenig et al. (2002), NeuroImage 16:41-48; Khanna et al. (2015), Neuroscience & Biobehavioral Reviews, 49, 105–113; Michel & Koenig (2018), NeuroImage 180:577-593.

## Failure modes

| Symptom | Action |
|---|---|
| Stage `*_summary.json` missing | Stop. Tell the user which stage didn't complete. |
| `ANALYSIS_PLAN.md` empty | Stop. Methods text without a stat plan is meaningless. |
| Backend version unknown | Re-run env probe; if still unknown, note "version not recorded" in the paragraph and the self-check warns. |
| Venue not recognized | Default to `generic`. Warn user. |
| LaTeX compilation fails | Output `.tex` anyway; note that user may need to adjust packages (siunitx, etc.). |
| BibTeX key collision | Append suffix (`_a`, `_b`) to disambiguate. |
| `ANALYSIS_PLAN.md` declares a source-localization claim but no `source-stage/source_summary.json` | Stop. The source rows (27-31) are `unavailable`; tell the user to run the source stage. |
| Cluster-forming threshold reported in stats JSON as a bare number with no df/alpha | Recompute the intended threshold note as `t = scipy.stats.t.ppf(1-alpha/2, df)`; if df is unknown, write "cluster-forming threshold = MNE default (threshold=None)" and warn. |
| Stats JSON reports a p-value but no multiple-comparison method | Do NOT write "significant". Emit "uncorrected" with a self-check warning, and refuse to label it significant. |
| Trial counts per condition absent from epoch_summary | Report rejection percentage only, flag retained-trials as `missing`, and warn that SNR cannot be assessed. |
| Group n < ~12 for a between/within-subject test | Proceed but add an "underpowered (n < 12)" warning to the self-check. |

## Cross-references

- Reads: `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`, every stage's `*_summary.json` + `BACKEND_RESOLUTION.md`, `stats-stage/*_cluster_perm.json`.
- Writes: `report-stage/methods.md`, `report-stage/methods.tex`, `report-stage/methods_references.bib`, `report-stage/methods_artemis.json` (structured ARTEM-IS methods), `report-stage/preregistration_deviations.md` (executed-vs-planned diff), optionally `report-stage/methods_supplementary.md`.
- Auditor (`eeg-audit`) verifies that every claim in the methods paragraph traces back to a `stats-stage` artifact.
