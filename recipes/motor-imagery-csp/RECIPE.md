---
recipe: motor-imagery-csp
version: 0.1.0
paradigm: Left versus right fist motor imagery with prediction on unseen recording runs
references:
  - "Blankertz et al. (2008). Optimizing Spatial Filters for Robust EEG Single-Trial Analysis. IEEE Signal Processing Magazine 25(1):41–56."
  - "Schalk et al. (2004). BCI2000: A General-Purpose Brain-Computer Interface (BCI) System. IEEE Transactions on Biomedical Engineering 51(6):1034–1043."
contributors:
  - "Haoyang Su <hoyantsu@gmail.com>"
license: CC-BY-4.0
status: experimental
validation_dataset: PhysioNet EEG Motor Movement/Imagery Dataset 1.0.0, S001–S005, runs 04, 08 and 12
---

# Recipe: `motor-imagery-csp`

This recipe measures whether oscillatory EEG features distinguish imagined left
and right fist movements in a recording that was withheld from fitting. It uses
common spatial patterns (CSP) and linear discriminant analysis (LDA), fitting a
separate model for each participant. Keeping entire runs apart makes the
evaluation useful for studying changes between recordings. The contribution
adds a concrete paradigm and public-data execution to AEA's existing CSP skill.

The supplied configuration is a fixed validation example. Its parameters were
selected before execution. Applying the recipe to another study requires that
study's event definitions and analysis plan. The recipe remains experimental
pending independent methodological review. Successful numerical replay alone
does not certify a neural interpretation or every preprocessing choice.

## What this recipe needs

The validation uses 64 scalp electrodes in the international 10–10 system,
sampled at 160 Hz. All channels must map to the documented scalp montage, with
C3, Cz and C4 present. No EOG or reference channel is included as scalp EEG.
For another dataset, use its documented channel identities and reference.

| Condition | Annotation | Applicable runs |
|---|---|---|
| Imagined left fist movement | T1 | 04, 08, 12 |
| Imagined right fist movement | T2 | 04, 08, 12 |
| Rest, excluded from decoding | T0 | 04, 08, 12 |

The same annotation codes mean different movements in other EEGBCI runs. The
code intentionally reads only the three unilateral imagery runs. Each run
must contain both classes. At least two training runs and one separate test
run are required for this configuration. The five participants are the first
five identifiers, chosen without inspecting decoding performance. They support
a bounded numerical example, not a population sample-size recommendation.

## Pipeline

### 1. Preprocess each recording separately

Standardize the documented EEGBCI channel names and attach the standard 10–05
montage. Apply a 7–30 Hz zero-phase Hamming FIR filter using MNE `firwin`, followed
by a 60 Hz zero-phase FIR notch. Apply the average EEG reference. Preserve the
160 Hz sampling grid. Separate filtering prevents a test recording from
entering the temporal padding of a training recording.

The frequency range and four-component model follow the published CSP method
and the [MNE CSP example](https://mne.tools/stable/auto_examples/decoding/decoding_csp_eeg.html).
The example here changes its hands-versus-feet contrast to left-versus-right
fist imagery, replaces random trial splits with whole-run splits, and adds
the explicit notch used by AEA. These differences are recorded rather than
presented as a reproduction of the example's accuracy.

### 2. Artifact treatment and epochs

Use one-second epochs from 1.0 through 2.0 seconds after the cue, including both
endpoints on the sampling grid. Do not subtract a baseline. Reject incomplete
epochs and annotated bad intervals, recording every dropped event. No
amplitude selection, channel interpolation, ICA, or fitted artifact removal
is performed in this validation. This deliberately follows the bounded CSP
example rather than the generic ERP cleaning sequence. It leaves ocular and
muscular contamination unresolved, so performance must not be described as
proof of exclusively cortical information. A cleaned-data variant would need
a separate declared analysis and validation.

### 3. Decode with whole-run cross-validation

For each participant, hold out runs 04, 08 and 12 in turn. Fit four CSP filters
on the other two runs using unregularized concatenated covariance, automatic
rank estimation, log mean-square features and no trace normalization. Average
reference reduces rank, which CSP estimates from training data. Fit LDA with
the SVD solver and empirical class priors on those training features. Apply
the fitted transforms to the untouched test run. There is no feature scaling,
hyperparameter search, model selection or tuning on held-out results.

Save each trial's source run, event sample, label, prediction and probability,
plus every fold's training runs, trial counts, confusion matrix and balanced
accuracy. CSP filters are predictive directions, not source-localization maps.

### 4. Claims and interpretation

| ID | Question | Unit and contrast | Evidence | Scope |
|---|---|---|---|---|
| C1 | What is held-out-run decoding performance? | Left versus right imagery within participant | All three fold scores and their participant mean | Descriptive, no predicted minimum score |
| C2 | Are test runs excluded from spatial-filter fitting? | Training/test run membership | Saved fold identities and a fit-input regression test | Computational separation |
| C3 | Do exported features implement log mean-square projected EEG? | CSP transform versus direct matrix projection | Numerical identity in every fold | Implementation consistency |
| C4 | Can the fixed analysis be replayed? | Original execution versus independent execution directory | Identical trial identities and predictions, probabilities within 1e-6 | Named data and software configuration |

Balanced accuracy gives equal weight to the two class recalls; its chance
reference is 0.5. Report every participant and every run, including scores
below chance. Summarize participant means and their sample standard deviation.
Folds share training data and are not independent subjects. This validation
does not perform a significance test, choose a favorable participant, or claim
population-level above-chance decoding. It therefore does not meet AEA's
inferential reporting requirements for a completed scientific decoding study.

### 5. Figure and stage handoff

The single figure shows all held-out-run scores, participant means and the
0.5 reference on a fixed 0–1 scale. It is rendered directly from the saved fold
values as PNG and SVG. No peak score is selected.

| Stage | Input | Saved evidence |
|---|---|---|
| Preprocessing and epoching | Fifteen public EDF files and `analysis/config.json` | Channel names, sampling rate, event counts and dropped events in participant JSON |
| CSP/LDA | Within-participant epochs with run identities | Fold identities, predictions, probabilities and feature identity errors |
| Summary | All participant JSON files | `folds.csv`, `predictions.csv`, `participants.csv`, `summary.json` |
| Figure and report | Saved fold scores | `reference_figures/held_out_runs.*` and the validation report |

The compact script keeps filtered and epoched arrays in memory. Raw data and
intermediate EEG arrays are not committed. Its configuration, participant
records and commands provide the computational handoff. See
[validation instructions](validation/README.md) for the executed configuration,
software versions, numerical results and limitations.

## Methods paragraph

The validation analyzed the first five participants in PhysioNet EEG Motor
Movement/Imagery Dataset version 1.0.0. Runs 04, 08 and 12 supplied left and
right fist imagery trials. Each recording was independently filtered at 7–30
Hz with a zero-phase FIR filter, notched at 60 Hz and rereferenced to the
average of 64 scalp electrodes. Epochs covered 1–2 seconds after cue onset,
without baseline correction or fitted artifact removal. Four CSP components
and an SVD LDA classifier were fitted within each participant using two runs
and evaluated on the third. All three run allocations were evaluated. The
analysis reports balanced accuracy per fold and participant, together with
trial-level predictions. No inferential significance or clinical claim is made.

## Reproducibility and limitations

The estimator has no stochastic fitting step. The synthetic separation test
uses seed 20261030. Public EDF files retain their Open Data Commons Attribution
License v1.0 and are obtained from PhysioNet rather than redistributed here.
Code follows the repository MIT license; recipe text is CC-BY-4.0.

Only one corpus, five people, one frequency band and one epoch window have
been examined. Tests concern unseen runs within known participants, not new
people, prospective sessions, clinical populations or online decoding.
Zero-phase filtering uses future samples, so this is an offline analysis.
The absence of manual artifact review and fitted cleaning limits physiological
interpretation. LDA probabilities are saved for replay, not asserted to be
calibrated. No independent AEA review has been completed. OpenAI Codex assisted
with preparation, implementation, execution and reporting.

## Changelog

- **0.1.0** (2026-10-30): initial whole-run CSP/LDA recipe and public-data validation.
