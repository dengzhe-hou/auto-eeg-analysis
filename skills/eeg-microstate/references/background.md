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
