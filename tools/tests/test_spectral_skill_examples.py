"""Run the documented Welch examples and compare real PSDs with SciPy."""
from pathlib import Path
import re
import sys

import mne
import numpy as np
import pytest
from scipy.signal import welch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / 'skills/eeg-spectral/references/procedure.md'
sys.path.insert(0, str(ROOT / 'tools'))
from load_skill import load_skill_packet


def _examples():
    text, _ = load_skill_packet(ROOT, 'eeg-spectral', section='Phase B — PSD computation')
    main = re.findall(r'```python\n(.*?)```', text, re.S)[0]
    before, after = main.split('# Task-related: epoched data', 1)
    fixed, _ = load_skill_packet(ROOT, 'eeg-spectral',
        section='Fixed-length epoching of continuous resting data')
    fixed = re.search(r'```python\n(.*?)```', fixed, re.S).group(1)
    return before, after, fixed


def _inputs(monkeypatch, n_times, n_fft, segment_seconds=2):
    sfreq = 500.0
    rng = np.random.default_rng(42)
    raw = mne.io.RawArray(rng.normal(size=(2, 3000)) * 1e-6,
                         mne.create_info(['Cz', 'Pz'], sfreq, 'eeg'), verbose=False)
    events = np.column_stack([np.arange(6) * n_times,
                              np.zeros(6, dtype=int), [1, 2, 1, 2, 1, 2]])
    epochs = mne.EpochsArray(rng.normal(size=(6, 2, n_times)) * 1e-6, raw.info,
                             events=events, event_id={'a': 1, 'b': 2}, verbose=False)
    monkeypatch.setattr(mne.io, 'read_raw_fif', lambda *args, **kwargs: raw)
    monkeypatch.setattr(mne, 'read_epochs', lambda *args, **kwargs: epochs)
    plan = {'method': 'welch', 'frequency_range_hz': [1, 40],
            'welch': {'segment_seconds': segment_seconds, 'n_fft': n_fft,
                      'window': 'hann', 'overlap_fraction': .5, 'remove_dc': True},
            'bands': {'alpha': [8, 13]}, 'band_measure': 'mean_density'}
    namespace = {'SPECTRAL_PLAN': plan, 'EPOCH_SECONDS': 2, 'EPOCH_OVERLAP_SECONDS': 0,
                 'preprocessed_path': 'synthetic-raw.fif', 'epochs_path': 'synthetic-epo.fif',
                 'condition': 'a'}
    return raw, epochs, namespace


def _assert_scipy(psd, data, n_per_seg, n_fft):
    frequencies, expected = welch(data, fs=500, window='hann', nperseg=n_per_seg,
                                   noverlap=n_per_seg // 2, nfft=n_fft,
                                   detrend='constant', scaling='density', axis=-1)
    keep = (frequencies >= 1) & (frequencies <= 40)
    np.testing.assert_array_equal(psd.freqs, frequencies[keep])
    np.testing.assert_allclose(psd.get_data(), expected[..., keep], rtol=1e-12, atol=0)


@pytest.mark.parametrize('n_times,n_fft,seconds', [(300, None, .6), (1000, None, 2),
                                                (5000, None, 4), (1000, 2048, 2),
                                                (5000, 2048, 4)])
def test_documented_welch_full_and_condition_match(monkeypatch, n_times, n_fft, seconds):
    raw, epochs, namespace = _inputs(monkeypatch, n_times, n_fft, seconds)
    before, after, _ = _examples()
    exec(compile(before, str(SKILL), 'exec'), namespace)
    segment = round(seconds * 500)
    _assert_scipy(namespace['psd'], raw.get_data(), segment, n_fft or segment)
    exec(compile(after, str(SKILL), 'exec'), namespace)
    _assert_scipy(namespace['psd'], epochs.get_data(), segment, n_fft or segment)
    np.testing.assert_array_equal(namespace['psd'].freqs, namespace['psd_cond'].freqs)
    np.testing.assert_allclose(namespace['psd_cond'].get_data(),
                               namespace['psd'].get_data()[[0, 2, 4]], rtol=1e-12, atol=0)
    assert namespace['band_power'].shape == (6, 2)
    mask = namespace['freq_mask']
    np.testing.assert_allclose(namespace['band_power'],
                               namespace['psd'].get_data()[..., mask].mean(axis=-1))


def test_documented_welch_rejects_fft_shorter_than_segment(monkeypatch):
    _, _, namespace = _inputs(monkeypatch, 1000, 256)
    before, after, _ = _examples()
    with pytest.raises(ValueError, match='N_FFT must be >= n_per_seg'):
        exec(compile(before, str(SKILL), 'exec'), namespace)
    with pytest.raises(ValueError, match='N_FFT must be >= n_per_seg'):
        exec(compile(after, str(SKILL), 'exec'), namespace)


def test_documented_fixed_length_welch_matches_scipy(monkeypatch):
    _, _, namespace = _inputs(monkeypatch, 1000, None)
    before, _, fixed = _examples()
    exec(compile(before, str(SKILL), 'exec'), namespace)
    exec(compile(fixed, str(SKILL), 'exec'), namespace)
    _assert_scipy(namespace['psd'], namespace['epochs'].get_data(), 1000, 1000)


@pytest.mark.parametrize('key', ['segment_seconds', 'n_fft', 'window', 'overlap_fraction', 'remove_dc'])
def test_missing_welch_choice_fails_instead_of_inserting_a_default(monkeypatch, key):
    _, _, namespace = _inputs(monkeypatch, 1000, None)
    namespace['SPECTRAL_PLAN']['welch'].pop(key)
    before, _, _ = _examples()
    with pytest.raises(ValueError, match=f'Missing approved Welch settings:.*{key}'):
        exec(compile(before, str(SKILL), 'exec'), namespace)


def test_short_epoch_does_not_silently_shorten_approved_segment(monkeypatch):
    _, _, namespace = _inputs(monkeypatch, 300, None, segment_seconds=2)
    before, after, _ = _examples()
    exec(compile(before, str(SKILL), 'exec'), namespace)
    with pytest.raises(ValueError, match='segment duration does not fit'):
        exec(compile(after, str(SKILL), 'exec'), namespace)


@pytest.mark.parametrize('measure', ['integrated_power', 'mean_density', None])
def test_band_measure_is_explicit_and_executed(monkeypatch, measure):
    from scipy.integrate import trapezoid
    _, _, namespace = _inputs(monkeypatch, 1000, None)
    plan = namespace['SPECTRAL_PLAN']
    plan['band_measure'] = measure
    before, after, _ = _examples()
    exec(compile(before, str(SKILL), 'exec'), namespace)
    if measure is None:
        with pytest.raises(ValueError, match='Specify band_measure'):
            exec(compile(after, str(SKILL), 'exec'), namespace)
        return
    exec(compile(after, str(SKILL), 'exec'), namespace)
    psd, mask = namespace['psd'], namespace['freq_mask']
    selected = psd.get_data()[..., mask]
    expected = (trapezoid(selected, psd.freqs[mask], axis=-1)
                if measure == 'integrated_power' else selected.mean(axis=-1))
    np.testing.assert_allclose(namespace['band_power'], expected, rtol=1e-12)


def test_psd_only_does_not_require_unrequested_band_choices(monkeypatch):
    _, _, namespace = _inputs(monkeypatch, 1000, None)
    namespace['SPECTRAL_PLAN'].pop('bands')
    namespace['SPECTRAL_PLAN'].pop('band_measure')
    before, after, _ = _examples()
    exec(compile(before + after, str(SKILL), 'exec'), namespace)
    assert 'psd' in namespace and 'band_power' not in namespace


@pytest.mark.parametrize('has_peak', [True, False])
def test_documented_channel_alpha_peak_example(has_peak):
    text, _ = load_skill_packet(ROOT, 'eeg-spectral', section=
        'Estimate IAPF per channel, then average the estimates (restingIAF) — never peak-find a grand-averaged spectrum')
    code = re.search(r'```python\n(.*?)```', text, re.S).group(1)
    freqs = np.linspace(1, 40, 391)
    channels = ['P3', 'Pz', 'P4', 'PO3', 'POz', 'PO4', 'O1', 'Oz', 'O2']
    centers = np.linspace(9.6, 10.4, len(channels))
    spectra = {channel: 1 + (10 * np.exp(-((freqs - center) / 0.5)**2) if has_peak else np.zeros_like(freqs))
               for channel, center in zip(channels, centers)}
    plan = {'method': 'smoothed_channel_peak', 'channels': channels, 'band_hz': [7, 14],
            'smoothing': {'window_length': 11, 'polyorder': 5}, 'min_prominence': .1,
            'min_channels': 3}
    namespace = {'np': np, 'freqs': freqs, 'psd_ch': spectra, 'ALPHA_PLAN': plan}
    exec(compile(code, str(SKILL), 'exec'), namespace)
    if has_peak:
        assert namespace['iapf'] == pytest.approx(centers.mean(), abs=0.01)
        assert len(namespace['paf_per_chan']) == len(channels)
    else:
        assert namespace['iapf'] is None
        assert namespace['iapf_cog'] is None


@pytest.mark.parametrize('method,expected', [('psd_peak', 10), ('center_of_gravity', 11.2)])
def test_alpha_estimator_dispatch_uses_only_requested_definition(method, expected):
    text, _ = load_skill_packet(ROOT, 'eeg-spectral', section=
        'Phase D — Individual Alpha Peak Frequency (when `— iapf`)')
    code = re.search(r'```python\n(.*?)```', text, re.S).group(1)
    namespace = {'ALPHA_PLAN': {'method': method, 'band_hz': [8, 13],
                               'min_height': 0, 'min_prominence': .1},
                 'freqs': np.array([8., 9., 10., 11., 12., 13.]),
                 'psd': np.array([0., 0., 3., 0., 0., 2.])}
    exec(compile(code, str(SKILL), 'exec'), namespace)
    assert namespace['iapf'] == pytest.approx(expected)


def test_alpha_method_is_not_implicitly_selected():
    text, _ = load_skill_packet(ROOT, 'eeg-spectral', section=
        'Phase D — Individual Alpha Peak Frequency (when `— iapf`)')
    code = re.search(r'```python\n(.*?)```', text, re.S).group(1)
    with pytest.raises(KeyError, match='method'):
        exec(compile(code, str(SKILL), 'exec'), {'ALPHA_PLAN': {'band_hz': [8, 13]}})


def test_approved_ar_does_not_fall_back_when_dependency_is_missing(monkeypatch):
    import builtins
    text, _ = load_skill_packet(ROOT, 'eeg-spectral', section=
        'Parametric (AR) PSD — short-segment / high-resolution alternative to Welch')
    code = re.search(r'```python\n(.*?)```', text, re.S).group(1)
    original_import = builtins.__import__

    def import_without_statsmodels(name, *args, **kwargs):
        if name.startswith('statsmodels'):
            raise ImportError('simulated missing approved dependency')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', import_without_statsmodels)
    raw = mne.io.RawArray(np.zeros((1, 100)), mne.create_info(['Cz'], 100, 'eeg'), verbose=False)
    namespace = {'x_channel': np.zeros(100), 'raw': raw, 'AR_PLAN': {'order': 20},
                 'AR_FREQUENCIES': np.linspace(0, 50, 257)}
    with pytest.raises(ImportError, match='Approved AR analysis requires statsmodels'):
        exec(compile(code, str(SKILL), 'exec'), namespace)
    assert 'psd_obj' not in namespace
