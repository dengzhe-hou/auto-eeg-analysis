"""One-call regressions for the observed early-stop and lost-group-state failures."""
import csv
import json
from pathlib import Path
import sys

import mne
import numpy as np
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import run_erp_plan as entry


@pytest.fixture
def plan():
    return {'request_kind':'single_subject','component':'P3b','subjects':['sub-001'],
            'dataset':{'name':'ERP CORE','doi':'10.18115/D5JW4R','bids_task_label':'P3'},
            'analysis':{
                'channels':{'drop_before_processing':['HEOG_left','HEOG_right','VEOG_lower'],
                            'montage':'standard_1020','montage_match_case':False},
                'filter':{'type':'zero-phase FIR band-pass, mne.io.Raw.filter defaults',
                          'l_freq_hz':.1,'h_freq_hz':30.,'l_trans_bandwidth_hz':.1,
                          'h_trans_bandwidth':'MNE default rule: a quarter of the upper cutoff and at least 2 Hz',
                          'fir_design':'firwin','fir_window':'hamming','filter_length':'auto',
                          'pad':'reflect_limited','n_jobs':1},
                'resample_hz':256.,'resample_method':'mne.io.Raw.resample default',
                'reference':'average of the 30 scalp channels, applied directly (projection False)',
                'processing_order':['drop the three EOG channels','set montage','band-pass filter',
                                    'resample to 256 Hz','average reference','epoch'],
                'events':{'keep':'samples strictly inside the recording','sample_rule':'round(onset_seconds * 256)'},
                'epoch_s':[-.2,.8],'baseline_s':[-.2,0.],'rejection':'none',
                'minimum_trials':{'plus':2,'minus':2},'roi':['Cz','Pz'],
                'window_s':[.3,.5],'window_endpoints':'inclusive'},
            'derivatives':{'root':'derivatives/erp-analysis','contrast_label':'rareminusfrequent'},
            'group_test':{
                't_test':{'test':'two-sided one-sample t-test against zero','alpha':.05},
                'cluster':{'threshold':'one-sided t quantile at 0.95 with n_subjects minus 1 degrees of freedom, signed as the tail',
                           'tail':1,'function':'mne.stats.spatio_temporal_cluster_1samp_test',
                           'n_permutations':5000,'significant_if':'at least one cluster has p < 0.05'}},
            'required_results':dict.fromkeys(['status','component','dataset_doi','dataset_version','explanation',
                                             'subject','roi_amplitude_uv','n_trials_plus','n_trials_minus']),
            'required_evidence':dict.fromkeys(['times_s','roi_difference_uv'])}


def synthetic_inputs(tmp_path, plan, monkeypatch):
    root=tmp_path/'input';root.mkdir()
    (root/'CHANGES').write_text('Revision history\nversion 1.0 - 20 Jul 2020\n', encoding="utf-8")
    (root/'task-P3_events.json').write_text(json.dumps({'value':{'Levels':{
        '11':'Stimulus - block target A, trial stimulus A',
        '12':'Stimulus - block target A, trial stimulus B'}}}), encoding="utf-8")
    for subject in plan['subjects']:
        folder=root/subject/'ses-P3/eeg';folder.mkdir(parents=True)
        (folder/f'{subject}_task-P3_eeg.set').write_text('Synthetic read_raw fixture; not a real SET file', encoding="utf-8")
        with (folder/f'{subject}_task-P3_events.tsv').open('w',newline='', encoding="utf-8") as stream:
            writer=csv.writer(stream,delimiter='\t');writer.writerow(['trial_type','value','onset'])
            writer.writerows([['stimulus',11,5],['stimulus',12,15],['stimulus',11,25],['stimulus',12,35]])
    channels='Fp1 Fp2 F7 F3 Fz F4 F8 FC5 FC1 FCz FC2 FC6 T7 C3 Cz C4 T8 CP5 CP1 CPz CP2 CP6 P7 P3 Pz P4 P8 PO7 PO8 Oz'.split()
    channels+=plan['analysis']['channels']['drop_before_processing']
    data=np.zeros((33,50*256))
    for onset,value in [(5,8),(15,2),(25,10),(35,4)]:
        data[[channels.index('Cz'),channels.index('Pz')],int((onset+.1)*256):int((onset+.7)*256)]=value*1e-6
    raw=mne.io.RawArray(data,mne.create_info(channels,256.,'eeg'),verbose=False)
    calls=[]
    def read(path,**kwargs):
        calls.append(str(path));return raw.copy()
    monkeypatch.setattr(mne.io,'read_raw_eeglab',read)
    return root,calls,raw


def test_complete_entry_executes_order_and_delivers_real_named_roi(tmp_path,plan,monkeypatch):
    root,calls,raw=synthetic_inputs(tmp_path,plan,monkeypatch)
    original=raw.get_data().copy();out=tmp_path/'run'
    result,check=entry.run_plan(plan,root,out,atol_uv=1e-9)
    assert len(calls)==1 and check['passed'] and result['dataset_version']=='1.0'
    assert [result[k] for k in ('n_trials_plus','n_trials_minus')]==[2,2]
    state=entry.load_group_state(out/'participant-state',plan=plan)
    assert result['roi_amplitude_uv']==pytest.approx(state['result_fields']['group_mean_uv'])
    assert result['roi_amplitude_uv']>1 and abs(state['differences_uv'].mean())<1e-12
    assert json.loads((out/'FINAL_SUBMISSION.md').read_text(encoding="utf-8-sig"))==result
    np.testing.assert_array_equal(raw.get_data(),original)
    operations=json.loads((out/'execution.json').read_text(encoding="utf-8-sig"))['steps'][1]['operations']
    assert [s['operation'] for s in operations]==['read','drop_EOG_and_set_montage','filter','resample_and_average_reference','epoch']
    assert operations[2]['actual_arguments']['l_trans_bandwidth']==.1
    assert operations[-1]['event_rows_retained_for_epoching']==[0,1,2,3]
    assert (out/'executed-source/tools/run_erp_plan.py').read_bytes()==(ROOT/'tools/run_erp_plan.py').read_bytes()
    first=(out/'FINAL_SUBMISSION.md').read_bytes()
    with pytest.raises(FileExistsError,match='Completed delivery'):entry.run_plan(plan,root,out,atol_uv=1e-9,resume=True)
    assert (out/'FINAL_SUBMISSION.md').read_bytes()==first and len(calls)==1


def test_resume_reuses_each_saved_participant_after_statistics_error(tmp_path,plan,monkeypatch):
    plan.update(request_kind='group',subjects=['sub-001','sub-002'])
    plan['required_results']=dict.fromkeys(['status','dataset_version','subjects_included','subjects_excluded',
                                          'n_subjects','per_subject_amplitude_uv','group_mean_uv','effect_direction',
                                          'ttest_t','ttest_p','ttest_significant','cluster_min_p','cluster_significant'])
    plan['required_evidence']=dict.fromkeys(['subjects','roi_amplitudes_uv','times_s','grand_roi_difference_uv'])
    root,calls,_=synthetic_inputs(tmp_path,plan,monkeypatch);out=tmp_path/'run'
    def fail(*args):raise NameError('observed lost-statistic-variable regression')
    monkeypatch.setattr(entry,'_group_statistics',fail)
    with pytest.raises(NameError):entry.run_plan(plan,root,out,atol_uv=1e-9)
    first=[(out/'participant-state'/f'{s}.npz').read_bytes() for s in plan['subjects']]
    assert len(calls)==2 and json.loads((out/'execution.json').read_text(encoding="utf-8-sig"))['status']=='failed'
    monkeypatch.setattr(entry,'_group_statistics',lambda *args:{'ttest_t':2.,'ttest_p':.1,'ttest_significant':False,
                                                            'cluster_min_p':1.,'cluster_significant':False})
    result,check=entry.run_plan(plan,root,out,atol_uv=1e-9,resume=True)
    assert check['passed'] and result['n_subjects']==2 and len(calls)==2
    assert first==[(out/'participant-state'/f'{s}.npz').read_bytes() for s in plan['subjects']]
    attempts=json.loads((out/'execution.json').read_text(encoding="utf-8-sig"))['attempts']
    assert len(attempts)==2 and attempts[0]['error']['type']=='NameError'


@pytest.mark.parametrize('tail',[-1,1])
def test_group_test_uses_full_saved_array_and_requested_tail_without_new_seed(tmp_path,plan,monkeypatch,tail):
    plan['group_test']['cluster']['tail']=tail
    info=mne.create_info(['Cz','Pz','Fz'],256.,'eeg')
    state={'info':info,'channels':info.ch_names,'cluster_data_uv':np.arange(60.).reshape(5,4,3),
           'evidence':{'roi_amplitudes_uv':np.array([-2.,-3.,-1.,-2.,-4.])}}
    monkeypatch.setattr(mne.channels,'find_ch_adjacency',lambda *a,**kw:(np.eye(3),info.ch_names))
    observed={}
    def cluster(data,**kwargs):
        observed.update(kwargs);np.testing.assert_array_equal(data,state['cluster_data_uv'])
        return np.ones((4,3)),[(np.array([0]),np.array([1]))],np.array([.02]),np.array([1.,2.])
    monkeypatch.setattr(mne.stats,'spatio_temporal_cluster_1samp_test',cluster)
    result=entry._group_statistics(plan,state,tmp_path)
    assert observed['threshold']==pytest.approx(tail*stats.t.ppf(.95,4))
    assert observed['n_permutations']==5000 and observed['tail']==tail and observed['seed'] is None
    assert result['cluster_significant'] is True
    assert result['ttest_p']==pytest.approx(stats.ttest_1samp(state['evidence']['roi_amplitudes_uv'],0.).pvalue)
    assert (tmp_path/'cluster_rng_before.json').is_file() and (tmp_path/'cluster_evidence.npz').is_file()


def test_actual_low_retained_counts_deliver_ineligible_without_invented_amplitude(tmp_path,plan,monkeypatch):
    plan['analysis']['minimum_trials']['plus']=3
    root,_,_=synthetic_inputs(tmp_path,plan,monkeypatch)
    result,check=entry.run_plan(plan,root,tmp_path/'run',atol_uv=1e-9)
    assert check['passed'] and result['status']=='ineligible'
    assert result['roi_amplitude_uv'] is None and result['n_trials_plus']==2
    with np.load(tmp_path/'run/analysis_evidence.npz') as data:assert 'roi_difference_uv' not in data.files
