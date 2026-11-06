## Constants

Values below are literature/example settings, not approval for a study. The
executable resting-map path reads explicit approved preparation/clustering
parameters, including the GFP-threshold reference distribution, cap and seed.
ERP segmentation remains the separate route described in the entrypoint.

- **BACKEND = `pycrostates`** (Python). The primary backend for microstate analysis.
- **K = `4`** unless DATASET_BRIEF specifies otherwise (Koenig's canonical four: A, B, C, D). `5` and `6` also common in resting-state literature.
- **USE_GFP_PEAKS = `true`** — fit only on GFP-peak topographies (standard practice; reduces redundancy and noise).
- **FILTER_BAND = `(2, 20)` Hz** — band-pass for resting microstate analysis. This is the field default taught for microstate clustering (Murray/Michel/CARTOOL practice); `(1, 40)` Hz broadband is used only by a minority of studies. Van de Ville and Khanna 2014 used 1–30 / 2–20 Hz. The narrow 2–20 Hz band suppresses slow drifts and high-frequency muscle/line noise that destabilize topographies.
- **N_PEAKS_PER_SUBJECT = `1000`** — randomly subsample at most this many GFP-peak maps per subject before group clustering (Poulsen et al. 2018, §3.3.2). A cap limits longer recordings' contribution; it does not equalize weights when a participant supplies fewer than the cap. Record actual map counts; any further weighting is a scientific choice.
- **GFP_REJECT_SD = `1.0`** — drop GFP-peak maps whose GFP exceeds mean + 1·SD of all GFP values; extreme-GFP maps are usually non-neural artifacts (Poulsen et al. 2018, `GFPthresh=1`).
- **MIN_SEGMENT_MS = `30`** — minimum microstate segment length for small-segment rejection on back-fit labels (Poulsen toolbox default `minTime=30 ms`). Convert to samples: `int(round(0.030 * sfreq))`.
- **SMOOTH_HALF_WINDOW = `3`** samples each side (Pascual-Marqui et al. 1995 windowed-smoothing default). With the pycrostates `factor` (≈ λ) smoothing weight, λ=5 is the original recommendation.
- **N_INIT = `100`** — number of random initializations for modified k-means.
- **SEED = read from ANALYSIS_PLAN.md**, default `42`.
- **TEMPLATE_MODE = `fit-here`** by default. `— template: published` loads published canonical maps and skips clustering.
- **FIT_LEVEL = `group`** — fit on concatenated GFP peaks across all subjects (standard). Alternative: `individual` for per-subject fitting.
- **OUTPUT_DIR = `microstate-stage/`** — Create if missing.

> Override: `/eeg-microstate projects/my-study — k: 5 — template: fit-here — backend: pycrostates`

## Phase A — Data preparation

1. Load cleaned continuous EEG, with actual participant identity and channel metadata.
2. Resolve the approved EEG channel set/order, band-pass settings, applied average reference, peak separation **in samples**, annotation exclusion, GFP rejection, cap and seed.
3. Specify whether the rejection mean/SD comes from **all retained continuous samples** (`continuous`) or **GFP-peak maps** (`peaks`). These are different definitions; no silent substitution is allowed. The helper uses population SD (`ddof=0`) and records the threshold. An explicitly approved `None` disables rejection or the cap.
4. Reuse this exact preparation for individual and group clustering, and use the returned prepared Raw for back-fitting. It copies the input; it does not reprocess an already prepared copy in the group step.

```python
# AEA example: microstate-preparation
import runpy
from pathlib import Path
import mne
preparation = runpy.run_path(str(Path(AEA_ROOT) / 'skills/eeg-microstate/scripts/preparation.py'))
raw = mne.io.read_raw_fif(raw_fif_path, preload=True)
prepared_raw, gfp_peaks, peak_audit = preparation['prepare_peaks'](
    raw, **approved_microstate_preparation)
# Save peak_audit, including actual selected indices and counts, with participant_id.
```

`approved_microstate_preparation` supplies `channels`, `filter_kwargs`,
`reference`, `min_peak_distance`, `reject_by_annotation`, `gfp_reject_sd`,
`gfp_reference`, `max_peaks` and `seed`. Missing settings do not inherit the
literature values above. Complete filtering options belong to the approved
`filter_kwargs`; nondefault values pass through to MNE. Selected bad channels
must be handled upstream under the approved policy. No interpolation or automatic
extra channel removal is performed here.

## Phase B — Backend resolution

```
1. Read ENVIRONMENT.json
2. Verify pycrostates is available → generate Python code
3. Else → ERROR: pycrostates required (pip install pycrostates)
```

Write `microstate-stage/BACKEND_RESOLUTION.md`.

## Phase C — Clustering (Fit phase)

### Method: Modified k-means (default)

Modified k-means ignores map polarity (a topography and its polarity-inverted version are treated as the same microstate class). This is the standard method.

### Pycrostates path (default)

```python
# AEA example: microstate-group-preparation
# Each source path and participant ID comes from the actual recording ledger.
peak_records, prepared_raws = [], {}
for sub in subjects:
    raw = mne.io.read_raw_fif(raw_paths[sub], preload=True)
    prepared, peaks, audit = preparation['prepare_peaks'](
        raw, **approved_preparation_by_participant[sub])
    prepared_raws[sub] = prepared
    peak_records.append({'participant_id':sub, 'peaks':peaks, 'audit':audit})

# Same names but a different stored order are reordered before concatenation.
# Different sets or positions require approved upstream handling, not hstack.
group_peaks, all_peaks, group_peak_audit = preparation['pool_peaks'](
    peak_records, channels=approved_group_channels)
# Save group_peak_audit before fitting. all_peaks is aligned per-participant input.
```

```python
# AEA example: microstate-group-fitting
from pycrostates.cluster import ModKMeans
ModK = ModKMeans(**approved_modkmeans_params)
ModK.fit(group_peaks, n_jobs=approved_n_jobs)
ModK.save(str(group_model_path))  # native Pycrostates FIF file, e.g. group-model.fif
```

Plot the fitted model and report measured GEV after fitting. The group path now
performs the same rejection and cap as the individual path; they are not a
comment-only instruction. The audit retains each participant's original channel
order and preparation record. Channel location/unit/frame mismatches stop
pooling rather than attaching the first participant's metadata to different maps.

### Alternative clustering methods

- **AAHC (Atomize and Agglomerate Hierarchical Clustering)**: Deterministic (no random init), starts with each GFP peak as a cluster and iteratively merges. Available in pycrostates as `pycrostates.cluster.AAHCluster`.
- **PCA-based**: Use PCA on GFP-peak topographies; first K components correspond to microstate maps. Simpler but less standard.
- **TAAHC (Topographic Atomize and Agglomerate)**: Variant that uses topographic dissimilarity instead of GEV for merging criterion.

```python
# AAHC alternative
from pycrostates.cluster import AAHCluster
aahc = AAHCluster(n_clusters=4)
aahc.fit(group_peaks)
```

### Selecting K

K=4 a priori is the documented default (Koenig et al. 2002 convention; many studies simply force it). When you must justify K empirically, sweep and inspect — do **not** pick K by maximizing GEV.

```python
GEVs = {}
for k in range(2, 9):
    mk = ModKMeans(n_clusters=k, n_init=100, max_iter=1000, random_state=42)
    mk.fit(group_peaks, n_jobs=4)
    GEVs[k] = mk.GEV_
# Plot GEV vs k and pick the elbow (diminishing returns), not the maximum.
```

> **WARNING — polarity invariance.** GEV increases monotonically with K, so it cannot pick K alone; use the **GEV elbow** or the **cross-validation criterion** (CV; Pascual-Marqui et al. 1995, Eq. 10 — `CV = sigma_hat^2 * ((C-1)/(C-K-1))^2` on the residual variance), which is what modified k-means actually minimizes. **Do NOT use the Krzanowski-Lai (KL), normalised-KL, or dispersion (W) criteria with modified k-means / AAHC / TAAHC** — those are based on Euclidean sum-of-squares and are NOT polarity-invariant, so they are invalid for polarity-invariant clustering. Only GEV and CV are valid measures of fit there. Note the CV criterion often only reaches its true minimum at impractically large K, so the elbow is usually the operational choice.

**Meta-criterion (data-driven K).** When K must be chosen empirically rather than fixed a priori, the de-facto Cartool approach is a *meta-criterion*: normalize several cluster-validity indices (Silhouette, Davies-Bouldin, cross-validation, etc.) onto a common scale and let them vote, run first on 1st-level (per-subject) then on 2nd-level (group) maps. This typically lands on K=5–7. Consistent with the polarity warning above, **drop the polarity-sensitive members (KL, dispersion W) from the vote** for modified k-means / AAHC / TAAHC and keep only polarity-invariant indices. Cite: Brechet et al. (2019), NeuroImage 194:82.

**Algorithm choice is not where to agonize.** The clustering *algorithm* (modkmeans vs AAHC vs TAAHC) is information-theoretically invariant for the downstream sequence dynamics, so picking one and reporting it is sufficient — do not burn effort comparing algorithms (von Wegner et al. 2018, Front. Comput. Neurosci. 12:70). Spend the budget on K, ocular cleaning, and reliability instead.

**Reliability of K for trait/biomarker work.** In large (~500-subject) retest data, **K=5 (A, B, C, C', D) yields more reliable microstate parameters than K=4, 6, or 7** — prefer K=5 when the goal is an individual-differences or longitudinal biomarker rather than replicating a K=4-fixed literature. Cite: Kleinert et al. (2023), Brain Topogr. 37:271.

### FIT_LEVEL = `two-stage-global` (recommended for group studies)

The single-pass concatenation above is a valid lighter variant, but the canonical and most-reliable group strategy is hierarchical (Khanna et al. 2014 'global maps'): cluster each subject first, pool the per-subject maps, then re-cluster the pool into group templates.

```python
from pycrostates.io import ChData
import numpy as np
# all_peaks is the name-aligned, actually filtered/rejected/capped output above.
# 1) Per-subject clustering on that subject's prepared GFP peaks
subject_centers = []
for sub, peaks in zip(subjects, all_peaks):
    mk = ModKMeans(**approved_subject_modkmeans_params)
    mk.fit(peaks, n_jobs=approved_n_jobs)
    subject_centers.append(mk.cluster_centers_)        # (4, n_channels)

# 2) Pool subject-level maps (e.g. 4 x N_subjects) into one ChData
pooled = ChData(np.vstack(subject_centers).T, all_peaks[0].info)

# 3) Re-cluster the pooled maps into the 4 GROUP templates
group_ModK = ModKMeans(**approved_group_modkmeans_params)
group_ModK.fit(pooled, n_jobs=approved_n_jobs)

# 4) Back-fit the group templates to every subject's continuous data (Phase E)
```

Khanna 2014 found this 'global maps' strategy the most reliable (mean Cronbach's α ≈ 0.81) versus per-recording fitting (α ≈ 0.52). Prefer it over per-recording (`FIT_LEVEL = individual`), which is the least reliable strategy.

## Phase D — Template alignment

After fitting, microstate maps must be aligned across subjects (if individual fitting) or labeled consistently:

1. **Cross-subject alignment**: Reorder maps so that each subject's cluster 1 corresponds to the canonical map A, cluster 2 to B, etc.
   - Pycrostates: use spatial correlation to match maps to a reference (group template or published canonical maps).
2. **Polarity alignment**: Ensure consistent polarity across subjects (maps can be inverted).
3. **Labeling**: Assign labels A, B, C, D based on topographic similarity to Koenig et al. 2002 canonical maps. Beyond A–D, higher K reproducibly yields **C'** (an anterior variant of C), plus **F** and **G** — use these named labels instead of "extra map 5/6".

**Meta-microstate templates as the concrete similarity target.** "Verify topographic similarity to published canonical maps" (Phase D / Critical Rules) needs an objective reference rather than eyeballing whether a map "looks like Koenig's C". Use **meta-microstates**: published template maps re-clustered across many studies into consensus references, against which new maps are reported as spatial correlations. This replaces subjective matching with a number. Cite: Koenig et al. (2023), Brain Topogr. 37:218.

```python
# Align individual models to group template
from pycrostates.utils import _correlation  # internal, or compute manually

# For each subject's fitted model, compute spatial correlation with group template
# Reorder clusters to maximize correlation with reference
```

## Phase E — Segmentation (Back-fitting)

Assign each time point to the closest microstate class:

```python
# AEA example: microstate-backfit
# raw is prepared_raws[sub] or prepared_raw from the same preparation contract.
segmentation, backfit_audit = preparation['backfit_microstates'](
    raw, approved_fitted_model, settings=approved_microstate_backfit)
# Save the approved units/values and actual converted sample counts in backfit_audit.
```

`approved_microstate_backfit` declares factor, tol, half_window, min_segment,
reject_edges and reject_by_annotation. Each window has an explicit value and
unit (`samples`, `ms` or `s`). Both this skill and the recipe use this exact helper.
It does not select or fit a template, change duration policy, clamp a rounded
window, or infer the settings from a historical example. Read its returned
`predict_kwargs` as the actual native call configuration.

**Smoothing provenance & scope.** The literature example `half_window_size=3` and λ≈5 follows Pascual-Marqui et al. 1995 windowed smoothing; the example `minTime=30 ms` specifies toolbox small-segment rejection, recursively reassigning segments shorter than 30 ms to the most-correlated neighbour. Temporal smoothing is applied to **continuous back-fit labels and to ERP segmentation**, but **NOT** when clustering temporally-independent resting GFP peaks (peaks are not consecutive in time).

**Boundary / duration convention (midpoint rule).** Back-fitting labels every sample by maximum |spatial correlation| with the templates. The microstate-duration boundary between two *unlike* adjacent GFP-peak maps falls at the **midpoint** of the interval (first half → preceding class, second half → following class); this midpoint rule is what `mean_duration` measures (Khanna et al. 2014, Fig. 1).

**Distance metric — GMD / DISS (polarity-invariant).** Back-fitting uses Global Map Dissimilarity (GMD, = DISS), the GFP-normalized, polarity-invariant distance, **not** raw Euclidean distance: `GMD = || u/GFP_u − v/GFP_v || / sqrt(C)`, ranging 0 (identical) to 2 (polarity-reversed). It is monotonically related to spatial correlation (SCC) by `GMD^2 = 2(1 − SCC)`.

## Phase F — Compute microstate parameters

For each subject per condition, compute:

```python
# pycrostates computes all temporal parameters from the segmentation in one call.
# (The functions mean_duration/occurrence/coverage are NOT in pycrostates.metrics;
#  use Segmentation.compute_parameters() instead.)
params = segmentation.compute_parameters(norm_gfp=True)
# Returned per-class keys: '<label>_gev', '<label>_meandurs' (seconds),
#   '<label>_timecov' (proportion), '<label>_occurrences' (per second), '<label>_meancorr'.
# Convert durations to ms: params['A_meandurs'] * 1000

# --- Transition matrices: report OBSERVED and base-rate-EXPECTED, exclude self-transitions ---
from pycrostates.segmentation import (
    compute_transition_matrix,
    compute_expected_transition_matrix,
)
labels = segmentation.labels
T_obs = compute_transition_matrix(
    labels, n_clusters=4, stat='probability', ignore_repetitions=True,
)
# Expected under a null where time course is shuffled but coverage (base rates) is kept
T_exp = compute_expected_transition_matrix(
    labels, n_clusters=4, stat='probability', ignore_repetitions=True,
)
T_corrected = T_obs - T_exp   # base-rate-corrected dynamics (what to interpret / test)
```

Report **both** the observed matrix and the base-rate-corrected `T_obs − T_exp` (and state which you interpret). Self-transitions (i→i) are excluded (`ignore_repetitions=True`) because microstate **duration already captures dwell time**. Healthy resting transitions are significantly non-random and directional/asymmetric; group comparisons of transition matrices (χ² / permutation on the corrected matrix) belong in `eeg-stats`, not here.

**Information-theoretic sequence measures (beyond the transition matrix).** The label sequence carries dynamics the transition matrix alone misses. Add, when sequence dynamics are of interest: Shannon entropy of the marginal distribution; the **entropy rate** (the principled scalar complexity summary of the sequence); the **autoinformation function** `AIF(k)` (time-lagged mutual information across lags k, which exposes memory and periodicities such as ~100 ms alpha recurrence); and formal **Markov-order-0/1/2 tests**. An open MIT-licensed Python implementation exists (von Wegner & Laufs 2018). **Caveat to flag:** empirically, resting microstate sequences *fail* the first-order Markov property, so the base-rate `T_exp` null above (which assumes shuffled labels at fixed coverage) is itself only an approximation — note this when interpreting the corrected matrix. Cite: von Wegner & Laufs (2018), Front. Neuroinform. 12:30.

**Transition probabilities are the least reliable parameter.** In large retest data, transition probabilities have low test-retest reliability (ICC often < 0.50), whereas duration / occurrence / coverage are trait-like (ICC ≈ 0.87–0.92). **Do not use transition probabilities as standalone longitudinal or biomarker measures**; anchor biomarker claims on the duration/occurrence/coverage triad. Cite: Kleinert et al. (2023), Brain Topogr. 37:271.

**Metric definitions:**
- **GEV (Global Explained Variance)**: Proportion of total variance explained by the microstate segmentation. Higher = better fit. Typical values: 65–85% for 4 classes.
- **Mean duration**: Average time (ms) a microstate remains stable before transitioning. Typical: 60–120 ms.
- **Occurrence**: Number of times a microstate class appears per second. Typical: 2–6/s.
- **Coverage**: Percentage of total recording time assigned to each class. Should sum to ~100%.
- **Transition probabilities**: Markov-like matrix. Non-random transitions suggest structured temporal dynamics.

## Phase G — Write outputs

Retain per-participant preparation records and the group pooling record: input
and aligned channel order, source participant IDs, filter/reference settings,
actual GFP threshold/reference, extracted/rejected/selected counts, selected
indices, cap and seed. A cap alone is not proof of equal participant weighting.

### `microstate-stage/<sub>/<sub>-<cond>-microstate_params.json`
```json
{
  "subject": "sub-01",
  "condition": "rest",
  "k": 4,
  "method": "modified_k_means",
  "n_init": 100,
  "seed": 42,
  "GEV_total": 0.78,
  "GEV_per_class": {"A": 0.22, "B": 0.19, "C": 0.21, "D": 0.16},
  "mean_duration_ms": {"A": 82.3, "B": 71.5, "C": 89.1, "D": 66.7},
  "occurrence_per_sec": {"A": 3.2, "B": 4.1, "C": 2.8, "D": 3.9},
  "coverage_pct": {"A": 26.3, "B": 22.1, "C": 28.5, "D": 23.1},
  "transition_matrix": [[0.0, 0.35, 0.40, 0.25],
                         [0.30, 0.0, 0.28, 0.42],
                         [0.38, 0.25, 0.0, 0.37],
                         [0.22, 0.45, 0.33, 0.0]]
}
```

### `microstate-stage/group/group_template_maps.npz`
Contains: cluster centers (n_clusters × n_channels), channel names, GEV.

### `microstate-stage/group/group_params_summary.csv`
One row per subject per condition with: GEV, mean duration per class, occurrence per class, coverage per class.

### Append to `FINDINGS.md`
```markdown
## Microstates: [condition]
- K = [4], method = [modified k-means], GEV = [value]
- Duration (ms): A=[val], B=[val], C=[val], D=[val]
- Occurrence (/s): A=[val], B=[val], C=[val], D=[val]
- Coverage (%): A=[val], B=[val], C=[val], D=[val]
```

## Phase H — Sanity checks

All must pass before declaring success:

- [ ] GEV > 0.60 (warn if below; suggests poor clustering or wrong K).
- [ ] Coverage across all classes sums to ~100% (±2%).
- [ ] Mean duration is in plausible range (40–200 ms). If <40 ms, temporal smoothing may be too low. If >200 ms, data may not be resting-state.
- [ ] Transition matrix rows sum to 1.0 (within numerical tolerance).
- [ ] All subjects have consistent map labeling (verified via spatial correlation with group template > 0.7).
- [ ] BACKEND_RESOLUTION.md exists.
- [ ] Group summary CSV exists.

## Failure Modes

| Symptom | Action |
|---|---|
| GEV < 0.60 with K=4 | Try K=5 or K=6. Check data quality (residual artifacts inflate unexplained variance). |
| Maps do not resemble canonical A/B/C/D | Verify average reference and band-pass filter, and confirm ocular ICs were removed (residual EOG destabilizes maps). At K=5+ the extra maps are the named reproducible variants C' (anterior C), F, and G (Custo et al. 2017), not arbitrary "extras". |
| Coverage does not sum to ~100% | Check for unlabeled time points (GFP below threshold). Adjust GFP threshold. |
| Very short mean durations (<40 ms) | Increase temporal smoothing factor. Check sampling rate (low sfreq = fewer samples per state). |
| Transition matrix has zero rows | A microstate class is never visited — likely a fitting artifact. Reduce K. |
| pycrostates not installed | `pip install pycrostates`. Log in BACKEND_RESOLUTION.md. |
