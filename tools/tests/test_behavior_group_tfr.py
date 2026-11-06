"""Identity-preserving behavior, group-statistic outputs and TFR time grids."""
from pathlib import Path
import re
import runpy
import sys
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mne
import numpy as np
import pytest

pd = pytest.importorskip("pandas")
from scipy.stats import t, ttest_rel

ROOT = Path(__file__).resolve().parents[2]
trials = runpy.run_path(str(ROOT/'skills/eeg-behavior/scripts/trials.py'))
statistics = runpy.run_path(str(ROOT/'skills/eeg-group-compare/scripts/statistics.py'))
mne.set_log_level('ERROR')


def example(skill, label, **context):
    source = (ROOT/f'skills/{skill}/references/procedure.md').read_text(encoding="utf-8-sig")
    code, = [textwrap.dedent(x) for x in re.findall(r'```python\n(.*?)```', source, re.S)
             if f'# AEA example: {label}\n' in x]
    ns = {'mne':mne, 'np':np, 'pd':pd, 'AEA_ROOT':str(ROOT), **context}
    exec(compile(code, f'{skill}:{label}', 'exec'), ns)
    return ns


def response_policy(**overrides):
    return dict(group_keys=['subject','block'], trial_keys=['subject','block','stim_sample'],
        sfreq=1000., response_window_ms=[0.,1000.], stop_at_next_stimulus=True,
        assignment='first_unused', **overrides)


def stimulus_table(samples=(100,500), block='A'):
    return pd.DataFrame({'subject':['S1']*len(samples),'block':[block]*len(samples),
                         'stim_sample':samples,'condition':[17]*len(samples)})


def response_table(samples=(700,), block='A'):
    return pd.DataFrame({'subject':['S1']*len(samples),'block':[block]*len(samples),
                         'response_sample':samples,'response_code':[29]*len(samples)})


def test_missed_trial_does_not_borrow_the_next_trials_response():
    df,audit=trials['match_responses'](stimulus_table(),response_table(),**response_policy())
    assert df['status'].tolist()==['missed','matched']
    assert np.isnan(df.iloc[0]['rt']) and df.iloc[1]['rt']==200.
    assert audit['n_missed']==audit['n_matched']==1


def test_explicit_overlapping_window_policy_still_never_reuses_a_response():
    policy=response_policy();policy['stop_at_next_stimulus']=False
    df,audit=trials['match_responses'](stimulus_table(),response_table(),**policy)
    assert df['status'].tolist()==['matched','missed']
    assert df.iloc[0]['rt']==600. and audit['n_matched']==1


def test_identical_sample_numbers_in_different_blocks_do_not_cross_match():
    stimuli=pd.concat([stimulus_table((100,),block='A'),stimulus_table((100,),block='B')])
    df,audit=trials['match_responses'](stimuli,response_table((300,),block='B'),**response_policy())
    assert df['status'].tolist()==['missed','matched']
    assert df.iloc[1]['block']=='B' and audit['n_missed']==1


def test_rt_window_uses_the_explicit_half_open_boundary():
    policy=response_policy();policy['response_window_ms']=[100.,200.]
    df,audit=trials['match_responses'](stimulus_table((100,)),response_table((200,300)),**policy)
    assert df.iloc[0]['rt']==100.
    assert [r['response_sample'] for r in audit['unassigned_responses']]==[300]


def test_duplicate_source_rows_and_multiple_candidates_are_retained_in_audit():
    df,audit=trials['match_responses'](stimulus_table((100,)),response_table((400,300,300)),**response_policy())
    assert df.iloc[0]['response_row']==1 and df.iloc[0]['eligible_response_count']==3
    assert audit['duplicate_response_rows']==[1,2]
    assert len(audit['unassigned_responses'])==2


def test_unapproved_assignment_is_not_inferred():
    policy=response_policy();policy['assignment']='nearest'
    with pytest.raises(ValueError,match='first_unused'):
        trials['match_responses'](stimulus_table(),response_table(),**policy)


def test_documented_response_example_preserves_nondefault_codes_and_misses():
    raw=mne.io.RawArray(np.zeros((1,1200)),mne.create_info(['Cz'],1000,'eeg'))
    raw.set_annotations(mne.Annotations([.1,.5,.7],[0.,0.,0.],['stim','stim','resp']))
    policy=response_policy();policy.pop('sfreq')
    out=example('eeg-behavior','behavior-responses',raw=raw,
        recording_identity={'subject':'S1','block':'A'},is_correct=lambda stim,response:response==29,
        approved_behavior_params={'event_id':{'stim':17,'resp':29},'use_rounding':True,
            'stim_codes':[17],'resp_codes':[29],'response_policy':policy})
    assert out['df']['correct'].tolist()==[False,True]
    assert out['df']['stim_sample'].tolist()==[100,500]
    assert out['response_audit']['n_matched']==1


def identity_tables():
    eeg=pd.DataFrame({'subject':['S1']*4,'block':['A']*4,'trial':[1,3,4,5],
                      'eeg_amp':[1.,3.,4.,5.]})
    behavior=pd.DataFrame({'subject':['S1']*5,'block':['A']*5,'trial':[1,2,3,4,5],
                           'rt':[100.,200.,300.,400.,500.]})
    return eeg,behavior


def test_trial_join_is_invariant_to_behavior_row_order_and_reports_missing_ids():
    eeg,behavior=identity_tables()
    out,audit=trials['align_trials'](eeg,behavior.iloc[[4,0,2,1,3]],
        keys=['subject','block','trial'],right_columns=['rt'],unmatched_policy='intersection')
    assert out['trial'].tolist()==[1,3,4,5] and out['rt'].tolist()==[100.,300.,400.,500.]
    assert audit['unmatched_right']==[{'subject':'S1','block':'A','trial':2}]
    assert audit['unmatched_left']==[]


def test_unmatched_error_policy_does_not_silently_take_intersection():
    eeg,behavior=identity_tables()
    with pytest.raises(ValueError,match='Unmatched observation'):
        trials['align_trials'](eeg,behavior,keys=['subject','block','trial'],
                               right_columns=['rt'],unmatched_policy='error')


@pytest.mark.parametrize('defect',['duplicate','missing'])
def test_trial_join_rejects_invalid_identity(defect):
    eeg,behavior=identity_tables()
    if defect=='duplicate': behavior=pd.concat([behavior,behavior.iloc[[0]]])
    else: behavior.loc[0,'trial']=np.nan
    with pytest.raises(ValueError,match='observation identity'):
        trials['align_trials'](eeg,behavior,keys=['subject','block','trial'],
                               right_columns=['rt'],unmatched_policy='intersection')


def paired_table():
    return pd.DataFrame({'subject':['S1','S2','S3','S4']*2,
        'condition':['A']*4+['B']*4,'value':[100.,200.,300.,400.,151.,249.,352.,448.]})


def pairing_spec(**overrides):
    return dict(unit_keys=['subject'],condition_column='condition',conditions=['A','B'],
                value_column='value',unmatched_policy='error',**overrides)


def test_true_pair_ids_make_p_value_invariant_to_reordering():
    table=paired_table()
    a,b,audit=trials['paired_values'](table.iloc[[0,1,2,3,6,4,7,5]],**pairing_spec())
    np.testing.assert_array_equal(a,[100,200,300,400])
    np.testing.assert_array_equal(b,[151,249,352,448])
    assert ttest_rel(a,b).pvalue==pytest.approx(1.3405035117843083e-5)
    assert audit['n_matched']==4


def test_trials_cannot_be_automatically_aggregated_or_fabricated_into_subject_pairs():
    table=paired_table();table['subject']='S1'
    with pytest.raises(ValueError,match='observation identity'):
        trials['paired_values'](table,**pairing_spec())


def test_missing_pair_is_explicit_and_the_approved_intersection_is_logged():
    table=paired_table().drop(index=5)
    with pytest.raises(ValueError,match='Unmatched observation'):
        trials['paired_values'](table,**pairing_spec())
    policy=pairing_spec();policy['unmatched_policy']='intersection'
    a,b,audit=trials['paired_values'](table,**policy)
    assert len(a)==len(b)==3 and audit['unmatched_left']==[{'subject':'S2'}]


def test_documented_paired_test_uses_the_true_ids():
    out=example('eeg-behavior','behavior-paired-test',
        comparison_table=paired_table().iloc[[0,1,2,3,6,4,7,5]],
        approved_behavior_params={'condition_test':dict(method='paired_t',
            alternative='two-sided',pairing=pairing_spec())})
    assert out['p']==pytest.approx(1.3405035117843083e-5)


def run_regression_example(tmp_path,subjects):
    eeg,behavior=identity_tables();eeg['subject']=subjects
    if len(set(subjects))>1: behavior['subject']=['S1','S1','S1','S2','S2']
    ep=mne.EpochsArray(np.repeat(eeg['eeg_amp'].to_numpy()[:,None,None]*1e-6,101,axis=2),
        mne.create_info(['Cz'],100,'eeg'),tmin=-.1,metadata=eeg[['subject','block','trial']])
    path=tmp_path/'retained-epo.fif';ep.save(path)
    return example('eeg-behavior','behavior-eeg-regression',epochs_path=str(path),roi=['Cz'],
        tmin=0.,tmax=.2,df_clean=behavior.iloc[[4,0,3,2,1]],
        approved_behavior_params=dict(trial_keys=['subject','block','trial'],
            unmatched_policy='intersection',regression_method='single_subject_ols',subject_column='subject'))


def test_documented_eeg_regression_recovers_the_fixture_after_trial_rejection(tmp_path):
    out=run_regression_example(tmp_path,['S1']*4)
    assert out['aligned']['trial'].tolist()==[1,3,4,5]
    assert out['beta']==pytest.approx(100.,rel=1e-6)
    assert out['alignment_audit']['unmatched_right'][0]['trial']==2


def test_documented_ols_does_not_accept_pooled_subjects(tmp_path):
    with pytest.raises(ValueError,match='pool multiple subjects'):
        run_regression_example(tmp_path,['S1','S1','S2','S2'])


@pytest.mark.parametrize('tail,expected',[(0,2.0930240544083087),(1,1.7291328115213682),(-1,-1.7291328115213682)])
def test_alpha_to_t_threshold_matches_the_approved_tail(tail,expected):
    value=statistics['cluster_t_threshold'](n_observations=20,cluster_forming_alpha=.05,tail=tail)
    assert value==pytest.approx(expected)
    mass=2*t.sf(abs(value),19) if tail==0 else t.sf(abs(value),19)
    assert mass==pytest.approx(.05)


def test_tfce_map_uses_masks_not_the_order_of_the_flat_p_array():
    masks=[]
    for point in [5,0,3,1,4,2]:
        mask=np.zeros((2,3),bool);mask.flat[point]=True;masks.append(mask)
    result=statistics['tfce_p_map'](np.zeros((2,3)),masks,[.1,.2,.3,.4,.5,.6])
    np.testing.assert_allclose(result,[[.2,.4,.6],[.3,.5,.1]])


def test_ordinary_cluster_p_values_are_not_misrepresented_as_a_tfce_point_map():
    with pytest.raises(ValueError,match='singleton masks'):
        statistics['tfce_p_map'](np.zeros((2,3)),[np.ones((2,3),bool)],[.01])


def group_params(**overrides):
    return {**dict(design='within',statistic='t',tail=0,cluster_forming_alpha=.05,
                   alpha=.05,n_permutations=16,seed=31,tfce_threshold={'start':0.,'step':.2}),
            **overrides}


@pytest.mark.parametrize('tail',[-1,0,1])
def test_documented_within_cluster_uses_the_right_threshold_and_native_statistic(tail):
    x=np.random.default_rng(8).normal(size=(20,3,2)) + (-.8 if tail==-1 else .8)
    out=example('eeg-group-compare','group-cluster',X=x,adjacency=None,
                approved_group_params=group_params(tail=tail))
    assert out['thr']==pytest.approx(statistics['cluster_t_threshold'](
        n_observations=20,cluster_forming_alpha=.05,tail=tail))
    np.testing.assert_allclose(out['t_obs'],x.mean(0)/(x.std(0,ddof=1)/np.sqrt(20)))


def test_documented_independent_f_uses_the_group_arrays():
    rng=np.random.default_rng(9)
    groups=[rng.normal(size=(8,3,2)),rng.normal(size=(11,3,2))+1.]
    out=example('eeg-group-compare','group-cluster',group_arrays=groups,adjacency=None,
                approved_group_params=group_params(design='between',statistic='F'))
    assert out['t_obs'].shape==(3,2) and np.all(out['t_obs']>=0)
    from scipy.stats import f
    assert out['thr']==pytest.approx(f.ppf(.95,1,17))


@pytest.mark.parametrize('design',['within','between'])
def test_documented_tfce_maps_native_flat_p_values_to_the_statistic_grid(design):
    rng=np.random.default_rng(3)
    ns=dict(X=rng.normal(size=(10,2,3))+.5,group_arrays=[rng.normal(size=(8,2,3)),rng.normal(size=(9,2,3))+1.],adjacency=None)
    params=group_params(design=design,statistic='t' if design=='within' else 'F')
    out=example('eeg-group-compare','group-tfce',approved_group_params=params,**ns)
    assert out['p_values'].shape==(6,) and out['p_map'].shape==(2,3)
    for mask,value in zip(out['clusters'],out['p_values']):
        assert out['p_map'][mask].item()==value
    np.testing.assert_array_equal(out['significant_points'],out['p_map']<.05)


def test_documented_grand_average_reads_the_named_evoked_directly(tmp_path):
    subs=[]
    for index,level in enumerate([1.,2.]):
        stem=tmp_path/f'sub{index}';subs.append(str(stem))
        ev=[mne.EvokedArray(np.full((1,10),level*1e-6),mne.create_info(['Cz'],100,'eeg'),comment=cond)
            for cond in ['A','B']]
        mne.write_evokeds(f'{stem}-ave.fif',ev)
    out=example('eeg-group-compare','group-evokeds',subs=subs,conditions=['A','B'],roi=['Cz'],
                approved_group_params={'ci':False})
    np.testing.assert_allclose(out['grand']['A'].data,1.5e-6)
    assert all(isinstance(ev,mne.Evoked) for ev in out['evokeds']['A'])
    plt.close('all')


@pytest.mark.parametrize('decim',[1,4])
def test_documented_power_branches_keep_origin_channels_and_linear_power_decomposition(decim):
    rng=np.random.default_rng(4);times=np.arange(501)/250.-.5
    data=rng.normal(size=(4,3,501))*1e-6
    data[:,0,:]+=np.sin(2*np.pi*10*times)*2e-6
    data[:,2,:]*=100
    ep=mne.EpochsArray(data,mne.create_info(['Cz','Oz','EOG'],250,['eeg','eeg','eog']),tmin=-.5)
    original=ep.get_data().copy()
    out=example('eeg-tfr','tfr-power-time-grid',epochs=ep,
        approved_tfr_params=dict(method='morlet',channels=['Oz','Cz'],freqs=[10.,15.],
                                 n_cycles=3.,decim=decim,zero_mean=True,n_jobs=1))
    for key in ['power_total','power_induced','power_evoked']:
        result=out[key]
        assert result.times[0]==-.5 and result.ch_names==['Oz','Cz']
        np.testing.assert_array_equal(result.times,ep.times[::decim])
        assert np.any((result.times>=-.2)&(result.times<=-.1))
    np.testing.assert_allclose(out['power_total'].data,
        out['power_induced'].data+out['power_evoked'].data,rtol=1e-10,atol=1e-25)
    np.testing.assert_array_equal(ep.get_data(),original)
