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
- **BEAMFORMER_RANK = shared data-derived dictionary** — compute `shared_rank = mne.compute_rank(epochs, rank=None, proj=True)` once from the final cleaned source-analysis epochs, then pass that exact dictionary to noise/data covariance estimation and `make_lcmv`/`make_dics`. `rank='info'` uses channel counts and SSP/Maxwell metadata; it does not measure additional rank loss from ICA cleaning or interpolation. Keep the same channels and projector convention throughout. (Westner et al. 2022; MNE `compute_rank` documentation)

> Override: `/eeg-source projects/my-study — head-model: fsaverage — inverse: sloreta — backend: mne`

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
# Final cleaned epochs, with the approved source-analysis channels and conditions.
# proj=True applies saved projectors on loading (also read_epochs' default).
# set_eeg_reference(..., projection=True) alone only registers a projector;
# it does not subtract the average from the stored samples.
epochs = mne.read_epochs(epochs_fif_path, preload=True, proj=True)
info = epochs.info
# Estimate once from the actual cleaned samples, accounting for saved projectors.
# For a common filter, these must include the approved pooled conditions/windows.
shared_rank = mne.compute_rank(epochs, rank=None, proj=True)

# From the prestimulus baseline of the SAME cleaned epochs
noise_cov = mne.compute_covariance(
    epochs,
    tmin=None, tmax=0,        # baseline period
    method='auto',            # cross-validate empirical/shrunk/LW/FA, pick best (do NOT hand-guess)
    rank=shared_rank          # reuse below; do not re-estimate rank per covariance window
)
# Regularize if needed under the approved plan (often unnecessary with method='auto')
# noise_cov = mne.cov.regularize(noise_cov, info, eeg=0.1, rank=shared_rank)

# Save
mne.write_cov(f'source-stage/covariance/{sub}-cov.fif', noise_cov, overwrite=True)
```

**Mandatory whitening QC — never skip.** A wrong noise covariance does not error; it silently produces plausible-but-wrong sources. After estimating the covariance, whiten the evoked response and inspect the global field power of the whitened data: a correct covariance makes the whitened GFP hover around **1.0** in the baseline (it is then white, i.e. unit variance). Departures (GFP ≫ 1 or ≪ 1) mean the covariance — and therefore every downstream source estimate — is miscalibrated.

```python
evoked = epochs['condition_name'].average()
fig = evoked.plot_white(noise_cov, rank=shared_rank, time_unit='s')   # whitened GFP should sit ~1.0
fig.savefig(f'source-stage/covariance/{sub}-whitening-check.png')
```

(Engemann & Gramfort 2015, on automated covariance selection + the whitening sanity check.)

**Covariance estimation guidelines:**
- `method='auto'` subsumes the old manual choice; it cross-validates empirical/shrunk/Ledoit-Wolf/factor-analysis and is especially important when N_trials < N_channels (where `'empirical'` is rank-deficient and ill-conditioned).
- Estimate rank from the final cleaned epochs once with `compute_rank(..., rank=None, proj=True)`, then reuse `shared_rank` for noise/data covariance, whitening and inverse/filter construction. `rank='info'` subtracts SSP dimensions from metadata channel counts (or uses Maxwell metadata); it does not discover all ICA/PCA/interpolation dependencies. Do not independently use `rank=None` for each window, which can give inconsistent noise/data ranks. If a window has fewer independent samples or a different data subspace, retain the mismatch and resolve its cause before applying a common rank; do not force agreement by changing the rank or approved window.
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
    rank=shared_rank, # same cleaned-data rank used for noise covariance and whitening
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
    rank=shared_rank        # the SAME dictionary as noise_cov; do not estimate per window
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
    rank=shared_rank         # same rank as both covariances (Westner et al. 2022)
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
                     rank=shared_rank)                   # same cleaned epochs/channels/projectors as Phase C

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
  "noise_cov_rank": null,
  "noise_cov_tmin": null,
  "noise_cov_tmax": 0,
  "roi_atlas": "aparc",
  "roi_extraction_mode": "mean_flip",
  "n_rois": 68
}
```

Replace the `noise_cov_rank` placeholder with the actual `shared_rank` dictionary from Phase C when writing the record (for example, `{"eeg": 63}` only if that is the measured rank). Record the final channel names and applied projector state alongside it; this dictionary is shared by noise/data covariance and inverse/filter construction, not inferred separately from each covariance window.

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
- [ ] Rank was estimated from the final cleaned epochs with `compute_rank(..., rank=None, proj=True)` and the same dictionary was used for noise/data covariance (`method='auto'`), whitening and inverse/filter construction, with matching channels/projectors. Any window-specific rank mismatch was resolved and recorded rather than hidden by a metadata-only rank.
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
| Noise covariance is rank-deficient | Check the final cleaned-data `shared_rank` and projector/channel agreement; average reference, ICA cleaning and interpolation can make rank deficiency expected. If baseline/data subspaces differ, record and resolve the mismatch rather than automatically changing the estimator or rank. |
| Forward solution has 0 sources | BEM surfaces are malformed. Regenerate with `mne.bem.make_watershed_bem`. |
| Source estimate is all zeros | Check: epochs loaded correctly? Noise cov and forward from same subject? Lambda2 too large? |
| Sources look plausible but are wrong / whitened GFP far from 1.0 | Check covariance calibration, baseline, channel/projector agreement and the data-derived `shared_rank`; use `method='auto'` and `evoked.plot_white(noise_cov, rank=shared_rank)`. Retain the failed QC while diagnosing it; do not tune rank just to make GFP approach 1.0. |
| Minimum-norm solution stuck on the cortical surface (no deep sources) | Depth weighting too light — using the MEG default `depth=0.8` on EEG. Raise to `DEPTH_EEG` (≈3.0). |
| Beamformer filter unstable / covariance inverse blows up | Check actual cleaned-data rank after reference/ICA/interpolation and reuse the same `shared_rank` dictionary for noise/data covariance and `make_lcmv`/`make_dics`; `rank='info'` alone cannot detect all such losses. |
| Peak activation in white matter | Forward model error or wrong coregistration. Verify BEM and electrode alignment. |
| LCMV output shows bilateral suppression | Expected — switch to MNE/dSPM for bilateral sources. Document in FINDINGS.md. |
| Beamformer source map is biased / unstable | Check EEG is common-average referenced (`set_eeg_reference('average', projection=True)`); a non-average reference contaminates all channels. |
| Between-condition source contrast looks too strong | A separate filter was likely computed per condition. Rebuild ONE filter on pooled data and reapply to each condition. |
| DICS relative-power contrast is biased | Baseline and active windows have unequal length. Use equal-duration windows so the CSDs share degrees of freedom. |
| Source localization ran with default/identity trans | Coregistration was never fitted/verified. Fit with `Coregistration.fit_fiducials()`+`fit_icp()` (or set the montage + fsaverage trans) and verify with `plot_alignment`. |
| `make_dics`/`csd_morlet` errors on a surface source space | Beamformer power maps need a volume source space — build one with `setup_volume_source_space(pos=10.0, bem=bem_sol)`. |
