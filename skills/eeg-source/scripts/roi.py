"""Surface ROI extraction with anatomical identity and explicit availability."""
import mne
import numpy as np


def extract_surface_rois(stc, labels, src, *, atlas_subject, mode, empty_policy):
    """Require an already matched STC/src/atlas; no automatic morph or relabel.

    empty_policy='error' stops on missing ROIs. 'flag' stores NaN and available=False;
    it does not authorize dropping those ROIs from a downstream analysis.
    """
    if empty_policy not in ('error', 'flag'):
        raise ValueError('Resolve empty ROI policy: error or flag')
    if len(src) != 2 or any(s['type'] != 'surf' for s in src) or stc.data.ndim != 2:
        raise ValueError('This helper accepts scalar two-hemisphere surface estimates')
    if not stc.subject or not atlas_subject or stc.subject != atlas_subject:
        raise ValueError('STC and atlas subject differ or are unresolved; use the approved morph')
    if any(s.get('subject_his_id') != stc.subject for s in src):
        raise ValueError('Source-space and STC subject differ or are unresolved')
    for vertices, space in zip(stc.vertices, src):
        if not np.isin(vertices, space['vertno']).all():
            raise ValueError('STC vertices do not belong to the supplied source space')
    labels = list(labels)
    if len({label.name for label in labels}) != len(labels):
        raise ValueError('ROI names must be distinct')
    n_vertices = []
    for label in labels:
        if label.subject != atlas_subject:
            raise ValueError('Label and atlas subject differ; do not rename subject metadata')
        if label.hemi not in ('lh', 'rh'):
            raise ValueError('Provide separate left/right cortical labels')
        vertices = stc.vertices[0 if label.hemi == 'lh' else 1]
        n_vertices.append(np.intersect1d(vertices, label.vertices).size)
    n_vertices = np.asarray(n_vertices, int)
    available = n_vertices > 0
    if not available.all() and empty_policy == 'error':
        missing = [label.name for label, ok in zip(labels, available) if not ok]
        raise ValueError(f'Unavailable ROIs in this source estimate: {missing}')
    label_ts = np.full((len(labels), stc.data.shape[1]), np.nan)
    if available.any():
        label_ts[available] = mne.extract_label_time_course(
            stc, [label for label, ok in zip(labels, available) if ok], src,
            mode=mode, allow_empty=False)
    return dict(label_ts=label_ts, label_names=np.asarray([label.name for label in labels]),
                times=stc.times.copy(), available=available, n_vertices=n_vertices,
                subject=stc.subject, atlas_subject=atlas_subject,
                roi_extraction_mode=mode, empty_policy=empty_policy)
