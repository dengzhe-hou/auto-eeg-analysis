"""Spectral primitives using approved, explicitly supplied settings."""
import numpy as np
import mne
from scipy.integrate import trapezoid


def welch_parameters(sfreq, n_times, *, segment_seconds, window,
                     overlap_fraction, n_fft, remove_dc, average):
    """Translate explicit settings to MNE keywords without changing the plan."""
    samples = round(segment_seconds * sfreq)
    overlap = round(samples * overlap_fraction)
    fft = samples if n_fft is None else int(n_fft)
    if samples < 2 or samples > n_times or not 0 <= overlap < samples or fft < samples:
        raise ValueError("Approved Welch settings must fit the actual segment")
    return dict(n_fft=fft, n_per_seg=samples, n_overlap=overlap,
                window=window, remove_dc=remove_dc, average=average)


def welch_psd(data, sfreq, *, segment_seconds, window, overlap_fraction, n_fft, remove_dc, average):
    """Return Hz and PSD with the original leading axes; EEG input is in V."""
    data = np.atleast_2d(np.asarray(data, dtype=float))
    settings = welch_parameters(sfreq, data.shape[-1],
        segment_seconds=segment_seconds, window=window,
        overlap_fraction=overlap_fraction, n_fft=n_fft, remove_dc=remove_dc,
        average=average)
    psd, freqs = mne.time_frequency.psd_array_welch(
        data, sfreq=sfreq, **settings, verbose=False)
    return freqs, psd


def band_bins(freqs, *, band, upper_closed):
    """Select approved bins only when the retained axis covers both bounds.

    This does not interpolate boundary bins or recover a filtered-out band.
    Supply the full PSD axis instead of silently integrating an intersection.
    """
    freqs = np.asarray(freqs)
    if freqs.ndim != 1:
        raise ValueError("Frequency bins must be one-dimensional. AEA Welch returns (freqs, psd); MNE psd_array_welch returns (psd, freqs)")
    if not len(freqs) or not freqs[0] <= band[0] <= band[1] <= freqs[-1]:
        raise ValueError("Requested band is not fully covered by the retained frequency axis")
    return (freqs >= band[0]) & ((freqs <= band[1]) if upper_closed else (freqs < band[1]))


def integrated_power(psd, freqs, *, band, upper_closed):
    freqs = np.asarray(freqs)
    psd = np.asarray(psd)
    mask = band_bins(freqs, band=band, upper_closed=upper_closed)
    if psd.ndim < 1 or psd.shape[-1] != len(freqs):
        raise ValueError("PSD's last axis must match the frequency bins; check the Welch return order before indexing or reshaping")
    if np.count_nonzero(mask) < 2:
        raise ValueError("Requested band contains fewer than two PSD bins")
    return trapezoid(psd[..., mask], freqs[mask], axis=-1)


def channel_relative_power(psd, freqs, *, band, total_band, upper_closed, total_upper_closed):
    numerator = integrated_power(psd, freqs, band=band, upper_closed=upper_closed)
    denominator = integrated_power(psd, freqs, band=total_band, upper_closed=total_upper_closed)
    if np.any(denominator <= 0):
        raise ValueError("Relative power needs a positive denominator")
    return numerator / denominator


def band_power_summary(psd, freqs, *, bands, power_kind, aggregation, total_band):
    """Apply an explicit power definition, returning values and the actual bins.

    Each band is {"band": [low, high], "upper_closed": bool}. Absolute power
    needs total_band=None. Relative power needs a denominator in the same form.
    No definition, channel weighting or integration boundary is inferred.
    """
    psd = np.asarray(psd)
    if psd.ndim != 2:
        raise ValueError("Band summaries need channel x frequency PSD")
    if not bands:
        raise ValueError("Supply the approved named bands")
    if power_kind not in ("absolute", "relative"):
        raise ValueError("Resolve power_kind as absolute or relative before computation")
    allowed = ("mean_channel_power",) if power_kind == "absolute" else (
        "mean_channel_ratios", "ratio_of_channel_means")
    if aggregation not in allowed:
        raise ValueError(f"Resolve aggregation for {power_kind} power: {allowed}")
    if (power_kind == "absolute") != (total_band is None):
        raise ValueError("Absolute power needs no denominator; relative power needs an explicit total_band")
    powers, bins = {}, {}
    for name, definition in bands.items():
        if not isinstance(definition["upper_closed"], bool):
            raise ValueError("Each band needs an explicit boolean upper_closed")
        powers[name] = integrated_power(psd, freqs, **definition)
        bins[name] = np.asarray(freqs)[band_bins(freqs, **definition)].tolist()
    denominator = None
    if total_band is not None:
        if not isinstance(total_band["upper_closed"], bool):
            raise ValueError("The denominator needs an explicit boolean upper_closed")
        denominator = integrated_power(psd, freqs, **total_band)
        if np.any(denominator <= 0):
            raise ValueError("Relative power needs a positive denominator per channel")
        bins["total"] = np.asarray(freqs)[band_bins(freqs, **total_band)].tolist()
    values = {}
    for name, power in powers.items():
        if power_kind == "absolute":
            values[name] = float(power.mean())
        elif aggregation == "mean_channel_ratios":
            values[name] = float((power / denominator).mean())
        else:
            values[name] = float(power.mean() / denominator.mean())
    maximum = max(values.values())
    return {"values": values, "dominant_bands": [name for name, value in values.items() if value == maximum],
            "selected_frequencies_hz": bins,
            "power_kind": power_kind, "aggregation": aggregation}


def maximum_bin_peak(psd, freqs, *, band):
    """Approved maximum-bin estimator only: inclusive bounds, earliest tie."""
    freqs = np.asarray(freqs)
    mask = band_bins(freqs, band=band, upper_closed=True)
    if not np.any(mask):
        raise ValueError("Approved peak band contains no bins")
    return freqs[mask][np.argmax(np.asarray(psd)[..., mask], axis=-1)]


def resolved_welch_settings(plan):
    """Use canonical remove_dc/null FFT or the retained detrend/n_per_seg form.

    These two interfaces already occur in AEA. Missing scientific choices are
    not filled. A contradictory declaration is an error, not an override.
    """
    if "detrend" in plan and plan["detrend"] not in ("constant", False):
        raise ValueError("This Welch implementation supports constant or no detrending")
    if "remove_dc" in plan:
        remove_dc = plan["remove_dc"]
        if not isinstance(remove_dc, bool):
            raise ValueError("Approved remove_dc must be a boolean")
        if "detrend" in plan and remove_dc != (plan["detrend"] == "constant"):
            raise ValueError("Conflicting approved remove_dc and detrend settings")
    else:
        remove_dc = plan["detrend"] == "constant"
    fft = plan["n_fft"]
    return dict(segment_seconds=plan["segment_seconds"], window=plan["window"],
                overlap_fraction=plan["overlap_fraction"],
                n_fft=None if fft == "n_per_seg" else fft,
                remove_dc=remove_dc, average=plan["average"])


def welch_from_plan(data, sfreq, *, plan):
    """Use resolved Welch settings; a frequency integration band is not a filter."""
    return welch_psd(data, sfreq, **resolved_welch_settings(plan))


def personalized_alpha_power(psd, freqs, *, search_band, offsets, total_band,
                             center_mode, upper_closed, total_upper_closed):
    """Distinguish a band centered on the mean peak from per-channel bands.

    All bounds and the choice of center come from the approved plan. Return
    per-channel ratios; any subsequent aggregation must also follow that plan.
    """
    psd = np.atleast_2d(psd)
    peaks = maximum_bin_peak(psd, freqs, band=search_band)
    mean_peak = float(peaks.mean())
    if center_mode == "mean_peak":
        centers = np.full(len(peaks), mean_peak)
    elif center_mode == "per_channel_peak":
        centers = peaks.copy()
    else:
        raise ValueError("Approve center_mode='mean_peak' or 'per_channel_peak'")
    ratios = np.asarray([
        channel_relative_power(row[None, :], freqs,
            band=(center + offsets[0], center + offsets[1]), total_band=total_band,
            upper_closed=upper_closed, total_upper_closed=total_upper_closed)[0]
        for row, center in zip(psd, centers)])
    return {"peaks_hz": peaks, "mean_peak_hz": mean_peak,
            "band_centers_hz": centers, "relative_power_per_channel": ratios}
