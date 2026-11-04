"""Public plan for each request. It carries tab:spec settings and no reference values."""
from __future__ import annotations

from components import COMPONENTS, DOI, FORMAL_SUBJECTS, MOUNT, OSF_COMPONENT, SCALP_DROP

DERIVATIVES_ROOT = 'derivatives/erp-analysis'
AMPLITUDE_TOLERANCE_UV = 0.1
WAVE_RMS_TOLERANCE_UV = 0.1
PUBLIC_PLAN_VERSION = 'erp-explicit-plan-20261101'


def contrast_label(component):
    return {'P3b': 'rareminusfrequent', 'N170': 'facesminuscars', 'ERN': 'errorminuscorrect', 'N400': 'unrelatedminusrelated'}[component]


def analysis(component):
    s = COMPONENTS[component]
    return {
        'channels': {
            'drop_before_processing': SCALP_DROP,
            'note': 'These three EOG channels are read as type EEG from the .set files. Remove them first; the 30 remaining scalp channels are analysed.',
            'montage': 'standard_1020', 'montage_match_case': False},
        'filter': {'type': 'zero-phase FIR band-pass, mne.io.Raw.filter defaults', 'l_freq_hz': s['band_hz'][0], 'h_freq_hz': s['band_hz'][1],
                   'l_trans_bandwidth_hz': 0.1, 'h_trans_bandwidth': 'MNE default rule: a quarter of the upper cutoff and at least 2 Hz',
                   'fir_design': 'firwin', 'fir_window': 'hamming', 'filter_length': 'auto', 'pad': 'reflect_limited', 'n_jobs': 1},
        'resample_hz': 256.0,
        'resample_method': 'mne.io.Raw.resample default',
        'reference': 'average of the 30 scalp channels, applied directly (projection False)',
        'processing_order': ['drop the three EOG channels', 'set montage', 'band-pass filter', 'resample to 256 Hz', 'average reference', 'epoch'],
        'events': {'source': 'the BIDS events.tsv of the recording', 'sample_rule': 'round(onset_seconds * 256)', 'keep': 'samples strictly inside the recording'},
        'time_lock': s['time_lock'],
        'contrast': {'plus': s['plus'], 'minus': s['minus'], 'difference': 'mean of plus trials minus mean of minus trials'},
        'epoch_s': s['epoch_s'], 'baseline_s': s['baseline_s'], 'rejection': 'none',
        'minimum_trials': s['minimum_trials'],
        'minimum_trials_rule': 'A subject with fewer retained trials than this in either condition is ineligible.',
        'roi': s['roi'], 'window_s': s['window_s'], 'window_endpoints': 'inclusive',
        'amplitude': 'mean over the ROI channels and window samples of the difference wave, in microvolts',
        'expected_direction': s['direction'],
    }


def group_test(component):
    s = COMPONENTS[component]
    return {
        't_test': {'data': 'per-subject ROI amplitudes of the eligible subjects', 'test': 'two-sided one-sample t-test against zero', 'alpha': 0.05},
        'cluster': {'function': 'mne.stats.spatio_temporal_cluster_1samp_test',
                    'data': 'eligible subjects x window samples x channels, difference waves restricted to the same window',
                    'n_permutations': 5000, 'tail': s['tail'],
                    'threshold': 'one-sided t quantile at 0.95 with n_subjects minus 1 degrees of freedom, signed as the tail',
                    'adjacency': "mne.channels.find_ch_adjacency(info, ch_type='eeg')",
                    'significant_if': 'at least one cluster has p < 0.05'},
        'effect_direction': 'sign of the group mean ROI amplitude: positive or negative'}


COMMON_RESULTS = {
    'status': 'computed, or ineligible for a subject below the trial minimum',
    'component': 'component name as given',
    'dataset_doi': 'DOI of the dataset',
    'dataset_version': "dataset version as stated in the dataset's own CHANGES file",
    'explanation': 'brief factual explanation',
}


def contract(request_id, component, kind, subjects):
    s = COMPONENTS[component]
    plan = {
        'request_id': request_id, 'public_plan_version': PUBLIC_PLAN_VERSION, 'request_kind': kind, 'component': component,
        'dataset': {'name': 'ERP CORE', 'doi': DOI, 'osf_component': OSF_COMPONENT, 'bids_root_readonly': MOUNT, 'bids_task_label': s['task'],
                    'discovery': 'Locate recording and event files by walking the BIDS directory. Work out which event codes form each condition from the dataset documentation in that directory.'},
        'subjects': subjects, 'analysis': analysis(component),
        'derivatives': {'root': DERIVATIVES_ROOT, 'contrast_label': contrast_label(component),
                        'requirement': 'A BIDS-Derivatives dataset that passes the BIDS validator with no errors and holds the ERP result of every analysed subject under its sub-XXX folder. The validator is not installed in this environment.'},
    }
    if kind == 'single_subject':
        plan['required_results'] = {**COMMON_RESULTS, 'subject': 'subject label', 'roi_amplitude_uv': 'ROI amplitude in microvolts, full precision',
                                    'n_trials_plus': 'retained plus trials', 'n_trials_minus': 'retained minus trials'}
        plan['required_evidence'] = {'times_s': 'all epoch sample times in seconds, whole epoch', 'roi_difference_uv': 'difference wave averaged over the ROI, microvolts, one value per epoch sample, whole epoch'}
    else:
        plan['group_test'] = group_test(component)
        plan['required_results'] = {**COMMON_RESULTS, 'subjects_included': 'eligible subject labels', 'subjects_excluded': 'ineligible subject labels',
                                    'n_subjects': 'number of eligible subjects', 'per_subject_amplitude_uv': 'object mapping subject label to ROI amplitude in microvolts',
                                    'group_mean_uv': 'mean ROI amplitude', 'effect_direction': 'positive or negative', 'ttest_t': 't statistic', 'ttest_p': 'two-sided p',
                                    'ttest_significant': 'true when p < 0.05', 'cluster_min_p': 'smallest cluster p, 1.0 if no cluster formed', 'cluster_significant': 'true when any cluster p < 0.05'}
        plan['required_evidence'] = {'subjects': 'eligible subject labels', 'roi_amplitudes_uv': 'ROI amplitudes in the same order', 'times_s': 'all epoch sample times in seconds, whole epoch',
                                     'grand_roi_difference_uv': 'mean across eligible subjects of the ROI difference wave, microvolts, one value per epoch sample, whole epoch'}
    return plan


def instruction(plan):
    who = plan['subjects'][0] if plan['request_kind'] == 'single_subject' else f"the {len(plan['subjects'])} subjects listed in the plan"
    kind = 'a single-subject ERP analysis' if plan['request_kind'] == 'single_subject' else 'a group-level ERP analysis'
    return (f"Carry out {kind} of the {plan['component']} component in the ERP CORE dataset (DOI {DOI}, OSF component {OSF_COMPONENT}) for {who}. "
            f"A read-only copy of the dataset's BIDS directory is at {MOUNT}; BIDS task label {plan['dataset']['bids_task_label']}. "
            "Starting from that directory, find the recordings and events yourself. "
            "The approved analysis plan is PUBLIC_CONTRACT.json in the working directory and is repeated below; apply every setting in it exactly.")
