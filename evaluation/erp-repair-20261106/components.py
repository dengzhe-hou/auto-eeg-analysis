"""The four ERP CORE analyses of Supplementary Table tab:spec, as data.

Everything here is public plan material except the script/function names used to
call the frozen v0.3.2 reference. No subject-level numbers live in this file.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_ROOT = Path('/home/hou/Research/data/raw/erpcore_osf_9f5w7/ERP_CORE_BIDS_Raw_Files')
MOUNT = '/input/erp_core_bids'
DOI = '10.18115/D5JW4R'
OSF_COMPONENT = 'https://osf.io/9f5w7/'
FORMAL_SUBJECTS = [f'sub-{i:03d}' for i in range(21, 41)]
CERTIFIED_SUBJECTS = [f'sub-{i:03d}' for i in range(1, 21)]
SCALP_DROP = ['HEOG_left', 'HEOG_right', 'VEOG_lower']

COMPONENTS = {
    'P3b': {
        'task': 'P3', 'script': 'validate_p3_group.py', 'subject_fn': 'subject_p3', 'amplitude_key': 'p3_uV',
        'recipe': 'p300-oddball', 'time_lock': 'stimulus',
        'plus': 'rare (the trial letter is the block target letter)',
        'minus': 'frequent (the trial letter is not the block target letter)',
        'band_hz': [0.1, 30.0], 'epoch_s': [-0.2, 0.8], 'baseline_s': [-0.2, 0.0],
        'minimum_trials': {'plus': 30, 'minus': 100}, 'roi': ['Fz', 'Cz', 'Pz', 'CPz'],
        'window_s': [0.30, 0.50], 'direction': 'positive', 'tail': 1,
    },
    'N170': {
        'task': 'N170', 'script': 'validate_n170_erpcore_group.py', 'subject_fn': 'subject_n170', 'amplitude_key': 'n170_uV',
        'recipe': 'n170-faces', 'time_lock': 'stimulus',
        'plus': 'faces (intact face images; scrambled images are not used)',
        'minus': 'cars (intact car images; scrambled images are not used)',
        'band_hz': [0.1, 40.0], 'epoch_s': [-0.2, 0.5], 'baseline_s': [-0.2, 0.0],
        'minimum_trials': {'plus': 30, 'minus': 30}, 'roi': ['PO7', 'PO8', 'P7', 'P8'],
        'window_s': [0.13, 0.20], 'direction': 'negative', 'tail': -1,
    },
    'ERN': {
        'task': 'ERN', 'script': 'validate_ern_erpcore_group.py', 'subject_fn': 'subject_ern', 'amplitude_key': 'ern_uV',
        'recipe': 'ern-flankers', 'time_lock': 'response',
        'plus': 'error (the response side differs from the target side)',
        'minus': 'correct (the response side equals the target side)',
        'band_hz': [0.1, 30.0], 'epoch_s': [-0.4, 0.6], 'baseline_s': [-0.4, -0.2],
        'minimum_trials': {'plus': 15, 'minus': 15}, 'roi': ['FCz', 'Fz', 'Cz'],
        'window_s': [0.0, 0.10], 'direction': 'negative', 'tail': -1,
    },
    'N400': {
        'task': 'N400', 'script': 'validate_n400_erpcore_group.py', 'subject_fn': 'subject_n400', 'amplitude_key': 'n400_uV',
        'recipe': 'n400-semantic', 'time_lock': 'stimulus',
        'plus': 'unrelated (target word of an unrelated word pair)',
        'minus': 'related (target word of a related word pair)',
        'band_hz': [0.1, 30.0], 'epoch_s': [-0.2, 0.8], 'baseline_s': [-0.2, 0.0],
        'minimum_trials': {'plus': 30, 'minus': 30}, 'roi': ['CPz', 'Cz', 'Pz'],
        'window_s': [0.30, 0.50], 'direction': 'negative', 'tail': -1,
    },
}
