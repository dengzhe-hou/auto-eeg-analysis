AEA complete approved ERP entry
This plan is supported by the saved one-call runner. Execute it instead of rebuilding the pipeline in notebook cells:
python /workspace/aea/tools/run_erp_plan.py --plan /workspace/PUBLIC_CONTRACT.json --dataset-root /input/erp_core_bids --workspace /workspace --atol-uv 1e-9
It checks actual event metadata, executes the supplied preprocessing in order, saves each participant, uses the named ROI, runs only the requested group tests, writes actual evidence and derivative files, and creates FINAL_SUBMISSION.md only after the delivery check passes. Read the printed result and return the complete contents of FINAL_SUBMISSION.md. A normal integer-sample epoch grid or a check not yet run is not a reason to stop. If execution fails, inspect execution.json and the saved participant-state files. After a timeout check its recorded PID before retrying. If the old process has stopped, the same command with --resume reuses saved participant states without preprocessing them again. Do not change the approved scientific settings or overwrite a completed delivery. The source is available in the checkout for inspection, not preloaded here. The lower-level interfaces below remain available when diagnosing a specific failure.

AEA preloaded procedures and executable templates

Use these selected procedures for the supplied approved task. Scientific settings come from that task and its approved plan, not an example. Record procedures/helpers actually used and any explicit adaptations. Complete input delivery is distinct from correct execution. Run the public artifact self-check before final delivery; external numerical verification remains separate.

AEA procedure: skills/eeg-epoch/references/approved-erp.md

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

AEA procedure: skills/eeg-epoch/scripts/erp.py

"""Integer-sample grids and ROI means for an explicitly approved ERP plan.

No filters, reference, baseline, rejection or scientific measurement window is
selected here. Dataset-specific event coding is loaded separately when needed.
"""
from pathlib import Path
import json

import numpy as np


def epoch_sample_times(*, epoch_s, sfreq):
    """MNE-style integer-sample epoch grid; t=0 remains on the sample grid."""
    if not np.isfinite(sfreq) or sfreq <= 0 or len(epoch_s) != 2:
        raise ValueError("Supply a positive sfreq and two epoch bounds")
    if not np.isfinite(epoch_s).all() or epoch_s[0] > epoch_s[1]:
        raise ValueError("Epoch bounds must be finite and increasing")
    first, last = [int(round(float(t) * sfreq)) for t in epoch_s]
    return np.arange(first, last + 1, dtype=float) / sfreq


def mean_roi_amplitude(epochs, *, plus, minus, roi, window_s):
    """Measure plus-minus using actual Epochs.times and the supplied ROI/window.

    MNE EEG input is V. Output waveform and mean are uV. The input epochs are
    already processed according to the plan and are not modified here.
    """
    if len(window_s) != 2 or not np.isfinite(window_s).all() or window_s[0] > window_s[1]:
        raise ValueError("Supply an increasing finite measurement window")
    if not roi or len(set(roi)) != len(roi):
        raise ValueError("Supply distinct ROI channel names")
    missing = [name for name in roi if name not in epochs.ch_names]
    if missing:
        raise ValueError(f"ROI channels absent from actual epochs: {missing}; available: {epochs.ch_names}")
    types = epochs.get_channel_types(picks=roi)
    if any(kind != 'eeg' for kind in types):
        raise ValueError(f"ERP uV measurement requires EEG ROI channels; actual types: {dict(zip(roi, types))}")
    times = epochs.times.copy()
    # Nominal epoch endpoints may differ by up to half a sample after rounding.
    half_sample = .5 / float(epochs.info['sfreq'])
    if window_s[0] < times[0] - half_sample or window_s[1] > times[-1] + half_sample:
        raise ValueError(f"Approved window {window_s} exceeds actual epoch range "
                         f"[{times[0]}, {times[-1]}] at {epochs.info['sfreq']} Hz")
    mask = (times >= window_s[0]) & (times <= window_s[1])
    if not mask.any():
        raise ValueError("No actual epoch samples lie in the approved window")
    p, m = epochs[plus], epochs[minus]
    if not len(p) or not len(m):
        raise ValueError("Both planned conditions must have retained trials")
    waveform = (p.average(picks=roi).data - m.average(picks=roi).data).mean(axis=0) * 1e6
    if not np.isfinite(waveform).all():
        raise ValueError("The actual ROI difference contains non-finite samples")
    return {
        'roi_amplitude_uv': float(waveform[mask].mean()),
        'n_trials_plus': len(p), 'n_trials_minus': len(m),
        'times_s': times, 'roi_difference_uv': waveform,
        'amplitude_unit': np.asarray('uV'), 'sfreq_hz': np.asarray(epochs.info['sfreq']),
    }


def save_erp_outputs(workspace, *, result, evidence):
    """Save actual computed artifacts before optional diagnostics, once per run.

    A later failed check does not delete/rewrite these artifacts. For a revision
    use a new run directory and preserve the original execution evidence.
    """
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    paths = [workspace / 'result.json', workspace / 'analysis_evidence.npz']
    if any(path.exists() for path in paths):
        raise FileExistsError("ERP outputs already exist; choose a new run directory")
    serialized = json.dumps(result, indent=2, allow_nan=False) + '\n'
    np.savez(paths[1], **evidence)
    paths[0].write_text(serialized, encoding='utf-8')


AEA procedure: skills/eeg-epoch/references/approved-erp.md

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

AEA procedure: tools/check_erp_outputs.py

"""Structural and optional arithmetic self-check of ERP outputs, without references.

Usage: python tools/check_erp_outputs.py --plan /workspace/PUBLIC_CONTRACT.json --workspace /workspace
Supply --atol-uv for result-to-evidence arithmetic and the actual epoch grid.
This never verifies the raw EEG, event mapping, t-test or permutation test.
Writes SELF_CHECK.json; it does not modify result.json or evidence arrays.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/eeg-epoch/scripts'))
from erp import epoch_sample_times


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def arithmetic_checks(plan, result, arrays, *, atol_uv):
    """Check arithmetic in delivered artifacts, not agreement with a private answer."""
    problems = []
    if not finite_number(atol_uv) or atol_uv < 0:
        raise ValueError('Supply a finite, nonnegative internal arithmetic tolerance in uV')
    try:
        unit = arrays['amplitude_unit'].item()
        sfreq = arrays['sfreq_hz'].item()
        times = np.asarray(arrays['times_s'], dtype=float)
        if unit != 'uV':
            problems.append('evidence amplitude_unit must declare uV')
        expected = epoch_sample_times(epoch_s=plan['analysis']['epoch_s'], sfreq=plan['analysis']['resample_hz'])
        if sfreq != plan['analysis']['resample_hz']:
            problems.append('evidence sfreq_hz differs from the approved output rate')
        if times.shape != expected.shape or not np.allclose(times, expected, rtol=0, atol=1e-12):
            problems.append('evidence times_s differs from the approved integer-sample epoch grid')
        group = plan['request_kind'] == 'group'
        name = 'grand_roi_difference_uv' if group else 'roi_difference_uv'
        wave = np.asarray(arrays[name], dtype=float)
        if times.ndim != 1 or wave.shape != times.shape or not np.isfinite(wave).all():
            problems.append('ROI waveform must be finite and match the one-dimensional time axis')
            return problems
        window = plan['analysis']['window_s']
        mask = (times >= window[0]) & (times <= window[1])
        key = 'group_mean_uv' if group else 'roi_amplitude_uv'
        if not mask.any():
            problems.append('No actual samples in the approved measurement window')
        elif not finite_number(result.get(key)) or abs(result[key] - float(wave[mask].mean())) > atol_uv:
            problems.append(f'{key} differs from the saved waveform mean in uV')
        if group:
            subjects = arrays['subjects'].astype(str).tolist()
            amplitudes = np.asarray(arrays['roi_amplitudes_uv'], dtype=float)
            if (amplitudes.shape != (len(subjects),) or not np.isfinite(amplitudes).all()
                    or not subjects or len(set(subjects)) != len(subjects)
                    or subjects != result.get('subjects_included')
                    or len(subjects) != result.get('n_subjects')):
                problems.append('Participant identities/counts/amplitudes do not align')
            else:
                per = result.get('per_subject_amplitude_uv')
                if (not isinstance(per, dict) or set(per) != set(subjects)
                        or any(not finite_number(per[s]) or abs(per[s] - value) > atol_uv
                               for s, value in zip(subjects, amplitudes))):
                    problems.append('Participant result fields differ from saved amplitudes')
                if not finite_number(result.get(key)) or abs(result[key] - float(amplitudes.mean())) > atol_uv:
                    problems.append('Group mean differs from the mean of participant amplitudes')
    except (KeyError, TypeError, ValueError) as exc:
        problems.append('Cannot check ERP evidence: ' + str(exc))
    return problems


def check_outputs(plan, workspace, *, atol_uv=None):
    workspace = Path(workspace)
    problems = []
    path = workspace / "result.json"
    result = {}
    if path.is_file():
        try:
            result = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            problems.append('result.json is unreadable: ' + str(exc))
    else:
        problems.append("result.json is missing")
    if not isinstance(result, dict):
        problems.append('result.json must contain an object')
        result = {}
    for key in plan["required_results"]:
        if key not in result:
            problems.append(f"result.json lacks {key}")
        elif result.get('status') == 'computed' and result[key] is None:
            problems.append(f'computed result has null field {key}')
        elif isinstance(result[key], str) and not result[key].strip():
            problems.append(f'result field {key} is empty')
        elif isinstance(result[key], float) and not math.isfinite(result[key]):
            problems.append(f'result field {key} is not finite')
    if result.get('status') not in ('computed', 'ineligible'):
        problems.append('Result is not a completed computed/ineligible delivery')
    if result.get('status') == 'computed':
        for key in ('roi_amplitude_uv', 'group_mean_uv', 'ttest_t', 'ttest_p', 'cluster_min_p'):
            if key in plan['required_results'] and not finite_number(result.get(key)):
                problems.append(f'computed field {key} must be a finite number')
        for key in ('ttest_significant', 'cluster_significant'):
            if key in plan['required_results'] and not isinstance(result.get(key), bool):
                problems.append(f'computed field {key} must be a boolean')
        for key in ('ttest_p', 'cluster_min_p'):
            if key in plan['required_results'] and finite_number(result.get(key)) and not 0 <= result[key] <= 1:
                problems.append(f'{key} must be in [0, 1]')
    if result.get('status') == 'ineligible':
        minimum = plan['analysis'].get('minimum_trials')
        counts = [result.get('n_trials_plus'), result.get('n_trials_minus')]
        if (plan['request_kind'] != 'single_subject' or minimum is None
                or any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in counts)):
            problems.append('ineligible requires actual retained counts and approved single-subject trial minima')
        elif counts[0] >= minimum['plus'] and counts[1] >= minimum['minus']:
            problems.append('ineligible contradicts retained counts meeting both approved minima')
    arrays = None
    evidence = workspace / "analysis_evidence.npz"
    if not evidence.is_file():
        problems.append("analysis_evidence.npz is missing")
    else:
        try:
            with np.load(evidence, allow_pickle=False) as data:
                arrays = {key: data[key] for key in data.files}
                for key in plan["required_evidence"]:
                    if result.get('status') == 'ineligible' and key == 'roi_difference_uv':
                        continue  # An excluded subject has no eligible amplitude estimate.
                    if key not in data:
                        problems.append(f"analysis_evidence.npz lacks {key}")
        except (ValueError, OSError) as exc:
            problems.append('Cannot read analysis_evidence.npz: ' + str(exc))
    root = workspace / plan["derivatives"]["root"]
    description = root / "dataset_description.json"
    if not description.is_file():
        problems.append("derivative dataset_description.json is missing")
    else:
        value = json.loads(description.read_text())
        if value.get("DatasetType") != "derivative":
            problems.append('derivative DatasetType must be "derivative"')
        if not value.get("SourceDatasets"):
            problems.append("derivative SourceDatasets is missing")
    for subject in result.get("subjects_included", [result.get("subject")]):
        if subject and not any(path.is_file() for path in (root / subject).rglob("*")):
            problems.append(f"no derivative files for {subject}")
    arithmetic_ran = atol_uv is not None and arrays is not None and result.get('status') == 'computed'
    if arithmetic_ran:
        problems.extend(arithmetic_checks(plan, result, arrays, atol_uv=atol_uv))
    return {"passed": not problems, "problems": problems,
            'coverage': {'structure': True, 'artifact_arithmetic_and_grid': arithmetic_ran,
                         'raw_input': False, 'event_mapping': False, 'group_statistics': False},
            'internal_arithmetic_atol_uv': atol_uv,
            "scope": "Structure and artifact arithmetic only at the recorded coverage. Raw-input/event and independent numerical verification remain separate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument('--atol-uv', type=float, help='Explicit tolerance for internal result-to-evidence arithmetic, not reference accuracy')
    args = parser.parse_args()
    report = check_outputs(json.loads(args.plan.read_text()), args.workspace, atol_uv=args.atol_uv)
    (args.workspace / "SELF_CHECK.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())


AEA callable interface: tools/erp_execution.py
Use the actual checkout, approved plan, dataset root and workspace paths from this task.
Execute python /workspace/aea/tools/erp_execution.py preflight --plan /workspace/PUBLIC_CONTRACT.json --dataset-root /input/erp_core_bids --workspace /workspace before implementing EEG processing. This reads task sidecars and actual event rows, writes conditions/counts/version in ERP_INPUTS.json, and identifies the next approved step. Pre-epoch counts do not replace retained-epoch eligibility.
From erp_execution import save_subject_state and load_group_state after adding /workspace/aea/tools to sys.path. After each processed participant call save_subject_state(STATE_DIRECTORY, subject, epochs, plan=plan, plus=plus_condition, minus=minus_condition). Before statistics use state = load_group_state(STATE_DIRECTORY, plan=plan). It restores actual channel Info and provides state["result_fields"], state["evidence"], state["info"] and state["cluster_data_uv"] (subjects x approved-window samples x channels). It selects the named ROI and saves excluded counts. Use only the approved tests and settings. Do not reset dictionaries or average all channels to recover a missing variable.
After saving actual results, evidence and derivatives, run python /workspace/aea/tools/erp_execution.py finalize --plan /workspace/PUBLIC_CONTRACT.json --workspace /workspace --atol-uv 1e-9. Only a successful check creates FINAL_SUBMISSION.md from the actual result.json. Return that file as the final response. A failed check preserves a numbered report. Fix implementation issues within the approved task; do not manufacture answers or treat a check not yet executed as a missing scientific choice. The callable helper source is on disk, not preloaded into this packet.


AEA procedure templates/bids_derivatives/README.md

# BIDS-Derivatives output template for ERP results

Write the analysis outputs as a derivative dataset, separate from the read-only raw
tree. The layout below passes the BIDS validator (schema validator 3.0.2, schema 1.2.7)
with no errors. ERP difference waves have no official BIDS suffix yet, so the `_erp`
files are declared in `.bidsignore`, which is how BIDS allows files outside the current
specification.

```
derivatives/<pipeline-name>/
    dataset_description.json     DatasetType "derivative", GeneratedBy, SourceDatasets
    .bidsignore                  lists *_erp.tsv and *_erp.json
    README
    sub-XXX/eeg/sub-XXX_task-<task>_desc-<contrast>_erp.tsv
    sub-XXX/eeg/sub-XXX_task-<task>_desc-<contrast>_erp.json
```

Rules that the validator enforces or that downstream users rely on:

- `dataset_description.json` must exist at the derivative root, with `"DatasetType": "derivative"`.
- `SourceDatasets` records the DOI of the raw dataset (`doi:` prefix) and its version.
  Read the version from the raw dataset's own `CHANGES` file instead of assuming one.
- `<task>` and `<contrast>` are alphanumeric, with no hyphen or underscore inside.
- Column units go in the `_erp.json` sidecar.

`tools/write_erp_derivatives.py` writes this layout:

```python
import sys
sys.path.insert(0, "/workspace/aea/tools")
from write_erp_derivatives import start_derivative, write_subject_erp
root = start_derivative("/workspace/derivatives/erp-analysis", pipeline="my-analysis",
                        source_doi="10.xxxx/xxxxx", source_version="1.0")
write_subject_erp(root, subject="sub-XXX", task="P3", contrast="rareminusfrequent",
                  times_s=times, values_uv=roi_wave)
```

Nothing in this template selects a method. Filter, epoch, ROI and test settings come
from the approved analysis plan.
