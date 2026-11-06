## Approved ERP execution

Use this route for an explicit ERP plan with resolved input, operation order,
conditions, epoch, baseline, ROI and measurement window. The plan supplies the
settings. Apply only its filtering, referencing, resampling and rejection steps.
Do not add ICA, change a contrast or import a recipe default to fill an already
resolved field. Use the software/data environment actually available.

Read the recording's task-specific events sidecar before constructing conditions.
The root dataset Name or an empty stim_file column alone does not establish that
a task is unavailable. Walk the actual task/session tree and inspect its sidecar.
Keep response locking distinct from stimulus locking and retain event identity.

Use the approved source of event positions. If the plan says onset seconds at
the current sampling rate, convert those seconds to that grid. A native sample
column is on its declared original grid and is not expected to equal resampled
sample indices. Include raw.first_samp only when converting to MNE event indices.

Create epochs with the approved MNE Epochs arguments. Use **epochs.times** for
all baseline/measurement checks and save it with the waveform. MNE rounds epoch
bounds to integer sample offsets. At 256 Hz, -0.2 s becomes -51/256 s, or
-0.19921875 s. This normal representation does not require a new scientific
choice. Do not replace it with arange(n)/sfreq + the nominal tmin.

The callable template in `scripts/erp.py` provides `epoch_sample_times` for grid
checks and `mean_roi_amplitude` for plus-minus measurement. Supply the actual
epochs, condition labels, approved ROI and inclusive window. Input MNE EEG is V;
the returned waveform and amplitude are uV. It does not preprocess or alter data.
Retain the helper's n_trials_plus/minus and apply the plan's eligibility rule.
For an ineligible subject, disclose its actual counts and continue other approved
subjects; do not invent an amplitude or exclude subjects without recording why.

Save actual computed result.json and analysis_evidence.npz before additional
diagnostics, using `save_erp_outputs`. Put only JSON fields in result, arrays in
evidence. Evidence includes times_s, the ROI waveform, amplitude_unit='uV', and
the actual sfreq_hz. Record actual channels, settings and event mapping separately
with the saved analysis. A structurally valid file is not numerical validation.

During already approved execution, inspect readable metadata and fix programming
errors as ordinary implementation work. A NameError names a missing variable;
check the actual variable names and saved arrays. It does not establish a kernel
restart. Continue the approved task after fixing such an error. Do not stop with
an incomplete final answer merely because another executable check remains.

Only an unresolved scientific choice or actual missing input/dependency blocks
the affected step. State the specific blocker, preserve computed artifacts and
continue independent approved work. Never fabricate missing choices or results.
An external grader/validator being absent from the agent environment does not
prevent computing the approved ERP or writing derivatives for that later check.
Report that external check as not run, with no claim of conformance.

Use tools/check_erp_outputs.py with an explicit internal arithmetic tolerance
when the plan and output schema match it. It checks declared units, actual grid,
required values and result-to-evidence arithmetic. State the fields and limits it
checked; it cannot independently establish that raw data or events were correct.
Fix a flagged implementation issue using the actual source arrays. Preserve old
artifacts and checks in their run directory; corrections use a new directory.

## ERP CORE response coding

For the ERP CORE ERN **error-minus-correct** contrast, task-ERN_events.json
defines three response digits: response direction, flanker compatibility, target
direction. Error compares the first and third digits, not the middle digit.
The template `erp_core_ern_events` in `scripts/erp_core_events.py` reads those response rows and the approved
output sfreq, raw.first_samp and raw.n_times. It retains responses without a
preceding stimulus because their own code contains the target direction.

Read and retain the task sidecar as provenance. Use this helper only when that
sidecar and contrast apply. Other datasets or compatibility contrasts need their
own documented mapping. The helper contains no subject answers or trial targets.
After epoching, use actual retained trial counts rather than pre-epoch counts.

## Approved ERP group statistics

Use this section only for participant-level group tasks. Preserve each eligible
participant's channel-resolved plus-minus ERP, actual times and ROI mean before
forming the grand average. Save subject identities in a matching fixed order.
Eligibility comes from the approved trial rule, not effect direction.

Run the approved participant-level t-test on those participant amplitudes. For
an approved spatio-temporal cluster test, keep participants x window samples x
channels; retain the channel dimension needed by the planned adjacency. Apply
the plan's sidedness, forming threshold, permutation count and seed. Keep the
forming threshold separate from final significance. Do not select a new test or
discard participants to complete a helper's preferred route.

Write actual effect direction, t statistic/p, cluster p and their significance
flags consistently to result.json and the final report. Preserve participant
amplitudes, grand ROI waveform, times and subject ordering in the evidence.
The public arithmetic self-check does not recompute the t-test or permutation
null. Record those computations and their limits separately.
