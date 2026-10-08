"""Offline numerical and known-input checks for selected AEA skill operations.

These fixtures test the named kernels/compositions, not full skill workflows or
biological validity. Reference formulas use NumPy/direct sums rather than the
backend routine under test. Source checks share MNE's spherical forward model;
they independently check the inverse calculation, not the head model.

Run from the repository root::

    python tools/tests/support/library_numerics.py --out /tmp/library-numerics.json

The default checks need no downloaded data, language model, GPU, MATLAB or
FreeSurfer. Select ``--checks qc qc_sample`` to include an internal before/after
injection comparison on an already cached MNE sample recording; it never downloads.
Missing optional dependencies are failures in this explicit validation run; pytest may
skip those checks in a minimal installation. Existing result files are not
modified unless explicitly selected with --out.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import tempfile

import mne
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qc_amplitude import amplitude_qc


def _comparison(actual, expected, *, atol, rtol=0.0):
    actual, expected = np.asarray(actual), np.asarray(expected)
    np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol)
    scale = float(np.max(np.abs(expected)))
    error = float(np.max(np.abs(actual - expected)))
    return {"max_abs_error": error, "reference_max_abs": scale,
            "max_error_over_reference_max": error / scale if scale else None,
            "atol": atol, "rtol": rtol}


def check_tfr():
    """Morlet coefficients/power/ITC and baseline units against direct formulas."""
    sfreq = 128.0
    times = np.arange(384) / sfreq - 1.0
    rng = np.random.default_rng(42)
    data = rng.normal(size=(6, 2, times.size)) * 1e-6
    data += (2e-6 * np.sin(2 * np.pi * 10 * times))[None, None, :]
    freqs = np.array([4., 10., 22.])
    cycles = freqs / 2.0  # released eeg-tfr adaptive-cycle convention
    decim = 4
    reference = np.empty((6, 2, len(freqs), times[::decim].size), complex)
    for fi, (freq, n_cycles) in enumerate(zip(freqs, cycles)):
        sigma = n_cycles / (2 * np.pi * freq)
        half = np.ceil(5 * sigma * sfreq).astype(int) - 1
        t_wavelet = np.arange(-half, half + 1) / sfreq
        wavelet = ((np.exp(2j * np.pi * freq * t_wavelet)
                    - np.exp(-n_cycles**2 / 2))
                   * np.exp(-t_wavelet**2 / (2 * sigma**2)))
        wavelet *= np.sqrt(2 / np.sum(abs(wavelet)**2))
        for trial in range(data.shape[0]):
            for ch in range(data.shape[1]):
                reference[trial, ch, fi] = np.convolve(
                    data[trial, ch], wavelet, mode="same")[::decim]
    actual = mne.time_frequency.tfr_array_morlet(
        data, sfreq, freqs, n_cycles=cycles, zero_mean=True,
        use_fft=True, decim=decim, output="complex", n_jobs=1, verbose=False)
    metrics = {"complex_coefficients": _comparison(actual, reference, atol=1e-18)}
    epochs = mne.EpochsArray(data, mne.create_info(["Fz", "Cz"], sfreq, "eeg"),
                             tmin=times[0], baseline=None, verbose=False)
    power, itc = epochs.compute_tfr(
        method="morlet", freqs=freqs, n_cycles=cycles, zero_mean=True,
        use_fft=True, decim=decim, average=True, return_itc=True,
        n_jobs=1, verbose=False)
    expected_power = np.mean(abs(reference)**2, axis=0)
    expected_itc = abs(np.mean(reference / abs(reference), axis=0))
    metrics["power"] = _comparison(power.data, expected_power, atol=1e-24)
    metrics["itc"] = _comparison(itc.data, expected_itc, atol=1e-12)
    baseline = (-0.5, -0.1)
    use = (power.times >= baseline[0]) & (power.times <= baseline[1])
    mean = expected_power[..., use].mean(axis=-1, keepdims=True)
    for mode, expected in {
        "logratio": np.log10(expected_power / mean),
        "percent": (expected_power - mean) / mean,
        "mean": expected_power - mean,
    }.items():
        corrected = power.copy().apply_baseline(baseline, mode=mode, verbose=False)
        metrics[mode] = _comparison(corrected.data, expected, atol=1e-23 if mode == "mean" else 1e-12)
    # dB is a deliberate unit conversion, not a mode accepted by apply_baseline.
    db = 10 * power.copy().apply_baseline(baseline, mode="logratio", verbose=False).data
    metrics["db"] = _comparison(db, 10 * np.log10(expected_power / mean), atol=1e-11)
    percent = 100 * power.copy().apply_baseline(baseline, mode="percent", verbose=False).data
    metrics["percent_units"] = _comparison(percent, 100 * (expected_power - mean) / mean, atol=1e-10)
    return {"skill": "eeg-tfr", "scope": "zero-mean Morlet, adaptive cycles, decim=4; power, ITC, baseline units",
            "reference": "explicit Gaussian wavelet plus direct time-domain convolution",
            "metrics": metrics}


def check_connectivity():
    """Debiased squared wPLI in the supported Fourier mode, no band averaging."""
    from mne_connectivity import spectral_connectivity_epochs
    rng = np.random.default_rng(42)
    sfreq, n_times, n_epochs = 128., 256, 24
    times = np.arange(n_times) / sfreq
    data = rng.normal(scale=0.3, size=(n_epochs, 3, n_times))
    for epoch in range(n_epochs):
        phase = rng.uniform(-np.pi, np.pi)
        data[epoch, 0] += np.sin(2 * np.pi * 10 * times + phase)
        data[epoch, 1] += np.sin(2 * np.pi * 10 * times + phase + 0.8)
    indices = (np.array([1, 2, 2]), np.array([0, 0, 1]))
    actual = spectral_connectivity_epochs(
        data, sfreq=sfreq, method="wpli2_debiased", mode="fourier",
        indices=indices, fmin=8., fmax=13., faverage=False, n_jobs=1, verbose=False)
    # Explicit DFT, avoiding MNE/SciPy's spectral helpers. Symmetric Hann matches
    # spectral_connectivity_epochs(mode='fourier'); scale factors cancel in wPLI².
    freqs = np.asarray(actual.freqs)
    centered = data - data.mean(axis=-1, keepdims=True)
    spectra = (centered * np.hanning(n_times)) @ np.exp(-2j * np.pi * times[:, None] * freqs)
    reference = []
    for a, b in zip(*indices):
        imaginary = (spectra[:, a] * spectra[:, b].conj()).imag
        square_sum = np.sum(imaginary**2, axis=0)
        numerator = np.sum(imaginary, axis=0)**2 - square_sum
        denominator = np.sum(abs(imaginary), axis=0)**2 - square_sum
        reference.append(numerator / denominator)
    reference = np.asarray(reference)
    return {"skill": "eeg-connectivity", "scope": "wpli2_debiased, Fourier mode, three edges, 8–13 Hz bins",
            "reference": "direct DFT and debiased imaginary-cross-spectrum moment formula",
            "metrics": _comparison(actual.get_data(), reference, atol=1e-12),
            "excludes": "multitaper, time-resolved estimators, PAC and biological connectivity claims"}


def check_ica():
    """Recover three known sources from a rank-three four-channel mixture."""
    from scipy.optimize import linear_sum_assignment
    rng = np.random.default_rng(42)
    sfreq, n_times = 250., 8000
    t = np.arange(n_times) / sfreq
    sources = np.array([rng.laplace(size=n_times), rng.uniform(-1, 1, n_times),
                        np.sin(2 * np.pi * 11 * t)])
    sources -= sources.mean(axis=1, keepdims=True)
    sources /= sources.std(axis=1, keepdims=True)
    mixing = np.array([[1., .3, .7], [.2, 1., -.4], [-.8, .1, 1.2], [-.4, -.6, .3]])
    mixing -= mixing.mean(axis=0)
    info = mne.create_info(["Fz", "Cz", "Pz", "Oz"], sfreq, "eeg")
    raw = mne.io.RawArray(mixing @ sources * 1e-5, info, verbose=False)
    raw.filter(1., None, verbose=False)
    # Filter the known sources identically solely to express ground truth at the
    # ICA input. This does not independently certify the high-pass filter.
    truth = mne.filter.filter_data(sources, sfreq, 1., None, verbose=False)
    ica = mne.preprocessing.ICA(n_components=3, method="infomax", random_state=42,
                                max_iter="auto", fit_params={"extended": True})
    ica.fit(raw, verbose=False)
    estimated = ica.get_sources(raw).get_data()
    correlations = abs(np.corrcoef(truth, estimated)[:3, 3:])
    source_ids, component_ids = linear_sum_assignment(-correlations)
    matched = correlations[source_ids, component_ids]
    assert matched.min() >= 0.98, matched
    # This known-source exclusion tests reconstruction; it is not ICLabel or
    # automatic ocular/muscle classification.
    excluded = int(component_ids[np.where(source_ids == 0)[0][0]])
    cleaned = ica.apply(raw.copy(), exclude=[excluded], verbose=False).get_data()
    expected = mixing[:, 1:] @ truth[1:] * 1e-5
    relative_rmse = float(np.linalg.norm(cleaned - expected) / np.linalg.norm(expected))
    assert relative_rmse < 0.1, relative_rmse
    retained = ica.apply(raw.copy(), exclude=[], verbose=False).get_data()
    return {"skill": "eeg-ica", "scope": "extended Infomax on a known rank-three mixture; specified component removal",
            "reference": "known sources, permutation/sign-invariant matching and known clean mixture",
            "min_absolute_source_correlation": float(matched.min()), "minimum_accepted_correlation": 0.98,
            "clean_relative_rmse": relative_rmse, "maximum_accepted_relative_rmse": 0.1,
            "no_exclusion_reconstruction": _comparison(retained, raw.get_data(), atol=1e-15),
            "iterations": int(ica.n_iter_), "max_iter": "auto", "excludes": "ICLabel, real artifact identification and arbitrary mixtures"}


def check_source():
    """Basic MNE and dSPM inverses against a direct ridge/noise formula."""
    chs = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2", "Fz", "Cz", "Pz"]
    info = mne.create_info(chs, 100., "eeg")
    info.set_montage("standard_1020")
    raw = mne.io.RawArray(np.zeros((len(chs), 101)), info, verbose=False)
    raw.set_eeg_reference("average", projection=True, verbose=False)
    info = raw.info
    source = mne.setup_volume_source_space(
        pos={"rr": np.array([[-.03, 0, .04], [.03, 0, .04], [0, -.025, .045]]),
             "nn": np.tile([0., 0., 1.], (3, 1))}, sphere=(0, 0, 0, .09), verbose=False)
    sphere = mne.make_sphere_model(r0=(0, 0, 0), head_radius=.09, verbose=False)
    forward = mne.make_forward_solution(info, trans=None, src=source, bem=sphere,
                                        eeg=True, meg=False, mindist=0, verbose=False)
    forward = mne.convert_forward_solution(forward, surf_ori=True, force_fixed=True,
                                           copy=True, verbose=False)
    gain = forward["sol"]["data"]
    noise_var = 1e-12
    noise_cov = mne.Covariance(noise_var * np.eye(len(chs)), chs, [], [], 100)
    inverse = mne.minimum_norm.make_inverse_operator(
        info, forward, noise_cov, loose=0., depth=None, fixed=True, rank="info", verbose=False)
    t = np.arange(101) / 100.
    currents = np.array([np.sin(2*np.pi*7*t), np.cos(2*np.pi*11*t), np.sin(2*np.pi*13*t)]) * 1e-9
    measurements = gain @ currents
    evoked = mne.EvokedArray(measurements, info, tmin=0., nave=1, verbose=False)
    projector = np.eye(len(chs)) - np.ones((len(chs), len(chs))) / len(chs)
    projected_gain = projector @ gain
    # Uniform source prior rescaled so the whitened gain has squared norm rank.
    prior = (len(chs) - 1) * noise_var / np.sum(projected_gain**2)
    lambda2 = 1 / 9
    kernel = prior * projected_gain.T @ np.linalg.pinv(
        prior * projected_gain @ projected_gain.T + lambda2 * noise_var * projector,
        hermitian=True) @ projector
    expected = kernel @ measurements
    mne_result = mne.minimum_norm.apply_inverse(evoked, inverse, lambda2, method="MNE", verbose=False)
    dspm_result = mne.minimum_norm.apply_inverse(evoked, inverse, lambda2, method="dSPM", verbose=False)
    expected_dspm = expected / np.sqrt(noise_var * np.sum(kernel**2, axis=1, keepdims=True))
    return {"skill": "eeg-source", "scope": "fixed-orientation, depth=None, spherical leadfield, average reference, lambda2=1/9",
            "reference": "direct regularized linear inverse and rowwise noise normalization",
            "metrics": {"MNE": _comparison(mne_result.data, expected, atol=1e-20),
                        "dSPM": _comparison(dspm_result.data, expected_dspm, atol=1e-10)},
            "excludes": "forward-model correctness, individual MRI, default depth=3/loose=.2, beamformers and localization accuracy"}


def check_decoding():
    """MNE grouped fold/time dispatch against explicit train-only pipelines."""
    from mne.decoding import SlidingEstimator, cross_val_multiscore
    from sklearn.base import clone
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(42)
    # Each group contains opposite labels with identical nuisance features.
    # Hence every fold's null-time accuracy is exactly .5, rather than a noisy
    # chance threshold that occasionally fails by sampling variation.
    groups = np.repeat(np.arange(18), 2)
    labels = np.tile([0, 1], 18)
    features = np.repeat(rng.normal(size=(18, 3, 5)), 2, axis=0)
    features[:, 0, 2:4] = (2 * labels[:, None] - 1) * 10
    folds = list(GroupKFold(3).split(features, labels, groups))
    pipeline = make_pipeline(StandardScaler(), LogisticRegression(C=1., solver="liblinear", random_state=42))
    sliding = SlidingEstimator(pipeline, scoring="accuracy", n_jobs=1, verbose=False)
    observed = cross_val_multiscore(sliding, features, labels, cv=folds, n_jobs=1, verbose=False)
    expected = np.zeros_like(observed)
    fold_sizes = []
    for fold, (train, test) in enumerate(folds):
        assert set(groups[train]).isdisjoint(groups[test])
        fold_sizes.append({"train": len(train), "test": len(test)})
        for time in range(features.shape[-1]):
            fitted = clone(pipeline).fit(features[train, :, time], labels[train])
            expected[fold, time] = np.mean(fitted.predict(features[test, :, time]) == labels[test])
    np.testing.assert_array_equal(observed[:, [0, 1, 4]], .5)
    np.testing.assert_array_equal(observed[:, [2, 3]], 1.)
    return {"skill": "eeg-decoding", "scope": "SlidingEstimator and group-disjoint CV on injected signal and paired null features",
            "reference": "explicit fold/time loop; same sklearn estimator, so not independent classifier certification",
            "metrics": _comparison(observed, expected, atol=0.), "scores": observed.tolist(),
            "fold_sizes": fold_sizes, "excludes": "real-data predictive accuracy and arbitrary generated split logic"}


def check_complexity():
    """Normalized permutation entropy against an explicit ordinal histogram."""
    import antropy
    rng = np.random.default_rng(42)
    metrics = {}
    for label, signal in {"monotonic": np.arange(256.), "noise": rng.normal(size=256)}.items():
        counts = Counter(tuple(np.argsort(signal[start:start+3])) for start in range(len(signal)-2))
        probabilities = np.array(list(counts.values())) / (len(signal)-2)
        expected = -np.sum(probabilities * np.log(probabilities)) / np.log(6.)
        observed = antropy.perm_entropy(signal, order=3, delay=1, normalize=True)
        metrics[label] = _comparison(observed, expected, atol=1e-14)
        metrics[label]["value"] = float(observed)
    return {"skill": "eeg-complexity", "scope": "permutation entropy, order=3, delay=1, distinct-valued fixtures",
            "reference": "explicit ordinal-pattern counts and Shannon entropy",
            "metrics": metrics, "excludes": "sample entropy, Lempel–Ziv, DFA, criticality and clinical interpretation"}


def check_microstate():
    """Observed transition matrix against literal changes in a known label stream."""
    from pycrostates.segmentation import compute_transition_matrix
    labels = np.array([0, 0, 1, 1, 2, 2, 0, 2, 2, -1, -1, 1, 0, 0, 1])
    counts = np.zeros((3, 3))
    for a, b in zip(labels[:-1], labels[1:]):
        if a >= 0 and b >= 0 and a != b:
            counts[a, b] += 1
    expected = counts / counts.sum(axis=1, keepdims=True)
    observed = compute_transition_matrix(labels, n_clusters=3, stat="probability", ignore_repetitions=True)
    return {"skill": "eeg-microstate", "scope": "observed transitions; repeated labels and unlabeled segments excluded",
            "reference": "literal adjacent-state counts", "counts": counts.tolist(),
            "metrics": _comparison(observed, expected, atol=1e-14),
            "excludes": "cluster fitting, template validity, duration/coverage and biological state interpretation"}


def check_bids():
    """BrainVision BIDS round trip preserves volts, channel identity and events."""
    from mne_bids import BIDSPath, read_raw_bids, write_raw_bids
    import pybv  # noqa: F401 -- writer is needed, not just the mne-bids interface
    sfreq = 250.
    t = np.arange(1000) / sfreq
    data = np.array([20e-6 * np.sin(2*np.pi*10*t), 40e-6 * np.cos(2*np.pi*7*t)])
    raw = mne.io.RawArray(data, mne.create_info(["Fz", "Cz"], sfreq, "eeg"), verbose=False)
    raw.info["line_freq"] = 50.
    raw.info["bads"] = ["Cz"]
    events = np.array([[125, 0, 1], [500, 0, 2], [875, 0, 1]])
    with tempfile.TemporaryDirectory(prefix="aea-bids-numerics-") as folder:
        path = BIDSPath(subject="01", task="numerics", datatype="eeg", root=folder)
        write_raw_bids(raw, path, events=events, event_id={"target": 1, "standard": 2},
                       allow_preload=True, format="BrainVision", overwrite=True, verbose=False)
        restored = read_raw_bids(path, verbose=False)
        got_events, _ = mne.events_from_annotations(restored, event_id={"target": 1, "standard": 2}, verbose=False)
        assert restored.ch_names == raw.ch_names
        assert restored.get_channel_types() == ["eeg", "eeg"]
        assert restored.info["bads"] == ["Cz"]
        assert restored.info["sfreq"] == sfreq
        np.testing.assert_array_equal(got_events, events)
        metrics = _comparison(restored.get_data(), data, atol=1e-11)
    return {"skill": "eeg-bids", "scope": "synthetic BrainVision round trip: signal units, channels, bad status, sample-aligned events",
            "reference": "original in-memory values and metadata", "metrics": metrics,
            "excludes": "all input formats and complete BIDS Validator conformance"}


def check_qc():
    """Test the distinct constant, low-amplitude and rapid-change diagnostics."""
    normal_controls = []
    for sfreq in (128., 250., 1000.):
        t = np.arange(int(2 * sfreq)) / sfreq
        for frequency in (1., 10., 40.):
            for phase in (0., .3, np.pi / 2):
                data = 20e-6 * np.sin(2 * np.pi * frequency * t + phase)
                raw = mne.io.RawArray(data[None], mne.create_info(["normal"], sfreq, "eeg"), verbose=False)
                result = amplitude_qc(raw)
                assert not result["constant_segments"], result
                assert not result["jump_segments"], result
                assert not result["bad_channel_candidates"], result
                normal_controls.append({"sfreq": sfreq, "frequency": frequency,
                    "phase": float(phase), "constant_count": 0, "jump_count": 0,
                    "bad_channel_candidates": [],
                    "low_amplitude_warning_count": len(result["low_amplitude_warnings"])})

    sfreq = 250.
    t = np.arange(2500) / sfreq
    data = np.array([20e-6 * np.sin(2*np.pi*10*t + phase) for phase in [0., .3, .6]])
    info = mne.create_info(["clean", "flat", "transient"], sfreq, "eeg")
    clean = mne.io.RawArray(data, info, verbose=False)
    clean_result = amplitude_qc(clean)
    assert not clean_result["bad_channel_candidates"]
    assert not clean_result["constant_segments"] and not clean_result["jump_segments"]

    corrupt = data.copy()
    corrupt[1] = 0
    corrupt[2, 500:550] = 0
    corrupt[2, 1000:1008] = np.tile([-300e-6, 300e-6], 4)
    raw = mne.io.RawArray(corrupt, info, verbose=False)
    injected = amplitude_qc(raw)
    assert injected["bad_channel_candidates"] == ["flat"], injected
    # Expected locations derive from literal injected sample ranges, not the
    # detector's run-finding code. A run of 50 equal samples spans 49 intervals.
    constant = next(s for s in injected["constant_segments"] if s["channel"] == "transient")
    np.testing.assert_allclose([constant["onset"], constant["duration"]], [500 / sfreq, 49 / sfreq], atol=1e-12)
    jump = next(s for s in injected["jump_segments"] if s["channel"] == "transient")
    # Eight alternating samples plus entry/exit transitions occupy nine intervals.
    np.testing.assert_allclose([jump["onset"], jump["duration"]], [999 / sfreq, 9 / sfreq], atol=1e-12)
    np.testing.assert_array_equal(raw.get_data(), corrupt)
    assert not raw.info["bads"] and len(raw.annotations) == 0

    low = mne.io.RawArray((.1e-6 * np.sin(2*np.pi*10*t))[None],
                         mne.create_info(["low"], sfreq, "eeg"), verbose=False)
    low_result = amplitude_qc(low)
    assert len(low_result["low_amplitude_warnings"]) == 100
    assert not low_result["bad_channel_candidates"]
    assert not low_result["constant_segments"] and not low_result["jump_segments"]

    # Retain the old released rule as a measured before/after comparison. Its
    # failure remains in the dated result files, which this run does not replace.
    legacy_annotations, legacy_bads = mne.preprocessing.annotate_amplitude(
        clean, peak={"eeg": 150e-6}, flat={"eeg": 5e-7}, bad_percent=5.,
        min_duration=.005, verbose=False)
    return {"status": "pass", "skill": "eeg-qc",
            "scope": "constant spans, window PTP warnings and rapid changes on specified synthetic controls",
            "reference": "literal injected sample ranges and known analytic waveforms",
            "mechanism_checks_passed": True, "sine_negative_control_passed": True,
            "normal_waveform_controls": normal_controls,
            "sine_fixture": "three 20 microvolt 10 Hz sinusoids, phases 0/.3/.6 rad, 250 Hz sampling",
            "legacy_adjacent_difference_rule": {"bad_channels": legacy_bads,
                "annotation_count": len(legacy_annotations),
                "negative_control_passed": not legacy_bads and len(legacy_annotations) == 0},
            "new_rule_clean_control": clean_result, "injected_control": injected,
            "low_amplitude_control": low_result,
            "excludes": "clinical QC sensitivity, arbitrary artifacts, LOF, RANSAC and full skill workflows"}


def check_qc_sample():
    """Internal cached-recording comparison; original data are not clean ground truth."""
    from regression_pipeline import resolve_raw_path

    source = resolve_raw_path(download=False)
    raw = mne.io.read_raw_fif(source, preload=False, verbose=False)
    picks = mne.pick_types(raw.info, meg=False, eeg=True, exclude="bads")[:3]
    raw.pick(picks).crop(tmin=0., tmax=10.).load_data(verbose=False)
    original = raw.get_data()
    before = amplitude_qc(raw)
    corrupt = original.copy()
    sfreq = raw.info["sfreq"]
    dropout_start, dropout_stop = int(round(2 * sfreq)), int(round(2.2 * sfreq))
    jump_start = int(round(4 * sfreq))
    jump_length = 8
    corrupt[0] = 0.
    corrupt[1, dropout_start:dropout_stop] = 0.
    corrupt[2, jump_start:jump_start + jump_length] = np.tile([-300e-6, 300e-6], 4)
    injected_raw = mne.io.RawArray(corrupt, raw.info.copy(), first_samp=raw.first_samp, verbose=False)
    after = amplitude_qc(injected_raw)
    assert raw.ch_names[0] in after["bad_channel_candidates"]
    whole = next(s for s in after["constant_segments"] if s["channel"] == raw.ch_names[0])
    np.testing.assert_allclose([whole["onset"], whole["duration"]], [0., (raw.n_times - 1) / sfreq], atol=1e-12)
    dropout = [s for s in after["constant_segments"] if s["channel"] == raw.ch_names[1]
               and abs(s["onset"] - dropout_start / sfreq) < 1e-12]
    assert len(dropout) == 1, after
    np.testing.assert_allclose(dropout[0]["duration"], (dropout_stop - dropout_start - 1) / sfreq, atol=1e-12)
    jump = [s for s in after["jump_segments"] if s["channel"] == raw.ch_names[2]
            and abs(s["onset"] - (jump_start - 1) / sfreq) < 1e-12]
    assert len(jump) == 1, after
    np.testing.assert_allclose(jump[0]["duration"], (jump_length + 1) / sfreq, atol=1e-12)
    # The unmodified recording has no constant/rapid-change event covering the
    # injected interval centers; other original findings remain in the report.
    for channel, key, point in [(raw.ch_names[1], "constant_segments", (dropout_start + dropout_stop - 1) / (2 * sfreq)),
                                (raw.ch_names[2], "jump_segments", (jump_start + 3) / sfreq)]:
        assert not any(s["channel"] == channel and s["onset"] <= point <= s["onset"] + s["duration"]
                       for s in before[key]), before
    np.testing.assert_array_equal(raw.get_data(), original)
    np.testing.assert_array_equal(injected_raw.get_data(), corrupt)
    return {"skill": "eeg-qc", "scope": "internal before/after injection on the first 10 seconds and first three usable EEG channels of cached MNE sample",
            "source": str(source), "sfreq": float(sfreq), "channels": raw.ch_names,
            "first_samp": int(raw.first_samp), "n_times": int(raw.n_times),
            "injections": {"whole_constant": {"channel": raw.ch_names[0]},
                "dropout": {"channel": raw.ch_names[1], "start_sample": dropout_start, "stop_sample_exclusive": dropout_stop},
                "rapid_change": {"channel": raw.ch_names[2], "start_sample": jump_start, "stop_sample_exclusive": jump_start + jump_length}},
            "original_recording": before, "with_injections": after,
            "input_data_unchanged": True,
            "excludes": "ground-truth quality labels for the original recording, clinical sensitivity and other skills"}


CHECKS = {"tfr": check_tfr, "connectivity": check_connectivity, "ica": check_ica,
          "source": check_source, "decoding": check_decoding, "complexity": check_complexity,
          "microstate": check_microstate, "bids": check_bids, "qc": check_qc,
          "qc_sample": check_qc_sample}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--checks", nargs="+", choices=CHECKS,
                        default=[name for name in CHECKS if name != "qc_sample"])
    args = parser.parse_args()
    mne.set_log_level("ERROR")
    versions = {}
    for name in ["numpy", "scipy", "mne", "scikit-learn", "mne-connectivity", "antropy", "pycrostates", "mne-bids", "pybv"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "versions": versions, "fixture_seed": 42, "checks": {}}
    for name in args.checks:
        try:
            result["checks"][name] = {"status": "pass", **CHECKS[name]()}
        except (AssertionError, ImportError) as error:
            result["checks"][name] = {"status": "fail", "error": f"{type(error).__name__}: {error}"}
        print(f"{name}: {result['checks'][name]['status']}", flush=True)
    result["passed"] = all(check["status"] == "pass" for check in result["checks"].values())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
