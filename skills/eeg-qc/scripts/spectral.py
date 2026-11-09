"""Spectral QC with explicit frequency availability, without changing data."""
from pathlib import Path
import runpy

import numpy as np

_spectral = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                               'eeg-spectral/scripts/continuous.py'))


def band_ratio(psd, freqs, *, numerator_band, denominator_bands, supported_band_hz,
               nyquist_hz, statistic):
    """Compute an approved band ratio only on represented, interpretable bands.

    supported_band_hz is the known high/low-pass support of the actual input,
    not a request to change its filter. None records unresolved support.
    statistic='mean_density' pools denominator bins; 'integrated_power' sums
    integrals of the declared non-overlapping denominator bands. No fallback.
    """
    psd, freqs = np.asarray(psd), np.asarray(freqs)
    if psd.ndim != 2 or freqs.ndim != 1 or psd.shape[1] != len(freqs):
        raise ValueError('QC PSD must have channel x frequency shape and matching coordinates')
    if statistic not in ('mean_density', 'integrated_power'):
        raise ValueError('Resolve ratio statistic: mean_density or integrated_power')
    bands = [list(numerator_band)] + [list(band) for band in denominator_bands]
    if len(bands) < 2 or any(len(b) != 2 or b[0] >= b[1] for b in bands):
        raise ValueError('Specify positive-width numerator and denominator bands')
    record = dict(statistic=statistic, numerator_band=list(numerator_band),
                  denominator_bands=[list(b) for b in denominator_bands],
                  supported_band_hz=supported_band_hz, nyquist_hz=nyquist_hz,
                  status='unavailable', values=None, reasons=[])
    if supported_band_hz is None:
        record['reasons'].append('Input filter support is not recorded')
    masks = []
    for band in bands:
        if band[1] > nyquist_hz:
            record['reasons'].append(f'Band {band} exceeds Nyquist')
        if supported_band_hz is not None and not (supported_band_hz[0] <= band[0] <= band[1] <= supported_band_hz[1]):
            record['reasons'].append(f'Band {band} lies outside recorded filter support')
        if not len(freqs) or not (freqs[0] <= band[0] <= band[1] <= freqs[-1]):
            record['reasons'].append(f'Band {band} is not fully represented in the PSD')
        mask = (freqs >= band[0]) & (freqs <= band[1])
        if np.count_nonzero(mask) < 2:
            record['reasons'].append(f'Band {band} has fewer than two PSD bins')
        masks.append(mask)
    record['band_bin_counts'] = [int(mask.sum()) for mask in masks]
    if record['reasons']:
        return record
    denominator_mask = np.logical_or.reduce(masks[1:])
    if sum(mask.sum() for mask in masks) != np.logical_or.reduce(masks).sum():
        raise ValueError('Approved QC numerator/flanking bands must not overlap')
    if statistic == 'mean_density':
        numerator = psd[:, masks[0]].mean(axis=-1)
        denominator = psd[:, denominator_mask].mean(axis=-1)
    else:
        numerator = _spectral['integrated_power'](psd, freqs, band=bands[0], upper_closed=True)
        denominator = sum(_spectral['integrated_power'](psd, freqs, band=b, upper_closed=True)
                          for b in bands[1:])
    available = np.isfinite(numerator) & np.isfinite(denominator) & (denominator > 0)
    values = [float(n/d) if ok else None for n, d, ok in zip(numerator, denominator, available)]
    record.update(status='computed' if available.all() else 'unavailable',
                  values=values, channel_available=available.tolist())
    if not available.all():
        record['reasons'].append('One or more channels have undefined power/denominator')
    return record


def qc_verdict(gates):
    """Do not turn an unavailable required QC metric into a green pass."""
    if not gates or set(gates.values()) - {'pass', 'warn', 'fail', 'unavailable', 'not_applicable'}:
        raise ValueError('Supply explicit QC gate states')
    states = set(gates.values())
    if 'fail' in states:
        return 'fail'
    if 'unavailable' in states or states == {'not_applicable'}:
        return 'incomplete'
    return 'warn' if 'warn' in states else 'pass'
