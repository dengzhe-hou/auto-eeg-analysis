# Deliver selected AEA procedures to an agent

For a client without native skill loading, use `tools/prepare_skill_packet.py`
to put selected complete procedures and optional helper source in the initial
model message. Select from the public task and approved plan. Do not include
private reference results, evaluation scripts or expected answers.

Example selection file:

```json
[
  {"skill": "eeg-spectral", "section": "Welch and band power",
   "scripts": ["scripts/continuous.py"]}
]
```

```bash
python tools/prepare_skill_packet.py selected.json --output AEA_PACKET.md --receipt AEA_PACKET.json
```

Append the full packet to the model input. Use `check_packet_in_request` from
`tools/load_skill.py` on the actual provider-format request to detect missing
or truncated delivery before sending it. Save that receipt and the actual
request. This proves delivery, not reading, adoption or numerical correctness.
An evaluation using preloaded procedures is a different condition from asking
the model to discover resources itself; label and report it separately.

## Execute and check a complete continuous plan

For an already resolved MNE GFP, Welch/band-power or multiband Hilbert request,
use the shared executable path after retaining its approved source instructions:

```bash
python tools/run_continuous_plan.py --plan APPROVED_PLAN.json --input recording.edf --output analysis-output
```

The runner reads the same explicit settings used by `check_outputs`, executes
the actual operations in order, saves real channel/sample metadata and returns
the complete result JSON. `FINAL_SUBMISSION.md` is generated from that object,
including its explanation. `SELF_CHECK.json` records source-data and derived
checks; a failed check raises after preserving artifacts. There are no model
calls, automatic plan changes or automatic repairs. A missing consequential
choice remains unresolved; the runner supplies no scientific defaults.

Use an empty output directory for each execution. The runner refuses existing
outputs, saves `APPROVED_PLAN.json`, records the input's actual channel types,
rate and dimensions in `execution.json`, and copies the six Python source files
it uses into `executed-source/` with their relative layout. These are small code
copies, not copies of the raw EEG. The execution record includes the coordinator
PID and stage progress; `tools/replay.py status --out analysis-output` inspects
it without repeating an operation. Python, MNE and NumPy versions are recorded;
preserve the study environment as described in [Replay](REPLAY.md).

Each completed Hilbert band is saved before the next band starts. If a later
branch fails, those actual values remain with `status="incomplete"`, the error
and failed stage are recorded, and no final submission is written. A successful
output check is still required for a completed delivery. Failed outputs are not
silently resumed or replaced.

To execute the saved source in a new directory with the same input and environment:

```bash
python analysis-output/executed-source/tools/run_continuous_plan.py --plan analysis-output/APPROVED_PLAN.json --input recording.edf --output analysis-output-repeat
```

This repeats the numerical script without a model call. For in-memory input,
retain the original source or its study-approved synthetic generation script;
the metadata record is not a substitute for the input samples.

Use exactly one of these documented analysis routes:

| Route | Resolved plan entries |
| --- | --- |
| GFP | `operations`, `gfp_peaks`, `evidence_interval_s`; signal and time tolerances |
| Welch and band power | `operations`, `welch`, optional `band_power`; PSD/grid and requested result tolerances |
| Hilbert PLV or ordinary wPLI | `hilbert_bands`, requested `connectivity_summaries` / `hemisphere_contrasts`; matrix and requested result tolerances |

All routes need `analysis_channels`, `required_results`, `required_evidence`
and `numeric_tolerance`. Retain the task/plan text with these settings. An
unambiguous approved text can be transcribed into the machine-readable form;
missing scientific choices must not be supplied by a benchmark reference.

The ordered `operations` include the final crop when the exported buffer is
narrower than the processed recording. For example, a request to process
continuous data before taking an interval needs that crop after processing.
Each branch retains a `processing_steps` record with actual before/after sample
counts, rates and input-relative time origins. For GFP, `gfp_peaks` uses the
actual exported buffer's `time_origin_s`, `sfreq_hz`, windows and approved tie
rule. `evidence_interval_s` explicitly declares the saved interval. Peak windows
alone do not select which samples get saved.

The `band_power` entry specifies all four scientific inputs below:

| Entry | Meaning |
| --- | --- |
| `bands` | Named definitions, each containing `band: [low, high]` and boolean `upper_closed`; lower bound inclusive in this helper |
| `power_kind` | `absolute` or `relative` |
| `aggregation` | `mean_channel_power` for absolute power; `mean_channel_ratios` or `ratio_of_channel_means` for relative power |
| `total_band` | Explicit null for absolute power; an explicit integration definition for relative power |

`result_fields` maps named bands to requested numeric fields; `result_scale`
explicitly converts the native band values to the requested units (for example
a fraction to percent). Optional `dominant_result` names a requested dominant
band field; tied maxima require a resolved reporting rule. Optional
`classifications` contain the task's `band`, `result_field` and ordered `levels`,
each with `upper_exclusive` and `label`; null marks the final unbounded level.
These thresholds come from the approved task. They are not library defaults.
The runner saves `band_power_definition`, including the actual frequency bins
and values. A PSD-only request does not require a band-power definition.

To check the actual final message, including prose around its JSON, separately:

```bash
python tools/check_analysis_outputs.py --plan APPROVED_PLAN.json --workspace analysis-output --raw-input recording.edf --report analysis-output/FINAL_SUBMISSION.md --output analysis-output/DELIVERY_CHECK.json
```

Preserve `coverage`: structural success alone does not establish approved
processing. The runner's checks share AEA numerical helpers and are not an
independent certification or evidence of an agent-level reliability improvement.
The previously documented primitives remain available for other approved work.

## Preserve full report and image-review context

`tools/prepare_analysis_review.py` builds review context from passed direct
checks, saved explanations and the complete actual final submission. For a PSD
image, supply the review's explicit `--plot-sample-hz` points; the context retains
checked channel minima/maxima and the mean, with units. Attach the actual image
named by `image_path` when using the image prompt. Preparing these files makes
no model call and does not assign or replace a verdict. Keep frozen grades and
first deliveries separate from any future approved evaluation.

For a future grader, replace incomplete context assembly with the reusable
`semantic_review_prompt` and `image_review_prompt` functions from that tool.
Invoke the existing approved judge only after the direct checks pass; model,
budget, criteria and reporting scope still come from the approved evaluation.
Feed both saved and full final explanations to semantic review, and the actual
PNG plus verified plot data to image review. Required structured fields remain
the deterministic checker's responsibility.

For the public artifact self-check, the approved JSON plan supplies
`analysis_channels`, `required_results` and `required_evidence`. The latter two
are mappings from output names to descriptions. Optional `output_filename`
requests a file under `file_check/`. Output status is `computed`, `unavailable`
or `limited_inference`; results go in `result.json`, arrays in
`analysis_evidence.npz`, and actual channel names in its `channels` array.

```bash
python tools/check_analysis_outputs.py --plan APPROVED_PLAN.json --workspace analysis-output --output analysis-output/SELF_CHECK.json
```

The basic check covers structure, channel order, PSD axes, matrix ranges and
selected internal consistency. Original-input recomputation requires the
additional public settings described below; structure-only success does not
establish that processing matches the plan. Keep code traces, helper calls and
numerical verification separate. A missing self-check or unused template is a protocol observation,
not grounds to discard a run or replace its first submission.

## Execute the approved bounded processing

For channel/filter/export tasks, include the `Bounded preprocessing` section
and `skills/eeg-preprocess/scripts/continuous.py` in the selected packet.
This helper takes an explicit ordered `operations` list and the actual
`analysis_channels` subset. An empty list selects channels without filtering.
A general `fir` parameter table never adds a processing operation.

Each operation is an object with `operation` and `parameters`:

| Operation | Parameters supplied by the approved plan |
| --- | --- |
| `crop` | `start_s`, `stop_s`, for a half-open interval relative to the current buffer |
| `filter` | `l_freq`, `h_freq` and the resolved FIR options; an explicit null bound means a one-sided filter |
| `notch_filter` | `freqs` and the resolved notch options |
| `resample` | `sfreq` and the resolved resampling options |
| `average_reference` | `projection: false`, for direct reference application to already resolved scalp EEG channels |

These are execution settings, not suggested scientific defaults. Translate
only operations actually approved for this request; record unresolved choices.
An unambiguous approved text can supply this list; the absence of an
`operations` field is not a scientific reason to refuse that calculation.
Resolve conflicting structured/text instructions before the affected step.
Each call starts from an independent Raw copy. Use a fresh branch from the
unchanged input for each frequency band.

MNE EEG data are already in V. `data_in_volts` reads those values without
another conversion. `array_in_volts` is for an external array whose source
unit is explicitly documented. Keep calculation/evidence units separate from
display conversions.

## Check calculations and exported contents

`check_outputs` still accepts existing structural plans. For recomputation
from the original input, also supply these approved fields:

- `operations`: the explicit processing list above. For a multiband Hilbert
  task, use each `hilbert_bands` branch's explicit list instead; no common
  `operations` list is required when only the branches are being checked.
- `welch`: `segment_seconds`, `window`, `overlap_fraction`, `n_fft`, `remove_dc`
  and `average`. Canonical `n_fft: null` means the approved segment length;
  `remove_dc` is boolean. Existing `n_fft: "n_per_seg"` and
  `detrend: "constant"`/false settings map to these same values. Conflicting DC
  declarations raise, and `average` must be supplied in both forms.
- `numeric_tolerance`: declared `psd`, `signal`, `connectivity` or `result` objects for the
  quantities being checked, each with `rtol` and `atol`, plus
  `frequency_atol_hz` for PSD grids. Absolute tolerances have their quantity's
  units: PSD uses V²/Hz, signal uses V, and a derived percentage uses percentage
  points. Do not reuse a signal tolerance as a PSD tolerance.

For example, this computes and checks a PSD-only delivery using a prepared
plan. The plan must contain all numerical settings; the code adds none.

```python
from pathlib import Path
import json
import runpy
import mne

root = Path(AEA_ROOT)
preprocessing = runpy.run_path(str(root / "skills/eeg-preprocess/scripts/continuous.py"))
spectral = runpy.run_path(str(root / "skills/eeg-spectral/scripts/continuous.py"))
delivery = runpy.run_path(str(root / "tools/check_analysis_outputs.py"))
plan = json.loads(Path("APPROVED_PLAN.json").read_text())
with mne.io.read_raw(plan["input_path"], preload=False, verbose=False) as original:
    processed = preprocessing["prepare_continuous"](
        original, analysis_channels=plan["analysis_channels"], operations=plan["operations"])
    freqs, psd = spectral["welch_from_plan"](
        preprocessing["data_in_volts"](processed), processed.info["sfreq"], plan=plan["welch"])
    result = {"status": "computed", "explanation": "PSD of the approved channels and processing."}
    final_result = delivery["write_outputs"](result, {
        "channels": processed.ch_names, "freqs": freqs, "psd": psd}, output_directory)
    check = delivery["check_outputs"](
        plan, output_directory, raw_input=original, final_result=final_result)
Path(output_directory, "SELF_CHECK.json").write_text(json.dumps(check, indent=2))
print(json.dumps(final_result))
```

For a task requesting additional metrics, compute them from these same arrays
and include them in `result` before calling `write_outputs`. Its returned JSON
object is also the structured final report, avoiding manual number copying.
Object arrays are rejected except string channel labels, which are saved as
ordinary string arrays readable without pickle.
Explicitly labelled equivalent evidence is converted before checking:
`signal_unit: "uV"`, `psd_unit: "uV^2/Hz"` and `variance_unit: "uV^2"` are
supported; absent labels mean the declared SI convention. A derived percentage
stored as a fraction can declare its result field's `_unit` as `"fraction"`.

For approved maximum-bin personalized alpha, `personalized_alpha_power`
requires `search_band`, `offsets`, `total_band`, `center_mode`, `upper_closed`
and `total_upper_closed`. Specify `mean_peak` for a common band centered on
the mean channel peak, or `per_channel_peak` for separately centered bands.
The function returns individual peaks, actual centers and per-channel ratios.
An optional `personalized_alpha` plan object can contain those settings plus
`mean_peak_result` and `mean_percent_result`, naming the result fields that
should contain the mean peak and mean channel relative power percentage.
The public checker then recomputes those two quantities from the saved PSD.

For EDF output, `export_checked_edf` takes the prepared Raw, output path,
approved `analysis_channels`, `sfreq` and `n_samples`. It selects that subset
and reopens the written file. The public checker also reopens an EDF; without
`raw_input`, declare `output_sfreq_hz` and `output_n_samples` to check the rate
and sample count as well as channel identities.

`coverage` reports whether original-input processing and personalized power
were actually recomputed. These checks can detect extra processing, repeated
unit conversion or output mismatches. They do not independently certify the
chosen scientific method, unimplemented metrics, interpretations or all files.

## Use a bounded request without a full study directory

When the user has already resolved the scientific choices, their explicit
request or approved JSON supplies the plan for that calculation. Save it with
the result. Continuous Pearson/Hilbert connectivity and segment SampEn do not
require an epoch directory, an ICA run or a new study checkbox. For a full
study, keep the study plan and the prerequisites for its selected methods.

For Raw-input SampEn, `sample_entropy_raw` in the complexity helper accepts
the approved `analysis_channels`, `operations`, `m`, `r_fraction` and `closed`.
It returns the actual SI-unit segment, per-channel values, match details and
`metadata`. Retain the approved aggregation/undefined-value policy.

For population-SD GFP, `population_gfp_raw` in the preprocessing helper takes
the approved operations including the half-open crop, explicit `time_origin_s`,
absolute `windows_s`, and `tie_rule`. It returns exactly the selected samples,
their times and peak times. The buffer origin is an approved coordinate value;
the helper does not guess the absolute recording time from a cropped object.

## Build report metadata from computed objects

`recording_metadata` reads actual channels, rate and sample count from the
selected Raw. Optional ROI labels and memberships come from the approved
plan and are checked against that selection, not inferred from signal values.
`summarize_undirected_connectivity` reads the actual matrix and labels to
produce its distinct-pair count, mean, and requested top pairs.

Include these values as `analysis_metadata` in the result, and construct the
explanation from those same values. The public checker compares supplied
channel/pair counts with the evidence; with the original-input path it also
checks the actual sample count/rate and population GFP values. It cannot
guarantee that arbitrary prose repeats the values correctly.

For this result interface, `unavailable` means the requested source/channel/
interval is missing. `limited_inference` means processing was possible but
the available processed signal cannot support the requested inference; retain
its processing evidence. An above-Nyquist band after resampling or a removed
band cannot be recovered by relabelling residual power. Apply these meanings
to the approved question, without changing its scientific choices. See the
preprocessing reference's `Result status and inference limits` section.

## Check derived numbers against the saved arrays

Enable only the checks that match the approved quantity and conventions.
The checker does not choose scientific rules by recognizing a result field name.

For a distinct-undirected-pair mean and ranked pair identities, add:

```json
{
  "connectivity_summaries": [{
    "matrix_key": "plv", "pair_scope": "undirected_distinct",
    "ranking": "value_desc_label_asc", "top_k": 3,
    "mean_result": "global_mean_plv", "pairs_result": "top3_plv_pairs"
  }]
}
```

`mean_result` and `pairs_result` can each be omitted when not requested. Set the
explicit `top_k` to zero for a mean-only check. Add the approved numeric
`numeric_tolerance.result` (`rtol`, `atol`) for a mean or hemisphere contrast.
Mean excludes self/duplicate pairs; ranking uses descending signed values with
alphabetical label ties. The two labels within an undirected pair may reverse;
the ranking among pairs must agree. Plain two-label lists and objects containing
`channel_pair` are supported. Undefined edges need the approved missing-value
policy instead of silent omission.

For an approved left-minus-right difference of within-hemisphere pair means,
add `hemisphere_contrasts`, a list of objects with `matrix_key`,
`homologous_pairs` (actual left/right labels in that order) and `result_field`.
No anatomical identity or side assignment is inferred from channel names.

For population-GFP peaks, add `gfp_peaks` with `sfreq_hz`, `time_origin_s`,
`windows_s`, `tie_rule: "first"` and a `result_fields` list matching the windows.
Use this tie rule only when approved; the helper supports no silent alternative.
Also supply `numeric_tolerance.time_atol_s`, in seconds. The checker compares
reported times and optional `gfp_times` with the saved GFP and these explicit
coordinates. The Raw path additionally checks GFP values and the actual rate.

The `connectivity_summary_recomputed`, `hemisphere_contrast_recomputed` and
`gfp_peaks_recomputed` coverage fields distinguish these optional checks from
structure-only success. Array-to-report agreement does not establish that a
matrix was computed correctly from the original signal or certify free prose.
For complete multiband execution, see the connectivity reference's
`Complete multiband Hilbert calculation` example. It starts every branch from
the unchanged recording and preserves each branch's explicit operations.
Passing `raw_input` with that `hilbert_bands` plan and an approved
`numeric_tolerance.connectivity` reconstructs and compares each saved matrix;
`coverage.hilbert_matrices_recomputed` lists the bands actually checked.
The returned `report_values_compared` coverage field records whether a supplied
final JSON object was compared with the saved numeric and categorical values.
Neither check certifies free-text interpretations or detects a disagreement
between an approved prose instruction and an incorrectly transcribed plan.
