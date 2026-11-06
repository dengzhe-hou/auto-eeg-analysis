"""ERP CORE's documented ERN response coding, without reference answers."""
import numpy as np


def erp_core_ern_events(rows, *, sfreq, first_samp, n_times):
    """Decode d1=response, d2=flankers, d3=target; error=1, correct=2.

    All response rows carry their own target, including responses without a
    preceding stimulus. Onsets are seconds relative to the recording. Supply
    the approved output rate, first sample and recording length explicitly.
    """
    if not np.isfinite(sfreq) or sfreq <= 0 or n_times <= 0:
        raise ValueError("Supply a positive sampling rate and recording length")
    events, decoded, excluded = [], [], []
    allowed = {111, 112, 121, 122, 211, 212, 221, 222}
    for index, row in enumerate(rows):
        if row['trial_type'] != 'response':
            continue
        value = float(row['value'])
        if not np.isfinite(value) or value not in allowed:
            raise ValueError(f"Unsupported ERP CORE response code at row {index}: {row['value']}")
        code = int(value)
        onset = float(row['onset'])
        if not np.isfinite(onset):
            raise ValueError(f"Nonfinite response onset at row {index}")
        sample = int(np.rint(onset * sfreq))
        if not 0 < sample < n_times:
            excluded.append({'row': index, 'sample': sample, 'reason': 'outside approved sample bounds'})
            continue
        label = 1 if code // 100 != code % 10 else 2
        events.append([sample + first_samp, 0, label])
        decoded.append({'row': index, 'code': code, 'condition': 'error' if label == 1 else 'correct'})
    if not events:
        raise ValueError("No ERP CORE ERN response remains inside the recording")
    return np.asarray(events, dtype=int), {
        'event_id': {'error': 1, 'correct': 2}, 'decoded': decoded, 'excluded': excluded,
        'sfreq': float(sfreq), 'first_samp': int(first_samp),
        'sample_rule': 'rint(onset_s * sfreq) + first_samp',
        'coding': 'ERP CORE task-ERN_events.json: compare response digit 1 with target digit 3',
    }
