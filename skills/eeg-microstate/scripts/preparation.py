"""Shared preparation and channel-identity alignment of resting GFP maps."""
import mne
import numpy as np


def prepare_peaks(raw, *, channels, filter_kwargs, reference, min_peak_distance,
                  reject_by_annotation, gfp_reject_sd, gfp_reference, max_peaks, seed):
    """Apply explicit approved settings once, for individual or group fitting.

    gfp_reference selects continuous-sample or peak-map GFP for the rejection
    mean/SD. max_peaks=None and gfp_reject_sd=None explicitly disable those steps.
    Returned raw is a prepared copy suitable for subsequent back-fitting.
    """
    from pycrostates.io import ChData
    from pycrostates.preprocessing import extract_gfp_peaks

    channels = list(channels)
    if len(channels) != len(set(channels)) or not channels:
        raise ValueError('Provide distinct approved channel names')
    if any(ch not in raw.ch_names for ch in channels):
        raise ValueError('Approved microstate channels are missing')
    if set(channels) & set(raw.info['bads']):
        raise ValueError('Resolve bad channels upstream before microstate preparation')
    if reference != 'average':
        raise ValueError('This resting-map preparation requires an approved average reference')
    if not isinstance(min_peak_distance, (int, np.integer)) or min_peak_distance < 1:
        raise ValueError('min_peak_distance must be an explicit positive number of samples')
    if gfp_reference not in ('continuous', 'peaks'):
        raise ValueError('Resolve gfp_reference: continuous or peaks')
    if max_peaks is not None and (not isinstance(max_peaks, (int, np.integer)) or max_peaks < 1):
        raise ValueError('max_peaks must be a positive integer or explicit None')
    if gfp_reject_sd is not None and (not np.isfinite(gfp_reject_sd) or gfp_reject_sd < 0):
        raise ValueError('gfp_reject_sd must be nonnegative or explicit None')

    prepared = raw.copy().pick(channels).load_data()
    if any(mne.channel_type(prepared.info, i) != 'eeg' for i in range(len(channels))):
        raise ValueError('Microstate maps must contain only the approved EEG channels')
    prepared.filter(**filter_kwargs)
    prepared.set_eeg_reference('average', projection=False)
    peaks = extract_gfp_peaks(prepared, picks=channels,
                              min_peak_distance=min_peak_distance,
                              reject_by_annotation=reject_by_annotation)
    maps = peaks.get_data()
    if maps.shape[1] == 0:
        raise ValueError('No GFP peaks remain for this recording')
    peak_gfp = maps.std(axis=0, ddof=0)
    if gfp_reference == 'continuous':
        reference_data = prepared.get_data(
            reject_by_annotation='omit' if reject_by_annotation else None)
        reference_gfp = reference_data.std(axis=0, ddof=0)
    else:
        reference_gfp = peak_gfp
    threshold = None
    selected = np.arange(maps.shape[1])
    if gfp_reject_sd is not None:
        threshold = float(reference_gfp.mean() + gfp_reject_sd * reference_gfp.std(ddof=0))
        selected = np.flatnonzero(peak_gfp <= threshold)
    after_rejection = len(selected)
    if max_peaks is not None and len(selected) > max_peaks:
        selected = np.sort(np.random.default_rng(seed).choice(selected, max_peaks, replace=False))
    if len(selected) == 0:
        raise ValueError('No GFP maps survived the approved rejection rule')
    result = ChData(maps[:, selected], peaks.info.copy())
    audit = dict(channels=channels, sfreq=float(prepared.info['sfreq']),
                 filter_kwargs=dict(filter_kwargs), reference=reference,
                 min_peak_distance_samples=int(min_peak_distance),
                 reject_by_annotation=bool(reject_by_annotation),
                 gfp_reference=gfp_reference, gfp_reject_sd=gfp_reject_sd,
                 gfp_threshold=threshold, gfp_ddof=0,
                 n_extracted=int(maps.shape[1]), n_after_rejection=after_rejection,
                 n_selected=len(selected), max_peaks=max_peaks, seed=seed,
                 selected_peak_indices=selected.tolist())
    return prepared, result, audit


def pool_peaks(records, *, channels):
    """Align actual name/position identity before pooling; do not interpolate.

    Each record has participant_id, peaks (ChData), and its preparation audit.
    Returns pooled ChData, aligned per-participant ChData, and a JSON-safe audit.
    """
    from pycrostates.io import ChData

    channels = list(channels)
    if not records or not channels or len(channels) != len(set(channels)):
        raise ValueError('Provide participant records and distinct approved channels')
    ids, aligned, audits = [], [], []
    reference_info = None
    for record in records:
        identity = record['participant_id']
        if identity is None or not str(identity) or str(identity) in ids:
            raise ValueError('Provide one peak record per actual participant')
        peaks = record['peaks']
        if set(peaks.ch_names) != set(channels) or len(peaks.ch_names) != len(channels):
            raise ValueError('Channel sets differ; resolve approved handling before pooling')
        order = [peaks.ch_names.index(ch) for ch in channels]
        info = mne.pick_info(peaks.info, order, copy=True)
        if reference_info is not None:
            for first, current in zip(reference_info['chs'], info['chs']):
                if (any(first[k] != current[k] for k in ('kind', 'unit', 'coord_frame'))
                        or not np.allclose(first['loc'], current['loc'], equal_nan=True)):
                    raise ValueError('Channel metadata/positions differ; resolve alignment upstream')
        else:
            reference_info = info
        data = peaks.get_data()[order]
        audit = record['audit']
        if audit['n_selected'] != data.shape[1]:
            raise ValueError('Peak count disagrees with the preparation record')
        if audit['max_peaks'] is not None and data.shape[1] > audit['max_peaks']:
            raise ValueError('Peak cap was not applied before group pooling')
        aligned.append(ChData(data, info))
        ids.append(str(identity))
        audits.append(dict(participant_id=str(identity), input_channels=list(peaks.ch_names),
                           preparation=audit))
    pooled = ChData(np.hstack([p.get_data() for p in aligned]), reference_info.copy())
    return pooled, aligned, dict(channels=channels, participant_ids=ids, participants=audits,
                                n_maps=int(pooled.get_data().shape[1]))


def backfit_microstates(raw, model, *, settings):
    """Pass one approved smoothing policy through recipe and skill unchanged.

    half_window and min_segment each provide value and unit ('samples', 'ms' or
    's'). Conversion uses round(value*sfreq), and records actual sample counts.
    Model fitting/template selection is an earlier, explicitly approved step.
    """
    sfreq = float(raw.info['sfreq'])

    def samples(spec):
        value, unit = spec['value'], spec['unit']
        if not np.isfinite(value) or value < 0:
            raise ValueError('Smoothing durations must be finite and nonnegative')
        if unit == 'samples':
            if int(value) != value:
                raise ValueError('Sample-based smoothing must specify an integer')
            return int(value)
        if unit == 'ms':
            return int(round(value * sfreq / 1000))
        if unit == 's':
            return int(round(value * sfreq))
        raise ValueError('Resolve smoothing unit: samples, ms or s')

    kwargs = dict(factor=settings['factor'], tol=settings['tol'],
                  half_window_size=samples(settings['half_window']),
                  min_segment_length=samples(settings['min_segment']),
                  reject_edges=settings['reject_edges'],
                  reject_by_annotation=settings['reject_by_annotation'])
    segmentation = model.predict(raw, **kwargs)
    return segmentation, dict(sfreq=sfreq, approved_settings=settings, predict_kwargs=kwargs)
