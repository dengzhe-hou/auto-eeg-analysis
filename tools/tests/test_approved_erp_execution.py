"""Deterministic regression checks for the observed ERP execution failures."""
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import mne
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'skills/eeg-epoch/scripts'))
from erp import epoch_sample_times, mean_roi_amplitude, save_erp_outputs
from erp_core_events import erp_core_ern_events
from check_erp_outputs import check_outputs
from prepare_erp_packet import prepare_erp_packet


@pytest.fixture
def epochs():
    info = mne.create_info(['Cz', 'Pz'], 100., 'eeg')
    values = np.zeros((4, 2, 101))
    values[:, :, 20:71] = np.asarray([[1, 2], [5, 6], [3, 4], [7, 8]])[:, :, None] * 1e-6
    return mne.EpochsArray(values, info, events=np.array([[100, 0, 1], [300, 0, 2],
                           [500, 0, 1], [700, 0, 2]]), event_id={'A': 1, 'B': 2},
                           tmin=-.2, baseline=None, verbose=False)


@pytest.fixture
def plan():
    return {'request_kind': 'single_subject', 'dataset': {'name': 'ERP CORE'},
            'analysis': {'epoch_s': [-.2, .8], 'resample_hz': 100., 'window_s': [.1, .3]},
            'derivatives': {'root': 'derivatives/erp-analysis', 'contrast_label': 'errorminuscorrect'},
            'required_results': dict.fromkeys(['status', 'subject', 'roi_amplitude_uv', 'n_trials_plus', 'n_trials_minus']),
            'required_evidence': dict.fromkeys(['times_s', 'roi_difference_uv'])}


def deliver(path, measured):
    result = {'status': 'computed', 'subject': 'sub-test',
              **{k: measured[k] for k in ['roi_amplitude_uv', 'n_trials_plus', 'n_trials_minus']}}
    evidence = {k: measured[k] for k in ['times_s', 'roi_difference_uv', 'amplitude_unit', 'sfreq_hz']}
    save_erp_outputs(path, result=result, evidence=evidence)
    derivative = path / 'derivatives/erp-analysis'
    (derivative / 'sub-test').mkdir(parents=True)
    (derivative / 'sub-test/result.tsv').write_text('actual synthetic fixture\n')
    (derivative / 'dataset_description.json').write_text(json.dumps(
        {'DatasetType': 'derivative', 'SourceDatasets': [{'DOI': 'synthetic-test'}]}))
    return result, evidence


def test_response_codes_use_target_digit_and_keep_first_responses():
    rows = [{'trial_type': 'response', 'value': '221', 'onset': '.1'},
            {'trial_type': 'response', 'value': '221', 'onset': '.2'},
            {'trial_type': 'stimulus', 'value': '21', 'onset': '.3'},
            {'trial_type': 'response', 'value': '121', 'onset': '.4'},
            {'trial_type': 'response', 'value': '212', 'onset': '.5'}]
    events, record = erp_core_ern_events(rows, sfreq=100., first_samp=1000, n_times=101)
    np.testing.assert_array_equal(events[:, 0], [1010, 1020, 1040, 1050])
    np.testing.assert_array_equal(events[:, 2], [1, 1, 2, 2])
    assert len(record['decoded']) == 4


def test_all_documented_response_codes_and_sample_boundaries():
    rows = [{'trial_type': 'response', 'value': str(c), 'onset': str(i / 10)}
            for i, c in enumerate([111, 112, 121, 122, 211, 212, 221, 222], 1)]
    rows += [{'trial_type': 'response', 'value': '111', 'onset': '0'},
             {'trial_type': 'response', 'value': '222', 'onset': '1'}]
    events, record = erp_core_ern_events(rows, sfreq=100., first_samp=0, n_times=100)
    np.testing.assert_array_equal(events[:, 2], [2, 1, 2, 1, 1, 2, 1, 2])
    assert len(record['excluded']) == 2
    with pytest.raises(ValueError, match='Unsupported'):
        erp_core_ern_events([{'trial_type': 'response', 'value': 999, 'onset': '.1'}],
                           sfreq=100., first_samp=0, n_times=100)


def test_epoch_grid_matches_actual_mne_rounding():
    raw = mne.io.RawArray(np.zeros((2, 1024)), mne.create_info(['Cz', 'Pz'], 256., 'eeg'), verbose=False)
    ep = mne.Epochs(raw, np.array([[300, 0, 1]]), tmin=-.2, tmax=.8,
                    baseline=None, preload=True, verbose=False)
    expected = epoch_sample_times(epoch_s=[-.2, .8], sfreq=256.)
    np.testing.assert_array_equal(expected, ep.times)
    assert expected[0] == -51 / 256 and expected[-1] == 205 / 256
    assert not np.allclose(expected, np.arange(len(expected)) / 256 - .2, rtol=0, atol=1e-12)


def test_measurement_keeps_epochs_and_uses_volts_to_uv(epochs):
    before = epochs.get_data(copy=True)
    a = mean_roi_amplitude(epochs, plus='A', minus='B', roi=['Cz', 'Pz'], window_s=[.1, .3])
    assert np.count_nonzero((a['times_s'] >= .1) & (a['times_s'] <= .3)) == 21
    assert a['roi_amplitude_uv'] == pytest.approx(-4., abs=1e-12)
    b = mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3])
    assert b['roi_amplitude_uv'] == pytest.approx(4., abs=1e-12)
    np.testing.assert_array_equal(before, epochs.get_data(copy=True))
    with pytest.raises(ValueError):
        mean_roi_amplitude(epochs, plus='A', minus='B', roi=['missing'], window_s=[.1, .3])


def test_computed_outputs_survive_a_later_check_error(tmp_path, epochs, plan):
    measured = mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3])
    deliver(tmp_path, measured)
    original = (tmp_path / 'result.json').read_bytes()
    with pytest.raises(NameError):
        exec('unassigned_diagnostic_variable + 1', {})
    assert (tmp_path / 'result.json').read_bytes() == original
    assert check_outputs(plan, tmp_path, atol_uv=1e-9)['passed']
    with pytest.raises(FileExistsError):
        deliver(tmp_path, measured)


@pytest.mark.parametrize('defect', ['null', 'empty', 'nonfinite', 'wrong_scale', 'unit', 'grid'])
def test_output_check_catches_observed_and_unit_defects(tmp_path, epochs, plan, defect):
    measured = mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3])
    result, evidence = deliver(tmp_path, measured)
    assert check_outputs(plan, tmp_path, atol_uv=1e-9)['passed']
    if defect == 'null':
        result['roi_amplitude_uv'] = None
    elif defect == 'empty':
        result['subject'] = ' '
    elif defect == 'nonfinite':
        result['roi_amplitude_uv'] = float('nan')
    elif defect == 'wrong_scale':
        result['roi_amplitude_uv'] *= 1e6
    elif defect == 'unit':
        evidence['amplitude_unit'] = np.asarray('V')
    elif defect == 'grid':
        evidence['times_s'] = evidence['times_s'] + .001
    (tmp_path / 'result.json').write_text(json.dumps(result))
    np.savez(tmp_path / 'analysis_evidence.npz', **evidence)
    report = check_outputs(plan, tmp_path, atol_uv=1e-9)
    assert not report['passed']
    assert report['coverage']['raw_input'] is False
    assert report['coverage']['event_mapping'] is False


def test_coverage_reports_arithmetic_not_run_without_tolerance(tmp_path, epochs, plan):
    deliver(tmp_path, mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3]))
    assert check_outputs(plan, tmp_path)['coverage']['artifact_arithmetic_and_grid'] is False


def test_checker_cli_returns_failure_and_preserves_artifacts(tmp_path, epochs, plan):
    result, _ = deliver(tmp_path, mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3]))
    result['roi_amplitude_uv'] = None
    (tmp_path / 'result.json').write_text(json.dumps(result))
    before = (tmp_path / 'result.json').read_bytes()
    p = tmp_path / 'PLAN.json';p.write_text(json.dumps(plan))
    run = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/check_erp_outputs.py'),
                          '--plan', str(p), '--workspace', str(tmp_path), '--atol-uv', '1e-9'],
                         capture_output=True, text=True)
    assert run.returncode == 1, run.stderr
    assert (tmp_path / 'result.json').read_bytes() == before
    assert not json.loads((tmp_path / 'SELF_CHECK.json').read_text())['passed']


def test_packet_selection_uses_only_public_task_and_preserves_full_delivery(plan):
    from load_skill import check_packet_in_request
    single, receipt = prepare_erp_packet(ROOT, plan)
    assert '## ERP CORE response coding' in single
    assert '## Approved ERP group statistics' not in single
    assert 'incomp_resp' not in single and 'RANSAC' not in single
    assert len(receipt['selections']) == 2
    check_packet_in_request({'messages': [{'role': 'user', 'content': single}]}, single)
    plan['request_kind'] = 'group'
    group, receipt = prepare_erp_packet(ROOT, plan)
    assert '## Approved ERP group statistics' in group
    assert len(receipt['selections']) == 3
    plan['derivatives']['contrast_label'] = 'facesminuscars'
    other, _ = prepare_erp_packet(ROOT, plan)
    assert '## ERP CORE response coding' not in other
    assert 'def erp_core_ern_events' not in other


def test_group_result_and_participant_arithmetic(tmp_path, epochs, plan):
    measured = mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3])
    plan['request_kind'] = 'group'
    plan['required_results'] = dict.fromkeys(['status', 'group_mean_uv', 'n_subjects', 'subjects_included', 'per_subject_amplitude_uv'])
    plan['required_evidence'] = dict.fromkeys(['times_s', 'grand_roi_difference_uv', 'roi_amplitudes_uv', 'subjects'])
    result = {'status': 'computed', 'group_mean_uv': 4., 'n_subjects': 2, 'subjects_included': ['s1', 's2'],
              'per_subject_amplitude_uv': {'s1': 3., 's2': 5.}}
    evidence = {'times_s': measured['times_s'], 'grand_roi_difference_uv': measured['roi_difference_uv'],
                'roi_amplitudes_uv': np.asarray([3., 5.]), 'subjects': np.asarray(['s1', 's2']),
                'amplitude_unit': np.asarray('uV'), 'sfreq_hz': np.asarray(100.)}
    save_erp_outputs(tmp_path, result=result, evidence=evidence)
    derivative = tmp_path / 'derivatives/erp-analysis';derivative.mkdir(parents=True)
    (derivative / 'dataset_description.json').write_text(json.dumps({'DatasetType': 'derivative', 'SourceDatasets': [{}]}))
    for subject in ['s1', 's2']:
        (derivative / subject).mkdir();(derivative / subject / 'wave.tsv').write_text('fixture')
    assert check_outputs(plan, tmp_path, atol_uv=1e-9)['passed']
    evidence['subjects'] = np.asarray(['s2', 's1'])
    np.savez(tmp_path / 'analysis_evidence.npz', **evidence)
    assert not check_outputs(plan, tmp_path, atol_uv=1e-9)['passed']
