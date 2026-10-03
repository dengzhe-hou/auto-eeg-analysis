---
name: eeg-source
description: "Source localization: scalp EEG → cortical/dipole sources via boundary-element model (BEM), MNE/dSPM/sLORETA/eLORETA, or beamformer. Default head model fsaverage (template); individual MRI requires FreeSurfer. Brainstorm export-only path supported. Use when the user wants to identify intracranial generators of scalp signals."
argument-hint: "[project-dir] [— head-model: fsaverage|individual] [— inverse: dspm|sloreta|eloreta|mne|lcmv]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-source: scalp → cortical sources

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne`** (Python). MNE-Python is the computation backend. Brainstorm path is **consume-only** — user exports source estimates as `.mat`, AEA reads them via `scipy.io.loadmat`.
- **HEAD_MODEL = `fsaverage`** (template). `individual` requires FreeSurfer recon-all output.
- **INVERSE = `dspm`** (default; well-behaved noise normalization). Alternatives: `sloreta`, `eloreta`, `mne`, `lcmv` (beamformer).
- **NOISE_COV_FROM = `prestim_baseline`** — baseline window of epochs.
- **SNR = `3.0`** → `lambda2 = 1.0 / SNR ** 2 = 0.111`.
- **SOURCE_SPACE_SPACING = `oct6`** (4098 sources per hemisphere, ~5 mm resolution).
- **OUTPUT_DIR = `source-stage/`** — Create if missing.
- **SEED = read from ANALYSIS_PLAN.md**, default `42`.
- **EEG_REFERENCE = `average` (mandatory for beamforming)** — set via `raw.set_eeg_reference('average', projection=True)` before source work. A forward-model error at any single physical reference electrode contaminates *all* channels; only the common average is consistent with the leadfield. Never drop channels after re-referencing.
- **BEAMFORMER_REG = `0.05`** (LCMV/DICS spatial-filter regularization; the FieldTrip `'5%'` lambda). For source-space connectivity use `0.1` (the PCC `'10%'` convention).
- **COMMON_FILTER = `true`** — for any between-condition / between-window contrast, build ONE spatial filter (or inverse) on the *pooled* data and apply it to each condition separately.
- **VOLUME_GRID_POS = `10.0` mm** — `setup_volume_source_space(pos=10.0)` for beamformers (the course's 1 cm grid); surface `oct6`/`ico-4` remains the default for distributed MNE/dSPM.
- **DEPTH_EEG = `3.0`** — depth-weighting exponent for minimum-norm inverses on **EEG**. The MNE default `depth=0.8` was validated on MEG; in EEG the skull blurs the leadfield far more, so the superficial bias is much stronger and a heavier weighting (≈2.0–5.0, default 3.0) is required to push solutions toward deeper generators. Do **not** carry the 0.8 MEG value into an EEG inverse. (Lin et al. 2006)
- **COV_METHOD = `auto`** — let `compute_covariance(method='auto')` pick (and cross-validate) among empirical/shrunk/Ledoit-Wolf/factor-analysis estimators rather than guessing one; always follow with the whitening QC below. (Engemann & Gramfort 2015)
- **BEAMFORMER_RANK = `info`** — pass `rank='info'` to `compute_covariance` **and** `make_lcmv`/`make_dics`. Mandatory average reference drops one rank, and ICA/interpolation drop more, so an unregularized full-rank inverse of a rank-deficient covariance is unstable. (Westner et al. 2022)

> Override: `/eeg-source projects/my-study — head-model: fsaverage — inverse: sloreta — backend: mne`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen. **Stop if missing or unfrozen.**
2. `epochs-stage/` — cleaned, epoched `.fif` files per subject per condition (for evoked source estimation).
3. `ENVIRONMENT.json` — to resolve backend.
4. (If `individual`): FreeSurfer `subjects_dir` with completed `recon-all` output per subject.
5. (If `individual`): Digitized electrode positions or fiducials (`.elp`, `.hsp`, or embedded in `.fif` info).

## Phase A — Pre-flight platform check

```
1. Read ENVIRONMENT.json
2. If head_model = individual:
   a. Check freesurfer.available = true  → proceed
   b. If false and OS = Windows native   → STOP: "Install FreeSurfer (Linux/Mac) or run inside WSL2, or switch to head_model=fsaverage"
   c. If false and OS = Linux/Mac        → STOP: "Install FreeSurfer 7.4+ and run recon-all first"
3. If head_model = fsaverage:
   a. Check mne.datasets.fetch_fsaverage() available → proceed
   b. Downloads ~30 MB on first run
4. Check backend availability:
   a. MNE-Python: import mne → OK
   b. Brainstorm: check for exported .mat files in brainstorm-export/ (consume-only)
```

Write `source-stage/PLATFORM_CHECK.md`.

## Phase B — Forward model construction

The forward model maps known source locations to expected scalp potentials.

### Step 1: Source space

```python
import mne

# Template (fsaverage)
subjects_dir = mne.datasets.fetch_fsaverage(verbose=True)
src = mne.setup_source_space(
    subject='fsaverage',
    spacing='oct6',          # 4098 sources/hemisphere
    subjects_dir=subjects_dir,
    add_dist='patch'
)

# Individual MRI
# src = mne.setup_source_space(
#     subject=sub_id,
#     spacing='oct6',
#     subjects_dir=freesurfer_subjects_dir,
#     add_dist='patch'
# )
```

**Volume source space (required for beamformers / non-surface-constrained inverse):**

```python
# Beamformers and volumetric reporting use a 3-D grid, not a cortical surface.
# (bem_sol is built in Step 2 below; build the volume space after the BEM.)
vol_src = mne.setup_volume_source_space(
    subject='fsaverage', pos=10.0,            # 10 mm grid = the course's 1 cm resolution
    bem=bem_sol,                              # restrict grid to inside inner skull
    subjects_dir=subjects_dir)
```

Use the surface space (`oct6`/`ico-4`) for distributed MNE/dSPM/sLORETA/eLORETA; use the volume space for LCMV/DICS power maps and for volumetric atlas (AAL) labeling.

### Step 2: BEM model

Boundary Element Model with 3 layers for EEG (brain, skull, scalp):

```python
# Template (fsaverage) — use precomputed BEM
model = mne.make_bem_model(
    subject='fsaverage',
    ico=4,                   # BEM mesh resolution
    conductivity=(0.3, 0.02, 0.3),   # brain, skull, scalp (S/m) — see note below
    subjects_dir=subjects_dir
)
bem_sol = mne.make_bem_solution(model)

# Individual MRI — requires watershed BEM surfaces from FreeSurfer
# mne.bem.make_watershed_bem(sub_id, subjects_dir=freesurfer_subjects_dir)
# model = mne.make_bem_model(subject=sub_id, ...)
# bem_sol = mne.make_bem_solution(model)
```

**BEM conductivity values:**
- Default here: brain=0.3, **skull=0.02**, scalp=0.3 S/m (brain:skull ≈ 1:15–20). This replaces the legacy 0.006 (1:50) tuple. The McCann et al. (2019) meta-analysis of 56 studies puts the bulk-skull conductivity near **0.02 S/m**, not 0.006 — the old value substantially over-insulates the skull and inflates localization error.
- The historical 0.006 (1:50) and 0.0042 (1:72) values are now considered too low; treat them only as legacy reproductions of older pipelines.
- For a 3-sublayer skull model (when geometry permits) the meta-analytic values are ≈0.048 spongiform / 0.007 inner-compact / 0.005 outer-compact S/m.
- Skull conductivity remains the dominant uncertainty and scales localization error directly, so prefer individual calibration when available; absent that, the meta-analytic 0.02 is the best fixed default. (McCann, Pisano & Beltrachini 2019)

### Step 3: Coregistration (electrode-to-head alignment)

```python
# Template (fsaverage) with standard montage — automatic
info = mne.io.read_info(epochs_fif_path)
# If using standard montage (e.g., standard_1020):
montage = mne.channels.make_standard_montage('standard_1020')
info.set_montage(montage)
trans = 'fsaverage'  # built-in identity transform for fsaverage + standard montage

# Individual MRI — requires manual/semi-automatic coregistration
# Option 1: GUI (requires display)
# mne.gui.coregistration(subject=sub_id, subjects_dir=freesurfer_subjects_dir)
# Option 2: Automated with digitized fiducials
# trans = mne.read_trans(trans_fif_path)  # from previously saved coregistration
```

**Coregistration is the hardest step**. If user has digitized fiducials (`.elp`), use those. Otherwise, standard montage on fsaverage is acceptable but introduces ~5–10 mm localization error.

**Programmatic coregistration for individual MRI (headless-safe, two-step like the course's fiducial→interactive refinement):**

```python
from mne.coreg import Coregistration
coreg = Coregistration(info, subject=sub_id, subjects_dir=freesurfer_subjects_dir,
                       fiducials='estimated')   # or 'auto' / a fiducials file
coreg.fit_fiducials(verbose=True)              # coarse: LPA/Nasion/RPA alignment
coreg.fit_icp(n_iterations=20, verbose=True)   # refine on head-shape points (analogue of interactive nudge)
coreg.omit_head_shape_points(distance=5e-3)    # drop outlier digitized points
coreg.fit_icp(n_iterations=20, verbose=True)
trans = coreg.trans
mne.write_trans(f'source-stage/coreg/{sub_id}-trans.fif', trans, overwrite=True)
```

**ALWAYS verify the fit visually before computing the forward solution** — a misaligned montage silently biases every source estimate:

```python
fig = mne.viz.plot_alignment(
    info, trans=trans, subject=sub_id, subjects_dir=subjects_dir,
    surfaces='head-dense', coord_frame='mri', eeg=['original', 'projected'])
# Sensors must sit ON the scalp; 'projected' shows where they land on the head surface.
```

For headless servers, save the figure (or `coreg.compute_dig_mri_distances()` summary) instead of an interactive window. The course warns that template-fiducial conventions differ — electrodes can end up *below* the skin anteriorly and *floating* posteriorly — so never trust an unverified fit.

### Step 4: Forward solution

```python
fwd = mne.make_forward_solution(
    info,
    trans=trans,
    src=src,
    bem=bem_sol,
    meg=False,
    eeg=True,
    mindist=5.0,    # exclude sources closer than 5mm to inner skull
    n_jobs=4,
    verbose=True
)
# Save for reuse
mne.write_forward_solution(f'source-stage/forward/{sub}-fwd.fif', fwd, overwrite=True)
```

## Phase C — Noise covariance estimation

```python
# From prestimulus baseline of epochs
epochs = mne.read_epochs(epochs_fif_path, preload=True)
noise_cov = mne.compute_covariance(
    epochs,
    tmin=None, tmax=0,        # baseline period
    method='auto',            # cross-validate empirical/shrunk/LW/FA, pick best (do NOT hand-guess)
    rank='info'               # respect the data rank recorded in info (avg-ref + ICA/interp reduce it)
)
# Regularize if needed (often unnecessary once method='auto'+rank='info' are used)
# noise_cov = mne.cov.regularize(noise_cov, info, eeg=0.1, rank='info')

# Save
mne.write_cov(f'source-stage/covariance/{sub}-cov.fif', noise_cov, overwrite=True)
```

**Mandatory whitening QC — never skip.** A wrong noise covariance does not error; it silently produces plausible-but-wrong sources. After estimating the covariance, whiten the evoked response and inspect the global field power of the whitened data: a correct covariance makes the whitened GFP hover around **1.0** in the baseline (it is then white, i.e. unit variance). Departures (GFP ≫ 1 or ≪ 1) mean the covariance — and therefore every downstream source estimate — is miscalibrated.

```python
evoked = epochs['condition_name'].average()
fig = evoked.plot_white(noise_cov, time_unit='s')   # whitened GFP should sit ~1.0
fig.savefig(f'source-stage/covariance/{sub}-whitening-check.png')
```

(Engemann & Gramfort 2015, on automated covariance selection + the whitening sanity check.)

**Covariance estimation guidelines:**
- `method='auto'` subsumes the old manual choice; it cross-validates empirical/shrunk/Ledoit-Wolf/factor-analysis and is especially important when N_trials < N_channels (where `'empirical'` is rank-deficient and ill-conditioned).
- Always pass `rank='info'` (not `None`): mandatory average reference drops one rank and ICA/PCA/interpolation drop more, so the true rank is below N_channels.
- If empty-room data is available (MEG mainly), use that instead of baseline. For EEG, baseline is standard.

## Phase D — Inverse operator and source estimation

### Minimum-norm methods (dSPM, sLORETA, eLORETA, MNE)

```python
from mne.minimum_norm import make_inverse_operator, apply_inverse

# Build inverse operator
inverse_operator = make_inverse_operator(
    info,
    fwd,
    noise_cov,
    loose=0.2,        # orientation constraint (0=fixed, 1=free)
    depth=3.0,        # DEPTH_EEG — EEG needs heavier depth weighting than the MEG default 0.8
    verbose=True
)
# depth=0.8 is the MEG-validated value; for EEG the skull blur makes the superficial
# bias far stronger, so use DEPTH_EEG (≈2.0–5.0, default 3.0). See Constants. (Lin et al. 2006)

# Apply to evoked data
evoked = epochs['condition_name'].average()
snr = 3.0
lambda2 = 1.0 / snr ** 2

# dSPM (default) — noise-normalized MNE
stc_dspm = apply_inverse(evoked, inverse_operator, lambda2, method='dSPM', verbose=True)

# sLORETA — standardized, zero localization bias for single dipoles
stc_sloreta = apply_inverse(evoked, inverse_operator, lambda2, method='sLORETA', verbose=True)

# eLORETA — exact LORETA, zero localization bias for any number of dipoles
stc_eloreta = apply_inverse(evoked, inverse_operator, lambda2, method='eLORETA', verbose=True)

# MNE — basic minimum norm, tends to favor superficial sources
stc_mne = apply_inverse(evoked, inverse_operator, lambda2, method='MNE', verbose=True)

# Save source estimate
stc_dspm.save(f'source-stage/{sub}/{sub}-{cond}-dspm', overwrite=True)
```

**Method comparison:**
| Method | Normalization | Localization bias | Units | Best for |
|--------|--------------|-------------------|-------|----------|
| MNE | None | Superficial bias | Am | When depth weighting is tuned |
| dSPM | Noise | Moderate | Unitless (F-stat) | General purpose, well-understood |
| sLORETA | Noise+source | Zero (single dipole) | Unitless | When precise localization matters |
| eLORETA | Exact | Zero (any config) | Am/m^2 | Gold standard for localization |

### LCMV Beamformer

**Between-condition / between-window contrasts — use a common filter.** When you will compare source power or connectivity across two conditions (or active vs baseline), do NOT compute a separate filter per condition: a condition that happens to have more power changes the data covariance and therefore the filter, which by itself biases the contrast. Compute the data covariance on the *pooled* epochs (both conditions appended, or the full pre+post window), build one `make_lcmv`/`make_dics` filter from it, then apply that single filter to each condition's epochs separately. Report the relative change `(active - baseline)/baseline`.

Beamformers are spatial filters that pass activity from a target location while suppressing other sources:

```python
from mne.beamformer import make_lcmv, apply_lcmv

# Data covariance (from active window)
data_cov = mne.compute_covariance(
    epochs['condition_name'],
    tmin=0.0, tmax=0.5,     # active window
    method='auto',          # cross-validated estimator (see Phase C)
    rank='info'             # avg-ref + ICA/interp reduce the rank
)

# Build LCMV spatial filter
filters = make_lcmv(
    info,
    fwd,
    data_cov,
    reg=0.05,                # regularization
    noise_cov=noise_cov,
    pick_ori='max-power',    # or 'normal' for fixed orientation
    weight_norm='unit-noise-gain',
    rank='info'              # NOT None — the covariance is rank-deficient after avg-ref + ICA; an
                             # unregularized full-rank inverse is unstable (Westner et al. 2022)
)

# Apply to evoked
stc_lcmv = apply_lcmv(evoked, filters, verbose=True)
stc_lcmv.save(f'source-stage/{sub}/{sub}-{cond}-lcmv', overwrite=True)
```

**Beamformer notes:**
- LCMV is best for localizing focal sources with known timing (e.g., auditory cortex response at 100 ms).
- Not suitable for correlated sources (two sources active simultaneously suppress each other).
- Data covariance should span the active window; noise covariance from baseline.
- `weight_norm='unit-noise-gain'` produces neural activity index (NAI), which is comparable across subjects.

### DICS Beamformer (frequency-domain)

DICS (Dynamic Imaging of Coherent Sources) is the frequency-domain analogue of LCMV — use it to localize *oscillatory power* at a target frequency band rather than a time-domain peak. **Average reference is mandatory** (see Constants).

```python
from mne.time_frequency import csd_morlet
from mne.beamformer import make_dics, apply_dics_csd

foi = 18.0            # target frequency (Hz); the course localizes a single foi
freqs = [foi]

# fwd_vol = forward solution built from the volume source space (vol_src, Phase B Step 1)
# Build ONE common filter from the pooled (active + baseline) epochs — see Critical Rules
csd_all  = csd_morlet(epochs, frequencies=freqs, tmin=-0.5, tmax=0.9, n_cycles=4)
filters  = make_dics(info, fwd_vol, csd_all, reg=0.05,   # 5% lambda; fwd from volume src
                     pick_ori='max-power', real_filter=True, depth=1.0,
                     rank='info')                        # rank-aware: avg-ref + ICA drop rank (Westner et al. 2022)

# Apply the SAME filter to each window/condition
csd_act  = csd_morlet(epochs, frequencies=freqs, tmin=0.4, tmax=0.9, n_cycles=4)
csd_base = csd_morlet(epochs, frequencies=freqs, tmin=-0.5, tmax=0.0, n_cycles=4)
stc_act,  _ = apply_dics_csd(csd_act,  filters)
stc_base, _ = apply_dics_csd(csd_base, filters)

# Report RELATIVE change (active - baseline)/baseline, matching the course
stc_ratio = stc_act.copy()
stc_ratio.data = (stc_act.data - stc_base.data) / stc_base.data
stc_ratio.save(f'source-stage/{sub}/{sub}-{cond}-dics-relpow', overwrite=True)
```

**DICS notes:**
- Pre/post windows must be **equal length** (equal degrees of freedom in the CSD) so the relative-power contrast is unbiased.
- `reg=0.05` (5% lambda) is the default; `real_filter=True` avoids spurious imaginary components.
- DICS and LCMV share the beamformer algorithm; DICS operates on the cross-spectral density (CSD), LCMV on the time-domain data covariance. For single-trial source Fourier coefficients feeding connectivity, apply a filter to epochs and pass the source time courses to `mne_connectivity.spectral_connectivity_epochs` (the analogue of FieldTrip's PCC).

### Brainstorm consume-only path

Brainstorm users export source estimates; AEA reads them:

```python
import scipy.io as sio

# Read Brainstorm-exported source file
mat = sio.loadmat('brainstorm-export/sub-01_cond_sources.mat')
# Expected fields: ImageGridAmp (n_sources x n_times), Time, Atlas, ...
source_data = mat['ImageGridAmp']
time = mat['Time'].flatten()
# Convert to MNE SourceEstimate for downstream compatibility
```

## Phase E — ROI extraction

Extract time courses per anatomical region for downstream connectivity or statistical analysis:

```python
# Use Desikan-Killiany atlas (aparc)
labels = mne.read_labels_from_annot(
    'fsaverage',
    parc='aparc',            # or 'aparc.a2009s' for Destrieux, 'HCPMMP1' for Glasser
    subjects_dir=subjects_dir
)

# Extract label time courses
label_ts = mne.extract_label_time_course(
    stc_dspm,
    labels,
    src,
    mode='mean_flip',        # sign-flip to align dipole orientations, then mean
    allow_empty=True
)
# label_ts shape: (n_labels, n_times)

# Save ROI time courses
np.savez(f'source-stage/{sub}/{sub}-{cond}-roi_ts.npz',
         label_ts=label_ts,
         label_names=[l.name for l in labels],
         times=stc_dspm.times)
```

**ROI extraction modes:**
- `'mean'`: Simple average across vertices in the label. Can cancel out if dipoles have opposite orientations.
- `'mean_flip'`: Flip sign of vertices whose orientation is opposite to the dominant direction, then average. Recommended.
- `'pca_flip'`: First PCA component, sign-flipped. Best for preserving variance.
- `'max'`: Maximum absolute value across vertices. Most focal but noisiest.

**Available atlases:**
- `'aparc'` (Desikan-Killiany): 68 cortical regions. Standard, coarse.
- `'aparc.a2009s'` (Destrieux): 148 regions. Finer parcellation.
- `'HCPMMP1'` (Glasser): 360 regions. Finest, based on HCP multimodal data.

**Source-space functional connectivity (route to `eeg-connectivity`).** To compute connectivity between brain regions rather than scalp channels, first reduce dimensionality to ROI time courses (`extract_label_time_course` above), then feed `label_ts` to `mne_connectivity.spectral_connectivity_epochs`. Running connectivity on parcellated ROIs (not on all 8196 vertices) controls dimensionality and multiple comparisons. This is the source-localization arm of volume-conduction mitigation: source/ROI signals plus a VC-insensitive metric (imaginary coherency, wPLI) is the most defensible combination ('double insurance'). See `eeg-connectivity` for the metric choice and for the sensor-space alternative (surface Laplacian / `mne.preprocessing.compute_current_source_density` before FC).

**Ghost-interactions caveat for networks of >2 nodes.** Pairwise leakage corrections — orthogonalization, imaginary coherency, wPLI — only cancel zero-lag mixing *between the two sources in a pair*. When three or more sources interact at near-zero lag, residual leakage produces spurious "ghost" interactions that no bivariate metric or pairwise orthogonalization can remove, and it can additionally *mask* genuine interactions. Rule: treat dense zero-lag triangles in source-space FC as suspect, and for any putative network (>2 nodes) corroborate with multivariate / hyperedge-aware methods rather than stitching a network from independent pairwise estimates. Cite: Palva, J. M., Wang, S. H., Palva, S., Zhigalov, A., Monto, S., Brookes, M. J., Schoffelen, J. M., & Jerbi, K. (2018). Ghost interactions in MEG/EEG source space: A note of caution on inter-areal coupling measures. NeuroImage, 173, 632–643.

## Phase F — Write outputs

### `source-stage/<sub>/<sub>-<cond>-<method>-stc.h5`
MNE SourceEstimate saved via `stc.save()`.

### `source-stage/<sub>/<sub>-<cond>-roi_ts.npz`
Contains: `label_ts` (n_labels × n_times), `label_names`, `times`.

### `source-stage/forward/<sub>-fwd.fif`
Forward solution for reuse.

### `source-stage/covariance/<sub>-cov.fif`
Noise covariance for reuse.

### `source-stage/SOURCE_PARAMS.json`
```json
{
  "head_model": "fsaverage",
  "source_space": "oct6",
  "n_sources_per_hemi": 4098,
  "bem_layers": 3,
  "conductivity": [0.3, 0.02, 0.3],
  "inverse_method": "dSPM",
  "snr": 3.0,
  "lambda2": 0.111,
  "loose": 0.2,
  "depth": 3.0,
  "noise_cov_method": "auto",
  "noise_cov_rank": "info",
  "noise_cov_tmin": null,
  "noise_cov_tmax": 0,
  "roi_atlas": "aparc",
  "roi_extraction_mode": "mean_flip",
  "n_rois": 68
}
```

### Reporting source results (group/MNI)

A defensible source report follows a fixed chain:

1. **Morph individual STCs to a common space** before any group display or MNI reporting:
   ```python
   morph = mne.compute_source_morph(stc, subject_from=sub_id, subject_to='fsaverage',
                                    subjects_dir=subjects_dir)
   stc_fs = morph.apply(stc)
   ```
   (For fsaverage-template analyses every subject is already in fsaverage space, so this is a no-op — but state that explicitly.)
2. **Threshold / mask the displayed map and report the threshold** (e.g. `clim=dict(kind='value', lims=[...])`, or the cluster-test mask). Never show an unmasked, unthresholded blob.
3. **Name peaks/clusters with a named atlas and report MNI coordinates** — `mne.read_labels_from_annot` (Desikan-Killiany / Destrieux) for surface, or a volumetric AAL atlas via `extract_label_time_course` for volume STCs.
4. **Render an inflated-surface or glass-brain figure** (`stc.plot(surface='inflated', hemi='both', ...)` or `mne.viz.plot_volume_source_estimates`).

Feed `eeg-methods-text` the boilerplate: head model (template fsaverage 3-layer BEM vs individual), inverse method + `lambda2`/SNR (or beamformer `reg`), noise- and data-covariance windows, source-space resolution, and the atlas used for labeling.

### Append to `FINDINGS.md`
```markdown
## Source localization: [condition]
- Method: [dSPM / sLORETA / eLORETA / LCMV], head model: [fsaverage / individual]
- Source space: [oct6], BEM: [3-layer], SNR: [3.0]
- ROI atlas: [aparc], extraction mode: [mean_flip]
- Peak activation: [region], latency: [time ms], amplitude: [value]
```

## Phase G — Sanity checks

All must pass before declaring success:

- [ ] Forward solution exists and has correct number of sources (2 × 4098 for oct6).
- [ ] Noise covariance rank matches data rank (after ICA/PCA/interpolation) and was estimated with `method='auto'`, `rank='info'`.
- [ ] **Whitening check passed**: `evoked.plot_white(noise_cov)` saved and whitened GFP ≈ 1.0 in baseline (covariance is correctly calibrated).
- [ ] Depth weighting set to the EEG value (`DEPTH_EEG`, default 3.0) — not the MEG default 0.8 — for minimum-norm inverses.
- [ ] Source estimate is not all zeros or all identical values.
- [ ] Peak source activation occurs in plausible brain region for the task (e.g., auditory cortex for auditory stimuli).
- [ ] ROI time courses have the expected number of labels and time points.
- [ ] SOURCE_PARAMS.json exists and documents all parameters.
- [ ] PLATFORM_CHECK.md exists.
- [ ] EEG was set to **common-average reference** (`set_eeg_reference('average', projection=True)`) before forward/inverse — mandatory for beamforming; recommended for all inverse methods.
- [ ] Coregistration was **visually verified** (`plot_alignment` saved) and sensors lie on the scalp — not the default identity/unfitted trans.
- [ ] For any between-condition contrast, a **single common spatial filter** was used (not one filter per condition).
- [ ] If DICS/LCMV contrast: pre and post windows are **equal length**.

## Critical Rules

- **Never** use a 1-layer BEM for EEG — EEG requires 3 layers (brain, skull, scalp). 1-layer is only acceptable for MEG.
- **Never** interpret source localization results with millimeter precision — EEG source localization has centimeter-scale accuracy at best, even with individual MRI.
- **Never** compare absolute source amplitudes across subjects without normalization (dSPM/sLORETA provide this; raw MNE does not).
- **Never** skip coregistration verification — misaligned electrodes produce systematically biased source estimates.
- **Never** use LCMV beamformer for correlated sources (e.g., bilateral auditory cortex activation) — beamformers suppress correlated sources by design.
- **Never** run a beamformer (LCMV/DICS) on non-average-referenced EEG — a forward-model error at the reference electrode contaminates all channels. Set `set_eeg_reference('average', projection=True)` first, and never drop channels afterward.
- **Never** estimate a separate spatial filter per condition when contrasting conditions — build ONE filter on pooled data and apply it to each condition; otherwise the filter itself encodes the condition difference and biases the contrast.
- **Never** compute the forward solution before verifying coregistration with `plot_alignment` — the BEM surfaces, source space, and montage must share one coordinate frame and one unit (mm) or the leadfield is silently wrong.
- **Never** claim voxel-precise peaks from a template BEM with template electrode positions — report coarse lobar/ROI/network-level localization only (see Domain Knowledge).
- **Never** change SNR/lambda2 to make results "look better" — use the pre-registered value.

## Domain Knowledge (distilled from source localization methodology literature)

### Review of inverse methods (Grech et al. 2008, Journal of NeuroEngineering and Rehabilitation)

- Comprehensive review comparing MNE, LORETA, sLORETA, LCMV, MUSIC, and dipole fitting methods for EEG source localization.
- **Key findings**:
  - No single method is universally best. Choice depends on the expected source configuration (focal vs. distributed, single vs. multiple).
  - MNE tends to produce diffuse solutions biased toward superficial sources. Depth weighting partially corrects this.
  - LORETA family (sLORETA, eLORETA) imposes spatial smoothness, producing blurred but well-localized solutions.
  - Beamformers excel for focal sources but fail for correlated sources.
  - All methods are sensitive to forward model accuracy (head model, electrode positions).
- **Recommendation**: Use dSPM or sLORETA as default for distributed source estimation; LCMV for focal source localization with known timing.
- Cite: Grech, R., Cassar, T., Muscat, J., Camilleri, K. P., Fabri, S. G., Zervakis, M., ... & Vanrumste, B. (2008). Review on solving the inverse problem in EEG source analysis. Journal of NeuroEngineering and Rehabilitation, 5(1), 25.

### eLORETA (Pascual-Marqui 2007, arXiv:0710.3341)

- eLORETA achieves exact (zero-error) localization for any number and configuration of point sources, unlike sLORETA which is exact only for single dipoles.
- The key insight: eLORETA uses a particular form of weighted minimum norm that makes the localization kernel a true delta function at each source location.
- **Practical implications**:
  - eLORETA is the method of choice when precise localization is the goal and the source configuration is unknown.
  - Computational cost is higher than sLORETA but negligible on modern hardware.
  - Available in MNE-Python as `method='eLORETA'` in `apply_inverse()`.
- Cite: Pascual-Marqui, R. D. (2007). Discrete, 3D distributed, linear imaging methods of electric neuronal activity. arXiv:0710.3341. (The 2002 Pascual-Marqui paper is the sLORETA reference, not eLORETA.)

### LCMV beamformer (Van Veen et al. 1997, IEEE Transactions on Biomedical Engineering)

- Linearly Constrained Minimum Variance (LCMV) beamformer is a spatial filter that passes signals from a target location with unit gain while minimizing total output power (suppressing interference).
- **How it works**: For each source location, a weight vector w is computed as w = (C^-1 * L) / (L' * C^-1 * L), where C is the data covariance and L is the lead field.
- **Strengths**:
  - Excellent spatial resolution for focal, uncorrelated sources.
  - Adaptive — uses the data covariance to suppress interfering sources.
  - Does not require explicit noise covariance (though it helps for NAI computation).
- **Weaknesses**:
  - Signal cancellation for correlated sources (e.g., bilateral activation).
  - Requires sufficient data for stable covariance estimation (N_samples >> N_channels).
  - Sensitive to forward model errors (more than MNE-based methods).
- **Neural Activity Index (NAI)**: Normalize beamformer output by the noise projection to get a unitless, cross-subject-comparable measure. In MNE: `weight_norm='unit-noise-gain'`.
- Cite: Van Veen, B. D., van Drongelen, W., Yuchtman, M., & Suzuki, A. (1997). Localization of brain electrical activity via linearly constrained minimum variance spatial filtering. IEEE Transactions on Biomedical Engineering, 44(9), 867–880.

### Interpretation of spatial patterns vs filters (Haufe et al. 2014, NeuroImage)

- **Critical distinction**: When decoding brain states from EEG (e.g., via CSP, LDA, or beamformers), the spatial filter weights do NOT reflect the spatial distribution of neural sources. Only the corresponding spatial patterns (activation patterns) do.
- **Why this matters for source analysis**:
  - Beamformer weights are spatial filters. Plotting beamformer weights on the scalp is meaningless for source interpretation.
  - To interpret which sources are active, compute the activation pattern: A = Cov_x * W * (W' * Cov_x * W)^-1, where W are the filter weights and Cov_x is the data covariance.
  - This applies to any linear spatial filter, including CSP, ICA (mixing matrix is the pattern, unmixing matrix is the filter), and beamformers.
- **Practical rule**: Always plot activation patterns (forward model), never filter weights (backward model), when making claims about neural sources.
- Cite: Haufe, S., Meinecke, F., Gorgen, K., Dahne, S., Haynes, J. D., Blankertz, B., & Biessmann, F. (2014). On the interpretation of weight vectors of linear models in multivariate neuroimaging. NeuroImage, 87, 96–110.

### dSPM — dynamic statistical parametric mapping (Dale et al. 2000, Neuron)

- dSPM normalizes the MNE solution by the estimated noise at each source location, yielding a unitless F-statistic-like map.
- **How it works**: For each source, divide the MNE amplitude by the square root of the corresponding diagonal entry of the noise-normalized resolution kernel. This makes the output reflect signal-to-noise ratio rather than absolute amplitude.
- **Advantages**:
  - Noise-normalized → comparable across subjects and sessions without further standardization.
  - Well-understood statistical behavior: under the null hypothesis, dSPM values follow an F-distribution.
  - Fast to compute (same cost as MNE, just one extra normalization step).
- **Limitations**:
  - Still inherits MNE's superficial bias (depth weighting mitigates but does not eliminate).
  - Non-zero localization bias — sLORETA and eLORETA are preferable when localization precision is the primary goal.
- **When to use**: Default choice for group-level source-space analyses where cross-subject comparability matters more than pinpoint localization.
- Cite: Dale, A. M., Liu, A. K., Fischl, B. R., Buckner, R. L., Belliveau, J. W., Lewine, J. D., & Halgren, E. (2000). Dynamic statistical parametric mapping: combining fMRI and MEG for high-resolution imaging of cortical activity. Neuron, 26(1), 55–67.

### MNE-Python forward/inverse implementation (Gramfort et al. 2014, NeuroImage)

- Reference implementation of the forward modeling and inverse solution pipeline used throughout this skill.
- **Key contributions**:
  - Unified Python API for BEM construction (`make_bem_model`, `make_bem_solution`), source space setup (`setup_source_space`), forward computation (`make_forward_solution`), and inverse estimation (`make_inverse_operator`, `apply_inverse`).
  - Tight integration with FreeSurfer for surface-based source spaces and cortical parcellations.
  - Support for multiple inverse methods (MNE, dSPM, sLORETA, eLORETA) through a single `method=` parameter.
  - Efficient handling of large source spaces (oct6 = 8196 sources) via sparse matrix operations.
- **Practical notes**:
  - Always use `mne.datasets.fetch_fsaverage()` for template analyses — this fetches BEM surfaces, source spaces, and the `fsaverage` subject directory.
  - Forward solutions are deterministic and can be cached/reused across inverse methods.
  - MNE-Python version must be ≥ 1.0 for stable eLORETA support.
- Cite: Gramfort, A., Luessi, M., Larson, E., Engemann, D. A., Strohmeier, D., Brodbeck, C., ... & Hämäläinen, M. S. (2014). MNE software for processing MEG and EEG data. NeuroImage, 86, 446–460.

### FreeSurfer aparc parcellation (Desikan et al. 2006, NeuroImage)

- The Desikan-Killiany atlas (`aparc`) parcellates each hemisphere into 34 cortical regions (68 total) based on sulcal and gyral landmarks.
- **Role in source localization**: After computing source estimates on the cortical surface, ROI extraction (`mne.extract_label_time_course`) uses atlas labels to aggregate vertex-level activity into region-level time courses.
- **Atlas hierarchy**:
  - `aparc` (Desikan-Killiany): 68 regions. Coarse but highly reproducible across subjects and studies. Standard choice for hypothesis-driven analyses with anatomically defined ROIs.
  - `aparc.a2009s` (Destrieux): 148 regions. Finer parcellation based on sulcal depth; better for distinguishing adjacent cortical areas.
  - `HCPMMP1` (Glasser): 360 regions. Multimodal parcellation from the Human Connectome Project; finest resolution but requires careful interpretation.
- **Practical guidance**:
  - Use `aparc` unless the hypothesis requires finer spatial resolution.
  - When using `fsaverage` template, all three atlases are available via `mne.read_labels_from_annot()`.
  - For individual MRI, the atlas must be mapped to the subject's cortical surface via FreeSurfer's `mri_annotation2label` or `mne.read_labels_from_annot(subject=sub_id)`.
  - Label names follow the convention `regionname-lh` / `regionname-rh` (e.g., `superiortemporal-lh`).
- Cite: Desikan, R. S., Ségonne, F., Fischl, B., Quinn, B. T., Dickerson, B. C., Blacker, D., ... & Killiany, R. J. (2006). An automated labeling system for subdividing the human cerebral cortex on MRI scans into gyral based regions of interest. NeuroImage, 31(3), 968–980.

### When is EEG source localization justified? (template-BEM, low-density caveats)

- **Common-average reference is a hard prerequisite for beamforming**, and recommended for all inverse methods: EEG measures potential *differences*, so an error in the forward model at any single reference electrode propagates to every channel. Re-reference to the common average before source work and do not drop channels afterward.
- **Template BEM + template electrodes → coarse claims only.** With no individual MRI and no digitized electrode positions (the common 'fsaverage + standard_1020' case), conductivity and geometry errors are large; co-registration of a standard montage to a template head is imperfect (electrodes sink below or float above the scalp and must be refined). Report lobar / ROI / network-level localization, never millimeter-precise peaks.
- **Spatial resolution scales with electrode count.** Low-density montages (<32 ch) give poor depth and spatial resolution; 64–256 channels are preferred for any localization claim beyond gross lateralization. Digitized electrode positions and an individual MRI (FreeSurfer recon-all + watershed/`make_bem_model` BEM) materially improve accuracy.
- **Skull conductivity is the dominant uncertainty.** Use **0.02 S/m** (brain:skull ≈ 1:15–20) as the fixed default, per the McCann et al. (2019) meta-analysis of 56 studies — the legacy 1:50 (0.006 S/m) tuple over-insulates the skull and inflates localization error. True skull conductivity varies with age and individual, so individual calibration beats any fixed value; absent that, 0.02 is the meta-analytic best estimate (3-sublayer alternative: 0.048 spongiform / 0.007 inner-compact / 0.005 outer-compact).
- Cite: Michel, C. M., & Brunet, D. (2019). EEG source imaging: a practical review of the analysis steps. Frontiers in Neurology, 10, 325. (See also Brodbeck et al. 2011, Brain, for high-density EEG source imaging clinical validation, and Vorwerk et al. 2014, NeuroImage, on head-model/conductivity sensitivity.)
- Cite: McCann, H., Pisano, G., & Beltrachini, L. (2019). Variation in reported human head tissue electrical conductivity values. Brain Topography, 32(5), 825–858.

### EEG-specific inverse defaults: depth weighting, covariance, rank (Lin / Engemann / Westner)

- **Depth weighting must be heavier for EEG than the MEG default.** MNE's `depth=0.8` was tuned on MEG; the skull blurs the EEG leadfield much more, so the minimum-norm superficial bias is stronger and needs a larger exponent. Use `DEPTH_EEG ≈ 2.0–5.0` (default 3.0) in `make_inverse_operator`. Carrying 0.8 into an EEG inverse leaves solutions pinned to the cortical surface. Cite: Lin, F. H., Witzel, T., Ahlfors, S. P., Stufflebeam, S. M., Belliveau, J. W., & Hämäläinen, M. S. (2006). Assessing and improving the spatial accuracy in EEG source localization by depth-weighted minimum-norm estimates. NeuroImage, 31(1), 160–171.
- **Estimate the covariance automatically and verify by whitening.** Prefer `compute_covariance(method='auto')` (cross-validated across empirical/shrunk/Ledoit-Wolf/factor-analysis) over hand-picking one estimator, then **always** run the whitening check (`evoked.plot_white(noise_cov)`): the whitened global field power should sit near 1.0 in baseline. A miscalibrated covariance produces plausible-but-wrong sources with no error message. Cite: Engemann, D. A., & Gramfort, A. (2015). Automated model selection in covariance estimation and spatial whitening of MEG and EEG signals. NeuroImage, 108, 328–342.
- **Make the covariance inverse rank-aware.** Mandatory average reference removes one rank and ICA/interpolation remove more, so pass `rank='info'` to `compute_covariance` and to `make_lcmv`/`make_dics` (not `rank=None`). An unregularized full-rank inverse of a rank-deficient covariance is numerically unstable and corrupts the spatial filter. Cite: Westner, B. U., Dalal, S. S., Gramfort, A., Litvak, V., Mosher, J. C., Oostenveld, R., & Schoffelen, J. M. (2022). A unified view on beamformers for M/EEG source reconstruction. NeuroImage, 246, 118789.

### DICS frequency-domain beamforming (Gross et al. 2001, PNAS)

- DICS (Dynamic Imaging of Coherent Sources) is the frequency-domain extension of the LCMV beamformer: it replaces the time-domain data covariance with the cross-spectral density (CSD) at a target frequency, yielding source-level power and coherence at that frequency.
- **Practical recipe** (matches the standard EEG implementation): common-average reference; split into equal-length baseline and active windows; estimate the CSD (`mne.time_frequency.csd_morlet` or `csd_multitaper`) at the band of interest; build ONE filter on the pooled CSD (`make_dics`, `reg=0.05`, `pick_ori='max-power'`, `real_filter=True`); apply the same filter to each window via `apply_dics_csd`; report relative power `(active − baseline)/baseline`.
- **Equal-window requirement**: the baseline and active CSDs must have equal duration (equal degrees of freedom) or the relative-power contrast is biased toward the longer window.
- **DICS vs LCMV vs PCC**: same beamformer algorithm; DICS/LCMV are memory-friendly and return power, PCC returns single-trial Fourier coefficients for connectivity at higher memory cost. In MNE, source-space connectivity is obtained by applying a filter to epochs and feeding the source time courses to `mne_connectivity.spectral_connectivity_epochs`.
- Cite: Gross, J., Kujala, J., Hämäläinen, M., Timmermann, L., Schnitzler, A., & Salmelin, R. (2001). Dynamic imaging of coherent sources: studying neural interactions in the human brain. Proceedings of the National Academy of Sciences, 98(2), 694–699.

## Platform-specific gotchas

- **Windows native**: fsaverage path works; individual MRI does not (FreeSurfer not native). Force degrade to fsaverage or route through WSL2.
- **macOS Apple Silicon**: FreeSurfer 7.4+ ships ARM binaries; OK natively. MNE-Python works natively.
- **Coregistration**: Hardest step. If user has digitized fiducials (`.elp`), use those; otherwise standard montage on fsaverage is acceptable but document the limitation.
- **Memory**: Source estimation with oct6 (8196 sources) is manageable. oct5 (1026/hemi) is faster for prototyping. oct7 (16386/hemi) requires >16 GB RAM.

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing or unfrozen | Stop. Ask user to fill and freeze the plan. |
| FreeSurfer not installed (individual MRI) | Degrade to fsaverage. Log in PLATFORM_CHECK.md. |
| Coregistration GUI not available (headless server) | Use standard montage on fsaverage (automated). Document limitation. |
| Noise covariance is rank-deficient | Use `method='shrunk'` or reduce rank explicitly. Check if ICA reduced data rank. |
| Forward solution has 0 sources | BEM surfaces are malformed. Regenerate with `mne.bem.make_watershed_bem`. |
| Source estimate is all zeros | Check: epochs loaded correctly? Noise cov and forward from same subject? Lambda2 too large? |
| Sources look plausible but are wrong / whitened GFP far from 1.0 | Noise covariance is miscalibrated. Re-estimate with `method='auto'`, `rank='info'`, and re-run `evoked.plot_white(noise_cov)` until baseline GFP ≈ 1.0. |
| Minimum-norm solution stuck on the cortical surface (no deep sources) | Depth weighting too light — using the MEG default `depth=0.8` on EEG. Raise to `DEPTH_EEG` (≈3.0). |
| Beamformer filter unstable / covariance inverse blows up | Covariance is rank-deficient after avg-ref + ICA. Pass `rank='info'` to `compute_covariance` and `make_lcmv`/`make_dics`. |
| Peak activation in white matter | Forward model error or wrong coregistration. Verify BEM and electrode alignment. |
| LCMV output shows bilateral suppression | Expected — switch to MNE/dSPM for bilateral sources. Document in FINDINGS.md. |
| Beamformer source map is biased / unstable | Check EEG is common-average referenced (`set_eeg_reference('average', projection=True)`); a non-average reference contaminates all channels. |
| Between-condition source contrast looks too strong | A separate filter was likely computed per condition. Rebuild ONE filter on pooled data and reapply to each condition. |
| DICS relative-power contrast is biased | Baseline and active windows have unequal length. Use equal-duration windows so the CSDs share degrees of freedom. |
| Source localization ran with default/identity trans | Coregistration was never fitted/verified. Fit with `Coregistration.fit_fiducials()`+`fit_icp()` (or set the montage + fsaverage trans) and verify with `plot_alignment`. |
| `make_dics`/`csd_morlet` errors on a surface source space | Beamformer power maps need a volume source space — build one with `setup_volume_source_space(pos=10.0, bem=bem_sol)`. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `epochs-stage/`, `ENVIRONMENT.json`, FreeSurfer `subjects_dir` (optional)
- Outputs: `source-stage/*-stc.h5`, `source-stage/*-roi_ts.npz`, `source-stage/forward/*-fwd.fif`, `source-stage/covariance/*-cov.fif`, `source-stage/SOURCE_PARAMS.json`, `source-stage/PLATFORM_CHECK.md`, `FINDINGS.md`
- Next: `eeg-connectivity` can use ROI time courses for source-space connectivity. `eeg-stats` for statistical comparison of source estimates. `eeg-figure` for cortical surface plots. `eeg-methods-text` for the source localization paragraph.
- Source-space statistics: contrast source estimates with `mne.stats.spatio_temporal_cluster_1samp_test` (paired/within-subject) or `spatio_temporal_cluster_test`, using source-space adjacency `mne.spatial_src_adjacency(src)`, ≥1000 permutations, and a two-tailed threshold (the course convention is alpha = 0.025 per tail = 0.05 overall). When whole-brain cluster tests are underpowered, reduce to ROI time courses (`extract_label_time_course` over an atlas) and run ROI-wise paired t-tests with FDR/Bonferroni correction across ROIs. (Detailed protocol in `eeg-stats`.)
