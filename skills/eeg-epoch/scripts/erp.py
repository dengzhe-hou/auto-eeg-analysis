"""Integer-sample grids and ROI means for an explicitly approved ERP plan.

No filters, reference, baseline, rejection or scientific measurement window is
selected here. Dataset-specific event coding is loaded separately when needed.
"""
from pathlib import Path
import json

import numpy as np


def epoch_sample_times(*, epoch_s, sfreq):
    """MNE-style integer-sample epoch grid; t=0 remains on the sample grid."""
    if not np.isfinite(sfreq) or sfreq <= 0 or len(epoch_s) != 2:
        raise ValueError("Supply a positive sfreq and two epoch bounds")
    if not np.isfinite(epoch_s).all() or epoch_s[0] > epoch_s[1]:
        raise ValueError("Epoch bounds must be finite and increasing")
    first, last = [int(round(float(t) * sfreq)) for t in epoch_s]
    return np.arange(first, last + 1, dtype=float) / sfreq


def mean_roi_amplitude(epochs, *, plus, minus, roi, window_s):
    """Measure plus-minus using actual Epochs.times and the supplied ROI/window.

    MNE EEG input is V. Output waveform and mean are uV. The input epochs are
    already processed according to the plan and are not modified here.
    """
    if len(window_s) != 2 or not np.isfinite(window_s).all() or window_s[0] > window_s[1]:
        raise ValueError("Supply an increasing finite measurement window")
    if not roi or len(set(roi)) != len(roi):
        raise ValueError("Supply distinct ROI channel names")
    missing = [name for name in roi if name not in epochs.ch_names]
    if missing:
        raise ValueError(f"ROI channels absent from actual epochs: {missing}; available: {epochs.ch_names}")
    types = epochs.get_channel_types(picks=roi)
    if any(kind != 'eeg' for kind in types):
        raise ValueError(f"ERP uV measurement requires EEG ROI channels; actual types: {dict(zip(roi, types))}")
    times = epochs.times.copy()
    # Nominal epoch endpoints may differ by up to half a sample after rounding.
    half_sample = .5 / float(epochs.info['sfreq'])
    if window_s[0] < times[0] - half_sample or window_s[1] > times[-1] + half_sample:
        raise ValueError(f"Approved window {window_s} exceeds actual epoch range "
                         f"[{times[0]}, {times[-1]}] at {epochs.info['sfreq']} Hz")
    mask = (times >= window_s[0]) & (times <= window_s[1])
    if not mask.any():
        raise ValueError("No actual epoch samples lie in the approved window")
    p, m = epochs[plus], epochs[minus]
    if not len(p) or not len(m):
        raise ValueError("Both planned conditions must have retained trials")
    waveform = (p.average(picks=roi).data - m.average(picks=roi).data).mean(axis=0) * 1e6
    if not np.isfinite(waveform).all():
        raise ValueError("The actual ROI difference contains non-finite samples")
    return {
        'roi_amplitude_uv': float(waveform[mask].mean()),
        'n_trials_plus': len(p), 'n_trials_minus': len(m),
        'times_s': times, 'roi_difference_uv': waveform,
        'amplitude_unit': np.asarray('uV'), 'sfreq_hz': np.asarray(epochs.info['sfreq']),
    }


def save_erp_outputs(workspace, *, result, evidence):
    """Save actual computed artifacts before optional diagnostics, once per run.

    A later failed check does not delete/rewrite these artifacts. For a revision
    use a new run directory and preserve the original execution evidence.
    """
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    paths = [workspace / 'result.json', workspace / 'analysis_evidence.npz']
    if any(path.exists() for path in paths):
        raise FileExistsError("ERP outputs already exist; choose a new run directory")
    serialized = json.dumps(result, indent=2, allow_nan=False) + '\n'
    np.savez(paths[1], **evidence)
    paths[0].write_text(serialized, encoding='utf-8')
