"""Amplitude diagnostics for EEG: constant spans, low amplitude, rapid changes.

The function returns findings without changing data, annotations or bad-channel
metadata. Low amplitude is always a warning, never a bad-channel candidate.
"""
from __future__ import annotations

import mne
import numpy as np


def _runs(mask):
    """Half-open index ranges of contiguous True entries."""
    boundaries = np.diff(np.r_[False, mask, False].astype(int))
    return zip(np.flatnonzero(boundaries == 1), np.flatnonzero(boundaries == -1))


def amplitude_qc(
    raw,
    *,
    constant_min_duration=0.02,
    low_amplitude_window=0.1,
    low_amplitude_ptp=0.5e-6,
    jump_threshold=150e-6,
    jump_min_duration=0.005,
    bad_percent=5.0,
):
    """Return amplitude findings for every EEG channel, including existing bads.

    Parameters use seconds and volts. ``constant_min_duration`` is the observed
    elapsed time across identical samples: at 250 Hz, six identical samples span
    five intervals, or 20 ms. Rapid changes use their own duration threshold.
    Neither criterion depends on the low-amplitude window duration.

    Low amplitude is the peak-to-peak range in non-overlapping windows of
    ``ceil(low_amplitude_window * sfreq)`` samples. A final incomplete window is
    omitted and its sample count is reported. Unlike a constant segment, a low
    amplitude window can contain a legitimate oscillation or a slow-wave extremum.

    Returns
    -------
    findings : dict
        ``constant_segments``, ``jump_segments`` and ``low_amplitude_warnings``
        contain ``channel``, ``onset`` and ``duration``. Times are relative to
        the first recording sample. Constant/jump durations count consecutive
        sample intervals; low-amplitude durations describe the full sample-bin
        window. Low-amplitude entries also retain ``peak_to_peak`` in volts.
        ``per_channel`` reports each retained segment type's fraction of the
        ``n_times - 1`` observed intervals and ``candidate_reasons``.
        ``bad_channel_candidates`` includes channels above ``bad_percent`` for
        constant or rapid-change segments, but never because of low amplitude.
        These are diagnostic candidates, not an instruction to reject data.
    """
    if constant_min_duration <= 0 or jump_min_duration <= 0:
        raise ValueError("Duration thresholds must be positive.")
    if low_amplitude_window <= 0 or low_amplitude_ptp < 0 or jump_threshold <= 0:
        raise ValueError("Window and jump thresholds must be positive; low-amplitude PTP must be nonnegative.")
    if not 0 <= bad_percent <= 100:
        raise ValueError("bad_percent must be between 0 and 100.")
    picks = mne.pick_types(raw.info, meg=False, eeg=True, exclude=[])
    if not len(picks):
        raise ValueError("Amplitude QC requires EEG channels.")
    n_times = int(raw.n_times)
    if n_times < 2:
        raise ValueError("Amplitude QC requires at least two samples.")
    sfreq = float(raw.info["sfreq"])
    window_samples = int(np.ceil(low_amplitude_window * sfreq))
    if window_samples < 2:
        raise ValueError("The low-amplitude window must contain at least two samples.")
    result = {
        "constant_segments": [], "low_amplitude_warnings": [], "jump_segments": [],
        "per_channel": {}, "bad_channel_candidates": [],
        "settings": {
            "constant_min_duration": float(constant_min_duration),
            "low_amplitude_window": float(low_amplitude_window),
            "low_amplitude_window_samples": window_samples,
            "low_amplitude_ptp": float(low_amplitude_ptp),
            "jump_threshold": float(jump_threshold), "jump_min_duration": float(jump_min_duration),
            "bad_percent": float(bad_percent), "sfreq": sfreq,
        },
        "ignored_tail_samples": n_times % window_samples,
    }
    for channel, values in zip(np.array(raw.ch_names)[picks], raw.get_data(picks=picks)):
        channel = str(channel)
        delta = np.diff(values)
        counts = {}
        for kind, output, mask, duration_threshold in [
            ("constant", "constant_segments", delta == 0, constant_min_duration),
            ("rapid_change", "jump_segments", abs(delta) >= jump_threshold, jump_min_duration),
        ]:
            count = 0
            for start, stop in _runs(mask):
                duration = float((stop - start) / sfreq)
                if duration >= duration_threshold:
                    result[output].append({"channel": channel, "onset": float(start / sfreq),
                                           "duration": duration})
                    count += stop - start
            counts[kind] = float(count / (n_times - 1))
        reasons = [kind for kind, fraction in counts.items() if 100 * fraction > bad_percent]
        result["per_channel"][channel] = {
            "constant_fraction": counts["constant"], "jump_fraction": counts["rapid_change"],
            "candidate_reasons": reasons,
        }
        if reasons:
            result["bad_channel_candidates"].append(channel)
        for start in range(0, n_times - window_samples + 1, window_samples):
            ptp = float(np.ptp(values[start:start + window_samples]))
            if ptp <= low_amplitude_ptp:
                result["low_amplitude_warnings"].append({
                    "channel": channel, "onset": float(start / sfreq),
                    "duration": window_samples / sfreq, "peak_to_peak": ptp,
                })
    return result
