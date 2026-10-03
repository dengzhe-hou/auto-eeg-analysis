---
name: eeg-microstate
description: "Fit modified k-means microstate templates on EEG (or apply published templates), segment data per condition, compute coverage / GEV / mean duration / occurrence / transition matrix. Backend: pycrostates (Python)."
argument-hint: "[project-dir] [— k: 4|5|6] [— template: published|fit-here]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-microstate: scalp microstate analysis

## Context: $ARGUMENTS

## Constants

- **BACKEND = `pycrostates`** (Python). The primary backend for microstate analysis.
- **K = `4`** unless DATASET_BRIEF specifies otherwise (Koenig's canonical four: A, B, C, D). `5` and `6` also common in resting-state literature.
- **USE_GFP_PEAKS = `true`** — fit only on GFP-peak topographies (standard practice; reduces redundancy and noise).
- **FILTER_BAND = `(2, 20)` Hz** — band-pass for resting microstate analysis. This is the field default taught for microstate clustering (Murray/Michel/CARTOOL practice); `(1, 40)` Hz broadband is used only by a minority of studies. Van de Ville and Khanna 2014 used 1–30 / 2–20 Hz. The narrow 2–20 Hz band suppresses slow drifts and high-frequency muscle/line noise that destabilize topographies.
- **N_PEAKS_PER_SUBJECT = `1000`** — randomly subsample at most this many GFP-peak maps per subject before group clustering (Poulsen et al. 2018, §3.3.2). Capping peaks per subject equalizes each subject's weight in the pooled clustering so longer recordings do not dominate the group template.
- **GFP_REJECT_SD = `1.0`** — drop GFP-peak maps whose GFP exceeds mean + 1·SD of all GFP values; extreme-GFP maps are usually non-neural artifacts (Poulsen et al. 2018, `GFPthresh=1`).
- **MIN_SEGMENT_MS = `30`** — minimum microstate segment length for small-segment rejection on back-fit labels (Poulsen toolbox default `minTime=30 ms`). Convert to samples: `int(round(0.030 * sfreq))`.
- **SMOOTH_HALF_WINDOW = `3`** samples each side (Pascual-Marqui et al. 1995 windowed-smoothing default). With the pycrostates `factor` (≈ λ) smoothing weight, λ=5 is the original recommendation.
- **N_INIT = `100`** — number of random initializations for modified k-means.
- **SEED = read from ANALYSIS_PLAN.md**, default `42`.
- **TEMPLATE_MODE = `fit-here`** by default. `— template: published` loads published canonical maps and skips clustering.
- **FIT_LEVEL = `group`** — fit on concatenated GFP peaks across all subjects (standard). Alternative: `individual` for per-subject fitting.
- **OUTPUT_DIR = `microstate-stage/`** — Create if missing.

> Override: `/eeg-microstate projects/my-study — k: 5 — template: fit-here — backend: pycrostates`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen. **Stop if missing or unfrozen.**
2. `epochs-stage/` or `clean-stage/` — cleaned continuous or epoched EEG (`.fif`). Continuous preferred for microstate analysis.
3. `ENVIRONMENT.json` — to resolve backend.

**Preconditions (check before fitting; warn/abort if unmet):**
- **>= 20 EEG channels with montage positions** for full-head coverage. Lower-density arrays (19 or even 8 ch) still recover duration/frequency/coverage reliably (Khanna 2014, α 0.87–0.91), but **flag that maps C and D are less consistent** at low density.
- **>= 180 s of clean, average-referenced, artifact-free data** per recording (warn below ~120 s; Khanna used ~128 s, range 80–204 s). Bad channels must be interpolated or removed first.
- **Prefer group / global templates over per-recording fitting.** Per-recording (individual) template fitting is the *least* reliable strategy (Khanna 2014, Cronbach α ≈ 0.52 vs ≈ 0.81 for global maps).
- **Ocular ICA removal is mandatory before clustering, not optional.** Residual eye-movement/blink activity destabilizes the cluster-validity criteria (so K selection becomes unreliable) and distorts the resulting topographies. Removing the ocular ICs is the step that matters; aggressive "keep brain-ICs-only" cleaning beyond that adds little. Treat upstream EOG-component rejection as a hard precondition and abort/warn if `clean-stage` was produced without it. Cite: Artoni & Michel (2025), Brain Topogr. 38:28.

## Phase A — Data preparation

1. Load cleaned continuous EEG (or concatenated epochs) per subject.
2. Band-pass filter to **2–20 Hz** (`FILTER_BAND`, the resting-microstate default). Use 1–40 Hz only if DATASET_BRIEF/ANALYSIS_PLAN explicitly calls for broadband; note it in the methods text. Do **not** silently assume broadband.
3. Re-reference to average reference (required for microstate analysis).
4. Compute Global Field Power (GFP) = spatial standard deviation across channels at each time point.
5. Extract GFP-peak topographies: local maxima of GFP with a **minimum inter-peak distance of ~10 ms** (converted to samples), reject extreme-GFP maps (> mean + `GFP_REJECT_SD`·SD), and randomly subsample to `N_PEAKS_PER_SUBJECT`.

```python
import mne
import numpy as np
from pycrostates.preprocessing import extract_gfp_peaks
from pycrostates.io import ChData

# Load continuous data
raw = mne.io.read_raw_fif(raw_fif_path, preload=True)
raw.filter(2, 20)                       # FILTER_BAND = (2, 20) Hz (resting default)
raw.set_eeg_reference('average')

sfreq = raw.info['sfreq']
min_dist = int(round(0.010 * sfreq))    # 10 ms expressed in SAMPLES (>=1)

# Extract GFP peaks (min_peak_distance is in SAMPLES, not ms)
gfp_peaks = extract_gfp_peaks(raw, min_peak_distance=max(min_dist, 1))

# --- Reject extreme-GFP (artifact) peaks: GFP > mean + GFP_REJECT_SD*SD ---
maps = gfp_peaks.get_data()             # (n_channels, n_peaks)
gfp = maps.std(axis=0, ddof=0)          # GFP per peak map
keep = gfp <= (gfp.mean() + 1.0 * gfp.std())     # GFP_REJECT_SD = 1.0

# --- Cap to N_PEAKS_PER_SUBJECT (equalize each subject's weight) ---
idx = np.flatnonzero(keep)
rng = np.random.default_rng(42)         # SEED
if idx.size > 1000:                     # N_PEAKS_PER_SUBJECT
    idx = rng.choice(idx, size=1000, replace=False)
gfp_peaks = ChData(maps[:, np.sort(idx)], gfp_peaks.info)
```

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
from pycrostates.cluster import ModKMeans
from pycrostates.io import ChData
import numpy as np

# Collect (filtered, average-ref, GFP-peak, capped) topographies across subjects.
# Reuse the Phase A extraction (2-20 Hz, 10 ms min distance, GFP rejection, cap).
all_peaks = []  # list of ChData, one per subject (see Phase A)
for sub in subjects:
    raw = mne.io.read_raw_fif(f'clean-stage/{sub}/{sub}-clean.fif', preload=True)
    raw.filter(2, 20)                   # FILTER_BAND, NOT 1-40 Hz
    raw.set_eeg_reference('average')
    peaks = extract_gfp_peaks(raw, min_peak_distance=max(int(round(0.010 * raw.info['sfreq'])), 1))
    all_peaks.append(peaks)             # apply GFP rejection + cap as in Phase A

# Stack subject peak-map arrays into one ChData for single-pass group fitting
group_arr = np.hstack([p.get_data() for p in all_peaks])
group_peaks = ChData(group_arr, all_peaks[0].info)

# Fit modified k-means (polarity-invariant)
ModK = ModKMeans(n_clusters=4, n_init=100, max_iter=1000, random_state=42)
ModK.fit(group_peaks, n_jobs=4)

ModK.plot()                              # topographic maps A, B, C, D
print(f"GEV: {ModK.GEV_:.3f}")
ModK.save('microstate-stage/group/fitted_model.pkl')
```

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
# 1) Per-subject clustering on that subject's GFP peaks
subject_centers = []
for sub, peaks in zip(subjects, all_peaks):
    mk = ModKMeans(n_clusters=4, n_init=100, max_iter=1000, random_state=42)
    mk.fit(peaks, n_jobs=4)
    subject_centers.append(mk.cluster_centers_)        # (4, n_channels)

# 2) Pool subject-level maps (e.g. 4 x N_subjects) into one ChData
pooled = ChData(np.vstack(subject_centers).T, all_peaks[0].info)

# 3) Re-cluster the pooled maps into the 4 GROUP templates
group_ModK = ModKMeans(n_clusters=4, n_init=100, max_iter=1000, random_state=42)
group_ModK.fit(pooled, n_jobs=4)

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
# Back-fit the fitted (group) model to ALL samples of continuous data.
# Clustering used only GFP peaks, but predict() assigns EVERY time point.
sfreq = raw.info['sfreq']
segmentation = ModK.predict(
    raw,
    factor=10,                                  # label-smoothing weight (lambda-like); 0 = none
    half_window_size=3,                         # SMOOTH_HALF_WINDOW: 3 samples each side (Pascual-Marqui)
    min_segment_length=int(round(0.030 * sfreq)),  # MIN_SEGMENT_MS=30 -> small-segment rejection
    reject_edges=True,
)
# segmentation.labels: microstate label per sample (-1 = unlabeled / rejected)
```

**Smoothing provenance & scope.** `half_window_size=3` and λ≈5 follow Pascual-Marqui et al. 1995 windowed smoothing; `min_segment_length` implements toolbox small-segment rejection (`minTime=30 ms`), recursively reassigning segments shorter than 30 ms to the most-correlated neighbour. Temporal smoothing is applied to **continuous back-fit labels and to ERP segmentation**, but **NOT** when clustering temporally-independent resting GFP peaks (peaks are not consecutive in time).

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

## Critical Rules

- **Resting microstate defaults (GFP-peak selection, polarity-invariant modified k-means, no smoothing during clustering) do NOT apply to ERP / event-locked data.** Topographic ERP microstate segmentation is a distinct, well-established method — do not blanket-forbid it. For evoked data: cluster on **all time points** of the grand-average Evoked (not GFP peaks), use **polarity-aware standard k-means** (Euclidean), and **smooth at the segmentation step** (timepoints are time-ordered). ERP microstate classes map to ERP component latency windows, not the canonical A–D. See `eeg-erp` and Murray et al. 2008 (TANOVA, GFP, topographic segmentation).
- **Never** compare microstate parameters across studies with different K values.
- **Never** skip GFP-peak extraction and fit on all time points — this inflates GEV and produces unstable maps.
- **Never** interpret microstate labels (A, B, C, D) as fixed neural generators without verifying topographic similarity to published canonical maps.
- **Never** use transition probabilities without testing against a Markov null model (random transitions given observed coverage) — but note that resting sequences empirically *fail* the first-order Markov property (von Wegner & Laufs 2018), so treat this null as an approximation and prefer entropy-rate / autoinformation summaries for the full dynamics.
- **Never** report transition probabilities as a standalone longitudinal biomarker — they are the least reliable parameter (ICC often < 0.50); base biomarker claims on duration / occurrence / coverage (Kleinert et al. 2023).

## Domain Knowledge (distilled from EEG microstate methodology literature)

### Canonical microstates A/B/C/D (Koenig et al. 2002, NeuroImage)

- Four reproducible microstate classes (A, B, C, D) consistently emerge from resting-state EEG across studies.
- **Map A**: right-anterior to left-posterior diagonal orientation. Associated with phonological processing networks.
- **Map B**: left-anterior to right-posterior diagonal (orthogonal to A). Associated with visual processing networks.
- **Map C**: frontal-to-occipital (anterior-positive / posterior-negative). Associated with salience / default-mode network.
- **Map D**: fronto-central maximum. Associated with attention / dorsal attention network.
- These canonical maps are remarkably stable across healthy adults but shift in neuropsychiatric conditions (e.g., altered Map C duration in schizophrenia).
- Cite: Koenig, T., Prichep, L., Lehmann, D., Sosa, P. V., Braeker, E., Kleinlogel, H., ... & John, E. R. (2002). Millisecond by millisecond, year by year: normative EEG microstates and developmental stages. NeuroImage, 16(1), 41–48.

### Updated functional labels and the 7-map decomposition (consensus-level)

- A 50-study consensus refines the older one-network-per-map story. Best-supported functional attributions: **A/B = auditory / visual** sensory processing; **C = interoception / autonomic regulation and DMN/salience**; **D = attention reorientation**; with **mind-wandering specifically tied to C'**, which is why separating C from C' (i.e. running K=5) matters for cognitive interpretation. Cite: Tarailis et al. (2024), Brain Topogr. 37:181.
- When more than four classes are warranted, the reproducible 7-map decomposition (Custo et al. 2017, source-localized) names the additional maps **C', F, G** alongside A/B/C/D — use these labels rather than inventing study-specific ones. Cite: Custo, A., et al. (2017). Electroencephalographic resting-state networks: source localization of microstates. Brain Connectivity, 7(10), 671–682.

### Scale-free dynamics and the HMM alternative

- Resting microstate sequences are **monofractal with long-range temporal dependence** (Hurst exponent H > 0.5, estimated via wavelet or DFA on the label sequence) — they are not memoryless, reinforcing the Markov-failure point in Phase F. Cite: Van de Ville, D., Britz, J., & Michel, C. M. (2010). EEG microstate sequences in healthy humans at rest reveal scale-free dynamics. PNAS, 107(42), 18179–18184.
- **Hidden Markov models (HMM)** are a complementary paradigm: soft/probabilistic state assignment with an explicit transition model, vs the hard winner-take-all back-fit here. Caveat: the HMM's Markov assumption *discards* the long-range / scale-free dependence that classical winner-take-all microstates preserve — choose the method to match the dynamics you intend to claim.

### Microstate review (Michel & Koenig 2018, NeuroImage)

- Microstates represent brief (60–120 ms) periods of quasi-stable scalp topography, reflecting coordinated large-scale brain network activity.
- The "atoms of thought" hypothesis: microstates are the basic building blocks of conscious mentation, each reflecting a different mode of information processing.
- **Methodological consensus**:
  - Use **average reference** and band-pass **2–20 Hz** for resting microstates (the taught/CARTOOL default); broadband 1–40 Hz is the minority choice. Khanna 2014 / Van de Ville used 1–30 / 2–20 Hz.
  - Fit on GFP peaks only (reduces redundancy).
  - Modified k-means is the most common algorithm; AAHC is a deterministic alternative.
  - Random-restart count: literature uses **100–300** k-means restarts (Khanna 2014 used 300) and keeps the highest-GEV solution; the Poulsen toolbox default of 10 is a speed tradeoff. `N_INIT = 100` is adequate — raise it if topographies are not reproducible across runs. **AAHC / TAAHC are deterministic** (no restarts) and make good stability cross-checks; the three algorithms usually agree on clean, high-SNR data.
  - Report GEV, mean duration, occurrence, coverage, and transition probabilities.
- **Clinical relevance**: Microstate parameters differ in schizophrenia (shortened Map C), Alzheimer's (altered Map D), depression, and other conditions.
- Cite: Michel, C. M., & Koenig, T. (2018). EEG microstates as a tool for studying the temporal dynamics of whole-brain neuronal networks: a review. NeuroImage, 180, 577–593.

### GEV as quality metric (Murray et al. 2008, Brain Topography)

- Global Explained Variance (GEV) quantifies how well the microstate segmentation represents the original data.
- Computed as: GEV = sum over all time points of (GFP(t)^2 * spatial_correlation(t, assigned_map)^2) / sum(GFP(t)^2).
- **Interpretation**: GEV of 0.65–0.85 is typical for K=4 in resting-state EEG. Lower values suggest suboptimal K or poor data quality.
- GEV increases monotonically with K — use cross-validation, KL criterion, or the elbow method to select optimal K rather than maximizing GEV.
- Cite: Murray, M. M., Brunet, D., & Michel, C. M. (2008). Topographic ERP analyses: a step-by-step tutorial review. Brain Topography, 20(4), 249–264.

### Typical healthy-adult values and clinical directions (Koenig 2002; Khanna 2014/2015; Rieger 2016)

| Parameter | Typical healthy-adult value (K=4) |
|---|---|
| Mean duration | ~80–120 ms per class (Khanna lifespans ~94–102 ms) |
| Occurrence | ~2–6 /s per class; ~10 /s total |
| Coverage | A ~21%, B ~25%, C ~27%, D ~27% |
| GEV (K=4) | ~70% (range 65–78%, Khanna 2014) |
| Duration vs frequency | inversely correlated, R ≈ −0.72 |

- Use these as **sanity bands** for outputs and for auto-generated methods/report text. The Phase H GEV floor of 0.60 is a conservative lower bound; ~70% is the expected value for K=4.
- **Known clinical directions** (sanity-check, do not over-interpret): schizophrenia → increased C occurrence/coverage, shortened B and D duration, altered A↔D syntax; frontotemporal dementia → shortened C; Alzheimer's → shortened overall durations / D; panic disorder → longer A, less C; Tourette → more frequent A.
- Cite: Koenig, T., et al. (2002). NeuroImage, 16(1), 41–48. Khanna, A., et al. (2015). Neurosci. Biobehav. Rev., 49, 105–113. Rieger, K., et al. (2016). Frontiers in Psychiatry, 7, 22.

## Failure Modes

| Symptom | Action |
|---|---|
| GEV < 0.60 with K=4 | Try K=5 or K=6. Check data quality (residual artifacts inflate unexplained variance). |
| Maps do not resemble canonical A/B/C/D | Verify average reference and band-pass filter, and confirm ocular ICs were removed (residual EOG destabilizes maps). At K=5+ the extra maps are the named reproducible variants C' (anterior C), F, and G (Custo et al. 2017), not arbitrary "extras". |
| Coverage does not sum to ~100% | Check for unlabeled time points (GFP below threshold). Adjust GFP threshold. |
| Very short mean durations (<40 ms) | Increase temporal smoothing factor. Check sampling rate (low sfreq = fewer samples per state). |
| Transition matrix has zero rows | A microstate class is never visited — likely a fitting artifact. Reduce K. |
| pycrostates not installed | `pip install pycrostates`. Log in BACKEND_RESOLUTION.md. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `clean-stage/` or `epochs-stage/`, `ENVIRONMENT.json`
- Outputs: `microstate-stage/*-microstate_params.json`, `microstate-stage/group/group_template_maps.npz`, `microstate-stage/group/group_params_summary.csv`, `microstate-stage/BACKEND_RESOLUTION.md`, `FINDINGS.md`
- Next: `eeg-stats` for statistical comparison of microstate parameters between conditions (paired t / cluster perm on transition matrices). `eeg-figure` for topographic map plots and temporal segmentation visualization. For source-level microstates (rare), invoke after `eeg-source`.
