## Bounded preprocessing

For a bounded approved calculation, preserve its actual channels, interval,
filter settings and operation order. Load only the requested segment when the
approved pipeline starts with that selection. Otherwise process the required
continuous buffer before selecting the output segment. A full-study ERP pipeline is not a request to
add notch filtering, ICA, resampling or artifact rejection to every calculation.

A table of FIR parameters describes how to run an approved filter; its presence
does not authorize one. A PSD integration band is not a bandpass request.
Use an explicit ordered `operations` list; `[]` means select channels only.
If the approved procedure is unambiguous prose, transcribe its steps, bounds
and order into this list and retain the source text. A missing JSON key does
not cancel a step explicitly requested in that text. If structured settings
and the approved text conflict, flag the affected calculation for resolution;
do not silently choose one. Do not infer extra processing from available options.

Keep processing extent and exported extent distinct. If the approved request
filters continuous data and then asks for 30–60 s, put that crop after the
filter/resampling operations. Windows used to find peaks do not crop a saved
array. A shorter initial crop changes filter boundaries. Other requests may
explicitly crop before filtering; retain that different order.

Use the [bounded processing helpers](../scripts/continuous.py):

```python
from pathlib import Path
import runpy
preprocessing = runpy.run_path(str(Path(AEA_ROOT) / "skills/eeg-preprocess/scripts/continuous.py"))
processed = preprocessing["prepare_continuous"](
    original_raw, analysis_channels=approved_public_plan["analysis_channels"],
    operations=approved_public_plan["operations"])
data_in_volts = preprocessing["data_in_volts"](processed)
```

Pass an empty list as `operation_log=` to collect each actually applied step's
parameters, before/after sample counts, rates and input-relative time origins.
Retain this record with the output metadata. It records execution; it does not
resolve an ambiguous research plan. For supported complete MNE calculations,
use the [continuous-plan runner](../../../docs/PRELOADED_SKILLS.md#execute-and-check-a-complete-continuous-plan)
to connect execution, saving and source-data checks without rewriting the steps.

Each operation has `operation` and `parameters`: supported operations are
`crop` (`start_s`, `stop_s`), `filter` (explicit `l_freq`, `h_freq` and approved
FIR options), `notch_filter` (`freqs` and approved options), `resample`
(`sfreq` and approved options), and direct `average_reference`
(`projection: false`). Resolve any other workflow in the full procedure.
Channel identities must already be established; select `analysis_channels`,
which can be a subset of all eligible scalp EEG channels.

MNE readers expose EEG in V. Do not multiply `raw.get_data()` by `1e-6` again.
For an external array documented in uV, use `array_in_volts` with that explicit
source unit once. Convert to uV for display only; keep calculation arrays in V.
For multiple frequency bands, start each branch from the same unchanged input.
`prepare_continuous` copies its input so one band cannot overwrite the next.
The same applies after a failed notebook cell: earlier MNE mutations survive
later exceptions. Retry from the unchanged original through a new copy, rather
than filtering or resampling the partially processed object again.

Use half-open sample intervals when the plan requests them. If sampling rate
is sfreq, the samples in [start, stop) have indices round(start*sfreq) through
round(stop*sfreq)-1. MNE `crop` usually includes its final sample; set the last
sample time explicitly or use an exclusive endpoint. Record the actual count.
Filtering before cropping and filtering an already cropped segment can differ
at its boundaries; retain the approved order.
`Raw.get_data(start=..., stop=...)` uses an exclusive sample stop. Its `tmax`
interface also uses an exclusive stop; do not transfer the final-sample time
used for inclusive `Raw.crop` into that interface.
See the [MNE Raw API](https://mne.tools/1.8/generated/mne.io.Raw.html#mne.io.Raw.get_data).

Pass approved FIR options explicitly to `raw.filter` or `raw.notch_filter`.
Read the task's actual notch frequency rather than inferring it from a power
evaluation band. MNE resampling applies anti-alias filtering; simple slicing
does not. Preserve full channel identities and their declared row order.

Before average reference or ranking, apply the channel checker on the actual
data used, using independently documented channel roles and the approved set.
Do not include EOG, ECG, standalone mastoids or unresolved auxiliaries. An EEG
derivation with a mastoid reference suffix remains a scalp derivation.

For requests restricted to processed-data interpretation, read
[Result status and inference limits](#result-status-and-inference-limits).
A missing source and a supported calculation with limited inference require
different reports; a code-interface error is neither scientific conclusion.

For EDF export, save in the requested directory with the exact filename,
channel labels, sampling rate and sample count. EDF quantization is separate
from the analysis's signal units; preserve the floating point array as evidence
when the approved output contract requests it.

Use `export_checked_edf(processed, path, analysis_channels=..., sfreq=...,
n_samples=...)` with the approved output requirements. It selects that subset,
writes the EDF, then reopens it to check actual labels, rate and sample count.
Do not replace an analysis subset with every scalp channel or add label prefixes.

## Population global field power

For an approved population-SD GFP definition, compute `data.std(axis=0, ddof=0)`
over the declared channels. Other GFP definitions and ddof values differ.
Use the approved reference, resampling, filtering and cropping order. Report
peak times as absolute recording times when requested, not window-relative
indices. For a half-open window, select its actual sample indices and use the
first maximum only when that tie convention is approved. Keep GFP in V unless
an explicitly labelled conversion is requested.

For a Raw input, use `population_gfp_raw` from the bounded processing helpers.
Supply the approved operations including the half-open crop, the recording
time of the resulting buffer's first sample, absolute windows, and tie rule:

```python
from pathlib import Path
import runpy
preprocessing = runpy.run_path(str(Path(AEA_ROOT) / "skills/eeg-preprocess/scripts/continuous.py"))
computed = preprocessing["population_gfp_raw"](
    original_raw, analysis_channels=approved_channels,
    operations=approved_operations, time_origin_s=approved_buffer_origin_s,
    windows_s=approved_absolute_windows_s, tie_rule="first")
evidence = {"channels": computed["metadata"]["channels"],
            "gfp": computed["gfp"], "gfp_times": computed["times_s"]}
analysis_metadata = computed["metadata"]
peak_times = computed["peak_times_s"]
```

Read `n_samples`, `sfreq_hz`, channel labels and counts from this metadata.
At 100 Hz an approved [30,60) buffer has 3000 samples; subtracting a tiny
epsilon from MNE's inclusive endpoint is not a reliable sample selection.
Use integer sample endpoints. `tie_rule="first"` is the helper's spelling for
an approved earliest maximum; do not pass a prose description as this argument.
It does not add a reference or change the population-SD rule. Cropping earlier
to save work, or swapping filtering and resampling, changes the requested pipeline.

For a public peak-time consistency check, supply `gfp_peaks` with explicit
`sfreq_hz`, `time_origin_s`, `windows_s`, `tie_rule` and matching `result_fields`,
plus `numeric_tolerance.time_atol_s`. The checker uses the same selected GFP
samples to verify both the reported absolute peak times and saved `gfp_times`.
Passing `raw_input` additionally checks the GFP against the approved processed
signal. The saved-array check alone does not prove that upstream processing.
Also supply `evidence_interval_s` for the approved saved interval, independently
of the peak windows. The checker then checks its sample count and time origin;
a 0–60 s array is not a 30–60 s delivery even when its peak times happen to agree.

## Result status and inference limits

For a workflow using the AEA result interface, interpret its three statuses
according to the approved request:

| Status | Meaning | What to retain |
| --- | --- | --- |
| `computed` | The requested quantity is supported by the available input and was computed. | The actual values, evidence and factual explanation. |
| `unavailable` | The requested input channel, interval or source is missing, so the approved computation cannot be performed. | The missing-input reason; no invented substitute or numerical result. |
| `limited_inference` | The source and approved processing are available, but the processed signal cannot support the requested inference. | The processing evidence and supported calculations, plus the limitation; no unsupported state conclusion. |

For example, a requested band above the resampled Nyquist frequency is an
inference limitation of the processed data, not a missing source recording.
Likewise, residual power after removing a band does not recover that band's
original activity. A filter alone does not make every analysis inference-limited;
judge the requested quantity and question under the approved plan. If the task
uses another status vocabulary, preserve that interface instead.
Describing a residual line-noise peak after notch filtering can be a supported
calculation; it does not estimate the original unfiltered peak. Missing helper
keys or a code exception are execution problems, not evidence of missing data
or a scientific inference limitation. Retain and report that failure honestly.
This classification does not authorize changing the analysis or substituting
an unprocessed signal for a request restricted to processed data.

## Public artifact self-check

For a full delivery, check the actual final report's JSON as well as the saved
file. `report_explanation_present` must pass; prose outside a JSON object does
not supply a required field inside it. `write_outputs` returns the complete
object to print, including its explanation. Never substitute an empty channel
list when a local variable is missing: use the actual selected object's metadata.

Write the actual results to `result.json` and contracted arrays to
`analysis_evidence.npz`. Use actual full channel names in row order, signals
in V and PSD in V²/Hz, preserving a row for a single channel. Include a brief
factual explanation in the saved result and final report; their numeric and
categorical fields must agree. An unavailable input must be reported without
inventing a replacement electrode, time interval or numerical result.

The following minimal call checks public artifact structure
and internal consistency only, without access to private numerical references.
It cannot replace the external scientific/numerical checks.

```python
from pathlib import Path
import json, runpy
check = runpy.run_path(str(Path(AEA_ROOT) / "tools/check_analysis_outputs.py"))["check_outputs"]
self_check = check(approved_public_plan, output_directory)
Path(output_directory, "SELF_CHECK.json").write_text(json.dumps(self_check, indent=2))
print(self_check)
```

Retain a failed self-check and any corrections. Save code, procedure/helper
paths used and explicit adaptations to the approved plan. Do not describe a
helper as executed merely because it appeared in the input packet.

For stronger public checks, pass `raw_input=original_raw` with the explicit
approved `operations`, `welch` and `numeric_tolerance` settings. This recomputes
the declared processing and PSD from the unchanged input, detecting extra
filtering or repeated unit scaling. It uses no private reference answers.
`coverage` states which checks actually ran; structure-only success does not
establish that processing followed the plan.
For PSD recomputation, `numeric_tolerance` needs `psd` (`rtol`, `atol`) and
`frequency_atol_hz`; signal/GFP comparison needs `signal` (`rtol`, `atol`).
Transfer these values from the approved tolerances without changing units.
The [complete PSD example](../../../docs/PRELOADED_SKILLS.md#check-calculations-and-exported-contents)
shows the required plan fields and connects saving, recomputation and reporting.

Use `write_outputs(result, evidence, output_directory)` from the same tool to
save full-precision values and ordinary numeric/string arrays. Include its
returned JSON object in the final report instead of manually copying numbers.
Pass that object as `final_result=` when checking numeric/categorical agreement.
Print `json.dumps(final_result)` and include that actual JSON in a requested
machine-readable final answer; placeholder expressions such as `{value}` are
not computed JSON numbers. Construct explanations from the same actual metadata
and use the saved explanation in the final answer to avoid stale channel counts.
Save the requested result file even when the supported outcome is a limitation.
EDF checks reopen the actual file; provide `output_sfreq_hz` and
`output_n_samples` when the original input is not available for recomputation.
