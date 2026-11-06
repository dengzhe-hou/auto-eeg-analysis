"""Executable metadata checks, saved participant state and ERP delivery.

This applies an existing explicit plan. It does not preprocess data, choose a
test, consult reference answers, or control an agent's termination policy.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/eeg-epoch/scripts'))
from erp import epoch_sample_times, mean_roi_amplitude
from check_erp_outputs import check_outputs

TASK_CONTRASTS = {'P3': 'rareminusfrequent', 'N170': 'facesminuscars',
                  'N400': 'unrelatedminusrelated', 'ERN': 'errorminuscorrect'}


def supports_input_check(plan):
    dataset = plan['dataset']
    return (dataset['name'] == 'ERP CORE'
            and dataset.get('bids_task_label') in TASK_CONTRASTS
            and TASK_CONTRASTS[dataset['bids_task_label']] == plan['derivatives']['contrast_label'])


def erp_core_conditions(task, rows, levels):
    """Return documented condition rows, without resampling or trial rejection."""
    selected = []
    for index, row in enumerate(rows):
        if row['trial_type'] != ('response' if task == 'ERN' else 'stimulus'):
            continue
        code = int(row['value'])
        if task == 'P3':
            if not (1 <= code // 10 <= 5 and 1 <= code % 10 <= 5):
                raise ValueError(f'Unknown P3 stimulus at row {index}: {code}')
            first, second = 'ABCDE'[code // 10 - 1], 'ABCDE'[code % 10 - 1]
            if f'block target {first}, trial stimulus {second}' not in levels.get(str(code), ''):
                raise ValueError(f'P3 sidecar does not confirm row {index}, code {code}')
            condition = 'plus' if first == second else 'minus'
        elif task == 'N170':
            if levels.get('1-40') != 'Stimulus - faces' or levels.get('41-80') != 'Stimulus - cars':
                raise ValueError('N170 sidecar must document faces 1-40 and cars 41-80')
            if 101 <= code <= 180:
                continue  # Scrambled images are outside this explicit contrast.
            if not 1 <= code <= 80:
                raise ValueError(f'Unknown N170 stimulus at row {index}: {code}')
            condition = 'plus' if code <= 40 else 'minus'
        elif task == 'N400':
            if code in (111, 112, 121, 122):
                continue  # Prime words are not target-locked trials.
            if code not in (211, 212, 221, 222):
                raise ValueError(f'Unknown N400 stimulus at row {index}: {code}')
            meaning = 'unrelated' if code in (221, 222) else 'related'
            if f'target word, {meaning} word pair' not in levels.get(str(code), ''):
                raise ValueError(f'N400 sidecar does not confirm row {index}, code {code}')
            condition = 'plus' if meaning == 'unrelated' else 'minus'
        elif task == 'ERN':
            if code not in (111, 112, 121, 122, 211, 212, 221, 222):
                raise ValueError(f'Unknown ERN response at row {index}: {code}')
            if 'Response' not in levels.get(str(code), ''):
                raise ValueError(f'ERN sidecar does not confirm response code {code}')
            condition = 'plus' if code // 100 != code % 10 else 'minus'
        else:
            raise ValueError(f'Unsupported ERP CORE task: {task}')
        onset = float(row['onset'])
        if not np.isfinite(onset):
            raise ValueError(f'Nonfinite onset at row {index}')
        selected.append({'row': index, 'code': code, 'onset_s': onset, 'condition': condition})
    return selected


def inspect_inputs(plan, dataset_root):
    """Read actual sidecars/counts. Raw counts never establish epoch eligibility."""
    root = Path(dataset_root)
    task = plan['dataset']['bids_task_label']
    if not supports_input_check(plan):
        raise ValueError('This metadata reader supports the four documented ERP CORE contrasts only')
    sidecar = root / f'task-{task}_events.json'
    levels = json.loads(sidecar.read_text(encoding="utf-8-sig"))['value']['Levels']
    changes = (root / 'CHANGES').read_text(encoding="utf-8-sig")
    version = re.search(r'(?im)^\s*version\s+(\d+(?:\.\d+)+)\b', changes)
    if version is None:
        raise ValueError('No dataset version found in an actual CHANGES version line')
    subjects = {}
    for subject in plan['subjects']:
        matches = list((root / subject / f'ses-{task}' / 'eeg').glob(f'*task-{task}_eeg.set'))
        if len(matches) != 1:
            raise ValueError(f'Expected one {task} recording for {subject}, found {len(matches)}')
        events = matches[0].with_name(matches[0].name.replace('_eeg.set', '_events.tsv'))
        with events.open(encoding="utf-8-sig") as stream:
            classified = erp_core_conditions(task, list(csv.DictReader(stream, delimiter='\t')), levels)
        subjects[subject] = {'recording': str(matches[0]), 'events': str(events),
                             'raw_n_plus': sum(x['condition'] == 'plus' for x in classified),
                             'raw_n_minus': sum(x['condition'] == 'minus' for x in classified)}
    return {'plan': plan, 'dataset_version': version[1], 'events_sidecar': str(sidecar),
            'subjects': subjects, 'coverage': 'Readable metadata and pre-epoch counts only; no EEG samples or retained-epoch eligibility checked',
            'next_step': 'Continue the approved processing, then apply its minimum to actual retained epochs'}


def save_subject_state(directory, subject, epochs, *, plan, plus, minus):
    """Save actual participant data before group tests or optional diagnostics."""
    import mne
    if subject not in plan['subjects']:
        raise ValueError(f'{subject} is not in the approved participant list')
    expected_times = epoch_sample_times(epoch_s=plan['analysis']['epoch_s'],
                                       sfreq=plan['analysis']['resample_hz'])
    if (epochs.info['sfreq'] != plan['analysis']['resample_hz']
            or not np.array_equal(epochs.times, expected_times)):
        raise ValueError('Actual epochs do not match the approved sampling rate and integer-sample grid')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path, info_path = directory / f'{subject}.npz', directory / f'{subject}-info.fif'
    if path.exists() or info_path.exists():
        raise FileExistsError(f'Participant state exists for {subject}; preserve it and use a new directory')
    counts = [len(epochs[plus]), len(epochs[minus])]
    minimum = plan['analysis']['minimum_trials']
    eligible = counts[0] >= minimum['plus'] and counts[1] >= minimum['minus']
    state = {'subject': np.asarray(subject), 'plan_json': np.asarray(json.dumps(plan)),
             'channels': np.asarray(epochs.ch_names), 'times_s': epochs.times.copy(),
             'sfreq_hz': np.asarray(epochs.info['sfreq']), 'amplitude_unit': np.asarray('uV'),
             'retained_counts': np.asarray(counts), 'eligible': np.asarray(eligible)}
    if eligible:
        # Explicit picks preserve the full channel order, including marked channels.
        measured = mean_roi_amplitude(epochs, plus=plus, minus=minus,
                                      roi=plan['analysis']['roi'], window_s=plan['analysis']['window_s'])
        state['difference_uv'] = (epochs[plus].average(picks=epochs.ch_names).data
                                 - epochs[minus].average(picks=epochs.ch_names).data) * 1e6
        state['roi_amplitude_uv'] = np.asarray(measured['roi_amplitude_uv'])
    # The existence check above preserves prior files on both MNE 1.8 and newer MNE.
    mne.io.write_info(info_path, epochs.info)
    np.savez(path, **state)
    return path


def load_group_state(directory, *, plan):
    """Restore named arrays and Info; select ROI by names, never by all channels."""
    import mne
    directory = Path(directory)
    included, excluded, waves, amplitudes, counts = [], [], [], [], {}
    times, channels, info = None, None, None
    for subject in plan['subjects']:
        with np.load(directory / f'{subject}.npz', allow_pickle=False) as saved:
            if json.loads(saved['plan_json'].item()) != plan:
                raise ValueError(f'Saved plan differs for {subject}; do not reuse state for a changed plan')
            if saved['subject'].item() != subject or saved['amplitude_unit'].item() != 'uV':
                raise ValueError(f'Saved identity or units differ for {subject}')
            counts[subject] = saved['retained_counts'].tolist()
            minimum = plan['analysis']['minimum_trials']
            eligible = counts[subject][0] >= minimum['plus'] and counts[subject][1] >= minimum['minus']
            if not eligible:
                excluded.append(subject)
                continue
            actual_times, actual_channels = saved['times_s'].copy(), saved['channels'].astype(str).tolist()
            if times is None:
                times, channels = actual_times, actual_channels
                info = mne.io.read_info(directory / f'{subject}-info.fif', verbose=False)
                if info.ch_names != channels or info['sfreq'] != plan['analysis']['resample_hz']:
                    raise ValueError('Saved Info does not match the approved state channel order/rate')
            if not np.array_equal(times, actual_times) or channels != actual_channels:
                raise ValueError(f'Time or channel order differs for {subject}')
            wave = saved['difference_uv'].copy()
            if wave.shape != (len(channels), len(times)) or not np.isfinite(wave).all():
                raise ValueError(f'Expected channels x times finite ERP state for {subject}')
            missing = set(plan['analysis']['roi']) - set(channels)
            if missing:
                raise ValueError(f'ROI channels absent from saved state: {sorted(missing)}')
            roi_wave = wave[[channels.index(name) for name in plan['analysis']['roi']]].mean(axis=0)
            window = plan['analysis']['window_s']
            mask = (times >= window[0]) & (times <= window[1])
            if not mask.any():
                raise ValueError('No samples in the approved measurement window')
            amplitude = float(roi_wave[mask].mean())
            if not np.isclose(amplitude, saved['roi_amplitude_uv'].item(), rtol=0, atol=1e-9):
                raise ValueError(f'Saved amplitude differs from its named ROI evidence for {subject}')
            included.append(subject); waves.append(wave); amplitudes.append(amplitude)
    if not included:
        raise ValueError('No eligible participant state; retained counts are in the saved files')
    differences = np.asarray(waves)
    roi_waves = differences[:, [channels.index(name) for name in plan['analysis']['roi']], :].mean(axis=1)
    mask = (times >= plan['analysis']['window_s'][0]) & (times <= plan['analysis']['window_s'][1])
    return {'info': info, 'channels': channels, 'differences_uv': differences,
            'cluster_data_uv': differences[:, :, mask].transpose(0, 2, 1),
            'retained_counts': counts,
            'result_fields': {'subjects_included': included, 'subjects_excluded': excluded,
                              'n_subjects': len(included), 'per_subject_amplitude_uv': dict(zip(included, amplitudes)),
                              'group_mean_uv': float(np.mean(amplitudes))},
            'evidence': {'subjects': np.asarray(included), 'roi_amplitudes_uv': np.asarray(amplitudes),
                         'times_s': times, 'grand_roi_difference_uv': roi_waves.mean(axis=0),
                         'amplitude_unit': np.asarray('uV'), 'sfreq_hz': np.asarray(info['sfreq'])}}


def finalize_delivery(plan, workspace, *, atol_uv):
    """Write a final response from real artifacts only after checks pass.

    Failed check attempts are retained. No missing answer is filled or inferred.
    This is a callable gate, not a modification to the CodeAct termination loop.
    """
    workspace = Path(workspace)
    final = workspace / 'FINAL_SUBMISSION.md'
    if final.exists():
        raise FileExistsError('Final submission already exists; preserve the first delivery')
    report = check_outputs(plan, workspace, atol_uv=atol_uv)
    if supports_input_check(plan):
        preflight = workspace / 'ERP_INPUTS.json'
        if not preflight.is_file():
            report['problems'].append('Run ERP CORE preflight and save ERP_INPUTS.json before delivery')
        elif (workspace / 'result.json').is_file():
            metadata = json.loads(preflight.read_text(encoding="utf-8-sig"))
            result = json.loads((workspace / 'result.json').read_text(encoding="utf-8-sig"))
            if metadata['plan'] != plan:
                report['problems'].append('Input check belongs to a different approved plan')
            if result.get('dataset_version') != metadata['dataset_version']:
                report['problems'].append('dataset_version differs from the actual CHANGES version line')
    report['passed'] = not report['problems']
    attempts = workspace / 'delivery-checks'
    attempts.mkdir(parents=True, exist_ok=True)
    record = attempts / f'check-{len(list(attempts.glob("check-*.json"))) + 1:03d}.json'
    with record.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    if report['passed']:
        result = json.loads((workspace / 'result.json').read_text(encoding="utf-8-sig"))
        with final.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('preflight')
    inspect.add_argument('--dataset-root', type=Path, required=True)
    inspect.add_argument('--plan', type=Path, required=True)
    inspect.add_argument('--workspace', type=Path, required=True)
    finish = sub.add_parser('finalize')
    finish.add_argument('--plan', type=Path, required=True)
    finish.add_argument('--workspace', type=Path, required=True)
    finish.add_argument('--atol-uv', type=float, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    if args.command == 'preflight':
        report = inspect_inputs(plan, args.dataset_root)
        args.workspace.mkdir(parents=True, exist_ok=True)
        with (args.workspace / 'ERP_INPUTS.json').open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: v for k, v in report.items() if k != 'plan'}, indent=2))
        return 0
    report = finalize_delivery(plan, args.workspace, atol_uv=args.atol_uv)
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
