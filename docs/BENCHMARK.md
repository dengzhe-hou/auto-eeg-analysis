# AEA numeric benchmark — does the recipe's pipeline match the gold standard?

> This document records the numerical comparison introduced after the
> [original comparison review](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/docs/COMPARISON.md).
> Self-regression tests establish reproducibility, not **correctness**.
> The comparison asks: does an AEA
> recipe compute the *same numbers* as an independent, community-standard pipeline
> ([MNE-BIDS-Pipeline](https://mne.tools/mne-bids-pipeline/)) on the same public data?
>
> **Scope (read §5):** "the recipe's pipeline" here = a **faithful reference implementation of the
> recipe spec** (`tools/validation/validate_*_group.py`), run as a **harmonized minimal** pipeline
> — *not* the live `/eeg-recipe` LLM-generated code, and *not* the recipe's ICA/AutoReject defaults.

Status: **MMN + P3 + N170 + ERN + N400 executed** (§4, §4c–§4f), **CI regression gate live** (§6e), **kernel-independence bounded** (§4g), **toolbox independence established in EEGLAB *and* FieldTrip for all five components** (§4i) and **extended beyond ERP to resting spectral band power** (§4h). **5 of ERP CORE's 7 components** (Kappenman 2021: N170, MMN, N2pc, N400, P3, LRP, ERN); N2pc + LRP remain (§6a). All benchmarks use a *harmonized minimal* pipeline (see §5).

Historical evaluation reports, generated programs and rendered figures remain in the
[public evidence snapshot](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark).
Additional result records remain in the [versioned benchmark snapshot](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark).
Links below pin the corresponding snapshot. Numerical fixtures used by current CI,
comparison code and regression tests remain in the library; the snapshots retain
the original failures, limitations and generation records. See [worked examples](EXAMPLES.md)
for the separate case-study records.

---

## 1. Why this is the load-bearing test

AEA is a method/orchestration layer over MNE-Python — *"to MNE what HuggingFace Transformers
is to PyTorch"* ([README](../README.md), [COMPARISON.md](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/docs/COMPARISON.md)). An upper layer earns
trust by one thing above all: **the code it generates must compute what it claims, as well as the
reference implementation does.** A recipe that runs and produces a plausible figure is not enough —
the figure has to carry the *right numbers*.

There are three distinct things one can validate, often conflated:

| Level | Question | AEA status before this doc |
|------|----------|----------------------------|
| **Reproducibility** | Re-run → same output? | ✅ covered (self-regression tests) |
| **Implementation correctness** | Same spec → same number as an independent pipeline? | ❌ **this doc** |
| **Parameter optimality** | Are the recipe's *default choices* the best ones? | ⛔ out of scope (a science question, not a code question) |

This benchmark targets the middle row. It is the cheapest, most decisive evidence that AEA's
generated pipelines are not silently wrong.

---

## 2. The protocol (general, applies to any recipe)

1. **Pick a public dataset** with a published, canonical analysis (ERP CORE; Kappenman et al. 2021).
2. **Pick an independent gold standard** — different code, same numerical backend is fine
   (MNE-BIDS-Pipeline). Ideally a *second* backend too (EEGLAB/ERPLAB) for a cross-implementation check.
3. **Harmonize every analysis choice** (filter, resample, reference, montage handling, epoch
   window, baseline, artifact rejection, contrast) so the two pipelines differ *only in
   implementation*, never in parameters. This is what makes a numeric difference *interpretable*.
4. **Extract one scalar per subject** with identical measurement code (here: deviant−standard
   mean amplitude over Fz/FCz/Cz, 100–250 ms).
5. **Report agreement digit-by-digit**: per-subject Δ (max/mean/RMSE), Pearson r, Lin's
   concordance (CCC), Bland–Altman bias + 95% limits of agreement, and N within a stated tolerance.
6. **State a pass criterion up front.** For implementation-correctness we use
   **max per-subject |Δ| ≤ 0.10 µV** (≈ one quantization step of a typical ERP plot) and **CCC ≥ 0.99**.

Harmonization is deliberate and is the methodological point: it converts "the two tools give
different answers" (uninterpretable — could be parameters *or* bugs) into "given identical
parameters, do the two implementations agree?" (a clean correctness test).

---

## 3. The MMN instance — exact specification

**Dataset.** ERP CORE Mismatch Negativity (passive auditory oddball), OpenNeuro `ds003065`,
40 subjects, BIDS, EEGLAB `.set`, 1024 Hz, 30 EEG + 3 EOG, BioSemi CMS/DRL reference.
Standards = event `value` 80, deviants = `value` 70, first-stream standards (`value` 180) excluded
— the canonical ERP CORE MMN contrast.

**A fairness subtlety we had to fix.** In `ds003065` the standard/deviant label lives only in the
events `value` column; `trial_type` is `"stimulus"` for every tone. AEA's recipe keys on `value`;
MNE-BIDS-Pipeline keys on `trial_type`. `tools/benchmark/build_bids_subset.py` writes a working BIDS
copy (signal files symlinked, untouched) whose `trial_type` is relabeled from `value` so **both
tools analyze the identical contrast.** Without this step the comparison would silently contrast
different trials.

**Harmonized parameters** (AEA `tools/validation/validate_mmn_group.py` ↔ MNE-BIDS-Pipeline
`tools/benchmark/config_mmn_bidspipe.py`):

| Choice | Value (both pipelines) |
|--------|------------------------|
| Band-pass | 0.1–30 Hz, zero-phase FIR |
| Resample | 256 Hz |
| Reference | average (30 EEG; 3 EOG excluded) |
| Epoch | −0.2 to +0.5 s |
| Baseline | (−0.2, 0) s |
| Artifact rejection | peak-to-peak 100 µV |
| ICA / SSP | none |
| Contrast | deviant (70) − standard (80) |
| Metric | mean amplitude, Fz/FCz/Cz, 100–250 ms |

Residual *intentional* differences (documented, not harmonized away): montage source (AEA forces
`standard_1020` template; MNE-BIDS-Pipeline uses the dataset `electrodes.tsv`) — irrelevant to an
average-referenced ROI-mean metric; and the internal order of reference/baseline application. The
benchmark measures whether these residual differences matter. (They do not — see §4.)

---

## 4. Result

Run on **all available subjects** processed by both pipelines (gold pipeline ~9 s/subject).

<!-- RESULT_TABLE_START -->
**N = 38** (the subjects *both* pipelines retained). The two pipelines do **not** agree on subject
*retention*: the gold pipeline analyzed sub-007 (11 deviants, MMN +2.79 µV) and sub-012 (47 deviants,
MMN +0.17 µV) — both noisy, near-zero/reversed averages — while AEA's recipe excludes them via its
trial-count guard (≥ 50 deviants, ≥ 150 standards, matching `recipes/mmn-oddball/RECIPE.md`).
`compare_mmn.py` takes the **intersection**, so the table below measures per-subject numeric
agreement on the 38 shared subjects, *not* agreement on the inclusion decision (where the two tools
differ on these two low-trial subjects).

| Metric | AEA `mmn-oddball` | MNE-BIDS-Pipeline 1.10.1 |
|--------|------------------:|-------------------------:|
| Grand-mean MMN (Fz/FCz/Cz, 100–250 ms) | **−0.840 µV** | **−0.842 µV** |

| Agreement metric | Value (N=38) |
|------------------|--------------|
| Group-mean Δ | **+0.003 µV** |
| Per-subject max \|Δ\| | **0.090 µV** |
| Per-subject mean \|Δ\| | **0.003 µV** |
| Per-subject RMSE | 0.015 µV |
| Pearson r | **0.9998** |
| Lin's CCC | **0.9997** |
| Bland–Altman bias (95% LoA) | +0.003 µV (−0.026, +0.031) |
| Within ±0.10 µV tolerance | **38 / 38** |

**37 of 38 subjects agree to ≤ 0.005 µV.** The single outlier is sub-030 (AEA −2.894 vs gold
−2.984, Δ = 0.090 µV): the gold pipeline retained **one** additional epoch through the 100 µV
peak-to-peak rejection (86 vs 85), and on a small-N average (≈85 deviants) one epoch moves the mean
by ~0.09 µV. This is not a bug in either tool — it is a genuine, explainable single-epoch boundary
difference, and the benchmark correctly *surfaces* it rather than hiding it. (Full per-subject table:
[`tools/benchmark/MMN_BENCHMARK_RESULT.json`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/MMN_BENCHMARK_RESULT.json).)
<!-- RESULT_TABLE_END -->

The two pipelines agree to **~3 nanovolts on the group mean and ≤ 5 nanovolts per subject for
37/38 subjects** — at or near the floating-point/rounding floor — and select the *identical*
surviving epochs for every subject but one. **Pass criterion met** (max |Δ| ≤ 0.10 µV, CCC ≥ 0.99).

> **Read this floor correctly.** Both pipelines call the *same* MNE kernels (`filter`, `resample`,
> `set_eeg_reference`, `Epochs`, `combine_evoked`) with identical parameters, so a near-zero Δ is
> *expected* — it is essentially "the same numerics executed via two independent call sites." This
> benchmark therefore bounds AEA's **composition/wiring** correctness (does the recipe assemble the
> right stages with the right event codes, reference, and rejection?), **not** the correctness of the
> underlying numerics. The errors it *can* catch are real and common — a wrong event code, EOG leaking
> into the average reference, baseline applied at the wrong stage, a latency/sign slip — all of which
> survive harmonization and would show up as a non-trivial Δ. Testing the *kernels* requires a second,
> non-MNE backend (EEGLAB/ERPLAB; §6b).

> Reproducibility note: this benchmark independently *re-derives* AEA's committed grand-mean of
> **−0.840 µV** ([recipes/mmn-oddball/RECIPE.md](../recipes/mmn-oddball/RECIPE.md), "Validated results")
> from a wholly separate codebase — so it doubles as an external audit of that published number.

![MMN benchmark](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/figures/mmn_benchmark.png)

### 4b. Per-sample waveform agreement (not just the window mean)

A single 100–250 ms ROI-mean scalar can hide per-sample disagreement (an opposite-signed early
lobe, a latency shift, a one-channel polarity slip all integrate to the same window mean). So we
also compare the **full deviant−standard waveform — all 30 EEG channels × every sample, −0.2 to
0.5 s** (`tools/benchmark/compare_waveform.py`):

| Full-waveform metric (all ch × all samples) | Value (N=38) |
|---|---|
| RMSE — median / mean | **10.8 / 16.1 nV** |
| RMSE — 37 subjects with *identical* surviving epochs | median 10.7, max 36.0 nV |
| RMSE — worst subject (sub-030, epoch count differs by 1) | 137.7 nV |
| Worst single sample (max abs) — clean / overall | 0.21 µV (sub-017) / 0.80 µV (sub-030) |

This is **~3–5× looser than the ROI-window scalar (~3 nV)**: the window + ROI averaging washes out
per-sample micro-differences the waveform view exposes — exactly the blind spot a single scalar
carries. For the 37 subjects with identical surviving epochs the residual ~11 nV RMSE is **filter/
resample implementation micro-difference** — the only computation not bit-identical once the epoch
sets match (it is broadband, not filter-edge-concentrated). At **~0.01 µV it remains ~100× below the
~10–100 nV resolution of any ERP measurement**, so the correctness conclusion holds at the per-sample
level, not just for the summary statistic.

![MMN waveform agreement](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/figures/mmn_waveform.png)

The waveform check now runs for **all five** components (`compare_waveform.py --component X`,
committed `*_WAVEFORM_RESULT.json`) — full deviant/difference waveform, all 30 channels × every sample:

| Component | Waveform RMSE (nV): median / mean / max |
|---|---|
| MMN | 10.8 / 16.1 / 137.7 |
| P3 | 0.0 / 0.5 / 10.2 |
| N170 | 27.2 / 28.9 / 99.2 |
| ERN | 29.5 / 40.2 / 136.9 |
| N400 | 0.0 / 13.5 / 211.8 |

All medians ≤ 30 nV (≈ 0.03 µV) — the residual tracks passband width and trial count (widest for the
0.1–40 Hz N170 and the sparse-trial ERN; near bit-identical for P3/N400 on most subjects). Far below
any ERP measurement's resolution; the CI gate (§6e) bounds these medians.

### 4c. Second component — P3b (target − standard)

To show the result is not MMN-specific, the same benchmark was repeated on a *structurally
different* ERP: the **P3b** from ERP CORE's **active visual oddball** (`p300-oddball` recipe) — a
centro-parietal **positivity** 300–500 ms to rare targets (vs MMN's early frontocentral negativity;
active vs passive). Same harness, parameterized for P3 (`build_bids_subset_p3.py`,
`config_p3_bidspipe.py`, `extract_bidspipe_p3.py`, `compare_mmn.py --key p3_uV`), **N=20** subjects.

One deliberate change from MMN: **no peak-to-peak rejection.** The active task (button presses,
blinks across the 1 s epoch) without ICA would reject most trials at 100 µV, collapsing N. Averaging
all epochs keeps N=20 **and** — since both pipelines then average the *identical* 40 targets / 160
standards per subject — removes epoch-selection divergence entirely, making this the cleaner of the
two comparisons. (It also means this benchmark, like MMN, tests a harmonized *minimal* pipeline, not
the recipe's full ICA + AutoReject artifact handling.)

| | AEA `p300-oddball` | MNE-BIDS-Pipeline |
|---|---|---|
| Grand-mean P3b (Fz/Cz/Pz/CPz, 300–500 ms) | +1.683 µV | +1.683 µV |

- **AEA effect is real:** N=20, t(19)=4.15, **p = 5×10⁻⁴**, dz = 0.93, second-level cluster p=0.0002 (PASS).
- **Cross-tool agreement:** per-subject **max \|Δ\| = 0.5 nV**, **Lin's CCC = 1.000**, **20/20 within ±0.1 µV**;
  full-waveform RMSE ~0.5 nV (mean). With identical trial sets the agreement sits at the floating-point
  floor — *tighter* than MMN, whose only >5 nV cases came from epoch-rejection differences that reject=None
  removes here.

![P3 benchmark](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/figures/p3_benchmark.png)

### 4d. Third component — N170 (face − car)

A third paradigm, a third scalp topography: the **N170** from ERP CORE's face-perception task
(`n170-faces` recipe) — a **lateral occipito-temporal negativity** 130–200 ms, larger (more negative)
for faces than for the matched car control. Same harness (`build_bids_subset_n170.py`,
`config_n170_bidspipe.py`, `extract_bidspipe_n170.py`, `compare_mmn.py --key n170_uV`), N=20,
face (value 1–40) − car (41–80), ROI PO7/PO8/P7/P8, filter 0.1–40 Hz, reject=None.

| | AEA `n170-faces` | MNE-BIDS-Pipeline |
|---|---|---|
| Grand-mean N170 (PO7/PO8/P7/P8, 130–200 ms) | −1.181 µV | −1.182 µV |

- **AEA effect is real:** N=20, t(19)=−4.45, **p = 2.7×10⁻⁴**, dz = −0.99, second-level cluster p=0.0002 (PASS).
- **Cross-tool agreement:** per-subject **max \|Δ\| = 11 nV**, **CCC = 1.000**, **20/20 within ±0.1 µV**.
  Full-waveform RMSE ~27 nV (median) — *higher* than MMN's ~11 nV and P3's ~0.5 nV because the wider
  **0.1–40 Hz** passband (vs 0.1–30 for MMN/P3) admits more high-frequency content, where the two
  independent filter/resample implementations micro-differ. Still ~0.03 µV — ≪ the ~1 µV effect — and
  the measured ROI scalar agrees to 11 nV.

![N170 benchmark](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/figures/n170_benchmark.png)

### 4e. Fourth component — ERN (error − correct), *response-locked*

The first three components are all **stimulus-locked**. The **ERN** (error-related negativity) tests a
different pipeline mode entirely — **response-locked** epoching: a frontocentral negativity 0–100 ms
after an *erroneous* button press in ERP CORE's arrow-flankers task. Events lock to the response, split
by accuracy (response value d1==d3 ⇒ correct, else error), error − correct at FCz/Fz/Cz, pre-response
baseline (−0.4,−0.2). N=14 (6 subjects excluded for <15 errors — they were highly accurate).

> Note: this is the canonical **error−correct** ERN (the ERP CORE ERN primary contrast). The
> `ern-flankers` recipe's C2 frames ERN as *incompatible−compatible responses* — a different, weaker
> conflict effect needing per-response stimulus derivation. We benchmark the standard error−correct
> ERN, which is the robust effect and cleanly harmonizable, and it exercises response-locked epoching.

| | AEA (error−correct) | MNE-BIDS-Pipeline |
|---|---|---|
| Grand-mean ERN (FCz/Fz/Cz, 0–100 ms post-response) | −5.446 µV | −5.446 µV |

- **AEA effect is real and large:** N=14, t(13)=−6.31, **p = 2.7×10⁻⁵**, dz = −1.69, second-level cluster p=0.0004 (PASS).
- **Cross-tool agreement:** per-subject **max \|Δ\| = 32 nV**, **CCC = 1.000**, **14/14 within ±0.1 µV**.
  Slightly looser than the stimulus-locked components (P3 ≤0.5 nV) — errors are sparse (~15–60 trials),
  so filter/resample micro-differences on the thin error average show a touch more — still 0.03 µV.

![ERN benchmark](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/figures/ern_benchmark.png)

**Takeaway:** numeric faithfulness holds across **four** ERPs spanning **both epoching modes** —
stimulus-locked (MMN frontocentral −, P3b centro-parietal +, N170 occipito-temporal −) and
**response-locked** (ERN); passive and active tasks; 0.1–30 and 0.1–40 Hz bands. It is a property of
the recipe→pipeline composition, not a quirk of one paradigm or one time-lock.

### 4f. Fifth component — N400 (unrelated − related)

The N400 required writing a **new recipe** (`n400-semantic`) — the first benchmark component built
from scratch rather than an existing recipe. Semantic priming: a centro-parietal negativity 300–500 ms,
larger for semantically **unrelated** target words (Kutas & Federmeier 2011). Target words only,
unrelated (value 221/222) − related (211/212), ROI CPz/Cz/Pz, N=20, reject=None.

| | AEA `n400-semantic` | MNE-BIDS-Pipeline |
|---|---|---|
| Grand-mean N400 (CPz/Cz/Pz, 300–500 ms) | −2.957 µV | −2.957 µV |

- **AEA effect is real:** N=20, t(19)=−6.34, **p = 4.4×10⁻⁶**, dz = −1.42, second-level cluster p=0.0002 (PASS).
- **Cross-tool agreement:** per-subject **max \|Δ\| = 6 nV**, **CCC = 1.000**, **20/20 within ±0.1 µV**.

![N400 benchmark](https://raw.githubusercontent.com/dengzhe-hou/auto-eeg-analysis/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/figures/n400_benchmark.png)

**Takeaway:** the new-from-scratch recipe is *born faithful* — writing a recipe and getting the
digit-by-digit agreement is now a repeatable ~1-hour loop.

### 4g. Kernel independence — an independent (non-MNE) DSP

Every benchmark above sits on **MNE's** numerical kernels on *both* sides, so the nanovolt agreement
bounds *composition/wiring* error, not the kernels themselves (a recurring reviewer objection). To
bound **kernel** error, `independent_dsp.py` computes each subject's ERP two ways from the *same* raw
data: (A) MNE's DSP vs (B) an **independent SciPy implementation** of the same spec — 4th-order
Butterworth `sosfiltfilt` (vs MNE's FIR), `resample_poly` (vs MNE's resampler), mean-subtract
reference, hand-rolled epoch/baseline/average. Only the numerical kernels differ (file I/O is shared
and is not a kernel); `reject=None` on both, so the trial sets are identical and the residual is pure
kernel sensitivity.

| Component (N=12) | MNE mean | SciPy mean | group Δ | per-subject max \|Δ\| | mean \|Δ\| | r |
|---|---:|---:|---:|---:|---:|---:|
| MMN (passive) | −0.723 µV | −0.711 µV | −0.011 | **0.047 µV** | 0.019 | 0.9993 |
| P3 (active) | +2.372 µV | +2.459 µV | −0.087 | **0.871 µV** | 0.215 | 0.9896 |

**What this adds:** an independent DSP lands within **0.05 µV (MMN) / 0.09 µV group (P3)** of MNE —
so MNE's kernels are not idiosyncratic; the recipe numbers survive a change of numerical
implementation, not just of wiring. **What it honestly surfaces:** the P3's per-subject **max 0.87 µV**
residual — a *large slow* component is genuinely sensitive to the high-pass kernel (Butterworth-IIR vs
FIR treat sub-Hz drift differently). That ~1 µV sensitivity was **invisible** to the MNE-vs-MBP
nanovolt agreement (same kernel on both sides) — which is exactly why an independent backend is worth
having. It remains small vs the effect (P3 ≈ 2.4 µV, r = 0.99), but it means "faithful to nanovolts"
holds only *within* a fixed DSP kernel; across kernels, expect ~0.05–1 µV for slow components.

*(This is an independent-**implementation** bound. The independent-**toolbox** result is §4i.)*

Saved results: [MMN](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/MMN_KERNEL_INDEP_RESULT.json),
[P3](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/P3_KERNEL_INDEP_RESULT.json).

### 4i. Toolbox independence — all five components in EEGLAB *and* FieldTrip

Full write-up: [`tools/benchmark/CROSS_TOOLBOX_EVAL.md`](../tools/benchmark/CROSS_TOOLBOX_EVAL.md).
Every certified component was re-run in two independent toolboxes under GNU Octave 10.3 — EEGLAB
(git `sccn/eeglab`) and FieldTrip 20170830 — with a different reader, a different filter
implementation and, in each of the three arms, a **different resampling algorithm** (MNE FFT/polyphase,
EEGLAB cubic-spline fallback, FieldTrip decimation).

| component | EEGLAB Δ grand mean | EEGLAB CCC | FieldTrip Δ grand mean | FieldTrip CCC |
|---|---:|---:|---:|---:|
| P3b | **0.009 µV** (0.5%) | **0.9999** | 0.064 µV (3.8%) | 0.9928 |
| N400 | **0.015 µV** (0.5%) | **0.9999** | 0.024 µV (0.8%) | 0.9982 |
| ERN | **0.018 µV** (0.3%) | 0.9997 | 0.124 µV (2.3%) | 0.9979 |
| N170 | 0.039 µV (3.3%) | 0.9979 | 0.016 µV (1.4%) | 0.9990 |
| MMN (p2p) | 0.016 µV (1.8%) | 0.9953 | 0.010 µV (1.2%) | 0.9939 |

**10/10 runs reproduce the group-level conclusion.** Event decoding was verified independent of MNE
(the `.set` codes match the BIDS `_events.tsv` exactly for all five components) and confirmed
downstream: **0 trial-count mismatches** on every no-rejection component, and both toolboxes
independently excluded the same 6 of 20 ERN subjects the reference excludes.

Two controlled experiments then localized the residual disagreements to **unstated specification
parameters, not toolbox code**:

- **"±100 µV"** is peak-to-peak in MNE and absolute-amplitude in EEGLAB. Same toolbox, criterion
  harmonized → per-subject mean |Δ| **0.089 → 0.040 µV**, CCC 0.9845 → 0.9953, ρ 0.9676 → 0.9912.
- **"0.1–30 Hz zero-phase FIR"** does not say whether 0.1 Hz is the passband edge (EEGLAB, MNE:
  −6 dB at 0.05 Hz) or the −6 dB point itself (FieldTrip) — a 2× different high-pass. Pinning it took
  FieldTrip's P3 from max |Δ| **0.721 µV → 0.050 µV**, r 0.9939 → **1.0000**, ρ → **1.0000**, 10/20 →
  **20/20** within ±0.1 µV. The transition-band width, the parameter we first suspected, explained
  none of it (0.721 → 0.802 µV, i.e. slightly worse).

So the ~1 µV cross-kernel sensitivity noted in §4g is **not irreducible**: with the filter fully
specified, FieldTrip lands within 0.1 µV of the reference on all 74 no-rejection subject-component comparisons (per-component maxima 0.050–0.099 µV; MMN with rejection 0.184 µV), and EEGLAB at its own defaults on 68 of 74.
What is irreducible is that a prose protocol does not specify a filter.

### 4h. Beyond ERP — spectral band power (resting state)

Everything above is ERP. To extend the numeric validation to a **non-ERP** measure — AEA's
`eeg-spectral` band power — `independent_spectral.py` computes per-channel band power
(δ/θ/α/β) on resting eegbci (eyes-closed, N=12) three ways from the same data: (A) MNE Welch,
(B) a **from-scratch numpy Welch** (independent of MNE — note `scipy.signal.welch` shares MNE's FFT
path, so a hand-rolled version was needed), and (C) MNE **multitaper** (a different estimator).

| Band | (A vs B) independent-Welch max rel. err | (A vs C) Welch-vs-multitaper median rel. diff |
|---|---:|---:|
| delta | 4.7e-16 (relative) | 4.6 % |
| theta | 6.9e-16 | 1.6 % |
| alpha | 4.9e-16 | 1.9 % |
| beta | 5.5e-16 | 0.7 % |

**Two honest, separate findings.** (A vs B) AEA's band power matches an **independent from-scratch
Welch within floating-point precision** (max relative error 6.9e-16 — 6.8958×10⁻¹⁶ — over 12 eegbci eyes-closed recordings, four bands, 2-s Hamming windows at 50 % overlap, on this machine; an independent NumPy/SciPy stack gave 6.5–8.3×10⁻¹⁶ — the exact figure is environment-dependent at that level, the conclusion is not) — once the scratch
implementation uses the same two conventions MNE does: a *periodic* Hamming window and per-segment
demeaning. **Correction (2026-09-14, external review):** the first version of this comparison used a
symmetric window without demeaning, found a ≤ 0.44 % residual, and attributed it to
"segment-boundary/count handling". That attribution was unsupported — the residual *was* the two
unstated conventions, i.e. one more instance of a phrase ("Welch, Hamming window") that is not a
numerical specification. Welch is a deterministic formula with no kernel choice like an ERP filter, so
exact agreement is what correctness looks like here. (A vs C) swapping Welch for
**multitaper moves band power by ~1–5 %** — the spectral analog of the ERP filter-kernel sensitivity
(§4g): the reported number depends on the estimator choice at the low-single-digit-percent level, a
real sensitivity the ERP same-backend comparisons could not surface. Both are small relative to
between-subject variation, but they set the honest resolution of a spectral claim.

The certified run uses MNE's default Hamming taper, whereas the `eeg-spectral` skill and the resting recipe specify Hann as their default (external review, 2026-09-15). `independent_spectral.py --window hann` repeats the comparison with the Hann taper in both implementations: max relative error 5.2×10⁻¹⁶ across the four bands ([`SPECTRAL_KERNEL_INDEP_RESULT_hann.json`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT_hann.json)), so the L2 certification covers the released default as well.

The [Hamming result](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT.json)
and [original convention-gap result](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/546db87c2e7717ff2eeca83c6e4131294f14a97a/tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT_legacy_conventions.json)
remain in the same snapshot. The reproduction commands below still generate fresh result files.

---

## 5. What this proves — and what it does not

> **What "the pipeline" means here (read first — scope of the claim).** The AEA side of every
> benchmark is a **faithful reference implementation of the recipe's declared spec**
> (`tools/validation/validate_*_group.py`) — the analysis choices written in each `RECIPE.md`,
> coded by hand. It is **not** the byte-for-byte output of a live `/eeg-recipe` LLM run. So the
> benchmark proves the **recipe specification + its reference implementation** are numerically
> correct against the gold standard; it does **not** prove that the LLM, on a given day, generates
> identical code (that needs recipe-generation-under-CI — §6f). Read "the recipe's pipeline" below
> in that sense.

**Proves.** AEA's `mmn-oddball` recipe spec, run as its reference implementation, is *numerically
equivalent* to an independent community-standard implementation of the same analysis. The recipe's
event extraction, filtering, referencing, epoching, and averaging contain no hidden numerical error:
hand it the same spec and it lands on the same number a careful MNE-BIDS-Pipeline user would. This is
the empirical content behind the "HuggingFace-to-PyTorch" positioning — both layers call the same
kernels; the value, now demonstrated, is that the recipe *composes* them faithfully. Agreement holds
not only for the 100–250 ms ROI scalar (~3 nV) but across the **entire waveform** — all channels ×
all samples to ~11 nV RMSE (§4b) — so it is not an artifact of the summary statistic. The same holds
for four more ERPs (P3b §4c, N170 §4d, response-locked ERN §4e, N400 §4f — all CCC ≥ 0.9997), across
both stimulus- and response-locked epoching, so the faithfulness is a property of the
recipe→pipeline composition, not of one paradigm or time-lock.

**Does not prove.** (1) That a live LLM run generates the same code. A blind-generation pilot (§6f)
recorded seven pinned-spec generations hitting the certified values to 0.5 nV across MMN, P3 and N170
and two generator backends (Claude, GPT/Codex) — but the generated programs and, except MMN B1, the
per-subject vectors were not retained, so those are **retained scoring summaries, not reconstructable
evidence, and they do not certify the skill** (`eeg-recipe` is L0; external review 2026-09-13/14).
Generating from the recipe *as written* diverged systematically (0.245 µV, n=40 vs 38) because one
step was under-specified — that observation stands.
Scope: 3 recipes, 9 generations, 2 backends. (2) That AEA's
recipe **defaults** (ICA, AutoReject) are validated — the benchmark deliberately runs a *harmonized
minimal* pipeline (reject=None / no ICA for the active tasks) so only implementation differs; the
default-vs-minimal gap is unmeasured (§6d). (3) That AEA's *default parameter choices* are optimal —
a separate science question. (4) *Full* independence from MNE — §4g now bounds **kernel** error with an
independent SciPy DSP (MMN ≤0.05 µV; P3 ≤0.87 µV, revealing real slow-component filter sensitivity),
but the recognized independent *toolbox* (EEGLAB/ERPLAB) is still untested (§6b). (5) Anything about the remaining ERP CORE components
(N2pc, LRP), source localization, connectivity, or clinical populations. Those are §6.

Honest one-liner: **this retires "does the recipe spec's pipeline compute the wrong number?" for 5
ERP components. It does not, by itself, make AEA a validated toolbox** — it makes five recipes
demonstrably faithful to the reference, under a harmonized minimal pipeline, and gives a template for
the rest.

---

## 6. Roadmap to a real validation suite

| Step | What | Why it matters |
|------|------|----------------|
| **6a** 🔶 | Repeat for the other ERP CORE components. **Done: MMN + P3 + N170 + ERN + N400 (§4–§4f) = 5 of 7.** Remaining: **N2pc** (lateralized, needs contra/ipsi logic) and **LRP** (response-locked lateralized) — both need new recipes. | Generalizes the correctness claim beyond one ERP |
| **6b** ✅ | Add a **non-MNE backend**. **Done (§4g): independent SciPy DSP** (Butterworth+resample_poly) — bounds *kernel* error. **Done (§4i): EEGLAB and FieldTrip toolboxes**, all 5 components, 10/10 same conclusion; disagreements traced to unstated spec parameters, and with the filter pinned FieldTrip reaches r = ρ = 1.0000. **Remaining:** wire them into the skills as *selectable* backends (`eeg-preprocess` Phase B currently has one branch). | Bounds *kernel* error and *toolbox* error, not just composition error |
| ~~**6c**~~ ✅ | **Per-sample** waveform agreement (not just the 100–250 ms scalar): full-epoch all-channel RMSE — **done for all 5 components** (`compare_waveform.py --component X`; committed `*_WAVEFORM_RESULT.json`; §4b) | Catches errors a single summary statistic hides |
| **6d** | **Default-divergence axis**: run each tool at its *own* recommended defaults (ICA/AutoReject) and quantify/explain the gap vs the harmonized minimal pipeline | Tells users how much pipeline choice (not bugs) moves the number |
| ~~**6e**~~ ✅ | Benchmark wired into CI as a regression gate — `tools/tests/test_benchmark.py`: **done.** A CI-safe *consistency* gate asserts CCC ≥ 0.99, exact expected N, per-subject max \|Δ\| ≤ 0.1 µV, and waveform-RMSE bounds for all 5 components from the committed JSONs on every push (it does **not** rerun MNE-BIDS-Pipeline); a data-gated test reruns AEA's MMN pipeline on 2 subjects and checks it reproduces the committed µV (skips where raw data absent). | Locks in correctness against future recipe edits |
| **6g** 🔶 | **Beyond ERP**: numeric validation of non-ERP measures. **Done: spectral band power** (§4h — independent Welch at floating-point precision once the window-periodicity and demeaning conventions are pinned; estimator sensitivity ~1–5%). **Remaining:** connectivity (mne-connectivity), complexity, and source (need a real MRI + independent tool). | Extends validation past ERP |
| ~~**6f**~~ ✅ | **Recipe-generation eval — done.** 4 blind agents wrote MMN pipelines from the spec and ran them on real data. **Historical pilot (superseded 2026-09-13/14): 7 pinned-spec generation records PASS across MMN/P3/N170 and two generator backends (Claude + GPT/Codex), ≤0.5 nV, every subject in tolerance — but the generated programs and, except MMN B1, the per-subject vectors were not retained, so this does NOT certify the skill (`eeg-recipe` is L0); retained scores only.** Recipe-as-written → systematic 0.245 µV offset + n=40 vs 38, root-caused to an under-specified RANSAC step. [`RECIPE_GENERATION_EVAL.md`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/RECIPE_GENERATION_EVAL.md) | Historical pilot of the generation step (not a certification), not just the spec |

---

## 7. Reproduce

```bash
# 1. build a working BIDS copy with harmonized event labels (signal files symlinked)
python tools/benchmark/build_bids_subset.py --n 40

# 2. gold standard: MNE-BIDS-Pipeline with the harmonized config
BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_mmn_bidspipe.py

# 3. extract the per-subject MMN from the gold derivatives
python tools/benchmark/extract_bidspipe_mmn.py

# 4. AEA side (already committed): tools/validation/mmn_group_results.json
python tools/validation/validate_mmn_group.py --subjects 40   # (re)generate if needed

# 5. digit-by-digit comparison + figure
python tools/benchmark/compare_mmn.py
```

**Second component (P3b):**

```bash
# download ERP CORE P3 (20 subjects) from the local manifest's OSF URLs
python tools/benchmark/download_erpcore_component.py --component P3 --n 20
python tools/validation/validate_p3_group.py --subjects 20            # AEA side
python tools/benchmark/build_bids_subset_p3.py --n 20                 # working BIDS copy
BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_p3_bidspipe.py
python tools/benchmark/extract_bidspipe_p3.py                         # gold side
python tools/benchmark/compare_mmn.py --aea tools/validation/p3_group_results.json \
  --gold tools/benchmark/bidspipe_p3_results.json --key p3_uV --tol 0.10 \
  --out tools/benchmark/P3_BENCHMARK_RESULT.json --figure tools/benchmark/figures/p3_benchmark.png
```

**Third component (N170, face − car)** — same shape, `--component N170`, `--key n170_uV`:

```bash
python tools/benchmark/download_erpcore_component.py --component N170 --n 20
python tools/validation/validate_n170_erpcore_group.py --subjects 20
python tools/benchmark/build_bids_subset_n170.py --n 20
BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_n170_bidspipe.py
python tools/benchmark/extract_bidspipe_n170.py
python tools/benchmark/compare_mmn.py --aea tools/validation/n170_erpcore_results.json \
  --gold tools/benchmark/bidspipe_n170_results.json --key n170_uV --tol 0.10 \
  --out tools/benchmark/N170_BENCHMARK_RESULT.json --figure tools/benchmark/figures/n170_benchmark.png
```

**Fourth component (ERN, error − correct, response-locked)** — `--component ERN`, `--key ern_uV`:

```bash
python tools/benchmark/download_erpcore_component.py --component ERN --n 20
python tools/validation/validate_ern_erpcore_group.py --subjects 20
python tools/benchmark/build_bids_subset_ern.py --n 20
BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_ern_bidspipe.py
python tools/benchmark/extract_bidspipe_ern.py
python tools/benchmark/compare_mmn.py --aea tools/validation/ern_erpcore_results.json \
  --gold tools/benchmark/bidspipe_ern_results.json --key ern_uV --tol 0.10 \
  --out tools/benchmark/ERN_BENCHMARK_RESULT.json --figure tools/benchmark/figures/ern_benchmark.png
```

**Fifth component (N400, unrelated − related)** — `--component N400`, `--key n400_uV`:

```bash
python tools/benchmark/download_erpcore_component.py --component N400 --n 20
python tools/validation/validate_n400_erpcore_group.py --subjects 20
python tools/benchmark/build_bids_subset_n400.py --n 20
BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_n400_bidspipe.py
python tools/benchmark/extract_bidspipe_n400.py
python tools/benchmark/compare_mmn.py --aea tools/validation/n400_erpcore_results.json \
  --gold tools/benchmark/bidspipe_n400_results.json --key n400_uV --tol 0.10 \
  --out tools/benchmark/N400_BENCHMARK_RESULT.json --figure tools/benchmark/figures/n400_benchmark.png
```

**Kernel independence (§4g)** — MNE DSP vs independent SciPy DSP, same data:

```bash
python tools/benchmark/independent_dsp.py --component MMN --subjects 12
python tools/benchmark/independent_dsp.py --component P3  --subjects 12
python tools/benchmark/independent_spectral.py --subjects 12   # §4h non-ERP spectral band power
```

**CI regression gate:** `python -m pytest tools/tests/test_benchmark.py` (runs on every push).

Inputs: ERP CORE MMN at `~/mne_data/MNE-erpcoremmn2021-data` (OpenNeuro `ds003065`); P3 fetched to
`~/mne_data/erpcore-P3`. Pinned tool: `mne-bids-pipeline==1.10.1`, `mne==1.11.0`.
