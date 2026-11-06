"""Bounded MNE processing with explicitly approved operations and SI units."""
from pathlib import Path
from copy import deepcopy
import mne
import numpy as np


def prepare_continuous(raw, *, analysis_channels, operations, operation_log=None):
    """Select the approved subset and apply only the ordered operations supplied.

    Channel roles must already be resolved from the recording documentation.
    A separate FIR configuration does not authorize a filter. Each invocation
    starts from its own copy, including when used for separate frequency bands.
    Crop intervals are half-open, relative to the current buffer's start.
    An optional operation_log receives actual before/after dimensions in order.
    """
    prepared = raw.copy().pick(list(analysis_channels))
    prepared.reorder_channels(list(analysis_channels))
    origin_s = 0.0
    for step in operations:
        operation = step["operation"]
        parameters = dict(step["parameters"])
        entry = {"operation": operation, "parameters": deepcopy(parameters),
                 "input_n_samples": int(prepared.n_times),
                 "input_sfreq_hz": float(prepared.info["sfreq"]),
                 "input_time_origin_s": origin_s}
        if operation == "crop":
            sfreq = prepared.info["sfreq"]
            start = round(parameters["start_s"] * sfreq)
            stop = round(parameters["stop_s"] * sfreq)
            if not 0 <= start < stop <= prepared.n_times:
                raise ValueError("Approved half-open crop is outside the current data")
            prepared.crop(tmin=start / sfreq, tmax=(stop - 1) / sfreq)
            origin_s += start / sfreq
        elif operation == "filter":
            # Both bounds are explicit; None means an approved one-sided filter.
            low, high = parameters.pop("l_freq"), parameters.pop("h_freq")
            prepared.load_data(verbose=False).filter(low, high, **parameters, verbose=False)
        elif operation == "notch_filter":
            frequencies = parameters.pop("freqs")
            prepared.load_data(verbose=False).notch_filter(frequencies, **parameters, verbose=False)
        elif operation == "resample":
            sfreq = parameters.pop("sfreq")
            prepared.load_data(verbose=False).resample(sfreq, **parameters, verbose=False)
        elif operation == "average_reference":
            if parameters != {"projection": False}:
                raise ValueError("This bounded operation applies an approved average reference directly")
            if set(prepared.get_channel_types()) != {"eeg"}:
                raise ValueError("Resolve the approved scalp EEG types before average reference")
            prepared.load_data(verbose=False).set_eeg_reference("average", projection=False, verbose=False)
        else:
            raise ValueError(f"Unsupported bounded operation: {operation}")
        if operation_log is not None:
            entry.update(output_n_samples=int(prepared.n_times),
                         output_sfreq_hz=float(prepared.info["sfreq"]),
                         output_time_origin_s=origin_s)
            operation_log.append(entry)
    return prepared


def data_in_volts(raw):
    """Read selected MNE EEG channels in V, without a second uV-to-V conversion."""
    return raw.get_data(units="V")


def recording_metadata(raw, *, rois=None):
    """Describe the actual selected object; ROI membership is supplied by the plan."""
    names = list(raw.ch_names)
    roi_channels = {}
    for label, selected in (rois or {}).items():
        selected = list(selected)
        if any(name not in names for name in selected):
            raise ValueError(f"ROI {label!r} contains a channel absent from the actual selection")
        roi_channels[label] = selected
    return {"channels": names, "n_channels": len(names), "n_samples": int(raw.n_times),
            "sfreq_hz": float(raw.info["sfreq"]), "roi_channels": roi_channels}


def gfp_peak_times(gfp, *, sfreq_hz, time_origin_s, windows_s, tie_rule):
    """Locate absolute peaks in explicitly approved half-open GFP windows."""
    if tie_rule != "first":
        raise ValueError("This GFP helper implements tie_rule='first'; approve another implementation if needed")
    gfp = np.asarray(gfp)
    times = float(time_origin_s) + np.arange(len(gfp)) / sfreq_hz
    peaks = []
    for start_s, stop_s in windows_s:
        start = round((start_s - time_origin_s) * sfreq_hz)
        stop = round((stop_s - time_origin_s) * sfreq_hz)
        if not 0 <= start < stop <= len(gfp):
            raise ValueError("Approved GFP window is outside the actual half-open buffer")
        peaks.append(float(times[start + np.argmax(gfp[start:stop])]))
    return {"times_s": times, "peak_times_s": peaks}


def population_gfp_raw(raw, *, analysis_channels, operations, time_origin_s,
                       windows_s, tie_rule):
    """Population-SD GFP and absolute peak times on explicitly prepared data.

    operations includes the approved half-open crop. time_origin_s is the
    approved recording time of that buffer's first sample; windows are absolute
    recording intervals. No reference, resampling or filtering is added.
    """
    with prepare_continuous(raw, analysis_channels=analysis_channels, operations=operations) as prepared:
        data = data_in_volts(prepared)
        metadata = recording_metadata(prepared)
    gfp = data.std(axis=0, ddof=0)
    peaks = gfp_peak_times(gfp, sfreq_hz=metadata["sfreq_hz"],
        time_origin_s=time_origin_s, windows_s=windows_s, tie_rule=tie_rule)
    return {"gfp": gfp, **peaks, "metadata": metadata}


def array_in_volts(data, *, input_unit):
    """For an array source only: convert its documented unit exactly once."""
    scales = {"V": 1., "mV": 1e-3, "uV": 1e-6, "µV": 1e-6}
    if input_unit not in scales:
        raise ValueError("Provide the array source's documented V, mV or uV unit")
    return np.asarray(data, dtype=float) * scales[input_unit]


def check_edf(path, *, analysis_channels, sfreq=None, n_samples=None):
    """Reopen an actual EDF; inspect its contents rather than its filename."""
    with mne.io.read_raw_edf(path, preload=False, verbose=False) as exported:
        checks = {"edf.channels": exported.ch_names == list(analysis_channels)}
        if sfreq is not None:
            checks["edf.sfreq"] = bool(np.isclose(exported.info["sfreq"], sfreq, rtol=0, atol=1e-9))
        if n_samples is not None:
            checks["edf.n_samples"] = exported.n_times == n_samples
    return checks


def export_checked_edf(raw, path, *, analysis_channels, sfreq, n_samples, overwrite=False):
    """Export the requested subset and verify its declared output dimensions.

    sfreq and n_samples are approved output requirements, not values inferred
    from the file just written. Signal quantization is not checked here.
    """
    selected = raw.copy().pick(list(analysis_channels))
    selected.reorder_channels(list(analysis_channels))
    if not np.isclose(selected.info["sfreq"], sfreq, rtol=0, atol=1e-9) or selected.n_times != n_samples:
        raise ValueError("Prepared data do not meet the approved EDF rate/sample count")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    selected.export(path, fmt="edf", overwrite=overwrite, verbose=False)
    checks = check_edf(path, analysis_channels=analysis_channels, sfreq=sfreq, n_samples=n_samples)
    if not all(checks.values()):
        raise ValueError(f"Exported EDF differs from the approved output: {checks}")
    return checks
