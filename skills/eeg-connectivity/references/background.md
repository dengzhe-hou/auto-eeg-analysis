## Domain Knowledge (distilled from EEG connectivity methodology literature)

### Debiased wPLI (Vinck et al. 2011, NeuroImage)

- The weighted phase lag index (wPLI) weights the contribution of each observation by the magnitude of the imaginary component of the cross-spectrum.
- **Why wPLI over PLI**: Standard PLI is discontinuous around zero phase lag, making it noisy for weak coupling. wPLI smooths this discontinuity by weighting.
- **Why debiased squared wPLI**: The standard wPLI estimator has positive finite-sample bias. MNE's `wpli2_debiased` applies a bias correction to an estimator of **squared** wPLI; report this estimand and method name. Debiasing does not imply exact unbiasedness for arbitrary finite samples.
- Volume conduction produces zero-phase-lag signals; wPLI is insensitive to these because it ignores contributions at zero lag.
- Limitation: wPLI cannot detect true zero-lag interactions (which can exist in neural data due to common subcortical input).
- Cite: Vinck, M., Oostenveld, R., van Wingerden, M., Battaglia, F., & Pennartz, C. M. (2011). An improved index of phase-synchronization for electrophysiological data in the presence of volume-conduction, noise and sample-size bias. NeuroImage, 55(4), 1548–1565.

### Phase-locking value (Lachaux et al. 1999, Human Brain Mapping)

- PLV measures the consistency of phase differences between two signals across trials or time.
- PLV = |mean(exp(j * (phase_A - phase_B)))| across trials. Ranges from 0 (no synchrony) to 1 (perfect synchrony).
- **Limitation**: PLV is sensitive to volume conduction — two electrodes picking up the same source will show high PLV (zero-lag, in-phase or anti-phase). This is NOT neural connectivity.
- PLV is also biased by trial count: fewer trials → higher PLV due to finite-sample effects. Always match trial counts across conditions.
- For sensor-space analysis, PLV should only be interpreted for non-zero phase lags, or replaced with wPLI/imaginary coherence.
- Cite: Lachaux, J. P., Rodriguez, E., Martinerie, J., & Varela, F. J. (1999). Measuring phase synchrony in brain signals. Human Brain Mapping, 8(4), 194–208.

### Closed-form definitions (for verifying MNE output)

Given per-segment/per-trial phase difference `rp = phase_x - phase_y` and cross-spectrum `Sxy = X·conj(Y)` (analytic signals), the MNE method strings compute:
- **PLV** = `|mean(exp(1j·rp))|`, range [0,1]. 0 = uniform phase diffs (no sync); 1 = fixed phase diff.
- **PLI** = `|mean(sign(imag(Sxy)))|`, range [0,1]. 0 = phase-lag sign ± equally often; 1 = always one sign. Insensitive to zero-lag (VC).
- **wPLI** = `|mean(imag(Sxy))| / mean(|imag(Sxy)|)`, range [0,1]; the debiased variant (`wpli2_debiased`) removes finite-sample positive bias.
- **Coherence (MSC)** = `|mean(Sxy)|² / (mean(Sxx)·mean(Syy))`, range [0,1] — the average is over segments/trials **before** the magnitude ratio, so a single segment gives a trivial `|coh|=1`. `imcoh` uses the `imag` part of coherency (VC-robust).
- **ITC / inter-trial phase consistency** (same machinery, single channel vs reference) = `|mean over trials of exp(1j·angle(coef))|`; PLV is exactly this applied to the phase *difference* between two channels. ITC needs the per-trial complex coefficients, is amplitude-independent, and is positively biased at low trial counts.

These match MNE's `plv`/`pli`/`wpli`/`coh`/`imcoh`, so hand-computed values can be used to sanity-check `spectral_connectivity_*` output.

### Tutorial on connectivity methods (Bastos & Schoffelen 2016, NeuroImage)

- Comprehensive tutorial covering coherence, imaginary coherence, PLV, wPLI, Granger causality, and directed transfer function.
- **Key recommendations**:
  - Use directed measures (Granger, PDC, DTF) only when directionality is the research question and data quality supports it (long, stationary epochs).
  - For undirected functional connectivity, wPLI or imaginary coherence is preferred over coherence or PLV at the sensor level.
  - At the source level, signal leakage is the primary concern — apply orthogonalization or use leakage-robust metrics.
  - Always simulate known connectivity patterns to validate the pipeline before applying to real data.
- Cite: Bastos, A. M., & Schoffelen, J. M. (2016). A tutorial review of functional connectivity analysis methods and their interpretational pitfalls. Frontiers in Systems Neuroscience, 9, 175.

### Imaginary coherency (Nolte et al. 2004, Clinical Neurophysiology)

- The imaginary part of coherency is zero for instantaneous (zero-lag) mixing, so it cannot be produced by volume conduction of a single source to multiple electrodes — only by genuinely lagged (time-delayed) interaction.
- In MNE this is `method='imcoh'`; pair it with `coh` whenever coherence is requested on sensor data so the VC-robust reading is always available alongside the contaminated one.
- Limitation: like wPLI/PLI, it is blind to true zero-lag coupling and its sign/magnitude depends on the interaction's phase lag.
- Cite: Nolte, G., Bai, O., Wheaton, L., Mari, Z., Vorbach, S., & Hallett, M. (2004). Identifying true brain interaction from EEG data using the imaginary part of coherency. Clinical Neurophysiology, 115(10), 2292–2307.

### Granger causality: model order and the time-reversed control

- Bivariate spectral Granger asks whether adding y's past reduces the residual variance of predicting x: `GC = log(var_restricted / var_full) > 0` ⇒ y Granger-causes x.
- **Always test both directions** (x→y and y→x); cause vs effect is not known a priori.
- **Report the time-reversed control** (`method='gc_tr'` alongside `'gc'`): genuine GC should reverse under time reversal, whereas spurious GC driven by SNR/amplitude asymmetry or volume conduction does not — the net (gc − gc_tr) guards against false directionality.
- For any explicit-MVAR path (e.g. statsmodels VAR — note statsmodels is an optional dependency not present in `aeais`), **model order p must be selected first** via AIC/BIC; requires stationary, sufficiently long, well-SNR data.
- Granger on sensor data is highly susceptible to volume conduction → prefer source space.
- **PDC normalization — report the variant.** Standard column-normalized PDC is *not* scale-invariant and, perversely, **decreases** when one source drives several targets (the column normalization splits the outflow among targets). Use **generalized PDC (gPDC)**, which normalizes by the innovation (residual) variance and restores scale-invariance, and always state which variant you computed. Cite: Baccalá, L. A., & Sameshima, K. (2021). Partial directed coherence: twenty years on some history and an appraisal. Biological Cybernetics, 115(3), 195–204 (gPDC).
- Cite: Haufe, S., Nikulin, V. V., Müller, K. R., & Nolte, G. (2013). A critical assessment of connectivity measures for EEG data: A simulation study. NeuroImage, 64, 120–133 (time-reversed Granger control). Barnett, L., & Seth, A. K. (2014). The MVGC multivariate Granger causality toolbox. Journal of Neuroscience Methods, 223, 50–68 (model-order/spectral GC).

### Cross-frequency coupling (Palva & Palva 2012, Trends in Cognitive Sciences)

- Phase-amplitude coupling (PAC) is the most studied cross-frequency interaction: the phase of a slow oscillation modulates the amplitude of a faster oscillation.
- Common examples: theta-phase × gamma-amplitude coupling in hippocampus and cortex during memory tasks.
- **Methods**: Modulation Index (Tort et al. 2010), Mean Vector Length (Canolty et al. 2006), General Linear Model (Dupre la Tour et al. 2017).
- **Pitfalls**:
  - Sharp transients (e.g., epileptic spikes) create artifactual PAC due to harmonic content — filter carefully.
  - PAC estimates require long data segments; short epochs produce unreliable estimates.
  - Always test against surrogate distributions to establish significance.
- Cite: Palva, S., & Palva, J. M. (2012). Discovering oscillatory interaction networks with M/EEG: challenges and breakthroughs. Trends in Cognitive Sciences, 16(4), 219–230.

### Modulation Index and the comodulogram (Tort et al. 2010, J. Neurophysiol.)

- The **Modulation Index (MI)** quantifies PAC as the Kullback–Leibler divergence between the observed mean-amplitude-by-phase distribution and a uniform distribution, normalized by `log(n_bins)` so MI ∈ [0, 1] (0 = no coupling, larger = stronger phase modulation of amplitude). It is robust to amplitude scaling and to the number of phase bins (≈18 is standard).
- **Comodulogram**: computing MI over a grid of slow phase-frequencies × fast amplitude-frequencies maps where in the spectrum coupling lives, rather than assuming a band-pair a priori. The paper also formalizes the **filter-bandwidth constraint**: the amplitude filter must be wide enough (bandwidth ≳ 2× the modulating phase frequency) for the envelope to carry the slow rhythm — too-narrow amplitude filters destroy detectable PAC.
- **Preferred phase**: the phase bin (or amplitude-weighted circular mean of phase) at which the fast amplitude is maximal; comparable across conditions and the target of circular consistency tests (Rayleigh).
- **Surrogates are mandatory**: MI is positively biased, so significance must come from a surrogate null (block-shift / trial-shuffle / phase-scramble) and a z-score or permutation p, not the raw MI. The paper compares MI favourably to mean-vector-length and the GLM-PAC in robustness to noise and to the amplitude distribution.
- **Spurious PAC**: non-sinusoidal waveforms and sharp edges (spikes, ERPs, square-ish rhythms) inject harmonics that masquerade as PAC; inspect the raw waveform and never interpret MI without surrogate control.
- Cite: Tort, A. B. L., Komorowski, R., Eichenbaum, H., & Kopell, N. (2010). Measuring phase-amplitude coupling between neuronal oscillations of different frequencies. Journal of Neurophysiology, 104(2), 1195–1210.

### Signal leakage in source-space connectivity (Colclough et al. 2015, NeuroImage)

- Source reconstruction introduces artificial correlations between nearby sources due to the ill-posed inverse problem (spatial leakage).
- **Orthogonalization**: Symmetric multivariate orthogonalization removes instantaneous (zero-lag) correlations between all source pairs simultaneously, suppressing leakage while preserving lagged interactions.
- This is critical: computing connectivity (even wPLI) on source-space signals without leakage correction will show spurious local connectivity patterns.
- **Implementation**: `mne_connectivity` supports `method='plv'` on orthogonalized signals. Alternatively, compute envelope correlations after orthogonalization.
- Cite: Colclough, G. L., Brookes, M. J., Smith, S. M., & Woolrich, M. W. (2015). A symmetric multivariate leakage correction for MEG connectomes. NeuroImage, 117, 439–448.

### Leakage-corrected amplitude-envelope correlation (AEC-c) — the concrete recipe

The "compute envelope correlations after orthogonalization" line above needs a recipe, because AEC indexes slow band-power *co-fluctuation* and recovers a **different** network than wPLI/phase metrics — offer it alongside the phase metric, never as a substitute. Per ROI pair: band-pass both signals → pairwise-orthogonalize (regress out the real part of B from A) → Hilbert envelope → log → Pearson correlation. The Hipp/Brookes pairwise orthogonalization is **asymmetric** (`orth(A|B) ≠ orth(B|A)`), so you MUST symmetrize — average the upper and lower triangles of the AEC matrix before any graph analysis, or the network is direction-of-regression-dependent.

```python
def aec_corrected_pair(a, b):
    """Pairwise leakage-corrected AEC for one ROI pair (already band-passed)."""
    from scipy.signal import hilbert
    b_orth = b - (np.real(np.vdot(b, a)) / np.real(np.vdot(a, a))) * a  # regress real(A) out of B
    ea = np.log(np.abs(hilbert(a)))
    eb = np.log(np.abs(hilbert(b_orth)))
    return np.corrcoef(ea, eb)[0, 1]
# Build full matrix both ways, then: aec = 0.5 * (M + M.T)  # symmetrize (asymmetric orth)
```

- **Reliability-paradox Critical Rule:** do NOT justify skipping leakage correction by citing the high test–retest reliability of uncorrected AEC/PLV/COH. Uncorrected envelope/phase metrics are dominated by a *shared-leakage* signal that is itself highly stable across sessions, so their reliability (≈0.97) is artifactually inflated and not evidence of validity — leakage-corrected metrics legitimately show lower but trustworthy reliability.
- Cite: Hipp, J. F., Hawellek, D. J., Corbetta, M., Siegel, M., & Engel, A. K. (2012). Large-scale cortical correlation structure of spontaneous oscillatory activity. Nature Neuroscience, 15(6), 884–890 (pairwise orthogonalized AEC). Nagy, B. et al. (2024). The reliability paradox in EEG/MEG connectivity. Human Brain Mapping, 45, e26747 (inflated reliability of uncorrected metrics).
