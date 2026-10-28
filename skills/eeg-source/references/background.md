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
- **Make the covariance inverse rank-aware.** An applied average reference removes one dimension; ICA cleaning, PCA reconstruction or interpolation can introduce further dependencies that `rank='info'` does not measure. Estimate `shared_rank` from the final cleaned samples with `compute_rank(..., rank=None, proj=True)`, then pass that dictionary to noise/data covariance and inverse/filter construction. Keep channels and projectors identical; do not independently estimate incompatible ranks in each window. An unregularized full-rank inverse of a rank-deficient covariance is numerically unstable and corrupts the spatial filter. Cite: Westner, B. U., Dalal, S. S., Gramfort, A., Litvak, V., Mosher, J. C., Oostenveld, R., & Schoffelen, J. M. (2022). A unified view on beamformers for M/EEG source reconstruction. NeuroImage, 246, 118789. API mechanism: [MNE compute_rank](https://mne.tools/stable/generated/mne.compute_rank.html), [MNE ICA notes](https://mne.tools/stable/generated/mne.preprocessing.ICA.html#notes).

### DICS frequency-domain beamforming (Gross et al. 2001, PNAS)

- DICS (Dynamic Imaging of Coherent Sources) is the frequency-domain extension of the LCMV beamformer: it replaces the time-domain data covariance with the cross-spectral density (CSD) at a target frequency, yielding source-level power and coherence at that frequency.
- **Practical recipe** (matches the standard EEG implementation): common-average reference; split into equal-length baseline and active windows; estimate the CSD (`mne.time_frequency.csd_morlet` or `csd_multitaper`) at the band of interest; build ONE filter on the pooled CSD (`make_dics`, `reg=0.05`, `pick_ori='max-power'`, `real_filter=True`); apply the same filter to each window via `apply_dics_csd`; report relative power `(active − baseline)/baseline`.
- **Equal-window requirement**: the baseline and active CSDs must have equal duration (equal degrees of freedom) or the relative-power contrast is biased toward the longer window.
- **DICS vs LCMV vs PCC**: same beamformer algorithm; DICS/LCMV are memory-friendly and return power, PCC returns single-trial Fourier coefficients for connectivity at higher memory cost. In MNE, source-space connectivity is obtained by applying a filter to epochs and feeding the source time courses to `mne_connectivity.spectral_connectivity_epochs`.
- Cite: Gross, J., Kujala, J., Hämäläinen, M., Timmermann, L., Schnitzler, A., & Salmelin, R. (2001). Dynamic imaging of coherent sources: studying neural interactions in the human brain. Proceedings of the National Academy of Sciences, 98(2), 694–699.
