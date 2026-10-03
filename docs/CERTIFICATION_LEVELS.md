# What is certified, and what is only tested

AEA's benchmark results are strong for the things they cover, which makes it easy for a reader to
assume they cover everything. They do not. This table exists so the library's claim never runs
ahead of its evidence.

Four levels, from strongest to weakest:

| level | meaning |
|---|---|
| **L3 — cross-toolbox certified** | per-subject values or the observed group statistic reproduced by an independently implemented toolbox within the stated acceptance criterion for the tested outputs (end-to-end through the certified output, not stage by stage) |
| **L2 — cross-implementation certified** | reproduced by a second implementation of the same numerics (a different Python stack, or a gold-standard pipeline) |
| **L1 — behaviourally evaluated** | not a number, so measured a different way — detection rate against seeded defects, coverage against a checklist |
| **L0 — API-tested** | the documented interface is exercised by an automated test — from an import/presence check to a synthetic-data run returning a correctly shaped, sane result. This says the skill passes its specified interface checks. **It does not say the number is right.** |

## Per skill

| skill | level | evidence |
|---|:---:|---|
| `eeg-preprocess` | **L3** | 5 ERP CORE components vs MNE-BIDS-Pipeline (112/112 within 0.1 µV, CCC ≥ 0.9997); per-subject amplitudes vs FieldTrip with the filter specification pinned, 74/74 within 0.1 µV on the four components without trial rejection (MMN 34/38: reported, not certified); EEGLAB and FieldTrip 10/10 same group conclusion. Certified end-to-end through the ROI amplitude for the operations exercised (filter, average reference, resampling) |
| `eeg-epoch` | **L3** | same chain — epoching is inside every certified value |
| `eeg-erp` | **L3** | same chain — the certified quantity *is* an ERP amplitude |
| `eeg-stats` | **L3** *(cluster test only)* | cluster permutation vs FieldTrip `ft_timelockstatistics` at the shipped configuration (component window, one-sided t_0.95, B = 5000): identical cluster partitions and t-maps within 1.8e-15 for N400, P3b, N170 and ERN. The earlier 14-vs-18 cluster count on the full N400 epoch was the certification script's own t_0.975 threshold, a configuration error, not a toolbox convention. Other statistics in this skill are L0. |
| `eeg-spectral` | **L2** | band power vs a from-scratch NumPy Welch: floating-point precision (max relative error 6.9e-16 with the Hamming taper and 5.2e-16 with the skill's released default Hann taper, `SPECTRAL_KERNEL_INDEP_RESULT_hann.json`; 6.5–8.3×10⁻¹⁶ on an independent stack) once the window periodicity and per-segment demeaning conventions are pinned (a 0.44 % residual before that was those two conventions, not "segment handling"); Welch-vs-multitaper sensitivity 1–5 % quantified |
| `eeg-recipe` | **L0** | *historical pilot only*: seven pinned-spec generations recorded PASS (≤0.5 nV) in retained scoring summaries, but the programs and (except MMN B1) the per-subject vectors were not retained, so this is not reconstructable second-implementation evidence — reclassified from L2 on 2026-09-13 (result-to-claim gate) |
| `eeg-audit` | **L1** | 8/8 seeded EEG defects detected on both backends, clean control passed |
| `eeg-methods-text` | **L1** | 100% COBIDAS-MEEG coverage, 0/12 fabrications on deliberately withheld items |
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

**Summary: 4 skills at L3, 1 at L2, 3 at L1, 14 at L0** (eeg-recipe reclassified from L2 to L0 on 2026-09-13: its L2 rested solely on the historical generation pilot, whose programs and per-subject vectors were not retained).

## How to read this

An L0 skill is not untrustworthy — it calls the same MNE functions a careful analyst would, and its
API is exercised on every push. What L0 means precisely is that **nobody has checked its output
against an independent implementation**, so a composition error inside it would not be caught by
anything here.

The honest one-line version of AEA's numeric claim is therefore:

> **ERP amplitude and the cluster test are certified across independently implemented toolboxes.
> Everything else is tested, not certified.**

Anyone extending the library should raise a skill's level before, not after, describing its output
as validated. `tools/benchmark/` shows how each level was reached.
