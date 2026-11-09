"""Execute event export, QC availability and continuous-report/recipe handoffs."""
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import runpy
import textwrap

import mne
import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("mne_bids")
from mne_bids import BIDSPath, write_raw_bids

ROOT = Path(__file__).resolve().parents[2]
events = runpy.run_path(str(ROOT/'skills/eeg-bids/scripts/events.py'))
spectral = runpy.run_path(str(ROOT/'skills/eeg-qc/scripts/spectral.py'))
inputs = runpy.run_path(str(ROOT/'skills/eeg-report/scripts/inputs.py'))
preparation = runpy.run_path(str(ROOT/'skills/eeg-microstate/scripts/preparation.py'))
mne.set_log_level('ERROR')


def example(skill, label, **context):
    if skill.startswith('recipe:'):
        path = ROOT/'recipes'/skill.split(':')[1]/'RECIPE.md'
    else:
        path = ROOT/f'skills/{skill}/references/procedure.md'
    code, = [textwrap.dedent(x) for x in re.findall(r'```python\n(.*?)```', path.read_text(encoding="utf-8-sig"), re.S)
             if f'# AEA example: {label}\n' in x]
    ns = dict(mne=mne, np=np, AEA_ROOT=str(ROOT), preparation=preparation)
    ns.update(context)
    exec(compile(code, f'{skill}:{label}', 'exec'), ns)
    return ns


def recording(tmp_path, source, first_samp=0, dated=False):
    raw=mne.io.RawArray(np.zeros((1,1250)),mne.create_info(['Cz'],250,'eeg'),first_samp=first_samp)
    raw.info['line_freq']=50
    if dated: raw.set_meas_date(datetime(2020,1,2,tzinfo=timezone.utc))
    if source=='annotations':
        raw.set_annotations(mne.Annotations([1.,2.,3.],[.1,.2,.3],['target','standard','deviant']))
        mapping={'target':1,'standard':2,'deviant':3};auxiliary={};supplied=None
    else:
        raw.set_annotations(mne.Annotations([.5],[.25],['BAD_motion']))
        mapping={'target':17,'standard':29};auxiliary={'BAD_motion':99}
        supplied=np.column_stack([first_samp+np.array([250,500,750]),np.zeros(3,int),[17,29,17]])
    path=tmp_path/'input-raw.fif';raw.save(path,overwrite=True)
    return mne.io.read_raw_fif(path,preload=False),mapping,auxiliary,supplied


@pytest.mark.parametrize('source,first_samp,dated',[
    ('annotations',0,False),('annotations',500,False),('annotations',500,True),
    ('external',500,False),('external',500,True),('stim',0,False)])
def test_actual_documented_bids_roundtrip_preserves_one_task_source(tmp_path,source,first_samp,dated):
    raw,mapping,auxiliary,supplied=recording(tmp_path,source,first_samp,dated)
    original=raw.annotations.copy();before=raw.get_data().copy()
    out=example('eeg-bids','bids-event-inputs',raw=raw,approved_event_source=source,
        approved_event_id=mapping,approved_auxiliary_annotation_event_id=auxiliary,approved_events=supplied)
    bidspath=BIDSPath(subject='01',task='oddball',datatype='eeg',root=tmp_path/'bids')
    out=example('eeg-bids','bids-event-write-check',**out,bids_path=bidspath,
        approved_bids_write_params={'format':'BrainVision','overwrite':False},approved_event_time_atol_s=1e-9)
    frame=pd.read_csv(out['events_path'],sep='\t')
    assert out['event_kwargs']['events'] is None
    assert len(frame)==(3 if source=='annotations' else 4)
    task=frame.loc[frame['trial_type']!='BAD_motion']
    assert task['onset'].tolist()==[1.,2.,3.] and task['sample'].tolist()==[250,500,750]
    assert task['trial_type'].tolist()==(['target','standard','deviant'] if source=='annotations'
                                         else ['target','standard','target'])
    if source!='annotations':
        bad=frame.loc[frame['trial_type']=='BAD_motion'].iloc[0]
        assert bad['onset']==.5 and bad['duration']==.25
    assert out['event_check']['status']=='passed'
    np.testing.assert_array_equal(raw.annotations.onset,original.onset)
    np.testing.assert_array_equal(raw.annotations.duration,original.duration)
    np.testing.assert_array_equal(raw.get_data(),before)
    json.dumps(out['event_receipt'],allow_nan=False)


def test_event_export_rejects_unsynchronized_codes_and_duplicate_task_sources(tmp_path):
    raw,mapping,auxiliary,supplied=recording(tmp_path,'external')
    bad=supplied.copy();bad[0,2]=100
    with pytest.raises(ValueError,match='Actual event codes'):
        events['prepare_event_export'](raw,source='external',event_id=mapping,
                                       additional_annotation_event_id=auxiliary,events=bad)
    raw.set_annotations(mne.Annotations([1.],[0.],['target']))
    with pytest.raises(ValueError,match='duplicate task events'):
        events['prepare_event_export'](raw,source='external',event_id=mapping,
                                       additional_annotation_event_id={},events=supplied)
    with pytest.raises(ValueError,match='events=None'):
        events['prepare_event_export'](raw,source='annotations',event_id=mapping,
                                       additional_annotation_event_id={},events=supplied)


@pytest.mark.parametrize('field',['trial_type','value','sample','onset','duration','count'])
def test_export_readback_detects_each_identity_timing_or_count_corruption(tmp_path,field):
    raw,mapping,auxiliary,supplied=recording(tmp_path,'annotations')
    _,_,receipt=events['prepare_event_export'](raw,source='annotations',event_id=mapping,
        additional_annotation_event_id=auxiliary,events=supplied)
    frame=pd.DataFrame(receipt['expected_events'])
    if field=='count': frame=pd.concat([frame,frame.iloc[[0]]])
    elif field=='trial_type': frame.loc[0,field]='deviant'
    else: frame.loc[0,field]+=1
    path=tmp_path/'events.tsv';frame.to_csv(path,sep='\t',index=False)
    with pytest.raises(ValueError,match='Exported event'):
        events['check_exported_events'](path,receipt=receipt,time_atol_s=1e-9)


def test_continuous_record_can_explicitly_have_no_events(tmp_path):
    raw=mne.io.RawArray(np.zeros((1,500)),mne.create_info(['Cz'],250,'eeg'))
    _,_,receipt=events['prepare_event_export'](raw,source='annotations',event_id={},
                                              additional_annotation_event_id={},events=None)
    result=events['check_exported_events'](tmp_path/'missing-events.tsv',receipt=receipt,time_atol_s=1e-9)
    assert result['n_events']==0 and not result['events_file_present']


def line_params():
    return dict(numerator_band=[49.,51.],denominator_bands=[[46.,48.],[52.,54.]],statistic='mean_density')


def test_documented_qc_40hz_psd_cannot_pass_a_50hz_gate():
    time=np.arange(2500)/250
    raw=mne.io.RawArray(np.sin(2*np.pi*50*time)[None,:]*1e-6,mne.create_info(['Cz'],250,'eeg'))
    data=raw.get_data().copy()
    out=example('eeg-qc','qc-spectral-availability',raw=raw,recorded_input_filter_support_hz=[0.,125.],
        approved_line_ratio_params=line_params(),approved_qc_psd_params={'method':'welch',
            'fmin':1.,'fmax':40.,'n_fft':500,'n_per_seg':500,'n_overlap':250,'window':'hann','picks':'eeg'})
    assert out['line_metric']['status']=='unavailable' and out['line_metric']['values'] is None
    def gate_should_not_run(values): raise AssertionError('Unavailable values entered a numeric gate')
    out=example('eeg-qc','qc-availability-gate',**out,gates={'amplitude':'pass'},
                approved_line_gate=gate_should_not_run)
    assert out['gates']['line_ratio']=='unavailable' and out['verdict']=='incomplete'
    np.testing.assert_array_equal(raw.get_data(),data)
    json.dumps(out['line_metric'],allow_nan=False)


@pytest.mark.parametrize('statistic,expected',[('mean_density',10.),('integrated_power',5.)])
def test_explicit_qc_ratio_definition_has_correct_units_and_value(statistic,expected):
    freqs=np.arange(0.,101.,.5);psd=np.ones((2,len(freqs)))
    psd[:,(freqs>=49)&(freqs<=51)]=10.
    params=line_params();params['statistic']=statistic
    result=spectral['band_ratio'](psd,freqs,**params,supported_band_hz=[0.,125.],nyquist_hz=125.)
    assert result['status']=='computed'
    np.testing.assert_allclose(result['values'],expected)


@pytest.mark.parametrize('defect',['filtered','unknown_filter','nyquist','zero_denominator','few_bins'])
def test_qc_reports_unavailable_instead_of_filling_invalid_ratio(defect):
    freqs=np.arange(0.,101.,.5);psd=np.ones((1,len(freqs)));support=[0.,125.];nyquist=125.
    if defect=='filtered': support=[1.,40.]
    elif defect=='unknown_filter': support=None
    elif defect=='nyquist': nyquist=40.
    elif defect=='zero_denominator': psd[:]=0.
    else: freqs=np.arange(0.,101.,10.);psd=np.ones((1,len(freqs)))
    result=spectral['band_ratio'](psd,freqs,**line_params(),supported_band_hz=support,nyquist_hz=nyquist)
    assert result['status']=='unavailable' and result['reasons']
    assert spectral['qc_verdict']({'line_ratio':'unavailable','amplitude':'pass'})=='incomplete'
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('gates,verdict',[
    ({'a':'pass','b':'not_applicable'},'pass'),({'a':'warn','b':'pass'},'warn'),
    ({'a':'fail','b':'unavailable'},'fail'),({'a':'warn','b':'unavailable'},'incomplete'),
    ({'a':'not_applicable'},'incomplete')])
def test_qc_verdict_preserves_measured_failures_and_missing_coverage(gates,verdict):
    assert spectral['qc_verdict'](gates)==verdict


def make_run(tmp_path, stages):
    for name in ('ANALYSIS_PLAN.md','DATASET_BRIEF.md','ENVIRONMENT.json'):
        (tmp_path/name).write_text('{}', encoding="utf-8")
    required={}
    for stage in stages:
        file=tmp_path/f'{stage}-stage/S1/actual-output.json';file.parent.mkdir(parents=True)
        file.write_text('{}', encoding="utf-8");required[stage]=[f'{stage}-stage/S1/actual-output.json']
    return required


def test_continuous_methods_and_report_cover_all_five_previously_missing_stages(tmp_path):
    stages=['spectral','complexity','microstate','qc','behavior']
    required=make_run(tmp_path,stages)
    old=tmp_path/'epoch-stage';old.mkdir();(old/'old-output.txt').write_text('old run', encoding="utf-8")
    out=example('eeg-report','report-stage-inventory',run_dir=tmp_path,
        approved_reporting_stages=stages,recorded_required_stage_sources=required)
    saved=json.loads((tmp_path/'report-stage/STAGE_INVENTORY.json').read_text(encoding="utf-8-sig"))
    assert all(saved[stage]['status']=='available' for stage in stages)
    assert saved['epoch']['status']=='not_applicable' and saved['epoch']['directory_present']
    methods=example('eeg-methods-text','methods-stage-inputs',run_dir=tmp_path,
        approved_reporting_stages=stages,recorded_required_stage_sources=required)
    assert methods['stage_inventory']['stats']['status']=='not_applicable'


def test_planned_missing_source_blocks_methods_even_if_a_directory_exists(tmp_path):
    required=make_run(tmp_path,['microstate']);required['microstate']=['microstate-stage/S1/missing-params.json']
    with pytest.raises(ValueError,match='missing-params.json'):
        example('eeg-methods-text','methods-stage-inputs',run_dir=tmp_path,
            approved_reporting_stages=['microstate'],recorded_required_stage_sources=required)
    out=example('eeg-report','report-stage-inventory',run_dir=tmp_path,
        approved_reporting_stages=['microstate'],recorded_required_stage_sources=required)
    assert out['stage_inventory']['microstate']['status']=='unavailable'


def test_statistical_reporting_can_use_actual_noncluster_outputs(tmp_path):
    required=make_run(tmp_path,['stats']);file=tmp_path/'stats-stage/S1/actual-output.json'
    file.rename(file.with_name('C1_ttest.json'));required['stats']=['stats-stage/*/C1_ttest.json']
    out=example('eeg-methods-text','methods-stage-inputs',run_dir=tmp_path,
        approved_reporting_stages=['stats'],recorded_required_stage_sources=required)
    assert out['stage_inventory']['stats']['status']=='available'


def test_missing_core_provenance_is_not_filled_from_an_unrelated_run(tmp_path):
    required=make_run(tmp_path,['spectral']);(tmp_path/'ENVIRONMENT.json').unlink()
    with pytest.raises(ValueError,match='ENVIRONMENT.json'):
        example('eeg-methods-text','methods-stage-inputs',run_dir=tmp_path,
            approved_reporting_stages=['spectral'],recorded_required_stage_sources=required)


def microstate_raw(sfreq=250.):
    pytest.importorskip("pycrostates")
    time=np.arange(round(6*sfreq))/sfreq
    data=1e-6*(np.sin(2*np.pi*18*time)[None,:]*np.array([[3.],[-2.],[-1.]])+
               .4*np.cos(2*np.pi*7*time)[None,:]*np.array([[1.],[1.],[-2.]]))
    return mne.io.RawArray(data,mne.create_info(['Fz','Cz','Pz'],sfreq,'eeg')).set_montage('standard_1020')


def prepare_params():
    return dict(channels=['Pz','Fz','Cz'],filter_kwargs={'l_freq':3.,'h_freq':25.,'method':'iir',
        'iir_params':{'order':2,'ftype':'butter'}},reference='average',min_peak_distance=3,
        reject_by_annotation=True,gfp_reject_sd=None,gfp_reference='continuous',max_peaks=17,seed=11)


def backfit_params(unit='ms'):
    return dict(factor=10,tol=1e-5,half_window={'value':30.,'unit':unit},
                min_segment={'value':20.,'unit':unit},reject_edges=True,reject_by_annotation=True)


@pytest.mark.parametrize('sfreq,half,minimum',[(160.,5,3),(250.,8,5)])
def test_recipe_and_skill_share_explicit_physical_smoothing_policy(sfreq,half,minimum):
    raw=microstate_raw(sfreq)
    class CapturedSegmentation:
        def compute_parameters(self): return {'synthetic_capture':True}
    class CaptureModel:
        def predict(self,inst,**kwargs): self.kwargs=kwargs;return CapturedSegmentation()
    model=CaptureModel();settings=backfit_params()
    recipe=example('recipe:resting-microstate','recipe-microstate-backfit',prepared_raw=raw,
        approved_fitted_model=model,approved_microstate_backfit=settings)
    skill=example('eeg-microstate','microstate-backfit',raw=raw,
        approved_fitted_model=model,approved_microstate_backfit=settings)
    assert recipe['backfit_audit']==skill['backfit_audit']
    assert recipe['backfit_audit']['predict_kwargs']['half_window_size']==half
    assert recipe['backfit_audit']['predict_kwargs']['min_segment_length']==minimum


def test_approved_sample_units_are_not_replaced_by_physical_example():
    class CaptureModel:
        def predict(self,inst,**kwargs): self.kwargs=kwargs;return 'segmentation'
    settings=backfit_params('samples');settings['half_window']['value']=3;settings['min_segment']['value']=8
    model=CaptureModel()
    for sfreq in (160.,250.):
        _,audit=preparation['backfit_microstates'](microstate_raw(sfreq),model,settings=settings)
        assert audit['predict_kwargs']['half_window_size']==3
        assert audit['predict_kwargs']['min_segment_length']==8


def test_recipe_preparation_and_real_backfit_use_the_same_shared_helpers():
    pytest.importorskip("pycrostates")
    from pycrostates.cluster import ModKMeans
    raw=microstate_raw();original=raw.get_data().copy();policy=prepare_params()
    recipe=example('recipe:resting-microstate','recipe-microstate-preparation',raw=raw,
        approved_microstate_preparation=policy)
    assert recipe['gfp_peaks'].get_data().shape[1]==17
    direct=preparation['prepare_peaks'](raw,**policy)
    np.testing.assert_array_equal(recipe['gfp_peaks'].get_data(),direct[1].get_data())
    model=ModKMeans(n_clusters=2,n_init=2,max_iter=50,random_state=4)
    model.fit(recipe['gfp_peaks'],n_jobs=1)
    recipe=example('recipe:resting-microstate','recipe-microstate-backfit',**recipe,
        approved_fitted_model=model,approved_microstate_backfit=backfit_params())
    skill=example('eeg-microstate','microstate-backfit',raw=direct[0],approved_fitted_model=model,
        approved_microstate_backfit=backfit_params())
    np.testing.assert_array_equal(recipe['segmentation'].labels,skill['segmentation'].labels)
    assert recipe['backfit_audit']['predict_kwargs']==skill['backfit_audit']['predict_kwargs']
    np.testing.assert_array_equal(raw.get_data(),original)


def test_explicit_no_additional_filter_preserves_prepared_data():
    raw=microstate_raw().filter(3.,25.,method='iir',iir_params={'order':2,'ftype':'butter'})
    raw.set_eeg_reference('average');original=raw.get_data().copy()
    policy=prepare_params();policy['filter_kwargs']={'l_freq':None,'h_freq':None}
    prepared,_,_=preparation['prepare_peaks'](raw,**policy)
    np.testing.assert_allclose(prepared.get_data(),original[[2,0,1]],rtol=0,atol=1e-20)
