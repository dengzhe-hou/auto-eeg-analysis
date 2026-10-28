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
