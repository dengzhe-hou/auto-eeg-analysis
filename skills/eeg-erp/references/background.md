## Domain Knowledge (distilled from ERP methodology literature)

### Component measurement best practices (Luck 2014; Keil et al. 2014)

- **Mean amplitude is the default** — it is unbiased, noise-robust, and works for both peaked and broad components. Keil et al. (2014) committee guidelines explicitly recommend mean amplitude over peak amplitude for most ERP research.
- **Peak amplitude overestimates the true amplitude** because noise can only push the peak further from zero. This bias increases with noise and decreases with trial count (Kappenman & Luck 2016).
- **Peak latency is unreliable** in noisy data because the peak location is driven by the largest noise excursion within the window, not the true neural peak. Fractional area latency (50% area) is more robust (Luck 2014, Chapter 9).
- **Adaptive mean** is a good compromise when individual peak timing varies but the component is well-defined: find the individual peak, then measure mean amplitude in a narrow window centered on it.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.). MIT Press.
- Cite: Keil, A., et al. (2014). Committee report: Publication guidelines and recommendations for studies using electroencephalography and magnetoencephalography. Psychophysiology, 51(1), 1–21.
- Cite: Kappenman, E. S., & Luck, S. J. (2016). Best practices for event-related potential research in clinical populations. Biological Psychiatry: Cognitive Neuroscience and Neuroimaging, 1(2), 110–115.

### Difference waves and their interpretation

- A difference wave isolates the effect of a single experimental manipulation by subtracting one condition from another.
- The subtraction should be theory-driven: subtract the condition that lacks the process of interest from the one that contains it.
- Difference waves can reveal components not visible in the raw waveforms (e.g., MMN = deviant minus standard; N2pc = contralateral minus ipsilateral).
- **Warning**: difference wave amplitude depends on the correlation between conditions across subjects. If conditions are positively correlated, the difference wave variance is reduced, increasing statistical power.
- For statistical tests, always use subject-level difference waves, never the difference of grand averages.

### The averaging principle and trial count (Luck 2014)

- An ERP is recovered by averaging because the evoked signal is time- and phase-locked to the event while background EEG is approximately random with respect to it, so averaging cancels the noise and leaves the signal. Residual noise in the average falls as 1/√n, i.e. **SNR scales with √(trial count)** — doubling SNR requires roughly 4× the trials.
- ERP quality therefore depends on *both* trial count and trial quality. Favor **correction over rejection**: ICA-correct stereotyped artifacts (blinks, saccades) to preserve trials, and reject only non-correctable segments. Over-aggressive IC removal can erase part of the ERP (Chaumon et al. 2015).
- **Mean amplitude over a window is more robust than peak measures when trial counts are low or noise is high**, because peak amplitude bias grows as n shrinks (Kappenman & Luck 2016). Report per-condition trial counts so reviewers can judge SNR.
- Cite (averaging principle / trial count): Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique (2nd ed.). MIT Press.
- Cite (IC-removal point only): Chaumon, M., Bishop, D. V. M., & Busch, N. A. (2015). A practical guide to the selection of independent components of the electroencephalogram for artifact correction. Journal of Neuroscience Methods, 250, 47–63.

### Principled trial-count cutoff via Generalizability Theory

The fixed "< 30 trials = warn" heuristic is convenient but arbitrary — the trial count needed for a stable score depends on the specific component and paradigm. Generalizability Theory replaces it with a number derived from the data: a **G-study** partitions the person × trial variance to yield a dependability coefficient `phi` (a reliability index for absolute decisions) as a function of trial count, and a follow-up **D-study** solves for the minimum `n_trials` that reaches a target dependability (e.g. `phi ≥ 0.8`) for *that* score and paradigm. The ERA toolbox formulas are portable to Python. Report `phi` alongside the SME — they answer different questions: SME is a per-subject standard error of a single score, while `phi` is a population reliability of the measurement design. Cite: Clayson, P. E., Brush, C. J., & Hajcak, G. (2021). Data quality and reliability metrics for event-related potentials (ERPs): The utility of subject-level reliability. *International Journal of Psychophysiology*, 165, 121–136; Clayson, P. E., & Miller, G. A. (2017). ERP Reliability Analysis (ERA) Toolbox: An open-source toolbox for analyzing the reliability of event-related potentials. *International Journal of Psychophysiology*, 111, 68–79.

### ERP component naming conventions (Woodman 2010)

- Components are named by polarity and ordinal position (N1 = first negative, P2 = second positive) or by polarity and approximate latency (N400 = negative around 400 ms).
- The same component can have different names in different labs (N2pc vs PCN; N170 vs VPP).
- A "component" implies a single neural generator; an "ERP effect" is the difference between conditions and may reflect multiple components.
- Cite: Woodman, G. F. (2010). A brief introduction to the use of event-related potentials in studies of perception and attention. Attention, Perception, & Psychophysics, 72(8), 2031–2046.
