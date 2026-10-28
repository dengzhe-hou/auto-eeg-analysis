## Domain Knowledge (distilled from reporting methodology literature)

### COBIDAS-MEEG (Pernet et al. 2020, Nature Neuroscience)

The OHBM Committee on Best Practices in Data Analysis and Sharing (COBIDAS) published MEEG-specific guidelines requiring:

- Complete description of recording parameters (system, channels, sampling rate, filters, reference).
- Preprocessing pipeline with exact parameters (filter type, cutoff, order, transition bandwidth).
- Artifact handling: criteria, N rejected, method (manual, automatic, ICA).
- Epoching: time window, baseline, rejection thresholds.
- Statistical analysis: test, implementation, permutations, seed, threshold, adjacency, alpha, tail, effect size.
- The report must enable exact replication by an independent lab.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nature Neuroscience, 23(12), 1473–1483.

### BIDS-style provenance (Gorgolewski et al. 2016, Scientific Data)

- Organize derivatives following BIDS derivatives specification.
- Include `dataset_description.json` with pipeline name, version, and parameters.
- Record provenance: which input files produced which output files.
- Use stable identifiers (file hashes, git SHAs) for traceability.
- The REPRO_RECEIPT serves as a lightweight provenance record when full BIDS derivatives are not used. **It is a provenance record, not a guarantee of numerical reproduction** — see the caveat below.
- Cite: Gorgolewski, K. J., et al. (2016). The brain imaging data structure, a format for organizing and describing outputs of neuroimaging experiments. Scientific Data, 3, 160044.

### Reproducibility in EEG research

- Record all random seeds explicitly — permutation tests, ICA initialization, cross-validation splits.
- Pin software versions in a requirements file or conda environment export.
- Hash input files to detect silent data corruption or version changes.
- A clean git SHA proves the analysis code was version-controlled at execution time.
- If the git working tree was dirty, log the diff for full traceability.

#### Numerical reproducibility across machines (beyond git SHA + version pins)

Git SHA, seeds, file hashes, and a top-level package list pin *what code ran*, but they do **not** guarantee the same numbers on another machine. Single-precision math-library differences across operating systems and BLAS backends (MKL vs OpenBLAS, and thread count) accumulate over a long pipeline, so byte-identical code and data can diverge numerically elsewhere (Glatard et al. 2015). Strengthen the receipt accordingly:

- Capture a **full environment lockfile** (conda `environment.yml` export, or `pip freeze` / `uv.lock`) — not just the handful of top-level packages in the versions table.
- Record the **BLAS/threading backend** (MKL vs OpenBLAS via `numpy.show_config()`, plus the thread count) — it materially affects floating-point results.
- Recommend a **container** (Docker/Singularity image hash) as the only real guarantee of numerical reproducibility, and explicitly flag in the receipt that bit-level reproducibility is **not** guaranteed across OS/BLAS without one.
- Note that all reported numbers are **MNE-Python-specific**: differing cross-package defaults are a known source of non-reproduction, so a re-analysis in a different toolbox will not match exactly (Kabbara et al. 2023).
- Cite: Glatard, T., et al. (2015). Reproducibility of neuroimaging analyses across operating systems. Frontiers in Neuroinformatics, 9, 12.
- Cite: Kabbara, A., et al. (2023). The impact of EEG software/pipeline choice on connectivity results. NeuroImage: Reports, 3, 100169.

### Microstate reporting norms and clinical directions (report only if microstate-stage outputs exist)

When the project contains microstate outputs (`microstate-stage/`), the report should table the four canonical metrics per class (mean duration, occurrence/frequency, time coverage, GEV) and sanity-check them against published healthy-adult norms. Flag — do not silently drop — values outside these bands. The per-class parameters come from `pycrostates` segmentation `.compute_parameters()` outputs; transition structure comes from `pycrostates.segmentation.compute_transition_matrix` / `compute_expected_transition_matrix`.

**Typical healthy-adult values (eyes-closed resting EEG, canonical 4-map solution A/B/C/D):**

| Metric | Typical range / value | Note |
|---|---|---|
| Mean duration (per class) | 80–120 ms | Khanna 2014 lifespans ≈94–102 ms for A–D; the wider 40–200 ms band is a hard plausibility bound, not a norm |
| Occurrence (per class) | ~2–6 /s | Khanna: A≈2.3, B≈2.5, C≈2.65, D≈2.6 /s |
| Total occurrence (all classes) | ~10 /s | Sum across the four maps |
| Time coverage | A≈21%, B≈25%, C≈27%, D≈27% | Sums to ~100%; report as a split, not just per-class |
| Global Explained Variance (GEV) | ~70% for K=4 | If a 4-map solution explains far less, the segmentation or map quality is suspect |
| Duration vs. frequency | R≈−0.72 | Duration and occurrence are inversely correlated; both increasing together is a red flag |

**Known clinical effect directions** (report descriptively for context only — do not infer diagnosis):

- **Schizophrenia:** increased class C occurrence/coverage; shortened class D (and class B) duration; altered A→D transition syntax (Khanna 2015 Table 1; Rieger 2016 meta-analysis).
- **Frontotemporal dementia:** shortened class C.
- **Alzheimer's disease:** globally shortened durations (notably class D).
- **Panic disorder:** longer class A, reduced class C. **Tourette syndrome:** more frequent class A.

These directions are study-level associations with substantial overlap with healthy controls; the report must frame them as literature context, never as a per-subject classifier.

- Cite: Koenig, T., et al. (2002). Millisecond by millisecond, year by year: normative EEG microstates and developmental stages. NeuroImage, 16, 41–48.
- Cite: Khanna, A., Pascual-Leone, A., Michel, C. M., & Farzan, F. (2014/2015). Microstates in resting-state EEG: current status and future directions. Neuroscience & Biobehavioral Reviews, 49, 105–113.
- Cite: Rieger, K., Diaz Hernandez, L., Baenninger, A., & Koenig, T. (2016). 15 years of microstate research in schizophrenia — where are we? A meta-analysis. Frontiers in Psychiatry, 7, 22.
