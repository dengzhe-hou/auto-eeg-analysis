"""Run the documented Welch examples and compare real PSDs with SciPy."""
from pathlib import Path
import re

import mne
import numpy as np
import pytest
from scipy.signal import welch

SKILL = Path(__file__).resolve().parents[2] / 'skills/eeg-spectral/SKILL.md'


def _examples():
    text = SKILL.read_text(encoding="utf-8-sig")
    main = re.findall(r'```python\n(.*?)```', text, re.S)[0]
    before, after = main.split('# Task-related: epoched data', 1)
    fixed = text.split('### Fixed-length epoching of continuous resting data', 1)[1]
    fixed = re.search(r'```python\n(.*?)```', fixed, re.S).group(1)
    return before, after, fixed


def _inputs(monkeypatch, n_times, n_fft):
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
    namespace = {'FMIN': 1, 'FMAX': 40, 'N_FFT': n_fft, 'WINDOW': 'hann',
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


@pytest.mark.parametrize('n_times,n_fft', [(300, None), (1000, None), (5000, None),
                                         (1000, 2048), (5000, 2048)])
def test_documented_welch_full_and_condition_match(monkeypatch, n_times, n_fft):
    raw, epochs, namespace = _inputs(monkeypatch, n_times, n_fft)
    before, after, _ = _examples()
    exec(compile(before, str(SKILL), 'exec'), namespace)
    _assert_scipy(namespace['psd'], raw.get_data(), 1000, n_fft or 1000)
    exec(compile(after, str(SKILL), 'exec'), namespace)
    segment = min(1000, n_times)
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
