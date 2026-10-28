---
name: eeg-spectral
description: "Power spectral analysis: PSD, aperiodic+periodic decomposition (specparam/FOOOF), individual alpha peak frequency (IAPF), band power extraction, 1/f slope. For resting-state, task-related power, and any analysis requiring frequency-domain characterization. Use when user says 'PSD', 'spectral analysis', 'alpha peak', 'FOOOF', 'specparam', '1/f', 'aperiodic', 'resting state power', or needs frequency-domain features."
argument-hint: "[project-dir] [— method: welch|multitaper] [— bands: theta,alpha,beta] [— fooof] [— iapf]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-spectral: frequency-domain analysis

## Context: $ARGUMENTS

## Use this skill

Read the task and the approved analysis plan before choosing a procedure. The
name and description select this skill; they do not specify the analysis.
Load only the relevant sections below, rather than every reference in advance.
For a bounded calculation, use the supplied inputs without inventing upstream
stages or approvals. Keep the actual method, parameters, outputs, and checks.

Template values in the detailed procedures describe their documented examples.
Resolve scientific choices against the task and approved plan before execution;
do not treat an example, a timeout, or an unattended run as researcher approval.
Preserve explicitly fixed configurations. Record unresolved choices and continue
independent approved work, as described in the project instructions.

For clients without native skill loading, use the section loader from the
repository root; it loads the selected procedure, not the whole reference:

```bash
python tools/load_skill.py eeg-spectral --section "Phase A — Determine analysis type"
```

## Required Inputs

1. `DATASET_BRIEF.md` — to know paradigm (resting-state vs task-related).
2. Preprocessed data: `preprocess-stage/` (for resting-state continuous PSD) or `epoch-stage/` (for task-related epoched PSD).
3. `ENVIRONMENT.json` — to check specparam/fooof availability.
4. `ANALYSIS_PLAN.md` — if spectral claims exist (e.g., "alpha power is higher in condition A").
5. Explicit spectral settings from the task or approved plan: estimator and frequency range; for Welch, segment duration, taper, overlap, FFT choice and DC removal; for band power, band bounds and aggregation; for IAPF, the estimator and its range, channels and method parameters. Resolve missing choices before the affected computation. A recipe supplies these settings only when approved for this study.

## Critical Rules

- **Never** report band power without specifying whether it's absolute, relative, or dB.
- **Never** compare alpha power across subjects without considering IAPF differences (use individualized bands or specparam peaks).
- **Never** interpret a change in band power as oscillatory without ruling out aperiodic slope changes (use specparam).
- **Never** use a periodogram on short data segments — use Welch or multitaper.
- **Never** forget to report eyes-open vs eyes-closed for resting-state data.
- **Never** re-apply a `2/N` or factor-2 single-sided correction to MNE PSD output — it is already normalized (V²/Hz). The 2/N rule applies only to a hand-rolled `np.fft.rfft` amplitude, with DC and Nyquist left undoubled.
- **Never** substitute a library default for an unresolved Welch setting. Pass the approved taper and overlap explicitly; Hann with 50% overlap is one documented example, not a mandatory method for every study.
- **Never** claim that increasing `n_fft` (zero-padding) improves true frequency resolution — it only interpolates. Resolution = `sfreq / n_per_seg = 1 / segment_seconds`.
- **Never** interpret spectral content above the low-pass cutoff, even though bins exist up to Nyquist.
- **Never** report uncorrected per-frequency or per-channel p-maps for a group spectral contrast — use cluster-based permutation or FDR.
- **Never** call an amplitude spectrum 'power' (or vice versa); state amplitude vs power vs PSD explicitly before any statistics.
- **Never** trust a single AR model order — sweep it (e.g. P=10/20/50) and cross-check AR peaks against the Welch PSD. A peak present in the AR spectrum but absent in Welch is over-fitting (spurious), not an oscillation.
- **Never** fit an AR model to a non-detrended segment — drift appears as spurious low-frequency power. Detrend/demean first.
- **Never** trust the specparam exponent from `freq_range=[1, 40]`: a fit border on the delta peak (lower) or the noise plateau (upper) biases the exponent by up to ~18% / drives it downward. Raise the lower border into the delta/theta trough and set the upper border below the plateau onset, matched across conditions. Cross-check with IRASA.
- **Never** maximize peaks (`max_n_peaks=6`) for a slope-only study — every extra peak lowers exponent reliability. Use 0–1 peaks, alpha-censored regression, or IRASA.
- **Never** detect IAPF from a channel- or subject-averaged spectrum — differing individual peaks average into a smeared bump. Estimate per parieto-occipital channel and average the per-channel PAF/CoG estimates; flag participants with no resolvable peak instead of forcing one.
- **Never** age-correct the aperiodic offset (no reliable age effect), and never pool spectral biomarkers across sites without ComBat harmonization that protects age/sex/diagnosis covariates.


## Procedure reference

Choose the section that matches the current operation. Detailed code examples
and numerical conventions remain in the linked source.

Before computing, read [Method choices and numerical contract](references/method-contract.md)
to identify which parameters the task fixes and which still require a decision.
For EEG-only averages or rankings, check channel identities with the
[preprocessing channel procedure](../eeg-preprocess/references/channel-identity.md).

## Integrated relative band power numerical quick start

Read this section in [the detailed procedure](references/procedure.md).

## Constants

Read this section in [the detailed procedure](references/procedure.md).

## Phase A — Determine analysis type

Read this section in [the detailed procedure](references/procedure.md).

## Phase B — PSD computation

Read this section in [the detailed procedure](references/procedure.md).

## Phase C — Specparam / FOOOF decomposition (when `— fooof`)

Read this section in [the detailed procedure](references/procedure.md).

## Phase D — Individual Alpha Peak Frequency (when `— iapf`)

Read this section in [the detailed procedure](references/procedure.md).

## Phase E — Write outputs

Read this section in [the detailed procedure](references/procedure.md).

## Phase F — Figures

Read this section in [the detailed procedure](references/procedure.md).

## Phase G — Sanity checks

Read this section in [the detailed procedure](references/procedure.md).

## Domain Knowledge (distilled from spectral analysis literature)

Read this section in [the method background](references/background.md).

## Failure Modes

Read this section in [the detailed procedure](references/procedure.md).

## Cross-references

- Inputs: `preprocess-stage/` (resting-state), `epoch-stage/` (task-related), `DATASET_BRIEF.md`, `ANALYSIS_PLAN.md`
- Outputs: `spectral-stage/*.npz`, `spectral-stage/*.json`, `figure-stage/` (PSD plots, topomaps)
- Related: `eeg-tfr` (time-resolved spectral, complementary; share the same amplitude/power/PSD unit convention), `eeg-stats` (cluster permutation / FDR for group spectral contrasts), `eeg-epoch` (`make_fixed_length_epochs` for continuous resting data), `eeg-connectivity` (coherence/PLV from the cross-spectrum), `eeg-complexity` (DFA/Hurst and 1/f-slope criticality), `eeg-decoding` (AR coefficients from the parametric PSD as a compact tabular feature)
- Next: `eeg-stats` for group comparison of spectral features, `eeg-figure` for publication-ready spectral plots
