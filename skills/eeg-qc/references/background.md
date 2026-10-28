## Domain Knowledge (distilled from EEG data-quality literature)

These guidelines are encoded from EEG quality-control methodology. The LLM must follow them when computing metrics and setting gates.

### The PREP pipeline and before/after reporting (Bigdely-Shamlo et al. 2015, Frontiers in Neuroinformatics)

- PREP standardizes early-stage quality control: line-noise removal → robust average reference → RANSAC bad-channel detection → interpolation, with quality numbers logged at each step.
- **RANSAC** predicts each channel from a random subset of spatial neighbors and flags channels poorly predicted across many random subsets — robust to global noise that fools variance thresholds. In Python: `pyprep.NoisyChannels(raw).find_all_bads()` runs RANSAC plus correlation, deviation, high-frequency-noise, SNR, and flat criteria.
- PREP's reporting philosophy — record the data state *before and after* each operation so degradation is visible — is exactly the Phase C "stage SNR delta" table here.
- Cite: Bigdely-Shamlo, N., Mullen, T., Kothe, C., Su, K.-M., & Robbins, K. A. (2015). The PREP pipeline: standardized preprocessing for large-scale EEG analysis. Frontiers in Neuroinformatics, 9, 16.

### FASTER channel/epoch/component metrics (Nolan et al. 2010, Journal of Neuroscience Methods)

- FASTER (Fully Automated Statistical Thresholding for EEG artifact Rejection) thresholds z-scored statistical properties at three levels.
- **Channel level**: variance, mean correlation with other channels, and **Hurst exponent**; any metric with `|z| > 3` marks the channel bad. The Hurst criterion catches channels whose temporal-correlation structure departs from the clean-EEG norm (~0.7) — a detector that pure amplitude metrics miss.
- **Epoch level**: amplitude range, variance, channel deviation. **Component level** (after ICA): spatial kurtosis, slope, Hurst, median gradient, correlation with EOG.
- AEA's per-channel table (variance-z, correlation/spectral-z, Hurst-z) is a direct port of the FASTER channel metrics; combine with LOF/RANSAC rather than relying on any single one.
- Cite: Nolan, H., Whelan, R., & Reilly, R. B. (2010). FASTER: Fully Automated Statistical Thresholding for EEG artifact Rejection. Journal of Neuroscience Methods, 192(1), 152–162.

### Local Outlier Factor for bad-channel detection (Kumaravel et al. 2022, Sensors)

- LOF scores each channel by how isolated it is relative to its spatial neighbors in feature space, catching channels that are anomalous *given the montage geometry* even when their raw variance looks ordinary.
- MNE exposes it as `mne.preprocessing.find_bad_channels_lof(raw, n_neighbors=20, threshold=1.5)`; the default threshold ~1.5 balances sensitivity and false positives. It is the bad-channel detector adopted in the automated-EEG (HAPPE/automagic) family.
- LOF is geometry-aware but reference- and montage-dependent — corroborate with RANSAC and treat a single-detector flag as a candidate, not a verdict.
- Cite: Kumaravel, V. P., Buiatti, M., Parise, E., & Farella, E. (2022). Adaptable and robust EEG bad channel detection using Local Outlier Factor (LOF). Sensors, 22(19), 7314.

### Automated quality metrics for large/developmental datasets — HAPPE (Gabard-Durnam et al. 2018, Frontiers in Neuroscience)

- HAPPE (Harvard Automated Processing Pipeline for EEG) ships a per-file **quality-metrics report**: number/percent of good channels, percent of variance retained after artifact removal, percent of segments/trials kept, and cross-correlation of the data before vs after each step. These quality numbers — not just the cleaned data — are the deliverable.
- The design intent (high-throughput, developmental/clinical cohorts where manual inspection does not scale) is the same use case AEA's dashboard targets: a machine-readable pass/warn/fail per recording so bad data is caught before analysis.
- AEA's Phase D summary table (good-channel %, variance/SNR retained, trials kept, before/after correlation) mirrors the HAPPE quality report.
- Cite: Gabard-Durnam, L. J., Mendez Leal, A. S., Wilkinson, C. L., & Levin, A. R. (2018). The Harvard Automated Processing Pipeline for EEG (HAPPE): standardized processing software for developmental and high-artifact data. Frontiers in Neuroscience, 12, 97.

### EEG data quality at scale and NEMAR (Delorme 2023, Scientific Reports; Delorme et al. 2022, Database)

- Delorme (2023) introduces a quantitative EEG data-quality metric — the percentage of channels showing a significant condition difference in an early post-stimulus window — to objectively *compare* automated preprocessing methods, and finds that (apart from high-pass filtering and bad-channel interpolation) several automated corrections did not improve, and sometimes reduced, that metric. The lesson AEA encodes: a QC report needs an explicit, quantitative quality criterion, and a "cleaning" step is only justified if it measurably improves it — exactly the Phase C before/after delta.
- NEMAR / OpenNeuro (Delorme et al. 2022) provide automated quality dashboards over thousands of openly shared EEG/MEG datasets, surfacing per-dataset quality indicators (channel counts, sampling, artifact levels, processing provenance) so reusers can triage data before downloading.
- Implication for AEA: emit a machine-readable QC JSON + an HTML dashboard with explicit, reported thresholds, so a downstream consumer (or `eeg-audit`) can decide usability without re-running the pipeline.
- Cite: Delorme, A. (2023). EEG is better left alone. Scientific Reports, 13, 2372. (and) Delorme, A., et al. (2022). NEMAR: an open access data, tools and compute resource operating on neuroelectromagnetic data. Database (Oxford), 2022, baac096. (See also Pernet et al. 2019, EEG-BIDS, Scientific Data 6, 103, for the metadata that makes QC auditable.)

### AutoReject and data-driven rejection previews (Jas et al. 2017, NeuroImage)

- AutoReject learns per-channel peak-to-peak thresholds by cross-validation rather than using an arbitrary fixed number; `get_rejection_threshold(epochs)` returns a data-driven global threshold dict.
- For QC, run it in **preview** mode only: compare the data-driven threshold to what the epoch stage actually applied. A large gap means the upstream reject was mis-tuned. QC never re-rejects — it flags the discrepancy for `eeg-epoch` to revisit.
- Cite: Jas, M., Engemann, D. A., Bekhti, Y., Raimondo, F., & Gramfort, A. (2017). Autoreject: Automated artifact rejection for MEG and EEG data. NeuroImage, 159, 417–429.

### Standardized measurement error as a recording-quality metric (Luck et al. 2021, Psychophysiology)

- The standardized measurement error (SME) quantifies the data quality of a single-subject ERP measure (e.g. mean amplitude over a window) as the standard error of that measure across trials — a principled, score-specific SNR that an arbitrary "peak/RMS" ratio lacks.
- SME makes data quality comparable across subjects and labs and exposes when a low trial count, not the effect, drives a noisy estimate. Report SME (or an across-trial evoked SNR) alongside trial count, since ERP SNR improves as `sqrt(N)` (Luck 2014).
- Cite: Luck, S. J., Stewart, A. X., Simmons, A. M., & Rhemtulla, M. (2021). Standardized measurement error: A universal metric of data quality for averaged event-related potentials. Psychophysiology, 58(6), e13793.

### Head motion, EMG, and uncorrectable artifacts (Luck 2014, An Introduction to the ERP Technique, 2nd ed.)

- Large synchronous low-frequency swings across all channels are head/cable movement — **uncorrectable** by ICA or interpolation; they must be annotated and the segment rejected. A QC head-motion index (low-frequency RMS + count of large excursions) quantifies how much data this costs.
- Peri-auricular / temporalis EMG is high-frequency "fuzz" on ear-adjacent channels and is **ICA-resistant**; a high residual EMG/HF ratio after ICA is a genuine quality warning, not a pipeline bug. Quantify it as a high-band/low-band power ratio.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd ed., ch. 6 (artifact identification). MIT Press.

### COBIDAS-MEEG quality reporting (Pernet et al. 2020, Nature Neuroscience)

The methods/QC section must report, with exact numbers and thresholds:
- Number and percent of bad/interpolated channels per subject (mean, range), and the detection method and criteria.
- Percent of data/epochs rejected per subject and per condition, and the rejection method.
- Line-noise handling and any residual line power.
- The exact pass/warn/fail thresholds and how subjects were included/excluded — no hidden gating.
- Software and version for every metric.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nature Neuroscience, 23(12), 1473–1483.
