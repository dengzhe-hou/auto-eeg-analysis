---
name: eeg-erp
description: "Compute ERPs (evoked responses) per condition per subject; export grand averages, GFP (global field power), difference waves, and per-condition .fif evoked files for the figure and stats stages. Measures component amplitudes and latencies per ANALYSIS_PLAN. Reads epoch-stage/ output. Use when user says 'compute ERPs', 'average epochs', 'ERP components', or after epoch-stage completes."
argument-hint: "[project-dir] [— conditions: valid,invalid] [— measure: mean_amp|peak|area_latency] [— components: N1,P3b,N400]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-erp: epochs → evoked

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **CONDITIONS = read from ANALYSIS_PLAN claim rows** (the contrasts to be tested).
- **METHOD = `mean`** (vs `median` — use median if user has high outlier rate even after AR).
- **GFP = always computed** (paper-required for many ERP papers).
- **MEASURE = `mean_amp`** — Default component measurement. Override: `— measure: peak` or `— measure: area_latency`.
- **OUTPUT_DIR = `erp-stage/`** — Create if missing.

> Override: `/eeg-erp projects/my-study — conditions: target,standard — measure: mean_amp — components: N1,P3b`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with claim table filled. **Stop if missing or unfrozen.**
2. `epoch-stage/` — cleaned epochs per subject (`.fif` or `.set`).
3. `ENVIRONMENT.json` — to resolve backend.
4. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.

## Phase A — Parse conditions and components

1. Read ANALYSIS_PLAN claim table. Extract all unique conditions from the `contrast` column.
2. For each claim, extract the target ERP component (e.g., N1, P3b, N400) and its expected:
   - Time window (e.g., 80–150 ms for N1)
   - ROI channels (e.g., Fz, Cz for N1)
   - Direction (negative for N-components, positive for P-components)
3. Resolve ROI channels via `channel_mapping.json` if needed. **Stop and ask** if mapping is missing.
4. Write `erp-stage/ERP_PLAN.json` summarizing conditions, components, and measurement parameters.

## Phase B — Backend resolution

```
1. Read ENVIRONMENT.json
2. Verify MNE-Python is available → generate MNE-Python code
3. Else → ERROR: MNE-Python required
```

Write `erp-stage/BACKEND_RESOLUTION.md`.

## Phase C — Per-subject averaging

For each subject + each condition:

### MNE-Python path (default)

```python
import mne
import numpy as np

# Load cleaned epochs
epochs = mne.read_epochs(f'epoch-stage/{sub}/{sub}-epo.fif')

# Average per condition
for cond in conditions:
    evoked = epochs[cond].average()  # method='mean' by default
    evoked.save(f'erp-stage/{sub}/{sub}-{cond}-ave.fif', overwrite=True)

# Difference wave (condition_A minus condition_B per claim contrast)
diff = mne.combine_evoked([evoked_A, evoked_B], weights=[1, -1])
diff.save(f'erp-stage/{sub}/{sub}-diff_{contrast_name}-ave.fif', overwrite=True)
```

### Report retained trial counts (always)

ERP SNR scales with the square root of trial count, so per-condition trial counts are a first-class result, not an afterthought. Record them alongside every evoked file and flag imbalance.

```python
# Per-condition retained-trial counts (after AR/ICA cleaning)
n_trials = {cond: len(epochs[cond]) for cond in conditions}
# evoked.nave is the authoritative count actually averaged (respects drops/equalization)
for cond in conditions:
    print(cond, 'n_trials =', epochs[cond].average().nave)
```

- **Correction over rejection**: prefer ICA correction of *stereotyped* artifacts (blinks, saccades, line noise) so trials survive, and reserve trial *rejection* for non-correctable segments (gross movement, swallowing, muscle bursts). Over-aggressive IC rejection removes neural signal and can erase part of the ERP (Chaumon et al. 2015) — see `eeg-ica`.
- If trial counts differ across the conditions in a contrast, the difference wave is biased toward the noisier (lower-n) condition. Either equalize with `epochs.equalize_event_counts([...])` before averaging, or report the imbalance and confirm the effect survives it.
- Write per-condition `nave` into `ERP_PLAN.json` and surface it in `FINDINGS.md`.

### Standardized Measurement Error (SME) — quantitative per-subject data quality

Trial count alone is a coarse proxy; the SME is the actual standard error of the score you report, computed per subject, per condition, *per score*. For **mean amplitude** it has a closed form: the SD of the single-trial mean-amplitude values divided by `sqrt(n_trials)`. For **peak amplitude, peak/fractional-area latency, or any nonlinear score** there is no analytic SME, so bootstrap it: resample trials with replacement, re-average, re-score (~1000 iterations), and take the SD of the resulting score distribution.

```python
# Analytic SME for mean amplitude (Luck et al. 2021)
single_trial_amp = epochs[cond].get_data(picks=roi, tmin=t_min, tmax=t_max).mean(axis=(1, 2)) * 1e6
sme_mean_amp = single_trial_amp.std(ddof=1) / np.sqrt(len(single_trial_amp))

# Bootstrap SME for any nonlinear score (peak, fractional-area latency, ...)
def bootstrap_sme(epochs_cond, score_fn, n_boot=1000, rng=np.random.default_rng(0)):
    ep = epochs_cond.get_data()  # [n_trials, n_ch, n_times]
    n = ep.shape[0]
    scores = [score_fn(ep[rng.integers(0, n, n)].mean(axis=0)) for _ in range(n_boot)]
    return np.std(scores, ddof=1)
```

Aggregate across conditions as `RMS(SME)` and report a group-level `SNR = effect / RMS(SME)`. This gives a quantitative, score-specific number to gate subject inclusion, to explain a null as low power rather than absence of effect, and it bridges directly to `eeg-qc`. Write per-subject SME into `component_measures.csv` (one column per score) alongside `nave`. Cite: Luck, S. J., Stewart, A. X., Simmons, A. M., & Kappenman, E. S. (2021). Standardized measurement error: A universal metric of data quality for averaged event-related potentials. *Psychophysiology*, 58(6), e13793.

## Phase D — Component measurement

For each claim's target component, measure amplitude and latency using the method specified in ANALYSIS_PLAN (default: mean amplitude).

### Measurement methods (from Luck 2014; Keil et al. 2014; Kappenman & Luck 2016)

#### 1. Mean amplitude in time window (PREFERRED for most components)

The mean voltage in a pre-specified time window. Preferred because:
- Unbiased by noise — high-frequency noise averages out.
- Does not require a clear peak (works for broad components like N400, P3b, LPP).
- Less sensitive to individual differences in peak timing.
- Recommended by Keil et al. (2014) committee guidelines as the default choice.

```python
# MNE
times = evoked.times
mask = (times >= t_min) & (times <= t_max)
ch_idx = [evoked.ch_names.index(ch) for ch in roi_channels]
mean_amp = evoked.data[ch_idx][:, mask].mean() * 1e6  # convert to µV
```

#### 2. Peak amplitude + peak latency (USE WITH CAUTION)

The maximum (or minimum) voltage in a time window.

**Warnings** (Kappenman & Luck 2016):
- Biased by noise: peak amplitude is systematically overestimated in noisy data because noise can only increase the apparent peak.
- Unreliable for broad, plateau-shaped components (P3b, N400).
- Should only be used for sharp, well-defined components (e.g., P1, N1, N170) with high SNR.
- Never use peak amplitude as the primary measure when N < 20 or trial counts are low.

```python
# MNE — use with caution
ch, lat, amp = evoked.get_peak(ch_type='eeg', tmin=t_min, tmax=t_max, mode='neg')  # 'neg' for N-components
# mode: 'pos' for P-components, 'neg' for N-components, 'abs' for either
```

#### 3. Adaptive mean (window centered on individual peak)

A hybrid: find the individual's peak latency, then measure mean amplitude in a narrow window (e.g., +/-25 ms) around that peak. Combines noise robustness of mean amplitude with sensitivity to individual timing differences.

```python
# MNE + custom
_, peak_lat, _ = evoked.get_peak(tmin=t_min, tmax=t_max, mode='neg')
adaptive_tmin = peak_lat - 0.025
adaptive_tmax = peak_lat + 0.025
mask = (times >= adaptive_tmin) & (times <= adaptive_tmax)
adaptive_mean = evoked.data[ch_idx][:, mask].mean() * 1e6
```

#### 4. Fractional area latency (PREFERRED over peak latency)

The time point at which a specified fraction (typically 50%) of the area under the curve is reached. Better than peak latency because:
- Less sensitive to noise.
- More stable across subjects.
- Recommended by Luck (2014) and Keil et al. (2014).

```python
# Custom implementation (MNE does not have a built-in)
from scipy.integrate import cumulative_trapezoid
signal = evoked.data[ch_idx].mean(axis=0)[mask]
if component_polarity == 'negative':
    signal = -signal  # flip so area is positive
cumarea = cumulative_trapezoid(signal, times[mask], initial=0)
total_area = cumarea[-1]
frac_idx = np.searchsorted(cumarea, 0.5 * total_area)
frac_latency = times[mask][frac_idx]
```

#### 5. Jackknife latency (PREFERRED for latency *difference* tests)

For comparing onset or latency *between conditions/groups*, the jackknife is the most accurate approach: instead of scoring each noisy single-subject waveform, form `n` leave-one-out grand subaverages (omit one subject at a time), measure latency (fractional area or relative-criterion onset) on each near-noise-free subaverage, then run the across-subject test on those `n` jackknife values. Because the leave-one-out values are far less variable than independent observations, the raw `t`/`F` is hugely inflated and **must** be corrected before computing `p`: `t_corrected = t / (n - 1)` (equivalently `F_corrected = F / (n - 1)^2`). Omitting this correction is the classic and easy-to-miss error.

```python
# Jackknife latency-difference scoring (Kiesel et al. 2008; correction: Ulrich & Miller 2001)
n = len(evokeds_A)
def jk_latency(evokeds, roi, tmin, tmax, polarity):
    out = []
    for i in range(len(evokeds)):
        sub = mne.grand_average([e for j, e in enumerate(evokeds) if j != i])
        out.append(frac_area_latency(sub, roi, tmin, tmax, polarity))  # score the LOO subaverage
    return np.array(out)
lat_A, lat_B = jk_latency(evokeds_A, ...), jk_latency(evokeds_B, ...)
t_raw, _ = scipy.stats.ttest_rel(lat_A, lat_B)
t_corr = t_raw / (n - 1)               # MANDATORY jackknife correction
p = 2 * scipy.stats.t.sf(abs(t_corr), df=n - 1)
```
Cite: Kiesel, A., et al. (2008). Measurement of ERP latency differences: A comparison of single-participant and jackknife-based scoring methods. *Psychophysiology*, 45(2), 250–274; Ulrich, R., & Miller, J. (2001). Using the jackknife-based scoring method for measuring LRP onset effects in factorial designs. *Psychophysiology*, 38(5), 816–827.

### Standard ERP component reference (from Woodman 2010)

| Component | Polarity | Typical latency | Typical ROI | Notes |
|-----------|----------|-----------------|-------------|-------|
| P1 (C1) | Positive | 60–90 ms | O1, Oz, O2 | Early visual, striate cortex |
| N1 | Negative | 80–150 ms | Fz, Cz, FCz | Auditory; posterior N1 for visual |
| P1 (visual) | Positive | 80–130 ms | O1, Oz, O2 | Extrastriate visual |
| N170 | Negative | 140–200 ms | P7, P8 | Face/object processing |
| N2 | Negative | 200–350 ms | Fz, FCz | Conflict monitoring, inhibition |
| P3a | Positive | 250–350 ms | Fz, FCz | Novelty / involuntary attention |
| P3b | Positive | 300–600 ms | Pz, CPz | Target detection, context updating |
| N400 | Negative | 300–500 ms | Cz, CPz | Semantic processing |
| LRP | Neg (contra) | variable | C3, C4 | Lateralized readiness potential |
| ERN | Negative | 0–100 ms post-response | FCz, Cz | Error-related negativity |
| CRN | Negative | 0–100 ms post-response | FCz, Cz | Correct-response negativity (smaller than ERN) |
| LPP | Positive | 400–800 ms | Pz, CPz | Late positive potential (emotion) |
| MMN | Negative | 100–250 ms | Fz, FCz | Mismatch negativity (auditory) |

Use this table to validate that the user's time windows and ROI channels are reasonable for their claimed component. **Warn** if the planned window deviates strongly from the literature norm.

## Phase D.5 — Group statistics strategy (hypothesis-driven vs data-driven)

The ERP group-analysis flow is: individual averaging cancels trial noise → extract a metric per subject → test across subjects (which cancels inter-subject differences). There are two routes to the across-subject test; pick one *a priori* per claim and record it in `ERP_PLAN.json`.

### Route A — Hypothesis-driven (fixed ROI + fixed window)

When the claim names a component with an *a-priori* time window and ROI, reduce each subject to a single number and run one test — minimal multiple-comparison burden.

```python
# One mean-amplitude (or peak) value per subject, no mass correction needed
def subj_mean_amp(evoked, roi, tmin, tmax):
    return evoked.get_data(picks=roi, tmin=tmin, tmax=tmax).mean() * 1e6  # µV

vals_A = [subj_mean_amp(ev, roi, tmin, tmax) for ev in evokeds_A]
vals_B = [subj_mean_amp(ev, roi, tmin, tmax) for ev in evokeds_B]
# peak amplitude + latency per subject (sharp, high-SNR components only):
# get_peak has no `picks` arg — restrict channels first, e.g. ev.copy().pick(roi):
# _, lat, amp = ev.copy().pick(roi).get_peak(ch_type='eeg', tmin=tmin, tmax=tmax,
#                                            mode='neg', return_amplitude=True)
# → hand vals_A/vals_B (and latencies) to eeg-stats for a paired t-test / RM-ANOVA
```

### Route B — Data-driven (point-by-point, cluster-corrected)

Use when the window or ROI is *not* fixed in advance and you want the data to localize it:
- **"when?"** — fix the ROI/channel, test every time point across subjects → 1D temporal cluster permutation localizes the component window.
- **"where?"** — fix the latency, test every channel across subjects → spatial cluster permutation (with sensor adjacency) localizes the ROI.

Both must keep the **per-subject** array (do not collapse to grand average first) and use cluster correction. Hand the stacked `[n_subjects, n_times]` (when) or `[n_subjects, n_channels]` (where) array to `eeg-stats`, which runs `mne.stats.permutation_cluster_1samp_test` (within-subject difference waves) / `mne.stats.spatio_temporal_cluster_test` (with channel adjacency).

**Discipline**: do not run Route B and then report a Route-A test inside the discovered window as if it were pre-registered — that is the circular window problem (Luck & Gaspelin 2017). Choosing window/ROI from your own grand average is the same error. Either pre-register (Route A) or report the cluster-corrected result (Route B).

### The collapsed localizer — the sanctioned data-adaptive window/ROI selector

When no pre-registered or literature window is available, the *collapsed localizer* is the one legitimate way to let the data set the window/ROI without double-dipping: average together **all** the conditions that will later be contrasted, then pick the window and ROI where the component is maximal in that collapsed waveform, and finally measure the individual conditions there. Under the null the collapsed waveform is identical across conditions, so selecting from it is orthogonal to the difference being tested — selection bias is removed. This is the escape hatch that the "never pick a window from your data" rule otherwise leaves open. Cite: Luck, S. J., & Gaspelin, N. (2017). How to get statistically significant effects in any ERP experiment (and why you shouldn't). *Psychophysiology*, 54(1), 146–157.

### High-pass filter distortion guard for amplitude/latency measurement

The component score inherits the upstream filter. High-pass cutoffs at or above ~0.3 Hz introduce artifactual deflections of *opposite* polarity immediately adjacent in time to a real effect, which corrupt the amplitude, onset, and fractional-area latency measured in neighbouring windows. For amplitude/latency scoring prefer a high-pass cutoff of **≤ 0.1 Hz**. When the upstream filter (from `eeg-preprocess`/`ENVIRONMENT.json`) exceeds 0.1 Hz, flag it on every affected row of `component_measures.csv` so the distortion risk travels with the number. Cite: Tanner, D., Morgan-Short, K., & Luck, S. J. (2015). How inappropriate high-pass filters can produce artifactual effects and incorrect conclusions in ERP studies of language and cognition. *Psychophysiology*, 52(8), 997–1009.

## Phase E — Grand averages and difference waves

1. **Grand average per condition**: average across all subjects' evoked responses.
   ```python
   grand_avg = mne.grand_average([evoked_sub1, evoked_sub2, ...])
   grand_avg.save(f'erp-stage/grand_average/{cond}-grand-ave.fif', overwrite=True)
   ```

2. **Grand average difference wave**: compute the difference wave from grand averages (for visualization), AND from individual difference waves (for statistics — these are different!).
   ```python
   # For visualization
   grand_diff = mne.combine_evoked([grand_avg_A, grand_avg_B], weights=[1, -1])
   # For statistics — use individual subject differences averaged
   individual_diffs = [mne.combine_evoked([subj_A, subj_B], weights=[1, -1]) for ...]
   grand_diff_for_stats = mne.grand_average(individual_diffs)
   ```

3. **GFP** (Global Field Power): RMS across channels at each time point.
   ```python
   gfp = evoked.data.std(axis=0)  # or np.sqrt((evoked.data ** 2).mean(axis=0))
   ```

4. **Grand-average confidence band (mean ± SEM)**. A common convention is to shade ± 1 standard error of the mean across subjects, SEM = std(ddof=0)/√n_subjects.
   ```python
   import numpy as np
   data = np.array([ev.get_data(picks=roi).mean(axis=0) for ev in evokeds])  # [n_subjects, n_times]
   mean = data.mean(axis=0)
   sem = data.std(axis=0, ddof=0) / np.sqrt(data.shape[0])
   # plt.fill_between(times, mean - sem, mean + sem, alpha=0.2)
   ```
   `mne.viz.plot_compare_evokeds(evokeds_dict)` draws a band automatically when given a *list of per-subject Evoked* per condition: `ci=True` is equivalent to a 0.95 threshold (95% bootstrap CI for a single plot; parametric when `axes='topo'`), a float in (0, 1) sets the threshold, and a callable taking an `[n_observations × n_times]` array returns custom upper/lower margins (e.g. SEM). State the band definition in the figure caption.

**Keep the subject axis for statistics.** For any cluster/ANOVA test, retain the per-subject arrays — do *not* average across subjects before the test (the analog of FieldTrip's `keepindividual='yes'`). Collapsing first destroys the variance the test needs.

## Phase E.5 — Regression ERP (rERP) with overlap deconvolution (optional)

Plain condition averaging breaks down when events are spaced closely enough that adjacent responses overlap — fast RSVP, fixation- or saccade-locked reading and free-viewing, and button presses that fall near stimulus onsets. The average then confounds the response of interest with the tails of neighbouring responses, and there is no way to bin a *continuous* predictor (word frequency, luminance, saccade amplitude) without throwing away resolution. Regression ERP solves both: build a **time-expanded design matrix** with one impulse-response basis per predictor across the whole continuous recording and solve a single least-squares problem, which deconvolves the overlapping responses and yields a separate response estimate per predictor. Continuous covariates enter directly (no binning), and spline/GAM bases let a predictor's effect be nonlinear.

This is portable from the `unfold` time-expansion framework (and `pymatreader`/custom design matrices in Python). Treat it as an alternative to Phase C averaging when the design has overlap or continuous predictors; the recovered betas are non-overlapping evoked responses that feed the rest of the pipeline (component measurement, grand average, stats) exactly like condition evokeds. Cite: Smith, N. J., & Kutas, M. (2015). Regression-based estimation of ERP waveforms: I. The rERP framework. *Psychophysiology*, 52(2), 157–168; Ehinger, B. V., & Dimigen, O. (2019). Unfold: an integrated toolbox for overlap correction, non-linear modeling, and regression-based EEG analysis. *PeerJ*, 7, e7838.

## Phase F — Write outputs

### Per-subject files
- `erp-stage/<sub>/<sub>-<cond>-ave.fif` — per-condition evoked.
- `erp-stage/<sub>/<sub>-diff_<contrast>-ave.fif` — per-contrast difference wave.

### Grand average files
- `erp-stage/grand_average/<cond>-grand-ave.fif`
- `erp-stage/grand_average/diff_<contrast>-grand-ave.fif`

### Measurement tables
- `erp-stage/component_measures.csv` — one row per subject x component x condition:
  ```
  subject, component, condition, measure_type, amplitude_uV, latency_ms, time_window, roi_channels
  sub-01, N1, target, mean_amp, -3.42, NaN, 80-150, "Fz,Cz,FCz"
  sub-01, N1, target, peak_amp, -5.17, 112, 80-150, "Fz,Cz,FCz"
  sub-01, N1, target, frac_area_lat, NaN, 108, 80-150, "Fz,Cz,FCz"
  ```

- `erp-stage/peak_table.csv` — backward-compatible summary for figure stage.

### Append to `FINDINGS.md`
```markdown
## ERP Stage
- N subjects averaged: [N]
- Conditions: [list]
- Components measured: [list]
- Measurement method: [mean_amp / peak / adaptive_mean / frac_area_lat]
- Grand average files: erp-stage/grand_average/
```

## Phase G — Sanity checks

All must pass before declaring success:

- [ ] Every subject in `epoch-stage/` has corresponding evoked files in `erp-stage/`.
- [ ] Every condition in ANALYSIS_PLAN has a grand average file.
- [ ] `component_measures.csv` exists and has rows for every subject x component combination.
- [ ] Difference waves exist for every contrast in the claim table.
- [ ] GFP was computed for each condition and the difference wave.
- [ ] `ERP_PLAN.json` and `BACKEND_RESOLUTION.md` exist.
- [ ] Time windows in `component_measures.csv` match those in ANALYSIS_PLAN.

## Critical Rules

- **Never** measure a component not specified in ANALYSIS_PLAN (unless `— exploratory` is passed).
- **Never** choose time windows or ROI channels based on the grand average — this is circular (Luck & Gaspelin 2017). Use pre-registered or literature-based windows.
- **Never** use peak amplitude as the sole measure for broad components (P3b, N400, LPP). Use mean amplitude.
- **Never** report peak latency from noisy data — use fractional area latency instead (Luck 2014).
- **Never** confuse the grand average difference wave (for display) with subject-level difference waves (for statistics).
- **Never** average across subjects before a cluster/ANOVA test — retain the per-subject array (FieldTrip `keepindividual='yes'`); collapsing first destroys the variance the test needs.
- **Never** select the time window or ROI from a data-driven test and then report a fixed-window test inside it as pre-registered — that is the circular window problem (Luck & Gaspelin 2017). Pre-register the window (Route A) or report the cluster-corrected result (Route B).
- **Never** average a contrast whose conditions have very unequal trial counts without equalizing (`equalize_event_counts`) or reporting the imbalance — the difference wave is biased toward the noisier condition.

## Domain Knowledge (distilled from ERP methodology literature)

### Component measurement best practices (Luck 2014; Keil et al. 2014)

- **Mean amplitude is the default** — it is unbiased, noise-robust, and works for both peaked and broad components. Keil et al. (2014) committee guidelines explicitly recommend mean amplitude over peak amplitude for most ERP research.
- **Peak amplitude overestimates the true amplitude** because noise can only push the peak further from zero. This bias increases with noise and decreases with trial count (Kappenman & Luck 2016).
- **Peak latency is unreliable** in noisy data because the peak location is driven by the largest noise excursion within the window, not the true neural peak. Fractional area latency (50% area) is more robust (Luck 2014, Chapter 9).
- **Adaptive mean** is a good compromise when individual peak timing varies but the component is well-defined: find the individual peak, then measure mean amplitude in a narrow window centered on it.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.). MIT Press.
- Cite: Keil, A., et al. (2014). Committee report: Publication guidelines and recommendations for studies using electroencephalography and magnetoencephalography. Psychophysiology, 51(1), 1–21.
- Cite: Kappenman, E. S., & Luck, S. J. (2016). Best practices for event-related potential research in clinical populations. Biological Psychiatry: Cognitive Neuroscience and Neuroimaging, 1(2), 110–115.

### Difference waves and their interpretation

- A difference wave isolates the effect of a single experimental manipulation by subtracting one condition from another.
- The subtraction should be theory-driven: subtract the condition that lacks the process of interest from the one that contains it.
- Difference waves can reveal components not visible in the raw waveforms (e.g., MMN = deviant minus standard; N2pc = contralateral minus ipsilateral).
- **Warning**: difference wave amplitude depends on the correlation between conditions across subjects. If conditions are positively correlated, the difference wave variance is reduced, increasing statistical power.
- For statistical tests, always use subject-level difference waves, never the difference of grand averages.

### The averaging principle and trial count (Luck 2014)

- An ERP is recovered by averaging because the evoked signal is time- and phase-locked to the event while background EEG is approximately random with respect to it, so averaging cancels the noise and leaves the signal. Residual noise in the average falls as 1/√n, i.e. **SNR scales with √(trial count)** — doubling SNR requires roughly 4× the trials.
- ERP quality therefore depends on *both* trial count and trial quality. Favor **correction over rejection**: ICA-correct stereotyped artifacts (blinks, saccades) to preserve trials, and reject only non-correctable segments. Over-aggressive IC removal can erase part of the ERP (Chaumon et al. 2015).
- **Mean amplitude over a window is more robust than peak measures when trial counts are low or noise is high**, because peak amplitude bias grows as n shrinks (Kappenman & Luck 2016). Report per-condition trial counts so reviewers can judge SNR.
- Cite (averaging principle / trial count): Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.). MIT Press.
- Cite (IC-removal point only): Chaumon, M., Bishop, D. V. M., & Busch, N. A. (2015). A practical guide to the selection of independent components of the electroencephalogram for artifact correction. Journal of Neuroscience Methods, 250, 47–63.

### Principled trial-count cutoff via Generalizability Theory

The fixed "< 30 trials = warn" heuristic is convenient but arbitrary — the trial count needed for a stable score depends on the specific component and paradigm. Generalizability Theory replaces it with a number derived from the data: a **G-study** partitions the person × trial variance to yield a dependability coefficient `phi` (a reliability index for absolute decisions) as a function of trial count, and a follow-up **D-study** solves for the minimum `n_trials` that reaches a target dependability (e.g. `phi ≥ 0.8`) for *that* score and paradigm. The ERA toolbox formulas are portable to Python. Report `phi` alongside the SME — they answer different questions: SME is a per-subject standard error of a single score, while `phi` is a population reliability of the measurement design. Cite: Clayson, P. E., Brush, C. J., & Hajcak, G. (2021). Data quality and reliability metrics for event-related potentials (ERPs): The utility of subject-level reliability. *International Journal of Psychophysiology*, 165, 121–136; Clayson, P. E., & Miller, G. A. (2017). ERP Reliability Analysis (ERA) Toolbox: An open-source toolbox for analyzing the reliability of event-related potentials. *International Journal of Psychophysiology*, 111, 68–79.

### ERP component naming conventions (Woodman 2010)

- Components are named by polarity and ordinal position (N1 = first negative, P2 = second positive) or by polarity and approximate latency (N400 = negative around 400 ms).
- The same component can have different names in different labs (N2pc vs PCN; N170 vs VPP).
- A "component" implies a single neural generator; an "ERP effect" is the difference between conditions and may reflect multiple components.
- Cite: Woodman, G. F. (2010). A brief introduction to the use of event-related potentials in studies of perception and attention. Attention, Perception, & Psychophysics, 72(8), 2031–2046.

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing or has placeholders | Stop. Ask user to fill and freeze the plan. |
| Epoch files missing for some subjects | Report which subjects are missing. Proceed with available subjects but warn. |
| Fewer than 30 trials per condition per subject | Warn: low trial count degrades ERP quality; peak measures especially unreliable. The fixed 30 is a heuristic — prefer a G-theory D-study cutoff (`phi ≥ 0.8`) and per-subject SME for a principled, score-specific threshold (Clayson et al. 2021; Luck et al. 2021). |
| No clear peak in measurement window | Do not force a peak. Use mean amplitude instead. Log the issue. |
| Time window in plan does not match known component latency | Warn user but use the planned window (it may be intentional). |
| ROI channels not found in data | Stop. Check channel_mapping.json or ask user. |
| Mixed backends (some subjects in .fif, some in .set) | Convert all to one format before averaging. |
| Unequal trial counts across conditions in a contrast | Equalize with `epochs.equalize_event_counts([...])` or report the imbalance and confirm the effect survives it; the diff wave is biased toward the noisier condition. |
| Tempted to pick the window/ROI from the grand average then test it | Stop — circular (Luck & Gaspelin 2017). Use a pre-registered window (Route A) or a cluster-corrected data-driven test (Route B). |
| Per-subject arrays collapsed to grand average before stats | Re-extract per-subject values/arrays; cluster and ANOVA tests need the subject axis (FieldTrip keepindividual='yes'). |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `epoch-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `erp-stage/*-ave.fif`, `erp-stage/grand_average/`, `erp-stage/component_measures.csv`, `erp-stage/peak_table.csv`, `erp-stage/ERP_PLAN.json`, `erp-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Next: `eeg-stats` reads evoked files and the per-subject metric arrays from this stage — hand it Route-A subject values (paired t-test / `mne.stats.f_mway_rm` for factorial designs) or the per-subject arrays for Route-B cluster permutation ('when'/'where'). `eeg-figure` reads grand averages and the mean±SEM band for plots. `eeg-audit` verifies measurements and trial counts match the plan. For topographic segmentation of evoked data (ERP microstates), see `eeg-microstate` (polarity-aware, all-timepoints mode — distinct from resting defaults).
