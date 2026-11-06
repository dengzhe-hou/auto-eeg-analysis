## Continuous Pearson correlation

Select approved channels and interval, apply only requested processing, then
use `np.corrcoef(data)` with channels as rows. Rank signed correlations unless
absolute values are requested. Exclude self-entries and reversed duplicates.
Save the matrix and actual channel labels in matching row order.

## Continuous PLV

For approved Hilbert phase differences averaged across time, filter and crop
in the specified order and compute analytic signals across the sample axis.
This differs from spectral phase consistency across epochs. Do not replace
one with the other or infer anatomical connectivity from sensor PLV.

```python
from pathlib import Path
import runpy
from scipy.signal import hilbert
connectivity = runpy.run_path(str(Path(AEA_ROOT) / "skills/eeg-connectivity/scripts/continuous.py"))
analytic = hilbert(approved_filtered_data, axis=-1)
matrix = connectivity["plv_from_analytic"](analytic)
summary = connectivity["summarize_undirected_connectivity"](
    matrix, actual_channels, top_k=approved_top_k)
result = {"status": "computed", "global_mean_plv": summary["global_mean"],
          "top3_plv_pairs": summary["top_pairs"],
          "analysis_metadata": summary["metadata"],
          "explanation": (f"Computed PLV over {summary['metadata']['n_channels']} channels "
                          f"and {summary['metadata']['n_undirected_pairs']} distinct pairs.")}
```

Use distinct pairs for a global mean or ranking. Preserve channel order,
label identity and approved tie rules.
Use these computed values in both saved JSON and the final report. Do not
manually count the channel list or copy counts from another recording.
For the requested pair list, a plain list of two-label lists is sufficient;
named objects such as `{"channel_pair": ["F3", "F4"], "plv": value}` carry
the same identities. Preserve pair ordering when the task requests ranking.
The example result keys apply to the corresponding mean/top-pair PLV request;
adapt field names to the approved output interface without dropping values.

## Continuous ordinary wPLI

Use only for approved ordinary Hilbert wPLI over time. Apply specified bands
and time selection first. Full analytic cross-products supply amplitude
weights; `exp(1j*phase)` changes the estimator. Debiased squared wPLI also
differs. Do not add a fixed epsilon to its denominator.

```python
# Import connectivity and compute analytic as in Continuous PLV above.
matrix = connectivity["ordinary_wpli_from_analytic"](analytic)
difference = connectivity["hemisphere_difference"](
    matrix, actual_channels, homologous_pairs=approved_left_right_pairs)
```

Self-wPLI is undefined and stored NaN. Average distinct within-side pairs,
then left minus right, not homologous cross-side edges. Undefined edges cannot
be omitted without approval. Explain actual band differences and their signs.
Preserve approved FIR settings, bands, interval and channels.
When the approved order selects a time interval before filtering, filter that
selected buffer; a later crop of a full-recording filter is a different input
to Hilbert. For a half-open interval, use sample-index `start`/`stop` in
`get_data`, or the bounded crop helper, rather than mixing its stop convention
with MNE's inclusive `Raw.crop` endpoint.

Start each frequency band from an independent copy of the unchanged selected
input. Constructing an MNE `RawArray` from an existing float array can share
its memory, so filtering that RawArray may change the original array before
the next band's calculation. Use the bounded preprocessing helper on the
original Raw for each band, or explicitly copy the array at branch creation.

## Complete multiband Hilbert calculation

For the supplied approved MNE plan, prefer the
[continuous-plan runner](../../../docs/PRELOADED_SKILLS.md#execute-and-check-a-complete-continuous-plan).
It executes each band's own ordered operations from a fresh unchanged input,
retains actual processing metadata, saves the matrices and checks them from
the source. Each declared hemisphere contrast contributes its measured value
and direction to the saved explanation and final JSON. Structural checks alone
do not establish that the approved filtering/cropping order was used.

This example connects the approved operations, Hilbert estimator, summaries,
saved evidence and public self-check. It uses the same numerical helpers above.
The supplied plan's `hilbert_bands` mapping names each band and supplies its
ordered `operations`, `metric` (`plv` or ordinary `wpli`), and `matrix_key`.
Optional `mean_result`/`pairs_result` requests use an explicit `top_k` and the
approved distinct-pair mean/value-descending, label-ascending ranking. For a
left-minus-right within-hemisphere mean, supply `difference_result` and the
actual `homologous_pairs`; the example never infers hemispheres from strings.
Include matching `connectivity_summaries` or `hemisphere_contrasts` declarations
in the public plan when those derived checks are requested (see the setup guide).
Before running this example, supply `numeric_tolerance.connectivity` with the
approved dimensionless `rtol` and `atol` for matrix comparison. Requested mean
or hemisphere-contrast checks also need `numeric_tolerance.result`. These are
separate quantities; the example does not invent or copy one tolerance to the other.
This path preserves all requested off-diagonal values; undefined edges require
the approved missing-value policy rather than dropping them from the summary.

```python
from pathlib import Path
import json
import sys
import mne

sys.path.insert(0, str(Path(AEA_ROOT) / "tools"))
from run_continuous_plan import run_plan
with mne.io.read_raw(approved_public_plan["input_path"], preload=False, verbose=False) as original:
    final_result, self_check = run_plan(approved_public_plan, original, output_directory)
print(json.dumps(final_result))
```

The `operations` for each band include only approved filtering/cropping/reference
steps in their declared order. An available filter configuration adds no step.
With `raw_input`, `hilbert_bands` and the approved
`numeric_tolerance.connectivity` (`rtol`, `atol`), this check reconstructs each
band from the unchanged recording and compares the saved matrix. Requested
summaries are also recomputed from saved matrices. Without `raw_input`, only
the latter and structural checks run. Inspect `coverage.hilbert_matrices_recomputed`
for the actual bands checked. This shares AEA's helpers and is not independent
numerical certification. Do not pass one band's operations as though they
described every branch.
