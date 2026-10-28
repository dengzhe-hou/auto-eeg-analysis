## Domain Knowledge

### Pernet et al. 2020: COBIDAS-MEEG checklist
- The Committee on Best Practices in Data Analysis and Sharing (COBIDAS) for MEEG provides a comprehensive checklist for reproducible EEG/MEG research.
- Key principle: every analysis decision must be reported with enough detail that an independent researcher can reproduce the results.
- The checklist covers: participants, task, acquisition, preprocessing, time-domain analysis, frequency-domain analysis, source analysis, statistics, and data sharing.
- Common reviewer complaints addressed by COBIDAS: missing filter specifications, unclear re-referencing, unreported artifact rejection criteria, missing effect sizes.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee. Nature Neuroscience, 23, 1473–1483.

### What reviewers look for in EEG methods sections
- **Filter specs**: Reviewers at JNeurosci and NeuroImage specifically check for filter type (FIR/IIR), order, zero-phase vs causal, and transition bandwidth. "Bandpass filtered 0.1–30 Hz" without these details will trigger a revision request.
- **ICA details**: Number of components, algorithm, seed, and automatic vs manual labeling. Reviewers want to know how many components were rejected and by what criteria.
- **Statistical robustness**: Permutation count (< 1000 raises eyebrows), seed for reproducibility, cluster-forming threshold justification (not just "p < 0.05"), adjacency definition.
- **Effect sizes**: Mandatory at most venues since ~2020. Cohen's d or dz for t-tests, partial eta-squared for ANOVAs. Reviewers reject "significant" without effect size.
- **Software versions**: Exact version numbers, not just "MNE-Python". Pin to the version used.
- **Sample size justification**: Increasingly expected. Power analysis or reference to similar published studies.

### Common methods section mistakes (from reviewer perspective)
1. Reporting cluster boundaries as precise effect onset/offset (Sassenhagen & Draschkow 2019).
2. Not reporting online reference electrode.
3. Saying "artifact rejection" without specifying threshold, method, or percentage rejected.
4. Using ANOVA on ERP amplitudes without acknowledging sphericity violations.
5. Not reporting whether filters were applied before or after epoching.
6. Missing the distinction between online and offline reference.

### Multiple-comparison policy to verbalize (Bonferroni vs FDR vs cluster permutation)
- Three corrections, three control targets: **Bonferroni** controls FWER but is over-conservative for autocorrelated EEG time/frequency points — reserve it for a small, pre-specified set of channels/windows. **FDR** (Benjamini-Hochberg, `mne.stats.fdr_correction(pvals, alpha=0.05, method='indep')`) controls the false-discovery rate and is the lightweight default for sparse/non-contiguous point tests. **Cluster-based permutation** (Maris & Oostenveld 2007) is the EEG default when the effect is contiguous in time/space/frequency, and is itself nonparametric (distribution-free inference + MC control in one step).
- The methods paragraph must name which one was used and what it controls; "corrected for multiple comparisons" alone is not COBIDAS-compliant.
- Flag tiny-N group analyses (n < ~12) as underpowered in the self-check; do not silently omit the correction the way demo notebooks sometimes do for small N.
- Cite: Maris & Oostenveld (2007), J Neurosci Methods 164:177-190; Benjamini & Hochberg (1995), JRSS-B 57:289-300; Genovese et al. (2002), NeuroImage 15:870-878.

### Deriving and reporting the cluster-forming threshold
- The cluster-forming t-threshold is the critical t at the chosen alpha and the design-specific df, not a generic 2.0: `threshold = scipy.stats.t.ppf(1 - alpha/2, df)` for a two-tailed test (note the alpha/2), with df = n_subjects-1 for a within-subject/paired design and df = nA+nB-2 for an independent-samples design. For F-based (ANOVA) cluster tests use `scipy.stats.f.ppf(1 - alpha, dfn, dfd)`.
- `threshold=None` lets MNE pick a default, but to *report* a specific cluster-forming alpha the threshold must be derived from df. The methods text should state both the alpha and the resulting t (or that the TFCE / hat-variance default was used).

### Reporting retained trials and the correction-over-rejection principle
- ERP/TFR averaging cancels random noise and reveals the time- and phase-locked signal; SNR scales with sqrt(n_trials), so trial count is a first-class methods item. Report retained trials per condition (mean + range across subjects), not just the rejection percentage.
- Best practice is **correction over rejection**: stereotyped artifacts (blinks, saccades, line noise) are corrected with ICA to preserve trial count, and trial rejection is reserved for non-correctable segments (movement, swallowing, channel pops). The methods text should make this division explicit, and over-aggressive IC removal is itself a reviewer flag because it can erase evoked signal (Chaumon et al. 2015).
- Cite: Luck (2014), An Introduction to the ERP Technique, 2nd ed.; Chaumon, Bishop & Busch (2015), J Neurosci Methods 250:47-63.

### Microstate methods boilerplate and healthy-adult norms (if a microstate stage ran)
- Report: clustering method (modified k-means / AAHC), number of maps K and the GEV they explain, fitting/backfitting with polarity ignored, and the temporal-smoothing window. State the per-class metrics reported: mean duration, occurrence/coverage, and transition probabilities.
- Healthy-adult sanity bands to sanity-check (not to assert) outputs: mean duration ~80-120 ms per class, occurrence ~2-6 /s per class (~10 /s total), coverage roughly A~21% / B~25% / C~27% / D~27%, and K=4 canonical maps explaining ~70% GEV; duration and frequency are inversely correlated (R~-0.72).
- Cite: Koenig et al. (2002), NeuroImage 16:41-48; Khanna et al. (2015), Neuroscience & Biobehavioral Reviews, 49, 105–113; Michel & Koenig (2018), NeuroImage 180:577-593.
