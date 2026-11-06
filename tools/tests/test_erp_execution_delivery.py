"""Regressions for observed metadata early stops and group-state destruction."""
import csv
import json
from pathlib import Path
import subprocess
import sys

import mne
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'skills/eeg-epoch/scripts'))
from erp import mean_roi_amplitude, save_erp_outputs
from erp_execution import inspect_inputs, save_subject_state, load_group_state, finalize_delivery
from prepare_erp_packet import prepare_erp_packet
from check_erp_outputs import check_outputs


@pytest.fixture
def plan():
    return {'request_kind': 'single_subject', 'dataset': {'name': 'Synthetic'},
            'subjects': ['sub-001', 'sub-002'],
            'analysis': {'epoch_s': [-.2, .8], 'resample_hz': 100., 'window_s': [.1, .3],
                         'roi': ['Cz', 'Pz'], 'minimum_trials': {'plus': 2, 'minus': 2}},
            'derivatives': {'root': 'derivatives/erp-analysis', 'contrast_label': 'BminusA'},
            'required_results': dict.fromkeys(['status', 'subject', 'roi_amplitude_uv',
                                              'n_trials_plus', 'n_trials_minus', 'dataset_version']),
            'required_evidence': dict.fromkeys(['times_s', 'roi_difference_uv'])}


@pytest.fixture
def epochs():
    data = np.zeros((4, 4, 101))
    roi = np.array([[1, 2], [5, 6], [3, 4], [7, 8]])
    data[:, :, 20:71] = np.concatenate([roi, -roi], axis=1)[:, :, None] * 1e-6
    info = mne.create_info(['Cz', 'Pz', 'O1', 'O2'], 100., 'eeg')
    info.set_montage(mne.channels.make_standard_montage('standard_1020'))
    return mne.EpochsArray(data, info, events=np.array([[100,0,1],[300,0,2],[500,0,1],[700,0,2]]),
                           event_id={'A':1,'B':2}, tmin=-.2, baseline=None, verbose=False)


def dataset(tmp_path, plan, task):
    plan['dataset'] = {'name': 'ERP CORE', 'bids_task_label': task}
    contrasts = {'P3':'rareminusfrequent','N170':'facesminuscars',
                 'N400':'unrelatedminusrelated','ERN':'errorminuscorrect'}
    plan['derivatives']['contrast_label'] = contrasts[task]
    levels = {}
    if task == 'P3':
        codes = [11,12,21,22]
        for code in codes:
            levels[str(code)] = f'Stimulus - block target {"ABCDE"[code//10-1]}, trial stimulus {"ABCDE"[code%10-1]}'
    elif task == 'N170':
        codes = [1,40,41,80,101,141]
        levels = {'1-40':'Stimulus - faces','41-80':'Stimulus - cars'}
    elif task == 'N400':
        codes = [211,212,221,222,111,121]
        levels = {str(c): f'Stimulus - target word, {"unrelated" if c in (221,222) else "related"} word pair, list 1'
                  for c in codes}
    else:
        codes = [111,112,121,122,211,212,221,222]
        levels = {str(c): 'Response - documented ERP CORE response' for c in codes}
    root = tmp_path / 'bids';root.mkdir()
    (root/'CHANGES').write_text('Revision history for ERP CORE\n\nversion 1.0 - 20 Jul 2020\n')
    (root/f'task-{task}_events.json').write_text(json.dumps({'value':{'Levels':levels}}))
    for subject in plan['subjects']:
        d = root/subject/f'ses-{task}'/'eeg';d.mkdir(parents=True)
        (d/f'{subject}_ses-{task}_task-{task}_eeg.set').write_text('metadata-only fixture, not loaded as EEG')
        with (d/f'{subject}_ses-{task}_task-{task}_events.tsv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['trial_type','value','onset'],delimiter='\t');w.writeheader()
            for i,c in enumerate(codes):w.writerow({'trial_type':'response' if task=='ERN' else 'stimulus','value':c,'onset':.1*(i+1)})
    return root


@pytest.mark.parametrize('task,expected', [('P3',(2,2)),('N170',(2,2)),('N400',(2,2)),('ERN',(4,4))])
def test_metadata_executes_documented_condition_checks_and_reads_version(tmp_path, plan, task, expected):
    root=dataset(tmp_path,plan,task)
    check=inspect_inputs(plan,root)
    assert check['dataset_version']=='1.0'
    assert [(x['raw_n_plus'],x['raw_n_minus']) for x in check['subjects'].values()]==[expected,expected]
    assert 'retained-epoch' in check['coverage']
    assert 'Continue' in check['next_step']


def test_metadata_names_actual_missing_subject_and_rejects_changed_mapping(tmp_path, plan):
    root=dataset(tmp_path,plan,'P3')
    sidecar=root/'task-P3_events.json';value=json.loads(sidecar.read_text())
    value['value']['Levels']['11']='unknown code';sidecar.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='sidecar does not confirm row 0, code 11'):
        inspect_inputs(plan,root)
    plan['subjects']=['sub-absent']
    with pytest.raises(ValueError,match='sub-absent, found 0'):
        inspect_inputs(plan,root)


def test_group_checkpoint_restores_named_roi_after_variable_loss(tmp_path, plan, epochs):
    plan['request_kind']='group'
    original=epochs.get_data(copy=True)
    for subject in plan['subjects']:
        save_subject_state(tmp_path,subject,epochs,plan=plan,plus='B',minus='A')
    with pytest.raises(NameError):exec('missing_diagnostic_variable + 1',{})
    state=load_group_state(tmp_path,plan=plan)
    assert state['result_fields']['group_mean_uv']==pytest.approx(4.,abs=1e-12)
    assert abs(state['differences_uv'].mean())<1e-12  # All-channel averaging would incorrectly return zero.
    assert state['cluster_data_uv'].shape==(2,21,4)
    assert state['info'].ch_names==epochs.ch_names and state['info']['dig']
    np.testing.assert_array_equal(epochs.get_data(copy=True),original)
    script=("import sys,json; sys.path.insert(0,sys.argv[1]); from erp_execution import load_group_state; "
            "s=load_group_state(sys.argv[2],plan=json.loads(sys.argv[3])); print(json.dumps(s['result_fields']))")
    fresh=subprocess.run([sys.executable,'-B','-c',script,str(ROOT/'tools'),str(tmp_path),json.dumps(plan)],capture_output=True,text=True)
    assert fresh.returncode==0,fresh.stderr
    assert json.loads(fresh.stdout)['group_mean_uv']==pytest.approx(4.,abs=1e-12)


def test_group_checkpoint_preserves_existing_state_and_refuses_changed_plan(tmp_path, plan, epochs):
    for subject in plan['subjects']:save_subject_state(tmp_path,subject,epochs,plan=plan,plus='B',minus='A')
    before=(tmp_path/'sub-001.npz').read_bytes()
    with pytest.raises(FileExistsError):save_subject_state(tmp_path,'sub-001',epochs,plan=plan,plus='B',minus='A')
    assert (tmp_path/'sub-001.npz').read_bytes()==before
    plan['analysis']['roi']=['O1','O2']
    with pytest.raises(ValueError,match='Saved plan differs'):load_group_state(tmp_path,plan=plan)


def test_group_checkpoint_retains_excluded_counts_without_inventing_wave(tmp_path, plan, epochs):
    save_subject_state(tmp_path,'sub-001',epochs,plan=plan,plus='B',minus='A')
    save_subject_state(tmp_path,'sub-002',epochs[:2],plan=plan,plus='B',minus='A')
    state=load_group_state(tmp_path,plan=plan)
    assert state['result_fields']['subjects_excluded']==['sub-002']
    assert state['retained_counts']['sub-002']==[1,1]
    with np.load(tmp_path/'sub-002.npz') as x:assert 'difference_uv' not in x.files


def deliver(workspace, plan, epochs):
    measured=mean_roi_amplitude(epochs,plus='B',minus='A',roi=plan['analysis']['roi'],window_s=plan['analysis']['window_s'])
    result={'status':'computed','subject':'sub-001','dataset_version':'1.0',
            **{k:measured[k] for k in ('roi_amplitude_uv','n_trials_plus','n_trials_minus')}}
    save_erp_outputs(workspace,result=result,evidence={k:measured[k] for k in ('times_s','roi_difference_uv','amplitude_unit','sfreq_hz')})
    d=workspace/plan['derivatives']['root'];(d/'sub-001/eeg').mkdir(parents=True)
    (d/'dataset_description.json').write_text(json.dumps({'DatasetType':'derivative','SourceDatasets':[{'DOI':'synthetic'}]}))
    np.savetxt(d/'sub-001/eeg/erp.tsv',np.column_stack([measured['times_s'],measured['roi_difference_uv']]),delimiter='\t')
    return result


def test_submission_preserves_failed_check_then_uses_only_actual_result(tmp_path, plan, epochs):
    first=finalize_delivery(plan,tmp_path,atol_uv=1e-9)
    assert not first['passed'] and not (tmp_path/'FINAL_SUBMISSION.md').exists()
    original_check=(tmp_path/'delivery-checks/check-001.json').read_bytes()
    result=deliver(tmp_path,plan,epochs)
    assert finalize_delivery(plan,tmp_path,atol_uv=1e-9)['passed']
    assert json.loads((tmp_path/'FINAL_SUBMISSION.md').read_text())==result
    assert (tmp_path/'delivery-checks/check-001.json').read_bytes()==original_check
    assert (tmp_path/'delivery-checks/check-002.json').is_file()
    with pytest.raises(FileExistsError):finalize_delivery(plan,tmp_path,atol_uv=1e-9)


def test_submission_rejects_revision_as_dataset_version(tmp_path, plan, epochs):
    root=dataset(tmp_path,plan,'P3');workspace=tmp_path/'run'
    result=deliver(workspace,plan,epochs)
    (workspace/'ERP_INPUTS.json').write_text(json.dumps(inspect_inputs(plan,root)))
    result['dataset_version']='Revision';(workspace/'result.json').write_text(json.dumps(result))
    report=finalize_delivery(plan,workspace,atol_uv=1e-9)
    assert not report['passed'] and any('CHANGES version' in s for s in report['problems'])
    assert not (workspace/'FINAL_SUBMISSION.md').exists()


def test_submission_cli_returns_failure_for_an_early_incomplete_delivery(tmp_path, plan):
    p=tmp_path/'plan.json';p.write_text(json.dumps(plan))
    run=subprocess.run([sys.executable,'-B',str(ROOT/'tools/erp_execution.py'),'finalize','--plan',str(p),'--workspace',str(tmp_path),'--atol-uv','1e-9'],capture_output=True,text=True)
    assert run.returncode==1,run.stderr
    assert 'result.json is missing' in json.loads(run.stdout)['problems']
    assert not (tmp_path/'FINAL_SUBMISSION.md').exists()


def test_checker_rejects_ineligible_without_retained_counts_and_empty_derivative_dirs(tmp_path, plan, epochs):
    result=deliver(tmp_path,plan,epochs)
    result.update(status='ineligible',n_trials_plus=None,n_trials_minus=None)
    (tmp_path/'result.json').write_text(json.dumps(result))
    assert any('actual retained counts' in x for x in check_outputs(plan,tmp_path)['problems'])
    result.update(n_trials_plus=2,n_trials_minus=2);(tmp_path/'result.json').write_text(json.dumps(result))
    assert any('contradicts' in x for x in check_outputs(plan,tmp_path)['problems'])
    result['status']='computed';(tmp_path/'result.json').write_text(json.dumps(result))
    (tmp_path/plan['derivatives']['root']/'sub-001/eeg/erp.tsv').unlink()
    assert any('no derivative files' in x for x in check_outputs(plan,tmp_path)['problems'])


def test_packet_routes_only_matching_executable_interfaces(plan):
    plan['dataset']={'name':'ERP CORE','bids_task_label':'N170'}
    plan['derivatives']['contrast_label']='facesminuscars'
    packet,receipt=prepare_erp_packet(ROOT,plan)
    assert 'erp_execution.py preflight' in packet and 'FINAL_SUBMISSION.md' in packet
    assert 'save_subject_state' not in packet
    assert receipt['execution_helper_source_preloaded'] is False
    assert 'def inspect_inputs' not in packet
    plan['request_kind']='group'
    packet,_=prepare_erp_packet(ROOT,plan)
    assert 'save_subject_state' in packet and 'cluster_data_uv' in packet
    plan['dataset']['bids_task_label']='MMN';plan['derivatives']['contrast_label']='deviantminusstandard'
    packet,_=prepare_erp_packet(ROOT,plan)
    assert 'erp_execution.py preflight' not in packet
