"""Execute the shipped stage/ERP examples and check plan-record consistency."""
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import textwrap
import time

import mne
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from check_plan_provenance import check_plan_provenance

area_latency = runpy.run_path(str(
    ROOT / 'skills/eeg-erp/scripts/measurements.py'))['fractional_area_latency']


def run_example(skill, label, **context):
    """Labels locate source; assertions below check actual numerical behavior."""
    source = (ROOT / f'skills/{skill}/references/procedure.md').read_text(encoding="utf-8-sig")
    block, = [textwrap.dedent(block) for block in
              re.findall(r'```python\n(.*?)```', source, flags=re.S)
              if f'# AEA example: {label}\n' in block]
    namespace = {'mne': mne, 'np': np, 'AEA_ROOT': str(ROOT), **context}
    exec(compile(block, f'{skill}:{label}', 'exec'), namespace)
    return namespace


def epoch_params(**overrides):
    # Explicit synthetic study settings, not resource defaults.
    return dict(event_source='annotations', event_id={'rare': 17, 'common': 29},
                use_rounding=True, tmin=-.04, tmax=.12,
                baseline_at_creation=None, detrend=None, proj=False,
                reject_by_annotation=False, on_missing='raise',
                duration_s=2., overlap_s=0., **overrides)


def test_erp_difference_uses_fresh_named_conditions_and_approved_direction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'epoch-stage/S1').mkdir(parents=True)
    (tmp_path/'erp-stage/S1').mkdir(parents=True)
    data = np.arange(5*2*25,dtype=float).reshape(5,2,25)*1e-7
    codes = np.array([17,29,17,29,17])
    data[codes==17] += 3e-6
    epochs = mne.EpochsArray(data,mne.create_info(['Cz','Pz'],100.,'eeg'),
        events=np.column_stack([np.arange(5)*100,np.zeros(5,int),codes]),
        event_id={'unrelated':17,'related':29},tmin=-.1,baseline=None,verbose=False)
    epochs.save('epoch-stage/S1/S1-epo.fif',fmt='double',verbose=False)
    out = run_example('eeg-erp','erp-condition-averages',sub='S1',
        conditions=['related','unrelated'],contrast_name='unrelated_minus_related',
        approved_erp_params={'averaging_method':'mean','contrast':['unrelated','related']})
    expected = data[codes==17].mean(0)-data[codes==29].mean(0)
    np.testing.assert_allclose(expected,3e-6,rtol=1e-12,atol=1e-20)
    np.testing.assert_allclose(out['diff'].data,expected,rtol=1e-12,atol=1e-20)
    assert out['evokeds']['unrelated'].nave == 3 and out['evokeds']['related'].nave == 2
    saved = mne.read_evokeds('erp-stage/S1/S1-diff_unrelated_minus_related-ave.fif',verbose=False)[0]
    np.testing.assert_allclose(saved.data,expected,rtol=2e-6,atol=5e-12)


def test_annotation_mapping_preserves_codes_and_recording_sample_origin():
    raw = mne.io.RawArray(np.zeros((1, 1000)),
        mne.create_info(['Cz'], 250, 'eeg'), first_samp=125, verbose=False)
    raw.set_annotations(mne.Annotations([.1, .8], [0, 0], ['rare', 'common']))
    ns = run_example('eeg-epoch', 'event-source', raw=raw,
                     approved_epoch_params=epoch_params())
    np.testing.assert_array_equal(ns['events'], [[150, 0, 17], [325, 0, 29]])
    assert ns['event_id'] == {'rare': 17, 'common': 29}


def test_stim_branch_does_not_overwrite_events_with_empty_annotations():
    data = np.zeros((2, 1000)); data[1, 20] = 17; data[1, 80] = 29
    raw = mne.io.RawArray(data, mne.create_info(['Cz', 'Status'], 250,
        ['eeg', 'stim']), first_samp=125, verbose=False)
    params = epoch_params(); params.update(event_source='stim',
        stim_detection=dict(stim_channel='Status', min_duration=0., shortest_event=1))
    ns = run_example('eeg-epoch', 'event-source', raw=raw,
                     approved_epoch_params=params)
    np.testing.assert_array_equal(ns['events'], [[145, 0, 17], [205, 0, 29]])


def test_real_bids_sidecar_import_and_documented_event_branch(tmp_path):
    pytest.importorskip("mne_bids")
    from mne_bids import BIDSPath, write_raw_bids
    raw = mne.io.RawArray(np.zeros((2, 1000)),
        mne.create_info(['Cz', 'Oz'], 250, 'eeg'), verbose=False)
    raw.info['line_freq'] = 50
    bids_path = BIDSPath(subject='01', task='demo', datatype='eeg', root=tmp_path)
    expected = np.array([[125, 0, 17], [500, 0, 29]])
    write_raw_bids(raw, bids_path, events=expected,
        event_id={'rare': 17, 'common': 29}, format='BrainVision',
        allow_preload=True, verbose=False)
    loaded = run_example('eeg-epoch', 'bids-input', bids_path=bids_path)['raw']
    params = epoch_params(); params['event_source'] = 'bids'
    ns = run_example('eeg-epoch', 'event-source', raw=loaded,
                     approved_epoch_params=params)
    np.testing.assert_array_equal(ns['events'], expected)


def test_event_epochs_use_the_supplied_window_and_no_implicit_baseline():
    raw = mne.io.RawArray(np.full((1, 1000), 2e-6),
        mne.create_info(['Cz'], 250, 'eeg'), verbose=False)
    ns = run_example('eeg-epoch', 'event-epochs', raw=raw,
        events=np.array([[125, 0, 17], [500, 0, 29]]),
        approved_epoch_params=epoch_params())
    ep = ns['epochs']
    assert ep.get_data().shape == (2, 1, 41)
    assert ep.baseline is None
    np.testing.assert_allclose(ep.get_data(), 2e-6)
    assert ep.event_id == {'rare': 17, 'common': 29}


@pytest.mark.parametrize('sfreq,duration,overlap', [(250., 2., 0.), (128., 1.25, .25)])
def test_fixed_epoch_examples_have_identical_events_samples_and_last_segment(sfreq, duration, overlap):
    raw = mne.io.RawArray(np.arange(int(10*sfreq))[None, :] * 1e-9,
        mne.create_info(['Cz'], sfreq, 'eeg'), first_samp=100, verbose=False)
    params = epoch_params(); params.update(duration_s=duration, overlap_s=overlap)
    direct = run_example('eeg-epoch', 'fixed-epochs', raw=raw,
        approved_epoch_params=params)['epochs']
    manual = run_example('eeg-epoch', 'fixed-epochs-two-step', raw=raw,
        approved_epoch_params=params)['epochs']
    assert direct.get_data().shape[-1] == round(sfreq * duration)
    np.testing.assert_array_equal(direct.events, manual.events)
    np.testing.assert_array_equal(direct.get_data(), manual.get_data())
    if sfreq == 250:
        assert direct.get_data().shape == (5, 1, 500)


def rejection_epochs():
    data = np.zeros((3, 1, 5)); data[0, 0, 2] = 200e-6; data[1, 0, 2] = 30e-6
    return mne.EpochsArray(data, mne.create_info(['Cz'], 250, 'eeg'),
                           baseline=None, verbose=False)


def test_none_rejection_keeps_sparse_conditions_and_supplied_data():
    epochs = rejection_epochs()
    out = run_example('eeg-epoch', 'epoch-rejection', epochs=epochs,
        approved_epoch_params={'rejection_method': 'none'})
    assert len(out['epochs_clean']) == 3
    np.testing.assert_array_equal(out['epochs_clean'].get_data(), epochs.get_data())


def test_threshold_branch_uses_only_the_supplied_peak_to_peak_and_flat_policy():
    epochs = rejection_epochs()
    out = run_example('eeg-epoch', 'epoch-rejection', epochs=epochs,
        approved_epoch_params={'rejection_method': 'threshold',
                               'reject_v': {'eeg': 100e-6}, 'flat_v': None})
    assert len(epochs) == 3 and len(out['epochs_clean']) == 2
    assert out['epochs_clean'].drop_log == (('Cz',), (), ())
    # The zero/flat epoch survives because flat rejection was not requested.
    np.testing.assert_array_equal(out['epochs_clean'].get_data()[-1], 0.)


def test_missing_selected_autoreject_does_not_fall_back_to_a_threshold(monkeypatch):
    monkeypatch.setitem(sys.modules, 'autoreject', None)
    with pytest.raises(ModuleNotFoundError):
        run_example('eeg-epoch', 'epoch-rejection', epochs=rejection_epochs(),
                    approved_epoch_params={'rejection_method': 'autoreject_local'})


@pytest.mark.parametrize('domain', ['continuous', 'epochs'])
def test_ica_reads_the_approved_input_type_and_preserves_epoch_events(tmp_path, domain):
    if domain == 'continuous':
        inst = mne.io.RawArray(np.ones((1, 100)),
            mne.create_info(['Cz'], 100, 'eeg'), verbose=False)
        path = tmp_path / 'input-raw.fif'
    else:
        inst = rejection_epochs()
        path = tmp_path / 'input-preica-epo.fif'
    inst.save(path, overwrite=False)
    out = run_example('eeg-ica', 'ica-analysis-input',
        approved_ica_params={'fit_domain': domain, 'analysis_input': str(path)})['raw']
    assert isinstance(out, mne.io.BaseRaw if domain == 'continuous' else mne.BaseEpochs)
    np.testing.assert_allclose(out.get_data(), inst.get_data(), rtol=1e-6)
    if domain == 'epochs':
        np.testing.assert_array_equal(out.events, inst.events)
        assert out.baseline == inst.baseline


def example_evoked():
    data = np.full((2, 129), -2e-6)
    data[0, 32] = -4e-6; data[1, 48] = -20e-6
    return mne.EvokedArray(data, mne.create_info(['Cz', 'Oz'], 128, 'eeg'), tmin=0)


def test_original_peak_example_runs_and_stays_within_approved_roi():
    out = run_example('eeg-erp', 'erp-peak', evoked=example_evoked(),
        roi_channels=['Cz'], t_min=.125, t_max=.5,
        approved_erp_params={'peak_mode': 'neg'})
    assert out['ch'] == 'Cz' and out['lat'] == .25
    assert out['amp'] == pytest.approx(-4e-6)


def test_original_adaptive_example_uses_requested_width_and_return_arity():
    evoked = example_evoked()
    out = run_example('eeg-erp', 'erp-adaptive-mean', evoked=evoked,
        peak_evoked=evoked.copy().pick(['Cz']), times=evoked.times, ch_idx=[0],
        t_min=.125, t_max=.5,
        approved_erp_params={'peak_mode': 'neg', 'adaptive_half_width_s': .03125})
    assert out['adaptive_tmin'] == .21875 and out['adaptive_tmax'] == .28125
    assert out['adaptive_mean'] == pytest.approx(-20/9)


@pytest.mark.parametrize('mode,polarity,crossing,interpolation,expected', [
    ('signed', 'positive', 'first', 'sample', 1.),
    ('signed', 'positive', 'last', 'sample', 6.),
    ('signed', 'positive', 'last', 'linear', 5 + 2/3),
    ('positive', 'positive', 'first', 'linear', 4 + 1/3),
    ('absolute', None, 'first', 'linear', 3.75),
])
def test_area_latency_conventions_on_biphasic_trace(mode, polarity, crossing, interpolation, expected):
    out = area_latency([0, 4, 4, -8, -8, 12, 0], np.arange(7.),
        fraction=.5, area_mode=mode, polarity=polarity,
        crossing=crossing, interpolation=interpolation)
    assert out['latency_s'] == pytest.approx(expected)
    assert out['area_mode'] == mode and out['crossing'] == crossing


def test_area_example_calls_the_helper_with_the_explicit_plan():
    evoked = mne.EvokedArray(np.array([[0, -4, -4, 8, 8, -12, 0.]])*1e-6,
        mne.create_info(['Cz'], 1, 'eeg'), tmin=0)
    out = run_example('eeg-erp', 'erp-area-latency', evoked=evoked,
        ch_idx=[0], t_min=0, t_max=6,
        approved_erp_params={'fractional_area': dict(fraction=.5,
            area_mode='signed', polarity='negative', crossing='last', interpolation='sample')})
    assert out['frac_latency'] == 6.


def test_area_latency_never_selects_a_missing_convention_or_replaces_nonpositive_area():
    with pytest.raises(TypeError):
        area_latency([0, 1, 0], [0, 1, 2], fraction=.5)
    with pytest.raises(ValueError, match='No positive total area'):
        area_latency([-1, -1], [0, 1], fraction=.5, area_mode='signed',
                     polarity='positive', crossing='first', interpolation='sample')
    with pytest.raises(ValueError, match='polarity=None'):
        area_latency([-1, 1], [0, 1], fraction=.5, area_mode='absolute',
                     polarity='negative', crossing='first', interpolation='sample')


@pytest.fixture
def plan_evidence(tmp_path):
    plan = tmp_path/'ANALYSIS_PLAN.md'; plan.write_text('Condition A minus B\n', encoding="utf-8")
    approved = tmp_path/'approved-plan.md'; shutil.copyfile(plan, approved)
    approval = tmp_path/'approval.json'; approval.write_text(json.dumps(
        {'approved': True, 'timestamp': '2026-10-29T10:00:00+09:00'}), encoding="utf-8")
    run = tmp_path/'run.json'; run.write_text(json.dumps(
        {'analysis_started_at': '2026-10-29T10:01:00+09:00'}), encoding="utf-8")
    return plan, dict(approved_plan=approved, approval_record=approval,
                     analysis_record=run, approved_at='2026-10-29T10:00:00+09:00',
                     analysis_started_at='2026-10-29T10:01:00+09:00')


def test_copied_plan_mtime_is_only_an_observation(plan_evidence, tmp_path):
    plan, settings = plan_evidence
    now = time.time(); os.utime(plan, (now-60, now-60))
    stats = tmp_path/'stats.json'; stats.write_text('{}', encoding="utf-8"); os.utime(stats, (now-30, now-30))
    copied = tmp_path/'copied-plan.md'; shutil.copyfile(plan, copied)
    out = check_plan_provenance(copied, outputs=[stats], **settings)
    assert out['status'] == 'consistent'
    assert out['approved_snapshot_matches'] is True
    assert out['output_mtime_observations'][0]['plan_mtime_is_later'] is True


def test_early_mtime_does_not_establish_approval(plan_evidence):
    plan, _ = plan_evidence
    os.utime(plan, (1, 1))
    out = check_plan_provenance(plan)
    assert out['status'] == 'unverified'
    assert out['recorded_approval_before_analysis'] is None
    assert 'approval_record' in out['missing_evidence']


def test_plan_difference_requires_review_even_with_early_mtime(plan_evidence):
    plan, settings = plan_evidence
    plan.write_text('Condition B minus A\n', encoding="utf-8"); os.utime(plan, (1, 1))
    out = check_plan_provenance(plan, **settings)
    assert out['status'] == 'needs_review'
    assert 'run_plan_differs_from_supplied_approved_snapshot' in out['issues']


def test_recorded_late_approval_requires_review(plan_evidence):
    plan, settings = plan_evidence
    settings['approved_at'] = '2026-10-29T10:02:00+09:00'
    settings['approval_record'].write_text(json.dumps(
        {'approved': True, 'timestamp': settings['approved_at']}), encoding="utf-8")
    out = check_plan_provenance(plan, **settings)
    assert out['status'] == 'needs_review'
    assert out['recorded_approval_before_analysis'] is False


def test_provenance_cli_retains_sources_and_writes_an_unverified_result(plan_evidence, tmp_path):
    plan, _ = plan_evidence
    out = tmp_path/'audit-stage/PLAN_PROVENANCE.json'
    result = subprocess.run([sys.executable, str(ROOT/'tools/check_plan_provenance.py'),
        '--plan', str(plan), '--out', str(out)], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == json.loads(out.read_text(encoding="utf-8-sig"))
    assert json.loads(out.read_text(encoding="utf-8-sig"))['status'] == 'unverified'
