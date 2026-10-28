## Domain Knowledge (distilled from EEG complexity / nonlinear-dynamics literature)

### Lempel-Ziv complexity (Lempel & Ziv 1976; Aboy et al. 2006)
- Coarse-grain the signal to a binary string (median threshold is the amplitude-robust default), parse into the minimal set of distinct substrings, count `c(n)`, normalize `LZC = c(n) / (n / log2(n))` so values are ≈ `[0,1]` and comparable across epoch lengths.
- LZC tracks the rate of new-pattern generation — it drops under anesthesia/loss of consciousness and rises in alert, complex states.
- Cite: Lempel, A., & Ziv, J. (1976). On the complexity of finite sequences. IEEE Transactions on Information Theory, 22(1), 75–81. Aboy, M., Hornero, R., Abásolo, D., & Álvarez, D. (2006). Interpretation of the Lempel-Ziv complexity measure in the context of biomedical signal analysis. IEEE Transactions on Biomedical Engineering, 53(11), 2282–2288.

### Permutation entropy and PLZC (Bandt & Pompe 2002; Bai et al. 2015)
- Permutation entropy replaces amplitude values with ordinal patterns (rank order of `m` consecutive samples), making it amplitude-blind and robust to monotonic noise; `PE = H / ln(m!)`.
- PLZC = ordinal symbolization + LZ parse, normalized by `log_{m!}(n)`; combines PE's amplitude-independence with LZC's pattern-novelty sensitivity and is more noise-robust than amplitude-thresholded LZC.
- Default `order/m`: PE order 3 (3–7 typical), PLZC `m=4`; both require `m! ≪ window length`.
- Cite: Bandt, C., & Pompe, B. (2002). Permutation entropy: a natural complexity measure for time series. Physical Review Letters, 88(17), 174102. Bai, Y., Liang, Z., & Li, X. (2015). A permutation Lempel-Ziv complexity measure for EEG analysis. Biomedical Signal Processing and Control, 19, 102–114.

### Sample vs approximate entropy (Richman & Moorman 2000; Pincus 1991)
- ApEn counts self-matches and is biased toward regularity, with strong dependence on record length. SampEn excludes self-matches (`B_{m+1}/B_m` ratio, strict `< r`), removing this bias and giving more consistent estimates across data lengths — prefer SampEn.
- Standard parameters: `m = 2`, `r = 0.2 * SD` (Richman–Moorman); some EEG studies use `0.15 * SD`. Chebyshev (max-norm) distance. `r` must be expressed relative to the SD of the same segment.
- Cite: Richman, J. S., & Moorman, J. R. (2000). Physiological time-series analysis using approximate entropy and sample entropy. American Journal of Physiology - Heart and Circulatory Physiology, 278(6), H2039–H2049. Pincus, S. M. (1991). Approximate entropy as a measure of system complexity. Proceedings of the National Academy of Sciences, 88(6), 2297–2301.

### Wavelet entropy (Rosso et al. 2001)
- Compute relative energies of DWT sub-bands, then Shannon entropy of that distribution; quantifies spectral disorder (flat spectrum across sub-bands ⇒ high wavelet entropy). db4 with depth tied to `fs` maps sub-bands onto canonical EEG bands.
- Cite: Rosso, O. A., Blanco, S., Yordanova, J., Kolev, V., Figliola, A., Schürmann, M., & Başar, E. (2001). Wavelet entropy: a new tool for analysis of short duration brain electrical signals. Journal of Neuroscience Methods, 105(1), 65–75.

### Hilbert-Huang transform (Huang et al. 1998)
- EMD decomposes a signal into Intrinsic Mode Functions adaptively (no fixed basis); the Hilbert transform of each IMF yields instantaneous amplitude/frequency, summed over time into a marginal spectrum whose Shannon entropy is HHSE. EMD suffers end-effects and mode mixing — pad (e.g. triple) the signal and discard boundary thirds.
- Cite: Huang, N. E., Shen, Z., Long, S. R., Wu, M. C., Shih, H. H., Zheng, Q., Yen, N.-C., Tung, C. C., & Liu, H. H. (1998). The empirical mode decomposition and the Hilbert spectrum for nonlinear and non-stationary time series analysis. Proceedings of the Royal Society of London A, 454(1971), 903–995.

### Recurrence quantification analysis (Marwan et al. 2007)
- A recurrence plot marks when a trajectory revisits a neighbourhood in reconstructed phase space; RQA quantifies its texture: RR (density), DET (diagonal structure ⇒ determinism), L (mean diagonal length ⇒ predictability), ENTR (diagonal-length entropy ⇒ complexity). Set embedding dimension via FNN and delay via mutual information; threshold via fixed-fraction-of-SD or fixed recurrence rate.
- Cite: Marwan, N., Romano, M. C., Thiel, M., & Kurths, J. (2007). Recurrence plots for the analysis of complex systems. Physics Reports, 438(5–6), 237–329.

### Scale-free dynamics, DFA, and the slope-Hurst relation (Peng et al. 1994; He 2014; Donoghue et al. 2020)
- EEG power spectra follow `S(f) ∝ f^(-beta)`; the aperiodic exponent (specparam/FOOOF) is the modern, oscillation-corrected way to estimate `beta`. DFA gives the scaling exponent `alpha`; for fractional Gaussian/Brownian processes Hurst `H = (beta - 1) / 2` with `beta ∈ [1, 3]`. Scaling estimates require long segments and (for DFA) detrending; z-score each window.
- Cite: Peng, C.-K., Buldyrev, S. V., Havlin, S., Simons, M., Stanley, H. E., & Goldberger, A. L. (1994). Mosaic organization of DNA nucleotides. Physical Review E, 49(2), 1685–1689. He, B. J. (2014). Scale-free brain activity: history, mechanisms, cognition, and disease. Trends in Cognitive Sciences, 18(9), 480–487. Donoghue, T., Haller, M., Peterson, E. J., et al. (2020). Parameterizing neural power spectra into periodic and aperiodic components. Nature Neuroscience, 23(12), 1655–1665.

### Dispersion and multiscale entropy (Rostaghi & Azami 2016; Costa et al. 2002; Wu et al. 2014)
- Dispersion entropy maps amplitudes through the normal CDF into `c` classes and counts `c^m` dispersion patterns: `O(N)`, noise-tolerant, and amplitude-aware (PE discards amplitude). Multiscale entropy coarse-grains across scales `tau` and reports the area under the SampEn-vs-scale curve; the tolerance `r` is fixed at the scale-1 SD across all scales, and RCMSE (composite match-count averaging) is the robust short-window variant. RCMDE is the dispersion-entropy multiscale form for long EEG.
- Cite: Rostaghi, M., & Azami, H. (2016). Dispersion entropy: a measure for time-series analysis of complexity. IEEE Signal Processing Letters, 23(5), 610–614. Costa, M., Goldberger, A. L., & Peng, C.-K. (2002). Multiscale entropy analysis of complex physiologic time series. Physical Review Letters, 89(6), 068102. Wu, S.-D., et al. (2014). Time series analysis using composite multiscale entropy. Physics Letters A, 378(20), 1369–1374.

### Multichannel signal diversity and perturbational complexity (Schartner et al. 2015; Casali et al. 2013; Comolatti et al. 2019)
- Spatiotemporal LZc (Hilbert-binarized channels-by-time matrix) plus ACE (differentiation: variability of active-channel sets) and SCE (integration: variability of synchronous-channel sets) drop under propofol and rise under psychedelics; normalize against phase-shuffled surrogates before cross-montage comparison. PCI perturbs the cortex (TMS), compresses the source-space spatiotemporal response, and normalizes by source entropy as an explicit consciousness biomarker; PCIst is the source-model-free SVD variant.
- Cite: Schartner, M., et al. (2015). Complexity of multi-dimensional spontaneous EEG decreases during propofol-induced general anaesthesia. PLoS ONE, 10(8), e0133532. Casali, A. G., et al. (2013). A theoretically based index of consciousness independent of sensory processing and behavior. Science Translational Medicine, 5(198), 198ra105. Comolatti, R., et al. (2019). A fast and general method to empirically estimate the complexity of brain responses to transcranial and intracranial stimulations. Brain Stimulation, 12(5), 1280–1289.

### Criticality: LRTC and neuronal avalanches (Hardstone et al. 2012; Shriki et al. 2013; Toker et al. 2022)
- Long-range temporal correlations are quantified by DFA on the *amplitude envelope of a narrow-band oscillation* (e.g. alpha 8–13 Hz, exponent ~0.6–0.8) — not broadband DFA, which conflates the aperiodic slope with LRTC. Neuronal avalanches are runs of supra-threshold point events binned at the mean inter-event interval; criticality is evidenced by power-law size (~-1.5) and duration (~-2.0) distributions (ML-fit + Clauset KS), a branching ratio `sigma ≈ 1`, and the crackling-noise scaling relation. Edge-of-chaos chaoticity (0–1 test) is a complementary criticality view.
- Cite: Hardstone, R., et al. (2012). Detrended fluctuation analysis: a scale-free view on neuronal oscillations. Frontiers in Physiology, 3, 450. Shriki, O., et al. (2013). Neuronal avalanches in the resting MEG of the human brain. Journal of Neuroscience, 33(16), 7079–7090. Toker, D., et al. (2022). Consciousness is supported by near-critical slow cortical electrodynamics. PNAS, 119(7), e2024455119.

### Spatial complexity: Omega complexity and multichannel complexity (Wackermann 1996; Saito et al. 1998)
- Treat channels as variables, take the covariance eigenvalue spectrum, normalize to a probability vector and compute its entropy. Omega `= exp(entropy)`; NSC `= entropy / log(M)` ∈ `[0,1]`. High spatial complexity = many independent processes = low global functional connectivity — a reference/volume-conduction-robust complement to pairwise connectivity. Average reference is required so the spectrum reflects topography, not the reference choice.
- Cite: Wackermann, J. (1996). Beyond mapping: estimating complexity of multichannel EEG recordings. Acta Neurobiologiae Experimentalis, 56(1), 197–208. Saito, N., Kuginuki, T., Yagyu, T., Kinoshita, T., Koenig, T., Pascual-Marqui, R. D., Kochi, K., Wackermann, J., & Lehmann, D. (1998). Global, regional, and local measures of complexity of multichannel electroencephalography in acute, neuroleptic-naive, first-break schizophrenics. Biological Psychiatry, 43(11), 794–802.

### Clinical/validation conventions (anesthesia depth; eyes-open/closed)
- Across LZC, PLZC, SampEn, PE, wavelet/HHT entropy and RQA-DET/ENTR, complexity **decreases** (and RR **increases**) under deep anesthesia vs awake — the canonical demonstration. Eyes-open resting EEG should show **higher** complexity than eyes-closed; use this as a built-in sanity check.
- Window convention: 5 s windows with overlap (e.g. 2 s step) for entropy/LZC/RQA; ≥16 s for scale-free/Hurst.
- Cite: Zhang, X.-S., Roy, R. J., & Jensen, E. W. (2001). EEG complexity as a measure of depth of anesthesia for patients. IEEE Transactions on Biomedical Engineering, 48(12), 1424–1433.
