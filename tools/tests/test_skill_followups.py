"""Observed metadata, sample-unit and half-open GFP failures stay detectable."""
from pathlib import Path
import json
import runpy
import sys
import mne
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from check_analysis_outputs import check_outputs, write_outputs

prep = runpy.run_path(str(ROOT / 'skills/eeg-preprocess/scripts/continuous.py'))
complexity = runpy.run_path(str(ROOT / 'skills/eeg-complexity/scripts/sample_entropy.py'))
conn = runpy.run_path(str(ROOT / 'skills/eeg-connectivity/scripts/continuous.py'))


def test_connectivity_report_counts_come_from_the_actual_matrix(tmp_path):
    names = [f'E{i:02d}' for i in range(60)]
    matrix = np.full((60, 60), .2)
    np.fill_diagonal(matrix, 1.)
    summary = conn['summarize_undirected_connectivity'](matrix, names, top_k=3)
    assert summary['metadata']['n_channels'] == 60
    assert summary['metadata']['n_undirected_pairs'] == 1770
    assert summary['top_pairs'] == [['E00', 'E01'], ['E00', 'E02'], ['E00', 'E03']]
    assert np.isclose(summary['global_mean'], .2)
    result = {'status': 'computed', 'explanation': 'Counts from the actual matrix.',
              'analysis_metadata': summary['metadata']}
    evidence = {'channels': names, 'plv': matrix}
    plan = {'analysis_channels': names, 'required_results': {},
            'required_evidence': {'channels': '', 'plv': ''}}
    write_outputs(result, evidence, tmp_path)
    assert check_outputs(plan, tmp_path)['passed']
    write_outputs({**result, 'analysis_metadata': {**summary['metadata'],
                   'n_channels': 62, 'n_undirected_pairs': 1891}}, evidence, tmp_path)
    check = check_outputs(plan, tmp_path)
    assert not check['passed']
    assert {'metadata.n_channels', 'metadata.n_undirected_pairs'} <= {
        row['name'] for row in check['checks'] if not row['passed']}


def test_recording_metadata_preserves_actual_subset_and_declared_roi():
    raw = mne.io.RawArray(np.zeros((3, 500)), mne.create_info(['F3', 'F4', 'Pz'], 100., 'eeg'), verbose=False)
    selected = raw.copy().pick(['F4', 'F3'])
    metadata = prep['recording_metadata'](selected, rois={'approved_frontal': ['F4', 'F3']})
    assert metadata['channels'] == ['F4', 'F3']
    assert metadata['n_channels'] == 2 and metadata['n_samples'] == 500
    assert type(metadata['n_samples']) is int
    assert json.loads(json.dumps(metadata)) == metadata
    assert metadata['roi_channels'] == {'approved_frontal': ['F4', 'F3']}
    with pytest.raises(ValueError, match='absent'):
        prep['recording_metadata'](selected, rois={'posterior': ['Pz']})


def test_sampen_raw_keeps_si_units_and_approved_samples(tmp_path):
    data = np.random.default_rng(20).normal(size=(2, 500)) * 1e-6
    raw = mne.io.RawArray(data, mne.create_info(['F3', 'F4'], 100., 'eeg'), verbose=False)
    operations = [{'operation': 'crop', 'parameters': {'start_s': 1., 'stop_s': 4.5}}]
    out = complexity['sample_entropy_raw'](raw, analysis_channels=['F4', 'F3'],
        operations=operations, m=3, r_fraction=.3, closed=False)
    np.testing.assert_array_equal(out['segment'], data[[1, 0], 100:450])
    np.testing.assert_array_equal(raw.get_data(), data)
    assert out['metadata']['n_samples'] == 350
    assert all(value['m'] == 3 and value['comparison'] == '< r' for value in out['details'])
    plan = {'analysis_channels': ['F4', 'F3'], 'operations': operations,
            'required_results': {}, 'required_evidence': {'channels': '', 'segment': ''},
            'numeric_tolerance': {'signal': {'rtol': 1e-8, 'atol': 1e-15}}}
    result = {'status': 'computed', 'explanation': 'Entropy from the requested segment.',
              'analysis_metadata': out['metadata']}
    evidence = {'channels': out['channels'], 'segment': out['segment'],
                'channel_entropy': out['channel_entropy']}
    write_outputs(result, evidence, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw)['passed']
    write_outputs(result, {**evidence, 'segment': out['segment'] * 1e-6}, tmp_path)
    assert not check_outputs(plan, tmp_path, raw_input=raw)['passed']


def test_gfp_half_open_buffer_has_exact_samples_and_absolute_peaks(tmp_path):
    data = np.zeros((2, 6101))
    for sample in [3400, 4400, 5400]:
        data[:, sample] = [2e-6, -2e-6]
    raw = mne.io.RawArray(data, mne.create_info(['F3', 'F4'], 100., 'eeg'), verbose=False)
    operations = [{'operation': 'crop', 'parameters': {'start_s': 30., 'stop_s': 60.}}]
    out = prep['population_gfp_raw'](raw, analysis_channels=raw.ch_names,
        operations=operations, time_origin_s=30., windows_s=[(30., 40.), (40., 50.), (50., 60.)], tie_rule='first')
    assert out['gfp'].shape == (3000,)
    assert out['metadata']['n_samples'] == 3000
    np.testing.assert_allclose(out['peak_times_s'], [34., 44., 54.])
    assert np.isclose(out['times_s'][-1], 59.99)
    plan = {'analysis_channels': raw.ch_names, 'operations': operations,
            'required_results': {}, 'required_evidence': {'channels': '', 'gfp': ''},
            'numeric_tolerance': {'signal': {'rtol': 1e-8, 'atol': 1e-15}}}
    result = {'status': 'computed', 'explanation': 'Population GFP over exact windows.',
              'analysis_metadata': out['metadata']}
    evidence = {'channels': out['metadata']['channels'], 'gfp': out['gfp']}
    write_outputs(result, evidence, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw)['passed']
    write_outputs({**result, 'analysis_metadata': {**out['metadata'], 'n_samples': 3001}},
                  {**evidence, 'gfp': np.r_[out['gfp'], 0.]}, tmp_path)
    check = check_outputs(plan, tmp_path, raw_input=raw)
    assert not check['passed']
    assert {'approved_input.gfp', 'metadata.n_samples'} <= {
        row['name'] for row in check['checks'] if not row['passed']}
