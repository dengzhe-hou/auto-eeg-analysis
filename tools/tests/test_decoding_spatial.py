"""Exercise actual decoding, resting-map and surface-ROI handoff examples."""
from pathlib import Path
import re
import runpy
import textwrap

import mne
import numpy as np
import pytest
from scipy.stats import ttest_1samp
pytest.importorskip("sklearn")

from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
validation = runpy.run_path(str(ROOT/'skills/eeg-decoding/scripts/validation.py'))
preparation = runpy.run_path(str(ROOT/'skills/eeg-microstate/scripts/preparation.py'))
roi = runpy.run_path(str(ROOT/'skills/eeg-source/scripts/roi.py'))
mne.set_log_level('ERROR')


def example(skill, label, **context):
    source = (ROOT/f'skills/{skill}/references/procedure.md').read_text(encoding="utf-8-sig")
    code, = [textwrap.dedent(x) for x in re.findall(r'```python\n(.*?)```', source, re.S)
             if f'# AEA example: {label}\n' in x]
    ns = dict(mne=mne, np=np, AEA_ROOT=str(ROOT), validation=validation,
              preparation=preparation, **context)
    exec(compile(code, f'{skill}:{label}', 'exec'), ns)
    return ns


def classifier():
    return make_pipeline(StandardScaler(), LogisticRegression(solver='liblinear', random_state=17))


def binary_data():
    y = np.tile([0, 1], 20)
    X = np.random.default_rng(7).normal(size=(len(y), 3))
    X[:, 0] += 2*y
    return X, y


def decoding_epochs():
    X, y = binary_data()
    data = np.repeat(X[:, :, None], 11, axis=2)*1e-6
    data += np.random.default_rng(2).normal(0, 1e-7, data.shape)
    events = np.column_stack([np.arange(len(y))*30, np.zeros(len(y), int), y+1])
    return mne.EpochsArray(data, mne.create_info(['Fz','Cz','Pz'],100.,'eeg'),
                           events=events, tmin=-.02, baseline=None)


def split_records(n_people=3):
    splits = [(np.array([0,1]), np.array([2,3])), (np.array([2,3]), np.array([0,1]))]
    return [validation['participant_record'](f'S{i}',
                np.array([[.7,.8,.9],[.72,.79,.88]])+i*.01,
                times=np.array([-.1,.1,.2]),splits=splits,fold_aggregation='mean')
            for i in range(n_people)]


def test_documented_cv_splits_preserve_subject_exclusion_and_indices():
    X, y = binary_data(); groups=np.repeat(np.arange(10),4)
    out=example('eeg-decoding','decoding-splits',X=X,y=y,
                approved_cv_splitter=GroupKFold(5),approved_cv_groups=groups)
    assert len(out['splits'])==5
    for (train,test),receipt in zip(out['splits'],out['split_receipt']):
        assert set(groups[train]).isdisjoint(groups[test])
        assert receipt=={'train':train.tolist(),'test':test.tolist()}


def test_group_identity_leak_is_rejected_even_when_a_splitter_accepts_groups():
    X,y=binary_data(); groups=np.tile(np.arange(10),4)
    with pytest.warns(UserWarning,match='groups'):
        with pytest.raises(ValueError,match='CV group'):
            validation['cv_splits'](X,y,splitter=StratifiedKFold(5),groups=groups)


def test_documented_single_participant_sliding_returns_one_participant_not_five():
    out=example('eeg-decoding','decoding-sliding',epochs=decoding_epochs(),participant_id='S17',
        approved_classifier=classifier(),approved_cv_splitter=StratifiedKFold(5),
        approved_cv_groups=None,approved_decoding_params={'channels':['Pz','Fz'],
            'scoring':'roc_auc','n_jobs':1,'fold_aggregation':'mean'})
    assert out['fold_scores'].shape==(5,11)
    assert out['record']['participant_id']=='S17' and out['mean_scores'].shape==(11,)
    np.testing.assert_allclose(out['mean_scores'],out['fold_scores'].mean(0))
    with pytest.raises(ValueError,match='at least two'):
        validation['participant_matrix']([out['record']])
    with pytest.raises(ValueError,match='fold-score array'):
        validation['participant_matrix'](out['fold_scores'])


def test_explicit_fold_aggregation_keeps_unequal_test_sizes():
    record=validation['participant_record']('S1',[[.2],[.8]],times=[0.],
        splits=[([2,3,4],[0,1]),([0,1],[2,3,4])],fold_aggregation='test_size_weighted')
    assert record['score'][0]==pytest.approx(.56)
    with pytest.raises(ValueError,match='fold_aggregation'):
        validation['participant_record']('S1',[[.2]],times=[0.],splits=[([0],[1])],
                                          fold_aggregation='unspecified')


@pytest.mark.parametrize('defect', ['duplicate','times','unit'])
def test_group_observations_reject_duplicate_people_misaligned_times_and_folds(defect):
    records=split_records()
    if defect=='duplicate': records[1]['participant_id']=records[0]['participant_id']
    elif defect=='times': records[1]['times']=records[1]['times']+.01
    else: records[1]['observation_unit']='cv_fold'
    with pytest.raises(ValueError): validation['participant_matrix'](records)


def test_documented_group_inference_uses_actual_participant_count():
    records=split_records(4)
    out=example('eeg-decoding','decoding-group-inference',participant_records=records,
        approved_group_inference_params={'test_window_s':[0.,.2],'chance_level':.5,
            'threshold':2.,'tail':1,'n_permutations':8,'seed':5})
    assert out['scores_post'].shape==(4,2) and len(out['participant_ids'])==4
    np.testing.assert_allclose(out['t_obs'],ttest_1samp(out['scores_post'],0.).statistic)


def test_within_person_null_cannot_test_constant_person_diagnosis():
    y=np.repeat([0,0,1,1],4); units=np.repeat(np.arange(4),4)
    with pytest.raises(ValueError,match='cannot change any labels'):
        validation['permuted_labels'](y,policy='within_unit',units=units,
            exchangeability_blocks=np.zeros(len(y),int),rng=np.random.default_rng(2))


def test_between_person_null_exchanges_labels_as_whole_unequal_size_units():
    units=np.repeat(np.arange(6),[2,3,4,2,3,4]);labels=np.array([0,1,0,1,0,1])
    y=labels[units]; blocks=(units>=4).astype(int)
    draws=[validation['permuted_labels'](y,policy='between_units',units=units,
              exchangeability_blocks=blocks,rng=np.random.default_rng(seed)) for seed in range(6)]
    assert any(not np.array_equal(draw,y) for draw in draws)
    for draw in draws:
        assigned=[np.unique(draw[units==u]).item() for u in range(6)]
        assert sorted(assigned[:4])==sorted(labels[:4])
        assert sorted(assigned[4:])==sorted(labels[4:])


def test_within_person_shuffle_respects_trial_blocks():
    y=np.tile([0,1,1,0],4); units=np.repeat(['S1','S2'],8);blocks=np.tile(np.repeat([0,1],4),2)
    shuffled=validation['permuted_labels'](y,policy='within_unit',units=units,
        exchangeability_blocks=blocks,rng=np.random.default_rng(3))
    for subject in np.unique(units):
        for block in np.unique(blocks):
            mask=(units==subject)&(blocks==block)
            assert sorted(shuffled[mask])==sorted(y[mask])


@pytest.mark.parametrize('defect',['variable_label','variable_block'])
def test_between_unit_null_requires_constant_label_and_block_per_unit(defect):
    y=np.repeat([0,1],4);units=np.repeat([0,1],4);blocks=np.zeros(8,int)
    if defect=='variable_label': y[0]=1
    else: blocks[0]=1
    with pytest.raises(ValueError,match='one label and block'):
        validation['permuted_labels'](y,policy='between_units',units=units,
            exchangeability_blocks=blocks,rng=np.random.default_rng(0))


def test_documented_permutation_refits_and_reports_corrected_pointwise_p():
    X,y=binary_data(); splits,_=validation['cv_splits'](X,y,splitter=StratifiedKFold(4),groups=None)
    out=example('eeg-decoding','decoding-permutation',X=X,y=y,estimator=classifier(),splits=splits,
        permutation_units=np.zeros(len(y),int),exchangeability_blocks=np.zeros(len(y),int),
        approved_permutation_params={'scoring':'roc_auc','n_permutations':7,'seed':3,
            'fold_aggregation':'mean','policy':'within_unit'})
    assert out['null_scores'].shape==(7,) and np.ptp(out['null_scores'])>0
    assert out['pointwise_p']==(1+np.sum(out['null_scores']>=out['observed_score']))/8


def test_equal_null_scores_do_not_by_themselves_mean_label_degeneracy():
    X,y=binary_data();splits,_=validation['cv_splits'](X,y,splitter=StratifiedKFold(4),groups=None)
    observed,null,p=validation['permutation_scores'](DummyClassifier(strategy='most_frequent'),
        X,y,splits,scoring='balanced_accuracy',n_permutations=4,policy='within_unit',
        units=np.zeros(len(y),int),exchangeability_blocks=np.zeros(len(y),int),seed=7,
        fold_aggregation='mean')
    assert observed==.5 and np.all(null==.5) and p==1.


def test_documented_nested_cv_carries_group_units_into_inner_folds():
    X,y=binary_data();groups=np.repeat(np.arange(10),4)
    out=example('eeg-decoding','decoding-nested-cv',X_mean_time=X,y=y,
        approved_cv_groups=groups,approved_cv_splitter=GroupKFold(5),
        approved_inner_splitter=GroupKFold(2),approved_classifier=classifier(),
        approved_param_grid={'logisticregression__C':[.1,1.]},approved_scoring='roc_auc')
    assert out['outer_scores'].shape==(5,) and np.isfinite(out['outer_scores']).all()
    for receipt in out['inner_receipts']:
        train=np.asarray(receipt['outer_train_indices'])
        for split in receipt['inner_local_splits']:
            assert set(groups[train[split['train']]]).isdisjoint(groups[train[split['test']]])


@pytest.mark.parametrize('label',['decoding-generalization','decoding-searchlight'])
def test_other_decoding_routes_reuse_actual_grouped_splits(label):
    epochs=decoding_epochs().set_montage('standard_1020')
    X,y=epochs.get_data(),epochs.events[:,2]
    groups=np.repeat(np.arange(10),4)
    splits,_=validation['cv_splits'](X,y,splitter=GroupKFold(5),groups=groups)
    out=example('eeg-decoding',label,epochs=epochs,X=X,y=y,splits=splits,
        approved_classifier=classifier(),approved_decoding_params={'scoring':'roc_auc',
            'n_jobs':1,'fold_aggregation':'test_size_weighted'})
    result=out['mean_gen'] if label=='decoding-generalization' else out['searchlight_scores']
    assert result.shape==((11,11) if label=='decoding-generalization' else (3,11))
    assert np.isfinite(result).all()


def microstate_raw(seconds=60.):
    pytest.importorskip("pycrostates")
    times=np.arange(round(250*seconds))/250
    amplitudes=1.2+.6*np.sin(2*np.pi*.3*times)
    data=1e-6*amplitudes*np.sin(2*np.pi*18*times)[None,:]*np.array([[3.],[-2.],[-1.]])
    data+=2e-7*np.cos(2*np.pi*7*times)[None,:]*np.array([[1.],[1.],[-2.]])
    raw=mne.io.RawArray(data,mne.create_info(['Fz','Cz','Pz'],250,'eeg'))
    return raw.set_montage('standard_1020')


def peak_policy(**overrides):
    params=dict(channels=['Pz','Fz','Cz'],filter_kwargs={'l_freq':3.,'h_freq':25.,'method':'iir',
        'iir_params':{'order':2,'ftype':'butter'}},reference='average',min_peak_distance=3,
        reject_by_annotation=True,gfp_reject_sd=None,gfp_reference='continuous',max_peaks=1000,seed=11)
    params.update(overrides)
    return params


def test_microstate_preparation_applies_real_cap_and_preserves_input():
    raw=microstate_raw();original=raw.get_data().copy()
    prepared,peaks,audit=preparation['prepare_peaks'](raw,**peak_policy())
    assert audit['n_extracted']>1000 and peaks.get_data().shape==(3,1000)
    assert peaks.ch_names==['Pz','Fz','Cz'] and audit['n_selected']==1000
    np.testing.assert_allclose(prepared.get_data().mean(0),0.,atol=1e-20)
    np.testing.assert_array_equal(raw.get_data(),original)
    _,second,second_audit=preparation['prepare_peaks'](raw,**peak_policy())
    np.testing.assert_array_equal(peaks.get_data(),second.get_data())
    assert audit['selected_peak_indices']==second_audit['selected_peak_indices']


@pytest.mark.parametrize('reference',['continuous','peaks'])
def test_gfp_threshold_uses_the_explicit_reference_distribution(reference):
    pytest.importorskip("pycrostates")
    from pycrostates.preprocessing import extract_gfp_peaks
    prepared,peaks,audit=preparation['prepare_peaks'](microstate_raw(4),
        **peak_policy(gfp_reject_sd=.5,gfp_reference=reference,max_peaks=None))
    original=extract_gfp_peaks(prepared,picks=prepared.ch_names,min_peak_distance=3,
                               reject_by_annotation=True).get_data()
    source=prepared.get_data() if reference=='continuous' else original
    gfp=source.std(0,ddof=0);expected=gfp.mean()+.5*gfp.std(ddof=0)
    assert audit['gfp_threshold']==pytest.approx(expected)
    assert peaks.get_data().shape[1]==np.sum(original.std(0,ddof=0)<=expected)


def physical_peak_records():
    pytest.importorskip("pycrostates")
    from pycrostates.io import ChData
    info=microstate_raw(.1).info
    values=np.array([[3.,6.],[-2.,-4.],[-1.,-2.]])*1e-6
    order=[2,0,1]
    return [dict(participant_id='S1',peaks=ChData(values,info.copy()),
                 audit={'n_selected':2,'max_peaks':1000}),
            dict(participant_id='S2',peaks=ChData(values[order],mne.pick_info(info,order)),
                 audit={'n_selected':2,'max_peaks':1000})]


def test_group_map_pooling_restores_physical_maps_with_different_channel_orders():
    records=physical_peak_records()
    pooled,aligned,audit=preparation['pool_peaks'](records,channels=['Fz','Cz','Pz'])
    np.testing.assert_array_equal(pooled.get_data()[:,:2],pooled.get_data()[:,2:])
    assert abs(np.corrcoef(pooled.get_data()[:,0],pooled.get_data()[:,2])[0,1])==pytest.approx(1.)
    assert audit['participants'][1]['input_channels']==['Pz','Fz','Cz']
    assert records[1]['peaks'].ch_names==['Pz','Fz','Cz']


@pytest.mark.parametrize('defect',['channel_set','position','unapplied_cap'])
def test_pooling_refuses_mismatched_metadata_or_unapplied_preparation(defect):
    pytest.importorskip("pycrostates")
    from pycrostates.io import ChData
    records=physical_peak_records()
    if defect=='channel_set':
        records[1]['peaks']=ChData(np.ones((2,2)),mne.create_info(['Fz','Cz'],250,'eeg'))
    elif defect=='position': records[1]['peaks'].info['chs'][0]['loc'][0]+=.02
    else: records[1]['audit']['max_peaks']=1
    with pytest.raises(ValueError): preparation['pool_peaks'](records,channels=['Fz','Cz','Pz'])


def test_individual_and_group_documented_preparation_use_same_selection(tmp_path):
    paths={}
    for subject,order in [('S1',['Fz','Cz','Pz']),('S2',['Pz','Fz','Cz'])]:
        path=tmp_path/f'{subject}-raw.fif';microstate_raw(4).pick(order).save(path,overwrite=True)
        paths[subject]=path
    policy=peak_policy(max_peaks=17,gfp_reject_sd=.5)
    individual=example('eeg-microstate','microstate-preparation',raw_fif_path=paths['S1'],
                        approved_microstate_preparation=policy)
    group=example('eeg-microstate','microstate-group-preparation',subjects=list(paths),raw_paths=paths,
        approved_group_channels=['Fz','Cz','Pz'],approved_preparation_by_participant={s:policy for s in paths})
    assert group['group_peak_audit']['n_maps']==34
    np.testing.assert_allclose(individual['gfp_peaks'].get_data()[[1,2,0]],
                               group['all_peaks'][0].get_data())
    assert all(r['audit']['n_selected']==17 for r in group['peak_records'])


def test_documented_group_model_fits_and_reopens_native_fif(tmp_path):
    pytest.importorskip("pycrostates")
    from pycrostates.io import read_cluster
    _,peaks,audit=preparation['prepare_peaks'](microstate_raw(4),**peak_policy(max_peaks=80))
    out=example('eeg-microstate','microstate-group-fitting',group_peaks=peaks,
        approved_modkmeans_params={'n_clusters':2,'n_init':2,'max_iter':50,'random_state':4},
        approved_n_jobs=1,group_model_path=tmp_path/'group-model.fif')
    reopened=read_cluster(tmp_path/'group-model.fif')
    np.testing.assert_allclose(reopened.cluster_centers_,out['ModK'].cluster_centers_)


def surface_inputs():
    src=mne.SourceSpaces([dict(type='surf',vertno=np.array([0]),nn=np.array([[0.,0.,1.]]),
                              subject_his_id='S1') for _ in range(2)])
    stc=mne.SourceEstimate(np.array([[1.,2.,3.],[4.,5.,6.]]),
        vertices=[np.array([0]),np.array([0])],tmin=-.1,tstep=.01,subject='S1')
    return stc,src,[mne.Label(vertices=np.array([0]),hemi='lh',subject='S1',name='present-lh'),
                    mne.Label(vertices=np.array([9]),hemi='rh',subject='S1',name='absent-rh')]


@pytest.mark.parametrize('defect',['atlas','label','src','vertices'])
def test_roi_space_mismatch_is_not_repaired_by_renaming_metadata(defect):
    stc,src,labels=surface_inputs();atlas='S1'
    if defect=='atlas': atlas='fsaverage'
    elif defect=='label': labels[0].subject='fsaverage'
    elif defect=='src': src[0]['subject_his_id']='fsaverage'
    else: src[0]['vertno']=np.array([1])
    with pytest.raises(ValueError): roi['extract_surface_rois'](stc,labels,src,
        atlas_subject=atlas,mode='mean_flip',empty_policy='flag')


def test_unavailable_roi_has_nan_and_flag_but_real_zero_remains_available():
    stc,src,labels=surface_inputs();stc.data[0]=0.
    out=roi['extract_surface_rois'](stc,labels,src,atlas_subject='S1',mode='mean_flip',empty_policy='flag')
    assert out['available'].tolist()==[True,False] and out['n_vertices'].tolist()==[1,0]
    assert np.all(out['label_ts'][0]==0.) and np.isnan(out['label_ts'][1]).all()
    with pytest.raises(ValueError,match='Unavailable ROIs'):
        roi['extract_surface_rois'](stc,labels,src,atlas_subject='S1',mode='mean_flip',empty_policy='error')


def test_documented_roi_example_reads_actual_subject_and_saves_availability(tmp_path,monkeypatch):
    stc,src,labels=surface_inputs();calls=[]
    def read_labels(*,subject,parc,subjects_dir):
        calls.append((subject,parc));return labels
    monkeypatch.setattr(mne,'read_labels_from_annot',read_labels)
    path=tmp_path/'roi.npz'
    out=example('eeg-source','source-roi-extraction',stc_dspm=stc,src=src,subjects_dir=tmp_path,
        roi_output_path=path,approved_roi_params={'atlas_subject':'S1','parc':'aparc',
            'mode':'mean_flip','empty_policy':'flag'})
    assert calls==[('S1','aparc')]
    with np.load(path,allow_pickle=False) as saved:
        assert saved['subject'].item()=='S1' and saved['available'].tolist()==[True,False]
        np.testing.assert_allclose(saved['label_ts'][0],stc.data[0])
        assert np.isnan(saved['label_ts'][1]).all()
