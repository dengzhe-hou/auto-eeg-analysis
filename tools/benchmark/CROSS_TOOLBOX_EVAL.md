# Three toolboxes, five components: what the certified numbers actually depend on

**The objection this closes.** Every earlier benchmark ran on MNE primitives on both sides — even the
independent-DSP check ([BENCHMARK.md §4g](../../docs/BENCHMARK.md)) re-implemented the filtering in
SciPy but still read the data through MNE and compared against MNE-derived references. A reviewer can
reasonably ask whether the certified values are an artefact of one ecosystem.

This runs all five certified ERP CORE analyses in **two genuinely independent toolboxes** — EEGLAB and
FieldTrip, both under GNU Octave — and then asks the sharper question: **when they disagree, what is
it that they actually disagree about?**

The answer is not the toolbox. In every case we were able to trace, the divergence came from a
parameter that the analysis specification names in prose but does not pin numerically.

## Setup

| | |
|---|---|
| **Toolbox A** | MNE-Python 1.12.1 — the certified reference (itself certified against MNE-BIDS-Pipeline 1.10.1) |
| **Toolbox B** | **EEGLAB** (git `sccn/eeglab`) under **GNU Octave 10.3**, no MATLAB — `tools/benchmark/erpcore_eeglab.m` |
| **Toolbox C** | **FieldTrip 20170830** under the same Octave — `tools/benchmark/erpcore_fieldtrip.m` |
| **Components** | MMN, P3b, N170, ERN, N400 — the same five that are CI-gated against MNE-BIDS-Pipeline |
| **Comparison** | per-subject, against the committed `tools/validation/*_results.json` |

The contrast is held identical on purpose, so that only the *implementation* varies. Before running
anything we verified that the numeric event codes stored in each ERP CORE `.set` file are identical to
the `value` column of the corresponding BIDS `_events.tsv`, for all five components (onsets agree to
5×10⁻⁵ s, the TSV's rounding). Each toolbox therefore decodes conditions from its own native event
representation and still analyses exactly the same trials — confirmed downstream by
**0 trial-count mismatches** on every no-rejection component, and by EEGLAB and FieldTrip
independently excluding the *same* 6 of 20 ERN subjects that the reference excludes.

Three genuinely different implementations are involved at every stage:

| stage | MNE | EEGLAB (here) | FieldTrip (here) |
|---|---|---|---|
| reader | `read_raw_eeglab` | `pop_loadset` | `ft_read_header` / `read_eeglabdata` |
| filter | FIR firwin | `pop_eegfiltnew` (firws) | `ft_preproc_bandpassfilter` (firws) |
| **resampling** | FFT / polyphase | **cubic-spline interpolation** ¹ | **decimation** ² |
| data model | 3-D array | 3-D array | per-trial cell array |

¹ Octave Forge `signal` is not installed, so EEGLAB's `pop_resample` takes its spline fallback.
² `ft_resampledata` also needs `signal`, which cannot be built here (no C++ compiler). Decimation is
exact rather than a compromise: the data have just been low-passed at ≤40 Hz and the new Nyquist is
128 Hz, so keeping every 4th sample introduces no aliasing, and sample 1 is retained so the time origin
matches. The upshot is that the three arms use **three unrelated resampling algorithms**.

---

## Result 1 — the certified values are not an MNE artefact

Four of the five components use `reject=None` (every epoch averaged), so both toolboxes average an
identical trial set and the comparison isolates DSP alone.

| component | toolbox | grand mean | certified | Δ | max \|Δ\| | mean \|Δ\| | CCC | ≤0.1 µV | same conclusion |
|---|---|---:|---:|---:|---:|---:|---:|:---:|:---:|
| **P3b** | EEGLAB | +1.6739 | +1.6826 | **0.009** (0.5%) | 0.050 | 0.022 | **0.9999** | 20/20 | ✅ |
| **N400** | EEGLAB | −2.9723 | −2.9572 | **0.015** (0.5%) | 0.069 | 0.024 | **0.9999** | 20/20 | ✅ |
| **ERN** | EEGLAB | −5.4278 | −5.4462 | **0.018** (0.3%) | 0.210 | 0.056 | 0.9997 | 12/14 | ✅ |
| **N170** | EEGLAB | −1.2204 | −1.1812 | 0.039 (3.3%) | 0.161 | 0.057 | 0.9979 | 16/20 | ✅ |
| **MMN** | EEGLAB (p2p) | −0.8553 | −0.8398 | 0.016 (1.8%) | 0.233 | 0.040 | 0.9953 | 33/38 | ✅ |
| **N170** | FieldTrip | −1.1648 | −1.1812 | 0.016 (1.4%) | 0.117 | 0.039 | 0.9990 | 18/20 | ✅ |
| **N400** | FieldTrip | −2.9815 | −2.9572 | 0.024 (0.8%) | 0.229 | 0.106 | 0.9982 | 10/20 | ✅ |
| **MMN** | FieldTrip (p2p) | −0.8497 | −0.8398 | 0.010 (1.2%) | 0.189 | 0.057 | 0.9939 | 30/38 | ✅ |
| **ERN** | FieldTrip | −5.3223 | −5.4462 | 0.124 (2.3%) | 0.366 | 0.183 | 0.9979 | 3/14 | ✅ |
| **P3b** | FieldTrip | +1.7462 | +1.6826 | 0.064 (3.8%) | 0.721 | 0.139 | 0.9928 | 10/20 | ✅ |

**Every one of the ten cross-toolbox runs reproduces the group-level scientific conclusion, and the
grand means agree to 0.3–3.8%.** The certified values are a property of the analysis, not of MNE.

Note that the ≤0.1 µV column is not comparable across components: ERN's effect is −5.45 µV and MMN's
is −0.84 µV, so a fixed ±0.1 µV band is 6× stricter for MMN. The `%`-of-group-effect figures in
`CROSS_TOOLBOX_RESULT.json` are the like-for-like measure.

---

## Result 2 — the disagreements are specification ambiguities, not toolbox differences

This is the part that matters. Two controlled experiments, each changing **one** unstated parameter
while holding the toolbox fixed.

### 2a. "±100 µV rejection" — peak-to-peak or absolute?

MMN is the only certified component that applies artefact rejection. MNE's
`reject=dict(eeg=100e-6)` is a **peak-to-peak** criterion; EEGLAB's idiomatic
`pop_eegthresh(..., -100, 100, ...)` is an **absolute-amplitude** criterion. Both are legitimate
readings of "±100 µV". Same toolbox, same data, only the criterion changes:

| criterion | mean \|Δ\| | CCC | Spearman ρ | ≤0.1 µV | sub-001 deviants retained |
|---|---:|---:|---:|:---:|---:|
| `abs` — EEGLAB idiom | 0.0886 | 0.9845 | 0.9676 | 22/38 | 185 |
| **`p2p` — matched to MNE** | **0.0396** | **0.9953** | **0.9912** | **33/38** | 130 |
| *(MNE certified)* | — | — | — | — | *117* |

**Harmonizing one criterion of the specification (peak-to-peak vs absolute) improves per-subject agreement 2.2×.**

A second-order coupling is visible in the trial counts: even under a matched peak-to-peak rule EEGLAB
retains 130 deviants where MNE retains 117. That is because MNE's low-pass leaves the −6 dB point at
33.75 Hz while EEGLAB's sits at 30.05 Hz (see 2b), so MNE admits more high-frequency content, inflating
the peak-to-peak measure and rejecting more trials. **Two separately-unstated parameters interact.**

### 2b. "0.1–30 Hz zero-phase FIR" — is 0.1 Hz the passband edge or the −6 dB point?

The FieldTrip P3 arm was the worst row in the table (max |Δ| 0.72 µV = 43% of the group effect). We
formed a hypothesis, tested it, and **it was wrong** — which is how the real cause surfaced.

*Hypothesis 1 (refuted): the transition-band width.* The three toolboxes default differently —
MNE 0.1 Hz low / 7.5 Hz high, EEGLAB 0.1 Hz both, FieldTrip 0.2 Hz both, giving FieldTrip a filter of
half the length (16 896 vs 33 793 taps). Forcing FieldTrip to 0.1 Hz did not help; it made agreement
marginally **worse**.

*Hypothesis 2 (confirmed): what the stated frequency means.* EEGLAB and MNE treat `0.1` as the
**passband edge** and place the −6 dB point at 0.05 Hz. FieldTrip places −6 dB **at** 0.1 Hz. The same
phrase therefore specifies a **2× different high-pass**. Shifting FieldTrip's requested band by half a
transition width makes its filter identical to EEGLAB's (−6 dB at 0.05 / 30.05 Hz, df 0.1, order
33 792 vs 33 793):

| FieldTrip P3 configuration | grand Δ | max \|Δ\| | mean \|Δ\| | CCC | Pearson r | Spearman ρ | ≤0.1 µV |
|---|---:|---:|---:|---:|---:|---:|:---:|
| [1] FieldTrip defaults (df 0.2, −6 dB @ 0.1) | 0.064 | 0.721 | 0.139 | 0.9928 | 0.9939 | 0.9865 | 10/20 |
| [2] + transition width pinned to 0.1 | 0.065 | **0.802** | 0.160 | 0.9907 | 0.9918 | 0.9835 | 10/20 |
| **[3] + cutoff convention pinned (−6 dB @ 0.05)** | **0.003** | **0.050** | **0.014** | **0.9999** | **1.0000** | **1.0000** | **20/20** |
| *(EEGLAB, for reference)* | *0.009* | *0.050* | *0.022* | *0.9999* | *0.9999* | *0.9970* | *20/20* |

> **A 16× reduction in worst-case per-subject error, from `r = 0.9939` to `r = 1.0000` with perfect
> rank agreement across 20 subjects — produced by pinning the filter specification: the cutoff
> convention at a fixed transition width, i.e. two parameters, not one word.** With the filter fully specified,
> FieldTrip matches the certified values *better than EEGLAB does*, despite a different data model, a
> different reader and a different resampling algorithm.

The parameter one would naturally suspect — the transition-band width — accounted for **none** of it.

### 2c. The pin replicated on all five components (added 2026-08-19)

Same FieldTrip runs, cutoff convention pinned to the passband-edge reading (`CUTOFFCONV=eeglab`,
`FILTDF=0.1`), versus the certified MNE values:

| component | max \|Δ\| unpinned → pinned | ≤0.1 µV unpinned → pinned | CCC pinned |
|---|---:|:---:|---:|
| P3b | 0.721 → **0.050** | 10/20 → **20/20** | 0.9999 (r = ρ = 1.0000) |
| N400 | 0.229 → **0.050** | 10/20 → **20/20** | **1.0000** (r = 1.0000) |
| ERN | 0.366 → **0.070** | 3/14 → **14/14** | 0.9999 (ρ = 1.0000) |
| N170 | 0.117 → **0.099** | 18/20 → **20/20** | 0.9994 |
| MMN (p2p) | 0.189 → 0.184 | 30/38 → 34/38 | 0.9963 |

**For every no-rejection component, pinning the filter specification (cutoff convention together with transition width) brings every subject-component comparison within ±0.1 µV**
(74/74 across P3b/N400/ERN/N170, worst case 0.099 µV).

The two muted rows may share one residual mechanism — a candidate that was not isolated experimentally — and it is the honest asterisk on "pinned": the
pin harmonizes FieldTrip to **EEGLAB's** reading, but **MNE is the odd one out at the upper edge**
— its automatic transition puts −6 dB at 33.75 Hz (30 Hz bands) and 45.0 Hz (N170's 40 Hz band),
where the pinned MATLAB pair sit at 30.05/40.05. For N170 that leaves a small broadband residual;
for MMN it also **feeds the rejection coupling** (more high-frequency content in MNE → larger
peak-to-peak → different retained trials; mismatches fall only 34 → 29). MNE's
`h_trans_bandwidth` *is* settable — the certified reference simply used its default — so a full
three-way pin is possible but would mean re-running the certified baseline, and is left as stated
future work rather than done quietly.

---

## Findings

**1. Certified per-subject ERP amplitudes are reproducible in FieldTrip within 0.1 µV on all 74 no-rejection comparisons once the filter is pinned (per-component maxima 0.050–0.099 µV; MMN with rejection 0.184 µV; EEGLAB at defaults 68/74) —
but only when the specification pins the filter completely.** The cutoff frequency alone is not
enough; the specification must also state what the cutoff frequency *means* and how wide the
transition band is.

**2. This is the fifth and sixth independent instance of the same pattern in this project.** RANSAC
on/off, the reference scheme, sample-grid alignment at window edges, "±100 µV", and now the filter
cutoff convention: **a phrase that reads unambiguously to a human is not a numerical specification.**
Each was discovered the same way — a divergence that looked like an implementation difference turned
out to be an unstated parameter.

**3. Unstated parameters interact.** The filter's upper cutoff changes how many trials survive a
peak-to-peak rejection threshold. Pinning parameters one at a time can therefore *appear* not to help
(as in 2b step [2]) while the real cause sits elsewhere.

**4. Group-level statistics are robust; per-subject values are not — and the failure is structured.**
All ten runs reached the same conclusion. But the residual is a *systematic bias* rather than noise
(the signed mean difference is 17–69% of the mean absolute difference), and where the effect is near
zero it can flip sign at the individual level: FieldTrip's default-configuration P3 flipped 1 of 20
subjects (sub-014; the transition-width-only variant flipped 2, adding sub-006). Subjects with a clear effect agreed to ~1 nV
(sub-008: 2.711 vs 2.710 µV). **Group conclusions survive an under-specified pipeline.** Whether individual-differences
analyses or single-subject classification would survive it is *untested here*; the per-subject
residuals and the sign flip are the reason to expect that it matters, not evidence that it does.

**5. Faster components are more exposed to upper-edge mismatch.** EEGLAB's N170 (0.1–40 Hz band,
130–200 ms window) diverges 3× more than its P3/N400 (0.1–30 Hz, 300–500 ms), and the mechanism is
visible: MNE's automatic transition puts −6 dB at 45.0 Hz for the N170 band against EEGLAB's 40.05 Hz,
a 5.0 Hz gap versus 3.7 Hz for the 30 Hz band — a larger mismatch acting on a component with more
energy near the edge.

---

## Honest limitations

1. ~~The cutoff-convention experiment was run on P3 only~~ **Resolved (§2c): replicated on all
   five components.** Every no-rejection component reaches 100% of subjects within ±0.1 µV; the
   remaining residual is MNE's automatic upper transition bandwidth, named and bounded in §2c.
2. **Octave, not MATLAB.** Both toolboxes' numerical behaviour under Octave is assumed equivalent to
   MATLAB but was not verified against a MATLAB run.
3. **Resampling is not harmonized anywhere.** Three different algorithms are in play and their
   individual contribution was not isolated; after pinning the filter the P3 residual is 0.05 µV,
   which bounds it but does not attribute it.
4. **Data are read from the same `.set` files**, so file-format interpretation is shared, not
   independent. A truly independent arm would start from the raw `.bdf`.
5. **The FieldTrip build is from 2017.** Newer releases may differ in defaults, which would change the
   size — though not the existence — of the divergence.
6. **`n` is not identical everywhere.** For MMN, MNE analyses 38 of 40 subjects and EEGLAB/FieldTrip 39;
   the per-subject statistics use the 38 shared subjects, so the MMN grand means in Result 1 are not
   strictly like-for-like. (For ERN, all three arms independently arrived at the same 14.)
7. **These runs test the reference implementations, not generated pipelines.** The generation step is
   covered separately in [`RECIPE_GENERATION_EVAL.md`](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/76202d6071070c27ad2813561e54272969cacb4b/tools/benchmark/RECIPE_GENERATION_EVAL.md).

---

## What this changes for AEA

The recipes already carry a "numerical-specification note" warning that the prose pipeline and the
certified configuration differ. This evaluation says something stronger and more actionable:

> **A recipe intended to be portable across toolboxes must specify the filter's cutoff *convention*
> and transition width, and the rejection *criterion* — not just their numbers.** Otherwise two
> competent analysts using two standard toolboxes will produce per-subject values differing by up to
> half the group effect while both believe they followed the recipe.

That is a concrete, testable requirement to add to the recipe schema, and it is exactly the kind of
thing a certification harness catches and a prose protocol does not.

---

## Reproduce

```bash
export OCTAVE_HOME=$HOME/miniconda3/envs/octave   # conda Octave has an uninitialised load path
export EEGLAB_PATH=/path/to/eeglab                # dir containing eeglab.m
export FIELDTRIP_PATH=/path/to/fieldtrip          # dir containing ft_defaults.m
export AEA_DATA_ROOT=$HOME/mne_data               # where the ERP CORE datasets live
# Write the fresh runs to a directory of YOUR OWN and score THAT directory -- the earlier version of
# this block ran the arms (default outputs under /tmp) and then scored the committed archive, so a
# reader could obtain the published report without ever checking their own run (external review,
# 2026-09-14). Verified once on 2026-09-14: see "Reproduction route check" below.
mkdir -p /tmp/aea_repro
# EEGLAB arm  (COMP: MMN|P3|N170|ERN|N400 ; REJECT_MODE: none|abs|p2p)
COMP=P3 OUTFILE=/tmp/aea_repro/eeglab_P3.json \
  $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/erpcore_eeglab.m
# FieldTrip arm, filter fully pinned
COMP=P3 FILTDF=0.1 CUTOFFCONV=eeglab OUTFILE=/tmp/aea_repro/fieldtrip_P3_cutmatch.json \
  $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/erpcore_fieldtrip.m
# score the files you just produced (not the archive)
python tools/benchmark/compare_eeglab.py --all --glob-dir /tmp/aea_repro --pattern '*.json' --out /tmp/aea_repro/RESULT.json
python tools/benchmark/analyze_toolbox_divergence.py --scan /tmp/aea_repro --out /tmp/aea_repro/DIVERGENCE.json
# then compare /tmp/aea_repro/RESULT.json against the committed CROSS_TOOLBOX_RESULT.json rows
```

### Reproduction route check (2026-09-14)

The FieldTrip arm and the scorer of the block above were executed once as written, on this machine
(the EEGLAB arm was not re-run for this check), after the external review found that
its earlier form scored the archive: `COMP=P3 FILTDF=0.1 CUTOFFCONV=eeglab
OUTFILE=/tmp/aea_repro/fieldtrip_P3_cutmatch.json … erpcore_fieldtrip.m`, then
`compare_eeglab.py --all --glob-dir /tmp/aea_repro --pattern '*.json'`. The scorer read the freshly
written file (the directory contained nothing else) and reported grand +1.6855 vs +1.6826 µV,
max |Δ| **0.0496 µV**, mean |Δ| 0.0139, CCC **0.999943**, r = ρ = 1.0000, **20/20** within ±0.1 µV,
0 trial-count mismatches — identical to the committed `fieldtrip_P3_cutmatch.json` row, as expected
for a deterministic pipeline on the same inputs. The check is of the *route* (a reader's own run is
what gets scored), not new evidence about the toolboxes.

Raw per-subject outputs of the published runs are committed under
`tools/benchmark/cross_toolbox_results/`; the scored summaries are `CROSS_TOOLBOX_RESULT.json` and
`CROSS_TOOLBOX_DIVERGENCE.json`. Re-scoring that directory reproduces the summaries from the archive;
it does not check a new run.

Two environment fixes are worth recording: the conda Octave build starts with an uninitialised load
path (`OCTAVE_HOME` must be set, or core functions like `getfield` are undefined), and `eeglab nogui`
fails under Octave — adding `functions/` and `plugins/` to the path directly works.
