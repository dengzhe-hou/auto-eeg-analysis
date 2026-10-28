## Common EEG reviewer concerns (distilled from real peer reviews)

These are the most frequent methodological criticisms in EEG paper reviews. The audit explicitly checks for each:

### Statistical concerns
1. **Cluster-forming threshold not justified** — "Why alpha=0.05 for cluster formation? This is arbitrary." Reviewers expect justification (e.g., based on df) or use of TFCE which avoids threshold selection.
2. **Adjacency matrix not reported** — "How were channel neighbors defined?" Must state: Delaunay triangulation, distance-based (radius in mm), or template-based.
3. **Multiple comparisons not handled** — Running 5 claims at alpha=0.05 without correction. Even if each uses cluster permutation (which controls FWER within a test), testing multiple claims inflates the overall false positive rate.
4. **Effect size not reported** — "No effect size is reported, making it impossible to judge practical significance." Cohen's d or partial eta-squared is expected.
5. **Post-hoc exclusion not pre-registered** — "3 subjects were excluded for 'excessive artifacts' but no objective criterion is stated."

### Preprocessing concerns
6. **Bandpass too aggressive for time window** — A 1 Hz high-pass filter distorts ERP components slower than ~200 ms (P3, N400, LPP). Tanner et al. (2015) showed 0.1 Hz is safer for slow ERPs.
7. **ICA decisions not transparent** — "How were artifactual components identified? How many were rejected per subject?" Reviewers expect: method (manual, ICLabel, MARA), number rejected (mean +/- SD), criteria.
8. **Channel selection appears data-driven** — "The ROI appears to be chosen from the grand average topomap." This is circular (Luck & Gaspelin 2017).

### Reporting concerns
9. **Trial counts not reported per condition per subject** — Essential for judging ERP quality.
10. **Baseline correction window not stated** — Must report: window (e.g., -200 to 0 ms), method (subtractive).
11. **Filter settings incomplete** — Must report: passband, filter type (FIR/IIR), order/transition bandwidth, causal vs zero-phase.

### Figure concerns
12. **Jet colormap** — Perceptually non-uniform; creates artificial boundaries. Use `RdBu_r`, `viridis`, or `coolwarm`.
13. **Asymmetric color scales on difference topoplots** — e.g., -2 to +5 µV exaggerates the positive direction. Always use symmetric limits (e.g., -3 to +3).
14. **Missing scale bars** — Topoplots without color bar labels, or waveform plots without µV scale.
15. **No baseline period shown** — ERP waveform plots should show the pre-stimulus baseline.

## COBIDAS-MEEG checklist (Pernet et al. 2020, Nature Neuroscience)

The audit verifies these items are reported in the methods section. Each item is tagged as present, absent, or partial:

### Data acquisition
- [ ] EEG system (manufacturer, model)
- [ ] Number of channels and montage
- [ ] Sampling rate
- [ ] Online reference and ground
- [ ] Impedance threshold

### Preprocessing
- [ ] Offline re-reference scheme
- [ ] Filter type, passband, order/transition bandwidth
- [ ] Notch filter (if applied)
- [ ] Downsampling (if applied, with anti-aliasing filter)
- [ ] Epoch duration and event-locking
- [ ] Baseline correction window and method
- [ ] Artifact rejection method and criteria
- [ ] Artifact rejection rates (mean, range)
- [ ] ICA method, number of components removed (mean, range), identification criteria
- [ ] Channel interpolation (method, number per subject)
- [ ] Trial counts per condition per subject (mean, range)

### Analysis
- [ ] Statistical test and software (name + version)
- [ ] Number of permutations and RNG seed
- [ ] Cluster-forming threshold and derivation
- [ ] Channel adjacency matrix definition
- [ ] Alpha level and tail justification
- [ ] Multiple-comparisons correction (if multiple claims)
- [ ] Effect size metric and formula
- [ ] Time window and ROI with justification (literature or pre-registration)

## Domain knowledge (audit-relevant, with citations)

- **Microstate template strategy drives reliability.** A single GLOBAL/group template (maps clustered from data concatenated across subjects/recordings) yields high test-retest reliability (mean Cronbach alpha > 0.8, SEM ~10% of the mean), whereas fitting maps per individual recording is the LEAST reliable strategy (alpha ~0.52). Audit should prefer group/global templates and flag per-recording fitting. (Khanna et al. 2014, *Neurosci Biobehav Rev*, "Microstates in resting-state EEG: current status and future directions".)
- **Microstate data requirements.** Resting-state, full-head montage with >= 20 electrodes, average reference, no bad channels (interpolate/remove first), and >= ~3 min (warn below ~2 min) of clean post-preprocessing data. Khanna 2014 used ~128 s (range 80-204 s). Core features (duration, occurrence, coverage) are reliably recovered down to 19 and even 8 channels (alpha 0.87-0.91), but microstates C and D are slightly less consistent than A and B at low density. (Khanna et al. 2014.)
- **Microstate K=4 GEV range.** Four canonical maps explain ~65-78% of global field power variance (GEV) in healthy resting EEG; ~70% is typical. Values far below this floor indicate too few maps or noisy data (the eeg-microstate skill warns below 0.60). (Khanna et al. 2014; cf. Murray et al. 2008, *Brain Topogr*, for the GEV definition.)
- **Average reference is mandatory for EEG source localization.** A non-average reference biases the EEG forward model; common-average referencing before computing the leadfield is a hard methodological gate, not a stylistic choice. (Michel & Brunet 2019, *Front Neurol*, "EEG source imaging: a practical review of the analysis steps.")
- **Co-registration is a fitted, verified step — not an unintended identity transform.** Sensor positions must be aligned to the head/MRI via fiducials then refined (MNE: `Coregistration.fit_fiducials()` then `fit_icp()`, or the bundled `trans='fsaverage'` for the template head). Template-electrode fits are imperfect (electrodes sink below or float above the scalp) and must be eyeballed with `mne.viz.plot_alignment(..., surfaces='head-dense')`. An *unintended* identity trans on a non-template setup or an unset montage means co-registration never happened — but the documented `trans='fsaverage'` template path is legitimate (introduces ~5-10 mm error; restrict to ROI/lobar claims). (Michel & Brunet 2019; MNE coregistration docs; cf. eeg-source.)
- **Template-BEM EEG source results are approximate.** Template BEM (fsaverage/standard_bem) + template electrodes (standard_1020/1005) with no individual MRI and no digitized electrodes support only coarse ROI/lobar/network-level localization, never voxel-precise peaks; conductivity and geometry errors are large for EEG. Higher electrode density (64-256) and digitized positions + individual MRI are required for finer spatial claims; low-density (< 32 ch) montages give poor depth/spatial resolution. (Michel & Brunet 2019.)
