"""Check actual reference samples, auxiliary-channel rejection and plan agreement."""
from pathlib import Path
import runpy

import mne
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKS = runpy.run_path(str(ROOT / 'skills/eeg-preprocess/scripts/check_channels.py'))


def fixture():
    # Readers can label ocular derivations EEG; the independent recording map
    # defines their role. The deliberately large EOG makes contamination visible.
    values = np.array([[1., 3., 5.], [3., 5., 7.], [90., 100., 110.]]) * 1e-6
    raw = mne.io.RawArray(values, mne.create_info(
        ['Cz', 'Pz', 'LOC-A2'], sfreq=100, ch_types='eeg'), verbose=False)
    inputs = dict(expected_channels=['Cz', 'Pz'],
                  channel_roles={'Cz': 'scalp_eeg', 'Pz': 'scalp_eeg', 'LOC-A2': 'eog'},
                  mapping_source='Synthetic acquisition channel table')
    return raw, inputs, values


def test_eye_channel_mistyped_as_eeg_rejected_before_sample_change():
    raw, inputs, values = fixture()
    with pytest.raises(ValueError, match='Non-scalp.*LOC-A2'):
        CHECKS['apply_average_reference'](raw, **inputs, projection=False)
    np.testing.assert_array_equal(raw.get_data(), values)


def test_correct_types_apply_exact_scalp_mean_and_preserve_eog():
    raw, inputs, values = fixture()
    raw.set_channel_types({'LOC-A2': 'eog'})
    record = CHECKS['apply_average_reference'](raw, **inputs, projection=False)
    expected = values.copy()
    expected[:2] -= values[:2].mean(axis=0)
    np.testing.assert_allclose(raw.get_data(), expected, atol=1e-20, rtol=0)
    assert record['eeg_channels'] == ['Cz', 'Pz']
    assert record['excluded_channels'] == ['LOC-A2']


def test_unresolved_identity_is_not_silently_accepted():
    raw, inputs, _ = fixture()
    inputs['channel_roles'].pop('LOC-A2')
    with pytest.raises(ValueError, match='identities unresolved'):
        CHECKS['check_eeg_channels'](raw, **inputs)


def test_missing_planned_channel_rejected():
    raw, inputs, _ = fixture()
    raw.set_channel_types({'LOC-A2': 'eog'})
    inputs['expected_channels'].append('Fz')
    with pytest.raises(ValueError, match='missing=.*Fz'):
        CHECKS['check_eeg_channels'](raw, **inputs)


def test_bad_channel_set_matches_actual_mne_reference_contributors():
    raw, inputs, values = fixture()
    raw.set_channel_types({'LOC-A2': 'eog'})
    raw.info['bads'] = ['Pz']
    inputs['expected_channels'] = ['Cz']
    record = CHECKS['apply_average_reference'](raw, **inputs, projection=False)
    np.testing.assert_allclose(raw.get_data()[0], 0, atol=1e-20, rtol=0)
    np.testing.assert_array_equal(raw.get_data()[1:], values[1:])
    assert record['bad_channels'] == ['Pz']


def test_pending_projector_does_not_change_samples():
    raw, inputs, values = fixture()
    raw.set_channel_types({'LOC-A2': 'eog'})
    record = CHECKS['apply_average_reference'](raw, **inputs, projection=True)
    np.testing.assert_array_equal(raw.get_data(), values)
    assert record['operation'] == 'add_average_reference_projector'
    assert len(raw.info['projs']) == 1 and not raw.info['projs'][0]['active']


def test_documented_reference_example_runs_on_actual_object():
    raw, inputs, values = fixture()
    raw.set_channel_types({'LOC-A2': 'eog'})
    doc = (ROOT / 'skills/eeg-preprocess/references/channel-identity.md').read_text(encoding='utf-8-sig')
    code = doc.split('```python\n', 1)[1].split('```', 1)[0]
    namespace = dict(AEA_ROOT=ROOT, raw=raw,
                     approved_reference_channels=inputs['expected_channels'],
                     documented_channel_roles=inputs['channel_roles'],
                     channel_mapping_source=inputs['mapping_source'], planned_projection=False)
    exec(compile(code, 'channel-identity.md', 'exec'), namespace)
    np.testing.assert_allclose(raw.get_data()[:2], values[:2] - values[:2].mean(axis=0), atol=1e-20)
