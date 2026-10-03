# Backend templates — and why they pin so much

These are what `eeg-preprocess` emits when `tools/env/resolve_backend.py` resolves
`erp.preprocess_average` to a backend other than MNE. Fill the `SPEC` block; do not edit below it.

| file | backend |
|---|---|
| `erp_preprocess_eeglab.m` | EEGLAB, under MATLAB or GNU Octave |
| `erp_preprocess_fieldtrip.m` | FieldTrip, under MATLAB or GNU Octave |

## The point

Cross-toolbox agreement is a property of **how completely the specification is pinned**, not of the
toolbox. Each template therefore forces you to state four conventions that a prose protocol leaves
open, and that were measured to move the numbers
([CROSS_TOOLBOX_EVAL.md](../../tools/benchmark/CROSS_TOOLBOX_EVAL.md)):

| pin | the question a prose protocol does not answer |
|---|---|
| `filter.cutoff_convention` | does "0.1 Hz high-pass" name the **passband edge** or the **−6 dB point**? |
| `filter.transition_width` | how wide is the FIR transition band? |
| `reject.criterion` | is "±100 µV" **peak-to-peak** or **absolute amplitude**? |
| `resample.algorithm` | FFT/polyphase, spline interpolation, or decimation? |

## Validated — the templates reproduce the mechanism, not just the pipeline

`erp_preprocess_fieldtrip.m` was run on ERP CORE P3 (N=20) twice, changing **one SPEC field**:

| `SPEC.filter.cutoff_convention` | grand mean | vs certified +1.6826 µV | max \|Δ\| | Pearson r | Spearman ρ | ≤0.1 µV |
|---|---:|---:|---:|---:|---:|:---:|
| `'passband'` (matches MNE/EEGLAB) | +1.6855 | **0.17%** | **0.0496 µV** | **1.0000** | **1.0000** | **20/20** |
| `'minus6db'` (FieldTrip's own default) | +1.7472 | 3.84% | 0.8023 µV | 0.9918 | 0.9835 | 10/20 |

Both rows match the hand-written benchmark runs digit for digit, so the template is a faithful
implementation of the effect rather than a description of it: **flipping that one field changes
worst-case per-subject error by 16×.** Raw outputs: `validation/ft_p3_{passband,minus6db}.json`.

Group-level conclusion was the same either way. Per-subject values were not — which is the whole
reason the field exists.

## Refusals built into both templates

- **An empty run is an error, not a result.** A mean over an empty set is `0.0`, which reads as a
  finding. Both templates raise instead of writing a result file when no subject produced a value.
- **A missing ROI channel is an error**, not a silently smaller ROI.
- **Conditions are split on the time-locking event** (latency 0), not on the first event in the
  epoch — an epoch can contain several.
- Event types are normalised to strings before epoching: ERP CORE stores them as `char` in some
  datasets and `double` in others, and `pop_epoch` rejects a mixed-type event field.

## Running one

```bash
export OCTAVE_HOME=$HOME/miniconda3/envs/octave    # conda Octave needs this or getfield is undefined
export FIELDTRIP_PATH=/path/to/fieldtrip           # or EEGLAB_PATH for the EEGLAB template
$OCTAVE_HOME/bin/octave-cli --no-gui --quiet my_filled_template.m
```

The emitted JSON records the `pinned` block alongside the results, so a reader can tell which
conventions were in force without re-reading the script.
