## Domain Knowledge

### Single-trial EEG-behavior analysis (Pernet et al. 2011, Frontiers in Psychology)

- Single-trial regression is preferred over averaged ERP × averaged RT correlation: it preserves trial-level variability and avoids ecological fallacy.
- Use robust regression (e.g., Huber or IRLS) if single trials have outliers.
- Always report: predictor (which EEG measure, which ROI, which window), outcome, beta, r², p, and number of trials.
- Cite: Pernet, C. R., et al. (2011). Single-trial analyses: why bother? Frontiers in Psychology, 2, 322.

### Mixed-effects models for trial-level EEG-behavior (Volpert-Esmond et al. 2021, Int. J. Psychophysiology)

- When single trials are pooled across subjects, the trials are not independent: each subject contributes many correlated trials. Multilevel / linear mixed-effects models (random intercept per subject, random slopes where supported) partition within- vs between-subject variance and give correct standard errors; pooled OLS does not and inflates Type I error.
- The fixed-effect slope is the population EEG->behavior coupling; the random-effect variance quantifies how much that coupling varies across subjects. Always report both n_subjects and n_trials.
- Prefer mixed models over the two-step "per-subject slope then t-test against zero" especially when per-subject trial counts are uneven — the mixed model weights subjects appropriately.
- Cite: Volpert-Esmond, H. I., Page-Gould, E., & Bartholow, B. D. (2021). Using multilevel models for the analysis of event-related potentials. International Journal of Psychophysiology, 162, 145–156.

### Median split problems (MacCallum et al. 2002, Psychological Methods)

- Dichotomizing a continuous variable (median split) loses statistical power and can create spurious effects.
- Use continuous regression whenever possible. Only use median split for visualization.
- Cite: MacCallum, R. C., et al. (2002). On the practice of dichotomization of quantitative variables. Psychological Methods, 7(1), 19–40.

### Speed-accuracy tradeoff and delta plots (Ridderinkhof 2002, Psychophysiology)

- The Flanker effect typically increases with RT (delta plot slopes upward) because fast responses are too fast for the conflict to influence them.
- Delta plots (condition difference × RT quantile) reveal the time course of inhibition.
- Conditional accuracy functions (accuracy × RT quantile) reveal whether fast errors are the result of impulsive responding.
- Cite: Ridderinkhof, K. R. (2002). Activation and suppression in conflict tasks. In W. Prinz & B. Hommel (Eds.), Common Mechanisms in Perception and Action: Attention and Performance XIX (pp. 494–519). Oxford University Press.

### Inverse Efficiency Score (Townsend & Ashby 1978)

- IES = RT / proportion correct. Combines speed and accuracy into a single metric.
- Useful when there is a speed-accuracy tradeoff. Not meaningful when accuracy is at ceiling.
- Cite: Townsend, J. T., & Ashby, F. G. (1978). Methods of modeling capacity in simple processing systems. In J. Castellan & F. Restle (Eds.), Cognitive Theory (Vol. 3). Erlbaum.

### COBIDAS reporting for behavioral data

Report: number of trials per condition (before and after exclusion), outlier removal method and threshold, RT filter criteria, accuracy exclusion criteria, statistical test used, effect size.
