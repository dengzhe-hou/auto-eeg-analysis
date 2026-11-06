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
