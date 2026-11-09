# Execute an approved ERP plan

This route supports the explicit public ERP plan schema with `request_kind`,
`dataset`, `analysis`, `derivatives`, `required_results` and `required_evidence`.
An approved plan supplies processing order, conditions, epoch/baseline, ROI,
window, eligibility and any group tests. This route introduces no new defaults.

For the four explicit ERP CORE mean-amplitude contrasts below, execute the
complete plan from a saved entry point. Supply the actual paths and an internal
result-to-evidence tolerance in microvolts.

```bash
python tools/run_erp_plan.py --plan APPROVED_PLAN.json --dataset-root DATASET_ROOT --workspace NEW_RUN --atol-uv 1e-9
```

The entry checks actual events and dataset version, executes the plan's ordered
MNE preprocessing, saves each participant's counts, channel Info and difference
waves, then measures the named ROI. Group tests read these saved arrays. Only
the requested t-test and full-channel, window-restricted cluster test run. No
ICA, trial rejection, extra statistics or recipe parameters are added. This
bounded entry does not implement other datasets, peak measures or area latency.
Those tasks continue to use their matching skill procedures.

`execution.json` records actual arguments, dimensions, steps, PID, environment
and failed attempts. `executed-source` retains the program and helpers that ran.
Completed results, evidence and derivatives pass the public delivery check
before `FINAL_SUBMISSION.md` is created. This internal check does not replace an
independent raw-input comparison or the external BIDS validator.

After a timeout, inspect the recorded process and saved state first. If the
process has stopped, repeat the same command with `--resume`. It reuses saved
participant states and completed group statistics for that exact plan and
source. It preserves failed attempts and refuses to overwrite a completed final
delivery. Use a new directory for a changed source or scientific plan.

When the plan leaves the cluster seed unspecified, the entry retains MNE's
unspecified seed and saves the actual NumPy random state in
`cluster_rng_before.json`. A new-directory replay can pass that file with
`--replay-rng` in the same numerical environment. A declared seed in a plan is
passed unchanged. This records execution without inventing a scientific seed.

Prepare a task-matching resource packet from the checkout root.

```bash
python tools/prepare_erp_packet.py --plan projects/my-study/APPROVED_PLAN.json --output projects/my-study/ERP_PACKET.md --receipt projects/my-study/ERP_PACKET_RECEIPT.json
```

Single-subject packets contain the approved execution section and callable
helpers. Group packets add the participant-level group procedure. ERP CORE's
error-minus-correct contrast adds its documented response decoder. Whole general
manuals and unrelated recipe contrasts are not included. The receipt records
the actual selected sections and files. No private reference outputs are read.
This is a new resource configuration, not a modification of an old frozen run.

For ERP CORE's explicit rare-minus-frequent, faces-minus-cars,
unrelated-minus-related and error-minus-correct plans, execute the metadata
check before EEG processing. Replace these paths with the actual task paths.

```bash
python tools/erp_execution.py preflight --plan APPROVED_PLAN.json --dataset-root DATASET_ROOT --workspace NEW_RUN
```

This reads the requested task sidecar and real event rows, locates each
recording and saves `ERP_INPUTS.json` with condition counts and the dataset
version from a `version` line in CHANGES. It does not load EEG samples or
determine retained-epoch eligibility. The counts identify readable facts that
can be checked without another scientific approval. Unsupported task/contrast
pairs and genuinely missing inputs produce a specific error. The callable
`erp_core_conditions` also returns row identities, onset seconds and conditions
for an analysis script to convert on its approved sample grid.

The measurement functions can be used in that saved script as follows.

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(aea_checkout) / 'skills/eeg-epoch/scripts'))
from erp import mean_roi_amplitude, save_erp_outputs
from erp_core_events import erp_core_ern_events

# Only for ERP CORE's documented ERN error-minus-correct response mapping.
# rows are read from that recording's events.tsv. raw has been processed to the
# approved output rate. The sidecar is retained with the analysis provenance.
events, mapping_record = erp_core_ern_events(
    rows, sfreq=raw.info['sfreq'], first_samp=raw.first_samp, n_times=raw.n_times)

# Create epochs from events with the actual approved MNE Epochs arguments.
# Pass that existing Epochs object, its condition names and approved choices.
measured = mean_roi_amplitude(epochs, plus=plus_condition, minus=minus_condition,
                              roi=approved_roi, window_s=approved_window_s)
result.update({k: measured[k] for k in
               ['roi_amplitude_uv', 'n_trials_plus', 'n_trials_minus']})
evidence = {k: measured[k] for k in
            ['times_s', 'roi_difference_uv', 'amplitude_unit', 'sfreq_hz']}
save_erp_outputs(new_run_directory, result=result, evidence=evidence)
```

The snippet uses study variables from your saved script. It does not create an
analysis plan or apply preprocessing. Use the approved condition mapping and
trial threshold; the event decoder is not a general rule for every dataset.

For a group task, save each processed participant before group statistics or
diagnostics. Add the checkout's `tools` directory to the Python import path.

```python
from erp_execution import save_subject_state, load_group_state
save_subject_state(state_directory, subject, epochs, plan=plan,
                   plus=plus_condition, minus=minus_condition)
state = load_group_state(state_directory, plan=plan)
# Use these named arrays with the approved statistical tests.
result.update(state['result_fields'])
evidence = state['evidence']
info = state['info']
cluster_data_uv = state['cluster_data_uv']
```

State retains actual channel Info, time points, condition counts, channel-resolved
difference waves and the exact supplied plan. Reading it in a fresh Python
process does not rerun preprocessing. The loader selects ROI channels by name,
applies the plan's trial minima and returns cluster input ordered as participants
by approved-window samples by channels. It rejects changed plans and mismatched
axes. Existing participant files are preserved. It performs no t-test, cluster
test or scientific parameter selection. The caller still executes those tests.

The measurement helper reports missing ROI channels with the actual available
names and rejects non-EEG ROI types before interpreting values as EEG uV. It
uses the explicitly requested ROI channels, including a channel still marked
bad when the approved ROI includes it. Resolve exclusion in the approved plan;
the helper does not silently remove or interpolate it. A measurement window
extending outside the actual epoch is rejected instead of shortened. Normal
rounding of nominal epoch bounds by up to half a sample remains allowed. These
checks do not add preprocessing or change the requested ROI or window.

After writing actual derivative files, run the public self-check from the same
checkout. Supply an explicit tolerance for **internal arithmetic agreement**:

```bash
python tools/check_erp_outputs.py --plan projects/my-study/APPROVED_PLAN.json --workspace projects/my-study/new-run --atol-uv 1e-9
```

The example tolerance permits floating-point rounding when comparing a saved
mean with its own evidence arrays. It is not a scientific acceptance tolerance
against reference EEG results. Choose the internal precision for the actual
serialization used and record it. A failed check returns a nonzero exit status,
writes SELF_CHECK.json and leaves computed artifacts untouched. A revised run
uses a new directory. Without `--atol-uv`, the coverage reports arithmetic as
not run. Unavailable external checks are also recorded as not run.

For final delivery, use the callable submission gate with an explicit internal
arithmetic tolerance after all actual outputs have been written.

```bash
python tools/erp_execution.py finalize --plan APPROVED_PLAN.json --workspace NEW_RUN --atol-uv 1e-9
```

It retains numbered reports in `delivery-checks`. A failed check returns a
nonzero status and creates no final submission. A successful check writes
`FINAL_SUBMISSION.md` directly from the saved `result.json`. It never fills in
missing answers, changes the scientific plan or overwrites a prior final file.
ERP CORE delivery also checks the saved input check and actual CHANGES version.
Computed numeric fields and significance flags must have their declared types.
An `ineligible` result needs actual retained counts below an approved minimum,
and an empty participant directory is not a derivative output.

This gate is executable support for the client to call. It does not intercept a
client that returns early without calling it. Changing an evaluation agent's
termination loop is a separate execution change and has not been made here.

The arithmetic check requires `amplitude_unit='uV'` and the actual `sfreq_hz`
in the evidence. It checks the MNE integer-sample epoch grid, waveform shape,
finite values and result means. Group evidence additionally aligns participant
identities, their amplitudes, and the group mean. A unit declaration alone
cannot prove that raw V were converted correctly: both a wrong result and a
consistently scaled wrong waveform can agree internally. This tool does not
verify raw data, event classification, group tests or BIDS conformance.

For already approved execution, read available sidecars and repair programming
errors without stopping for renewed approval. Keep independent approved work
moving when a genuinely missing scientific choice blocks one step. Save actual
computed artifacts before further diagnostics and preserve failed checks. A
missing variable is not evidence of kernel-state loss. Follow the researcher's
decision boundary for scientific changes, model settings and new experiments.
