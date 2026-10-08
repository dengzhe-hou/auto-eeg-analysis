# What is certified, and what is only tested

Validation applies to specific outputs and configurations. The tables below
separate numerical certification, behavioural evaluation and API checks.

| level | meaning |
|---|---|
| **L3 — cross-toolbox certified** | per-subject values or the observed group statistic reproduced by an independently implemented toolbox within the stated acceptance criterion for the tested outputs (end-to-end through the certified output, not stage by stage) |
| **L2 — cross-implementation certified** | reproduced by a second implementation of the same numerics (a different Python stack, or a gold-standard pipeline) |
| **L1 — behaviourally evaluated** | not a number, so measured a different way — detection rate against seeded defects, coverage against a checklist |
| **L0 — API-tested** | the documented interface is exercised by an automated test — from an import/presence check to a synthetic-data run returning a correctly shaped, sane result. This says the skill passes its specified interface checks. **It does not say the number is right.** |

## Released certification inventory (v0.3.2)

| skill | level | evidence |
|---|:---:|---|
| `eeg-preprocess` | **L3** | 5 ERP CORE components vs MNE-BIDS-Pipeline (112/112 within 0.1 µV, CCC ≥ 0.9997); per-subject amplitudes vs FieldTrip with the filter specification pinned, 74/74 within 0.1 µV on the four components without trial rejection (MMN 34/38: reported, not certified); EEGLAB and FieldTrip 10/10 same group conclusion. Certified end-to-end through the ROI amplitude for the operations exercised (filter, average reference, resampling) |
| `eeg-epoch` | **L3** | same chain — epoching is inside every certified value |
| `eeg-erp` | **L3** | same chain — the certified quantity *is* an ERP amplitude |
| `eeg-stats` | **L3** *(cluster test only)* | cluster permutation vs FieldTrip `ft_timelockstatistics` at the shipped configuration (component window, one-sided t_0.95, B = 5000): identical cluster partitions and t-maps within 1.8e-15 for N400, P3b, N170 and ERN. Other statistics in this skill are L0. |
| `eeg-spectral` | **L2** | band power vs a from-scratch NumPy Welch: floating-point precision (max relative error 6.9e-16 with the Hamming taper and 5.2e-16 with the skill's released default Hann taper, [`SPECTRAL_KERNEL_INDEP_RESULT_hann.json`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT_hann.json); 6.5–8.3×10⁻¹⁶ on an independent stack) once the window periodicity and per-segment demeaning conventions are pinned; Welch-vs-multitaper sensitivity 1–5 % quantified |
| `eeg-recipe` | **L0** | *historical pilot only*: seven pinned-spec generations recorded PASS (≤0.5 nV) in retained scoring summaries, but the programs and (except MMN B1) the per-subject vectors were not retained, so this is not reconstructable second-implementation evidence |
| `eeg-audit` | **L1** | 8/8 seeded EEG defects detected on both backends, clean control passed; [archived evaluation](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/audit_eval) |
| `eeg-methods-text` | **L1** | 100% COBIDAS-MEEG coverage, 0/12 fabrications on deliberately withheld items; [archived evaluation](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/76202d6071070c27ad2813561e54272969cacb4b/tools/validation/methods_text_eval) |
| `eeg-figure` | **L1** | figure-to-data fidelity checks: plotted line, error-band type (SD vs SEM), axis units, significance mask — each shown to accept a correct figure *and* catch a corrupted one |
| `eeg-ica` | **L0** | API + ICLabel smoke. mne-icalabel and EEGLAB's ICLabel are **not** benchmarked against each other |
| `eeg-tfr` | **L0** | API smoke |
| `eeg-connectivity` | **L0** | API smoke |
| `eeg-source` | **L0** | API smoke; no individual-MRI validation |
| `eeg-microstate` | **L0** | API smoke; split-half stability only |
| `eeg-decoding` | **L0** | API smoke |
| `eeg-complexity` | **L0** | API smoke; ICA sensitivity characterised but not certified |
| `eeg-behavior` | **L0** | API smoke |
| `eeg-bids` | **L0** | API smoke |
| `eeg-qc` | **L0** | API smoke |
| `eeg-group-compare` | **L0** | API smoke |
| `eeg-report` | **L0** | API smoke |
| `eeg-pipeline` | **L0** | orchestration only; certification comes from the skills it calls |

**Released inventory: 4 skills at L3, 1 at L2, 3 at L1, 14 at L0.** The [inventory correction record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/CERTIFICATION_LEVELS.md#released-certification-inventory-v032) retains the recipe reclassification and earlier cluster-threshold/Welch-convention corrections.

## Additional output-specific checks (2026-10-03)

The released inventory above is retained as historical certification coverage. The following
new checks add independent formulas or known-input controls for selected outputs. They do not
promote an entire skill, certify a generated workflow, or extend a result to untested options.
The existing ERP, cluster and Welch evidence is unchanged.

| Skill | New check and reference | Result and scope |
|---|---|---|
| `eeg-tfr` | Explicit Gaussian Morlet wavelets and direct time-domain convolution vs MNE; independent power, ITC and baseline formulas | Pass for zero-mean Morlet, `n_cycles=f/2`, `decim=4`, power/ITC, logratio, dB and percentage units. This does not cover multitaper, Stockwell or arbitrary TFR workflows. |
| `eeg-connectivity` | Direct DFT and debiased imaginary-cross-spectrum moment formula vs `wpli2_debiased` | Pass for Fourier mode, three edges and 8–13 Hz bins. The default multitaper path, PAC and time-resolved estimators remain outside this numerical check. |
| `eeg-ica` | Known rank-three sources mixed into four average-referenced channels; extended Infomax and specified component removal | Pass for source recovery and reconstruction on this fixture. Component identity is supplied from ground truth; this is not ICLabel or real-artifact classification validation. The iteration count is retained. |
| `eeg-source` | Direct regularized matrix inverse and noise normalization vs MNE/dSPM | Pass for a spherical leadfield, fixed orientations, `depth=None`, average reference and `lambda2=1/9`. The forward model is shared, not independently checked. Individual MRI, default depth/loose settings, beamformers and localization accuracy are not tested. |
| `eeg-decoding` | Explicit train-only fold/time loop vs MNE `SlidingEstimator`, with disjoint groups | Exact score agreement: 1.0 on injected-signal times and 0.5 on paired null times, across three folds. The classifier implementation is shared; this validates dispatch, splitting and aggregation, not an independent classifier or real-data prediction. |
| `eeg-complexity` | Explicit ordinal-pattern histogram and Shannon formula vs normalized permutation entropy | Pass for order 3, delay 1, monotonic and random distinct-valued signals. Other complexity estimators remain outside this check. |
| `eeg-microstate` | Literal transitions in a known label sequence vs pycrostates | Exact observed transition probabilities with repeated and unlabeled samples excluded. Clustering, templates and temporal-duration estimates are not tested. |
| `eeg-bids` | Original volts, channels, bad status and event samples vs BrainVision BIDS read-back | Pass for the synthetic round trip, with 1e-11 V tolerance for float32 export. This is not all-format testing or full BIDS Validator conformance. |
| `eeg-qc` | Known constant/dropout and rapid-change spans; clean waveforms; low-amplitude warning controls | Current helper separates exact-constant intervals, window peak-to-peak warnings and rapid changes, with clean and injected-fault controls. This is an amplitude diagnostic, not complete artifact classification; the original failed rule and revised evidence are retained below. |

Run every check without downloading data:

```bash
conda run -n aeais python tools/tests/support/library_numerics.py --out /tmp/library-numerics.json
conda run -n aeais python -m pytest tools/tests/test_library_numerics.py -q
```

Current checks exercise the revised QC rule and retain the original failing rule as
an explicit comparison. Missing optional packages produce pytest skips; requesting
a standalone check without its required package fails.

### QC evidence and settings

The [revised QC result](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/qc_revision_2026-10-03.json)
records 27 clean sinusoid controls (1/10/40 Hz, three phases, 128/250/1000 Hz)
with no constant/rapid-change spans or bad-channel candidates. The original
three-sine fixture also produced none. Injected constant/dropout and rapid-change
intervals matched their known locations. A low-amplitude sine produced 100 warnings
and no bad-channel candidate.

The [amplitude helper](../tools/qc_amplitude.py) uses exact-constant spans of at
least 20 ms, low peak-to-peak warnings in complete 100 ms windows (≤0.5 µV), and
rapid changes of ≥150 µV for at least 5 ms. Settings are configurable diagnostics,
not universally validated physiological cutoffs. Low amplitude never creates a
bad-channel candidate. The helper modifies no signals, annotations or bad-channel
metadata.

The [cached MNE sample injection check](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/qc_sample_revision_2026-10-03.json)
uses the original first 10 seconds of three EEG channels with known added faults.
It measures injected-event localization and preservation of input data, not clinical
sensitivity: the recording has no ground-truth clean/bad labels.

The original adjacent-difference rule incorrectly flagged two of three clean sine
channels and 100 `BAD_flat` spans at 250 Hz; the standalone run exited 1. The
[initial result](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/library_numerics_initial_2026-10-03.json) and
[final original result](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/validation/library_numerics_2026-10-03.json)
preserve those failures, versions, fixtures, tolerances and measured errors. The
[historical correction record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/CERTIFICATION_LEVELS.md#additional-output-specific-checks-2026-10-03)
also retains the triangle-control addition and ICA iteration-setting correction.

### Numerical conventions to retain

- MNE `logratio` returns `log10(power/baseline)`; multiply by 10 for dB. `db` is not an MNE baseline mode. `percent` returns a fraction; multiply by 100 for a percentage label. The default remains `logratio`.
- Morlet amplitude-envelope frequency standard deviation is `f/n_cycles`. With `n_cycles=f/2`, time and frequency widths are constant in absolute units. Power is not a V²/Hz PSD. The finite-kernel edge margin is `5*n_cycles/(2*pi*f)`, rounded to included samples, approximately 0.398 s for the released cycle schedule. Explicit `zero_mean=True` matches the tested MNE 1.12.1 default.
- MNE `annotate_amplitude` thresholds adjacent-sample differences, emits `BAD_peak` and returns persistent high-change as well as flat channels. AEA's current diagnostic helper is described above.

[Executable checks](../tools/tests/support/library_numerics.py) and [pytest entry points](../tools/tests/test_library_numerics.py)
remain rerunnable. The historical record above preserves the earlier erroneous
formulas and correction rationale; original release results are unchanged.

## How to read this

Certification applies to a stated output and configuration. Cross-toolbox ERP amplitudes and
observed cluster statistics, the independent Welch implementation, and the additional formulas
above support their respective measured outputs. A passing API check alone does not establish
numerical correctness, and a known-source synthetic check does not establish biological validity.
Full generated workflows and options outside these checks still need their own evidence before
being described as certified. Current CI fixtures are in
[`tools/tests/fixtures/certification/`](../tools/tests/fixtures/certification/), with executable
support in [`tools/tests/support/`](../tools/tests/support/). The
[benchmark](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark) and
[validation](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/validation)
records remain in the fixed public snapshot; earlier records remain accessible through the links above.
