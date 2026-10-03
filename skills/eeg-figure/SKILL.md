---
name: eeg-figure
description: "Render paper-ready figures from stage outputs: ERP butterfly + topomap + cluster-masked difference, TFR maps with cluster outlines, microstate template + transitions, source dipole renderings. Reads FIGURE_PLAN.md and writes both SVG (editable) and PNG (preview)."
argument-hint: "[project-dir] [— figures: F1,F2,F3] [— journal: nature|jneurosci|neuroimage] [— width: single|double]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# eeg-figure: paper-ready figure rendering

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne` + `matplotlib`** — All figures use matplotlib as the rendering backend. MNE's `viz` module wraps matplotlib for EEG-specific plots.
- **OUTPUT_FORMATS = `[svg, png]`** — SVG is the editable source of truth; PNG for previews and quick sharing.
- **DPI_PNG = 300** — Minimum for print. Use 600 for final camera-ready if journal requires.
- **DPI_SVG = N/A** — SVG is vector; resolution-independent.
- **STYLE = constants from FIGURE_PLAN.md** — colormap, font, line widths read from plan.
- **FIGURE_DIR = `figure-stage/`** — Create if missing.
- **CAPTIONS_FILE = `figure-stage/CAPTIONS.md`**.

### Journal-specific dimensions

| Journal | Single column | Double column | Max height |
|---|---|---|---|
| Nature family | 89 mm | 183 mm | 247 mm |
| JNeurosci | 85 mm | 175 mm | 235 mm |
| NeuroImage | 90 mm | 180 mm | 240 mm |
| PNAS | 87 mm | 178 mm | 230 mm |
| Default | 89 mm | 183 mm | 247 mm |

- **WIDTH_SINGLECOL_MM = 89** (override via `— journal:` or `— width:`).
- **WIDTH_DOUBLECOL_MM = 183**.

### Default style constants

```python
STYLE_DEFAULTS = {
    "font_family": "Arial",           # sans-serif for most journals
    "font_size_axis_label": 8,        # minimum legible at print scale
    "font_size_tick_label": 7,
    "font_size_panel_label": 10,      # bold A, B, C panel labels
    "font_size_title": 9,
    "line_width_mean": 1.5,
    "line_width_individual": 0.3,
    "line_width_axis": 0.5,
    "marker_size": 3,
    "alpha_individual": 0.3,          # transparent for single subjects
    "alpha_ci": 0.2,                  # shading for confidence intervals
    "cmap_diverging": "RdBu_r",       # for difference maps, ERP diff
    "cmap_sequential": "viridis",     # for power, TFR magnitude
    "cmap_categorical": "Okabe-Ito",  # colorblind-safe discrete palette
    "panel_label_weight": "bold",
    "panel_label_x": -0.1,           # axes fraction
    "panel_label_y": 1.05,
}
```

## Required Inputs

Before rendering, these must exist:

1. `FIGURE_PLAN.md` — specifies each figure's panels, data sources, and layout. **Stop if missing.**
2. Stage outputs referenced in the plan: `erp-stage/`, `tfr-stage/`, `stats-stage/`, `connectivity-stage/`, `source-stage/`, etc.
3. `ANALYSIS_PLAN.md` — to verify figure content matches planned analyses.
4. `channel_mapping.json` — if topomaps need 10-20 labels but data uses numbered channels.

## Phase A — Parse figure plan

1. Read `FIGURE_PLAN.md`. Extract for each figure:
   - `figure_id` (F1, F2, ...), `short_name`, `width` (single/double), `n_panels`, `panel_layout` (e.g., "2×3").
   - Per panel: `panel_id`, `type` (ERP, TFR, topomap, bar, violin, decoding, spectral, ...), `data_source`, `conditions`, `channels/ROI`, `time_window`, `freq_band`, `colormap`, `vmin/vmax`, `caption_fragment`.
2. Resolve journal dimensions from `— journal:` argument or `FIGURE_PLAN.md` header.
3. Write `figure-stage/FIGURE_RENDER_PLAN.json` summarizing all resolved figures before rendering.

## Phase B — Figure type catalog and rendering

For each figure in the plan, generate a self-contained Python script that renders all panels.

### B.1 — ERP figures

#### Butterfly plot
```python
# All channels overlaid, highlight ROI channels
evoked.plot(spatial_colors=True, gfp=True, show=False)
# Or custom matplotlib for more control:
for ch in info['ch_names']:
    ax.plot(times, evoked.data[ch_idx], color=color, lw=0.3, alpha=0.3)
```

#### Condition overlay at ROI
```python
# Grand-average ERP at ROI channels, one line per condition
for cond, evoked in evokeds.items():
    roi_data = evoked.copy().pick(roi_channels).data.mean(axis=0)
    ax.plot(times * 1e3, roi_data * 1e6, label=cond, lw=1.5)
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Amplitude (µV)")
ax.axvline(0, color='k', ls='--', lw=0.5)  # stimulus onset
ax.axhline(0, color='k', ls='-', lw=0.3)
```

#### Difference wave with confidence interval
```python
# difference = condition_A - condition_B, per subject
diff_mean = np.mean(diff_array, axis=0)
diff_sem = scipy.stats.sem(diff_array, axis=0)
ci_95 = 1.96 * diff_sem
ax.plot(times, diff_mean, color='k', lw=1.5)
ax.fill_between(times, diff_mean - ci_95, diff_mean + ci_95, alpha=0.2, color='gray')
```

#### Group ERP with mean ± SEM band (preferred convenience)
```python
# Let MNE draw the grand average + variability band from a list/dict of per-subject
# Evoked objects. Default band is mean ± 1 SEM; ci=0.95 switches to a bootstrap CI.
mne.viz.plot_compare_evokeds(
    {'A': evokeds_A, 'B': evokeds_B},   # values are LISTS of per-subject Evoked
    picks=roi_channels, combine='mean',
    ci=True,                            # mean ± SEM; or ci=0.95 for bootstrap 95% CI
    show_sensors=False, show=False)

# Manual equivalent (when you need the raw array, e.g. to overlay a cluster mask):
data = np.array([ev.copy().pick(roi_channels).data.mean(0) for ev in evokeds_A])
avg = data.mean(0)
sem = data.std(0, ddof=0) / np.sqrt(data.shape[0])   # published default band
ax.plot(times, avg, lw=1.5)
ax.fill_between(times, avg - sem, avg + sem, alpha=0.2)
```

- The published default visual band is **mean ± 1 SEM**, with `SEM = std(ddof=0) / sqrt(n_subjects)`; state which band (SEM vs 95% CI) the figure uses in the caption — they are not interchangeable.
- Grand average across subjects: `mne.grand_average([ev1, ev2, ...])`.
- **Keep the per-subject axis** for cluster/ANOVA input — do NOT average across subjects before stats (the analog of FieldTrip `keepindividual='yes'`).

#### Cluster-masked significance
```python
# Overlay significant cluster as shaded region on ERP difference
mask = cluster_results['mask']  # boolean, shape (n_times,) or (n_times, n_channels)
for start, stop in _contiguous_regions(mask):
    ax.axvspan(times[start], times[stop], alpha=0.15, color='orange', label='p < 0.05' if first else None)
```

### B.2 — Time-frequency (TFR) figures

#### The standard TFR figure trio

For any TFR result, three views answer different questions. Reach for all three:

```python
# TFR data axes are ALWAYS (channels, freqs, times) — picks index the channel axis.
# 1. Montage overview — every channel laid out on the head, for exploration / sanity.
tfr.plot_topo(baseline=baseline, mode='logratio', layout=None,
              cmap='RdBu_r', show=False)        # analog of ft_multiplotTFR

# 2. ROI time-frequency image — plot(picks=...) AVERAGES over the picked channels.
#    NOTE (MNE 1.12): AverageTFR.plot takes vlim=(min, max), NOT vmin/vmax.
tfr.plot(picks=['Cz', 'C1'], baseline=baseline, mode='logratio',
         vlim=(-vmax, vmax), cmap='RdBu_r', combine='mean', show=False)

# 3. Band x time-window scalp map — topography for a chosen band over a window.
tfr.plot_topomap(tmin=0.08, tmax=0.42, fmin=8, fmax=13,   # alpha, 80-420 ms
                 baseline=baseline, mode='logratio',
                 vlim=(-vmax, vmax), cmap='RdBu_r', colorbar=True, show=False)
```

- `plot(picks=[...])` **averages** over the picked channels (it does not overlay them) — state this in the caption when picks span an ROI.
- The alpha 8–13 Hz, 80–420 ms topomap is a directly reusable default for motor/attention paradigms.
- For baseline-normalized data, **fix a symmetric scale** (`vlim=(-vmax, vmax)`) and **share the same scale across conditions** so panels are visually comparable.
- Group level: grand-average per-subject `AverageTFR` objects with `mne.grand_average([tfr1, tfr2, ...])` before any of the three plots.

#### Time-frequency heatmap
```python
# Single condition or difference, at ROI channels
tfr.plot(picks=roi_channels, baseline=baseline, mode='logratio',
         vmin=vmin, vmax=vmax, cmap='RdBu_r', show=False)
# Or custom:
im = ax.pcolormesh(times, freqs, tfr_data, cmap='RdBu_r', vmin=vmin, vmax=vmax)
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Frequency (Hz)")
cbar = fig.colorbar(im, ax=ax)
cbar.set_label("Power (dB)")  # or "ERDS (%)"
```

#### ERDS (event-related desynchronization/synchronization) map
```python
# Percentage change from baseline
# ERDS = (power - baseline_power) / baseline_power * 100
im = ax.pcolormesh(times, freqs, erds_pct, cmap='RdBu_r',
                   vmin=-100, vmax=100)  # symmetric around 0
cbar.set_label("ERDS (%)")
```

#### Band time courses
```python
# Average power in a frequency band over time
for band_name, (fmin, fmax) in bands.items():
    band_data = tfr.copy().crop(fmin=fmin, fmax=fmax).data.mean(axis=1)  # avg over freqs
    ax.plot(times, band_data, label=f"{band_name} ({fmin}-{fmax} Hz)")
```

### B.3 — Topomap figures

#### Scalp maps at specific times
```python
# ERP topography at selected latencies
evoked.plot_topomap(times=[0.1, 0.15, 0.2, 0.3], average=0.02,
                    cmap='RdBu_r', vlim=(-vmax, vmax),
                    colorbar=True, show=False)
```

#### Scalp maps at specific frequencies (TFR)
```python
# TFR topography at selected time-frequency points
tfr.plot_topomap(tmin=tmin, tmax=tmax, fmin=fmin, fmax=fmax,
                 baseline=baseline, mode='logratio',
                 cmap='RdBu_r', vlim=(-vmax, vmax),
                 colorbar=True, show=False)
```

#### Topomap rules
- **Always** include a colorbar with units (µV, dB, t-value, etc.).
- **Always** set explicit `vlim` — never auto-scale for difference maps.
- Use symmetric limits for diverging data (difference, t-values): `vlim=(-vmax, vmax)`.
- Mark ROI channels with bold dots if relevant.
- Use `mne.viz.plot_topomap()` for custom data; `evoked.plot_topomap()` for evoked objects.

### B.4 — Decoding figures

#### Sliding accuracy (temporal decoding)
```python
# Accuracy over time from decoding-stage results
ax.plot(times, scores_mean, color='steelblue', lw=1.5)
ax.fill_between(times, scores_mean - ci_95, scores_mean + ci_95, alpha=0.2)
ax.axhline(chance, color='k', ls='--', lw=0.5, label='Chance')
ax.set_xlabel("Time (ms)")
ax.set_ylabel("AUC" )  # or "Accuracy"
# Shade significant time points from stats
```

#### Temporal generalization matrix (TGM)
```python
# n_train_times × n_test_times matrix
im = ax.imshow(tgm_scores, origin='lower', cmap='RdBu_r',
               vmin=chance - vrange, vmax=chance + vrange,
               extent=[times[0], times[-1], times[0], times[-1]])
ax.set_xlabel("Testing time (ms)")
ax.set_ylabel("Training time (ms)")
ax.plot([times[0], times[-1]], [times[0], times[-1]], 'k--', lw=0.5)  # diagonal
cbar = fig.colorbar(im, ax=ax)
cbar.set_label("AUC")
```

### B.5 — Spectral figures

#### PSD curves
```python
# Power spectral density per condition
for cond, spectrum in spectra.items():
    psd_mean = spectrum.get_data().mean(axis=0)  # average over channels or subjects
    ax.semilogy(freqs, psd_mean, label=cond, lw=1.5)
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("PSD (µV²/Hz)")
```

#### Specparam (FOOOF) fit
```python
# Aperiodic + periodic component decomposition
# Plot original, aperiodic fit, flattened spectrum, identified peaks
ax.semilogy(freqs, psd, 'k', label='Original')
ax.semilogy(freqs, aperiodic_fit, 'b--', label='Aperiodic fit')
# Mark peaks with vertical lines at center frequency
```

#### Individual alpha peak frequency (IAPF) distribution
```python
# Histogram or strip plot of IAPF across subjects
ax.hist(iapf_values, bins='auto', edgecolor='black', alpha=0.7)
ax.axvline(np.median(iapf_values), color='red', ls='--', label='Median')
ax.set_xlabel("IAPF (Hz)")
ax.set_ylabel("Count")
```

### B.6 — Bar / violin / raincloud plots

#### Condition comparison with individual data points
```python
# NEVER use bar plots with SEM alone — they hide the distribution
# Preferred: violin + strip, or raincloud plot

# Violin + strip (Weissgerber et al. 2015)
import seaborn as sns
ax = sns.violinplot(data=df, x='condition', y='amplitude', inner=None, alpha=0.3)
ax = sns.stripplot(data=df, x='condition', y='amplitude', jitter=True,
                   size=3, alpha=0.6, color='black')
# Add group mean ± 95% CI
for i, cond in enumerate(conditions):
    mean = df[df.condition == cond]['amplitude'].mean()
    ci = 1.96 * scipy.stats.sem(df[df.condition == cond]['amplitude'])
    ax.errorbar(i, mean, yerr=ci, fmt='o', color='red', markersize=5, capsize=4)

# Alternative: Raincloud plot (Allen et al. 2019)
import ptitprince as pt
pt.RainCloud(data=df, x='condition', y='amplitude', ax=ax,
             orient='h', palette='Set2', bw=0.2, width_viol=0.6)
```

### B.7 — Connectivity figures

#### Connectivity matrix (heatmap)
```python
# con: (n_signals, n_signals) array. Undirected metrics (COH/PLV/PLI/wPLI) are
# SYMMETRIC; the diagonal is trivial (coh~1, pli/wpli~0) and must NOT drive the scale.
import numpy as np
M = con.copy()
np.fill_diagonal(M, np.nan)            # mask the trivial diagonal
off = M[~np.isnan(M)]
vmax = np.nanpercentile(np.abs(off), 99)  # scale from OFF-diagonal values only
im = ax.imshow(M, cmap='viridis', vmin=0, vmax=vmax)   # PLI/wPLI/coh in [0,1]
ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=90, fontsize=6)
ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=6)
cbar = fig.colorbar(im, ax=ax); cbar.set_label('wPLI')
# Directed metrics (Granger/TE/PSI) are ASYMMETRIC: row=source, col=target,
# diagonal=0; use a diverging map only if the metric is signed (e.g. PSI).
# 'wpli2_debiased' (the preferred debiased wPLI) CAN go negative: drop vmin=0 and
# use a symmetric diverging map (RdBu_r, vmin=-vmax) for that metric.
```

#### Connectivity circle (chord) plot
```python
from mne_connectivity.viz import plot_connectivity_circle
# Threshold to the strongest edges so the circle stays readable.
plot_connectivity_circle(con, node_names=labels, n_lines=30,
                         colormap='viridis', vmin=0, vmax=vmax,
                         facecolor='white', textcolor='black', show=False)
```

#### Connectivity rules
- **Mask the diagonal** before computing the color scale and never include it in the figure scale — it is trivial (coh≈1, PLI/wPLI≈0) and otherwise saturates the map.
- Undirected matrices are symmetric; show only one triangle (or the full masked matrix) and never read the two triangles as independent edges.
- Plot only the **unique** edges: undirected E·(E−1)/2, directed E·(E−1). This is also the N for any multiple-comparison annotation in the caption.
- For a thresholded/significant-edge graph, state the threshold (e.g. cluster-corrected p<0.05) in the caption.

### B.8 — Source-estimate figures

#### Surface render (cortically-constrained STC)
```python
# Morph individual STCs to fsaverage FIRST for group display / MNI reporting.
morph = mne.compute_source_morph(stc, subject_from='sub-01',
                                 subject_to='fsaverage', subjects_dir=subjects_dir)
stc_fs = morph.apply(stc)
# Threshold/mask the displayed map and STATE the threshold in the caption.
brain = stc_fs.plot(subjects_dir=subjects_dir, hemi='split', surface='inflated',
                    views=['lat', 'med'], time_viewer=False,
                    clim=dict(kind='value', lims=[t_lo, t_mid, t_hi]))
brain.save_image('figure-stage/F_source.png')
```

#### Volume STC (beamformer / volumetric)
```python
mne.viz.plot_volume_source_estimates(vol_stc, src=src, subject='fsaverage',
                                     subjects_dir=subjects_dir,
                                     clim=dict(kind='value', lims=[t_lo, t_mid, t_hi]))
```

#### Source reporting checklist (run before declaring a source figure done)
1. **Morph individual STCs to fsaverage** before any group display or MNI reporting (the analog of FieldTrip `ft_volumenormalise` to MNI).
2. **Threshold/mask** the displayed map via `clim=dict(kind='value', lims=[...])` and state the threshold in the caption.
3. **Name peaks/clusters** with a real atlas — `mne.read_labels_from_annot` (Desikan-Killiany `aparc` or Destrieux `aparc.a2009s`) for surface, or an AAL volume atlas — and report MNI coordinates.
4. Show an **inflated-surface or glass-brain** render, not raw voxel grids.

## Phase C — Style enforcement

Before saving each figure, apply these mandatory checks:

### C.1 — Font sizes
- Axis labels ≥ 8 pt — **never smaller**.
- Tick labels ≥ 7 pt.
- Panel labels (A, B, C) at 10 pt bold, positioned consistently.
- Legend text ≥ 7 pt.
- Verify at target print size: a 89 mm single-column figure scaled from a 6-inch-wide matplotlib figure means 8 pt in matplotlib ≈ 5.9 pt on paper. Compensate: use `font_size * (fig_width_inches / target_width_inches)`.

### C.2 — Colormaps
- **Perceptually uniform** for sequential data: `viridis`, `inferno`, `magma`, `cividis`.
- **Diverging** for signed data (differences, t-values): `RdBu_r`, `coolwarm`, `PiYG`.
- **NEVER use `jet`** — it creates perceptual artifacts, misleads viewers, and fails for colorblind readers. The audit will reject it.
- **Colorblind-safe discrete palette**: Okabe-Ito (8 colors) for categorical/condition comparisons.
- When in doubt, use `cividis` (perceptually uniform AND colorblind-safe).

### C.3 — Color accessibility
- Avoid red-green as the only distinguishing feature between conditions.
- Use both color AND linestyle/marker to distinguish conditions (double encoding).
- Test with a colorblind simulator (e.g., `colorspacious` or online tools) if >3 conditions.
- Cite: Crameri, F., Shephard, G. E., & Heron, P. J. (2020). The misuse of colour in science communication. Nature Communications, 11, 5444.

### C.4 — Scale bars and units
- **Always** label axes with units: µV, ms, Hz, dB, %, t-value.
- **Always** include colorbars for heatmaps and topomaps, with unit labels.
- Use SI prefixes consistently: µV (not uV), ms (not msec).
- Time axis: milliseconds for ERP (ms), seconds for long epochs (s).
- Amplitude: µV for ERP, dB or % for TFR power.

### C.5 — Individual subject data
- Use transparency (`alpha=0.3`) and thin lines (`lw=0.3`) for individual subjects.
- Use solid lines (`alpha=1.0`) and thicker lines (`lw=1.5`) for group mean.
- Never show only the mean — always show individual data or distribution when N < 30.

### C.6 — Statistical annotations
- Mark significance with shaded regions (ERP/TFR) or asterisks (bar/violin).
- Never write "p = 0.000" — use "p < 0.001".
- For cluster permutation results: shade the cluster region but note in caption that cluster boundaries do not imply precise onset/offset (Sassenhagen & Draschkow 2019).

## Phase D — Render and save

For each figure:

1. Create the matplotlib figure at the correct size:
   ```python
   fig_width_mm = 89 if single_col else 183
   fig_width_in = fig_width_mm / 25.4
   fig_height_in = fig_width_in * aspect_ratio  # or computed from panel layout
   fig, axes = plt.subplots(nrows, ncols, figsize=(fig_width_in, fig_height_in))
   ```
2. Render all panels with style constants applied.
3. Add panel labels (A, B, C ...) at consistent positions.
4. `fig.savefig(f"figure-stage/F{n}_{short_name}.svg", format='svg', bbox_inches='tight', pad_inches=0.02)`
5. `fig.savefig(f"figure-stage/F{n}_{short_name}.png", format='png', dpi=300, bbox_inches='tight', pad_inches=0.02)`
6. Close the figure to free memory.

## Phase E — Generate captions

Write `figure-stage/CAPTIONS.md`:

```markdown
## Figure 1: [Short descriptive title]

**[Panel-by-panel description.]** (A) Grand-average ERP at [ROI] for [conditions].
Shaded regions indicate ±95% CI. (B) Scalp topography of the [component] at [time] ms.
(C) Difference wave (A − B) with cluster-masked significance (p < 0.05, cluster permutation,
N = [perms] permutations). Gray shading: 95% CI. Orange shading: significant cluster
(note: cluster boundaries do not imply precise effect onset/offset).
```

- Each caption must be self-contained: a reader should understand the figure without the main text.
- Include: what is plotted, N, statistical test used, significance threshold.
- Never over-interpret cluster boundaries in captions.

## Phase F — Sanity checks

All must pass before declaring success:

- [ ] Every figure in FIGURE_PLAN has a corresponding `figure-stage/F<n>_<name>.svg` and `.png`.
- [ ] No figure uses the `jet` colormap.
- [ ] All difference/t-value plots have explicit symmetric `vmin/vmax`.
- [ ] All heatmaps and topomaps have colorbars with unit labels.
- [ ] All axis labels include units (µV, ms, Hz, dB, etc.).
- [ ] Font sizes ≥ 8 pt for axis labels at target print size.
- [ ] No bar plots with SEM only — distribution or individual data shown.
- [ ] No "p = 0.000" anywhere — replaced with "p < 0.001".
- [ ] No 3-D rotated topomaps unless explicitly requested.
- [ ] Panel labels (A, B, C) are consistent and present on multi-panel figures.
- [ ] `CAPTIONS.md` has one entry per figure.
- [ ] SVG files are well-formed and openable in Inkscape/Illustrator.
- [ ] Connectivity matrices mask the diagonal and scale color from off-diagonal values only.
- [ ] Source figures use morphed-to-fsaverage STCs for group display and state the display threshold.
- [ ] Group ERP/TFR bands declare SEM vs CI in the caption, and were built from a per-subject stack (subject axis retained for any stats).

## Forbidden styles (audit will flag)

- `jet` colormap — always rejected.
- Auto-scaled symmetric difference plots (`vmin`/`vmax` must be explicit).
- 3-D rotated topomaps without explicit user request.
- Bar plots with SEM only (must show distribution + 95% CI or individual data).
- "p = 0.000" — must be `p < 0.001`.
- Red-green only color coding without secondary encoding (linestyle/marker).
- Missing colorbars on heatmaps or topomaps.
- Missing units on any axis.

## Critical Rules

- **Never** render a figure not in FIGURE_PLAN. Ad hoc figures go in `figure-stage/exploratory/` and are labeled `[EXPLORATORY]`.
- **Never** auto-scale vmin/vmax for difference or t-value maps — always set symmetric explicit limits.
- **Never** use `plt.show()` in scripts — only `savefig()`. Rendering is headless.
- **Never** use `jet`. Not even "just for a quick look." The audit flags it. Use `viridis` or `RdBu_r`.
- **Never** produce bar plots that hide the underlying distribution. Use violin, raincloud, or dot plots.
- **Always** include scale bars, units, and colorbars.
- **Always** set `bbox_inches='tight'` to avoid clipping labels.
- **Never** include the connectivity-matrix diagonal in the color scale — it is trivial (coh≈1, PLI/wPLI≈0) and saturates the map. Mask it (`np.fill_diagonal(M, np.nan)`) and scale from off-diagonal values; count edges as E·(E−1)/2 (undirected) or E·(E−1) (directed).
- **Never** average across subjects before producing the array fed to cluster/permutation stats — keep the per-subject axis (the analog of FieldTrip `keepindividual='yes'`); collapse only for the visual mean.
- **Always** morph individual source estimates to `fsaverage` before group display or MNI reporting, and state the display threshold used to mask the map.

## Domain Knowledge (distilled from visualization methodology literature)

### Ten simple rules for better figures (Rougier et al. 2014, PLOS Computational Biology)

- Rule 1: Know your audience — adjust complexity for the target journal.
- Rule 2: Identify the message — each figure should convey one main point.
- Rule 3: Adapt the figure to the medium — print dimensions, color vs grayscale.
- Rule 4: Captions are essential — they should be self-contained.
- Rule 5: Do not trust defaults — explicitly set fonts, colors, line widths.
- Rule 6: Use color effectively — perceptually uniform, colorblind-safe.
- Rule 7: Do not mislead the reader — axis ranges, aspect ratios matter.
- Rule 8: Avoid chartjunk — remove gridlines, background fills, 3D effects.
- Rule 9: Message beats beauty — clarity over aesthetics.
- Rule 10: Get scientific feedback — iterate on figures with co-authors.
- Cite: Rougier, N. P., Droettboom, M., & Bourne, P. E. (2014). Ten simple rules for better figures. PLOS Computational Biology, 10(9), e1003833.

### Bar plots hide data (Weissgerber et al. 2015, PLOS Biology)

- Bar plots with error bars conceal the distribution shape, sample size, and outliers.
- For small N (typical in EEG, N=10–30), always show individual data points.
- Preferred alternatives: dot plots, violin plots, box plots with overlaid individual data, raincloud plots.
- Cite: Weissgerber, T. L., et al. (2015). Beyond bar and line graphs: time for a new data presentation paradigm. PLOS Biology, 13(4), e1002128.

### Raincloud plots (Allen et al. 2019, Wellcome Open Research)

- Combine: (1) half-violin for density, (2) box plot for summary statistics, (3) individual data points.
- Ideal for EEG condition comparisons with N=10–30 subjects.
- Available via `ptitprince` Python package or custom matplotlib.
- Cite: Allen, M., et al. (2019). Raincloud plots: a multi-platform tool for robust data visualization. Wellcome Open Research, 4, 63.

### Scientific colour maps (Crameri et al. 2020, Nature Communications)

- `jet` is perceptually non-uniform: creates artificial boundaries and is unreadable for ~8% of males with color vision deficiency.
- Perceptually uniform sequential: `viridis`, `inferno`, `magma`, `cividis`.
- Perceptually uniform diverging: `RdBu_r`, `PiYG`, `BrBG`.
- The `cividis` colormap is both perceptually uniform and colorblind-safe.
- Cite: Crameri, F., Shephard, G. E., & Heron, P. J. (2020). The misuse of colour in science communication. Nature Communications, 11, 5444.

### Group ERP/TFR bands: SEM vs CI, and keep the subject axis

- The conventional visual band on a grand-average waveform is **mean ± 1 SEM**, where `SEM = std(ddof=0) / sqrt(n_subjects)` (population SD over the subject axis divided by √N). A 95% CI ≈ 1.96·SEM (or a bootstrap CI) is wider and is a different claim — always say which one the figure shows.
- `mne.viz.plot_compare_evokeds` draws this band automatically from a list/dict of per-subject `Evoked` objects (`ci=True` → SEM band; `ci=0.95` → bootstrap CI).
- For cluster-permutation / ANOVA, the input must retain the subject dimension — averaging across subjects first discards exactly the variability the test needs (FieldTrip encodes this as `cfg.keepindividual='yes'`). The visual mean and the stats input come from the same per-subject stack, collapsed at different stages.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.), MIT Press (grand-average and SEM conventions); Maris, E. & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data. J. Neurosci. Methods, 164, 177–190 (per-subject input for cluster permutation).

### Connectivity-matrix plotting conventions

- Undirected metrics (coherence, PLV, PLI, wPLI) yield a **symmetric** E×E matrix; only E·(E−1)/2 edges are unique. Directed metrics (Granger causality, transfer entropy, PSI) yield an **asymmetric** matrix (row=source, col=target) with E·(E−1) directed edges.
- The **diagonal is trivial** and metric-dependent: coherence ≈ 1, PLI/wPLI ≈ 0 (and wPLI NaNs on the diagonal are conventionally set to 0). It must be masked before color scaling and excluded from statistics — including it saturates the colormap and inflates multiple-comparison counts.
- wPLI (debiased) is preferred over PLV/coherence when volume conduction / zero-lag leakage is a concern, because it is insensitive to zero-phase-lag coupling.
- Cite: Vinck, M., Oostenveld, R., van Wingerden, M., Battaglia, F., & Pennartz, C. M. A. (2011). An improved index of phase-synchronization for electrophysiological data in the presence of volume-conduction, noise and sample-size bias. NeuroImage, 55(4), 1548–1565.

## Failure Modes

| Symptom | Action |
|---|---|
| FIGURE_PLAN missing | Stop. Ask user to create or run eeg-pipeline planning phase. |
| Stage output missing for a figure | Stop. Tell user which stage must run first. |
| Topomap looks empty | Check channel positions — montage may not be set. Run `raw.set_montage()` first. |
| Colorbar missing | Add it. This is never optional for heatmaps/topomaps. |
| Text clipped in SVG | Use `bbox_inches='tight'` and increase `pad_inches`. |
| Figure too large for journal | Reduce panel count or switch to double-column width. |
| Individual points overlap heavily | Add jitter, reduce marker size, or use transparency. |
| Connectivity matrix all one color / saturated | Diagonal is dominating the scale. Mask it (`np.fill_diagonal(M, np.nan)`) and set `vmin/vmax` from off-diagonal values. |
| Source map looks like noise or peaks everywhere | No threshold applied, or individual STC not morphed to fsaverage. Apply `clim=dict(kind='value', lims=[...])` and `compute_source_morph` to fsaverage first. |
| Group band looks implausibly tight or wide | Confirm whether it is SEM or 95% CI, and that SEM uses `std(ddof=0)/sqrt(n_subjects)` over the subject axis (not over channels/time). |

## Cross-references

- Inputs: `FIGURE_PLAN.md`, `erp-stage/`, `tfr-stage/`, `stats-stage/`, `decoding-stage/`, `connectivity-stage/`, `source-stage/`, `ANALYSIS_PLAN.md`, `channel_mapping.json`
- Outputs: `figure-stage/F<n>_<name>.svg`, `figure-stage/F<n>_<name>.png`, `figure-stage/CAPTIONS.md`, `figure-stage/FIGURE_RENDER_PLAN.json`
- Next: `eeg-report` embeds figures into HTML report. `eeg-methods-text` references figure numbers. `eeg-audit` checks figures match the plan.
