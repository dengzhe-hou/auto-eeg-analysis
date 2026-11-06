"""Run one explicit ERP CORE plan with saved participant state and checked delivery.

This bounded route implements the four documented mean-amplitude contracts.
All scientific settings come from the supplied plan. No reference outputs are read.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys

import mne
import numpy as np
from scipy import stats

from erp_execution import (inspect_inputs, erp_core_conditions, supports_input_check,
                           save_subject_state, load_group_state, finalize_delivery)
from write_erp_derivatives import start_derivative, write_subject_erp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/eeg-epoch/scripts'))
from erp import save_erp_outputs

SOURCES = ['tools/run_erp_plan.py', 'tools/erp_execution.py',
           'tools/check_erp_outputs.py', 'tools/write_erp_derivatives.py',
           'skills/eeg-epoch/scripts/erp.py']


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def _validate(plan):
    a = plan['analysis']
    if not supports_input_check(plan):
        raise ValueError('This runner supports the four explicit ERP CORE mean-amplitude contrasts only')
    order = ['drop the three EOG channels', 'set montage', 'band-pass filter',
             f"resample to {a['resample_hz']:g} Hz", 'average reference', 'epoch']
    if a['processing_order'] != order:
        raise ValueError('The operation order is not supported by this bounded ERP runner')
    if (a['rejection'] != 'none' or 'zero-phase FIR band-pass' not in a['filter']['type']
            or a['reference'] != 'average of the 30 scalp channels, applied directly (projection False)'
            or a['window_endpoints'] != 'inclusive'):
        raise ValueError('Supply the explicit zero-phase FIR, 30-channel average-reference, no-rejection contract')
    if a['events']['keep'] != 'samples strictly inside the recording':
        raise ValueError('Use the approved strict-inside-recording onset rule')
    if a['events']['sample_rule'] != f"round(onset_seconds * {a['resample_hz']:g})":
        raise ValueError('Event samples must follow the supplied output-rate onset rule')
    if plan['request_kind'] not in ('single_subject', 'group'):
        raise ValueError('Expected a single-subject or participant-level group request')
    if plan['request_kind'] == 'single_subject' and len(plan['subjects']) != 1:
        raise ValueError('A single-subject request must name one participant')


def _participant(plan, metadata, subject, state_directory, operations):
    import csv
    a = plan['analysis']; source = metadata['subjects'][subject]
    with mne.io.read_raw_eeglab(source['recording'], preload=True, verbose=False) as raw:
        operations.append({'operation': 'read', 'n_channels': len(raw.ch_names),
                           'n_samples': int(raw.n_times), 'sfreq_hz': raw.info['sfreq']})
        raw.drop_channels(a['channels']['drop_before_processing'])
        if len(raw.ch_names) != 30:
            raise ValueError(f'{subject} has {len(raw.ch_names)} scalp channels after the approved EOG removal')
        raw.set_montage(mne.channels.make_standard_montage(a['channels']['montage']),
                        match_case=a['channels']['montage_match_case'])
        operations.append({'operation': 'drop_EOG_and_set_montage', 'channels': raw.ch_names.copy()})
        f = a['filter']
        h_transition = f['h_trans_bandwidth']
        if not isinstance(h_transition, (int, float)):
            if h_transition != 'MNE default rule: a quarter of the upper cutoff and at least 2 Hz':
                raise ValueError('Unsupported upper transition-band convention')
            h_transition = 'auto'
        kwargs = dict(l_freq=f['l_freq_hz'], h_freq=f['h_freq_hz'],
                      l_trans_bandwidth=f['l_trans_bandwidth_hz'], h_trans_bandwidth=h_transition,
                      method='fir', phase='zero', fir_design=f['fir_design'], fir_window=f['fir_window'],
                      filter_length=f['filter_length'], pad=f['pad'], n_jobs=f['n_jobs'])
        raw.filter(**kwargs, verbose=False)
        operations.append({'operation': 'filter', 'actual_arguments': kwargs})
        if a['resample_method'] != 'mne.io.Raw.resample default':
            raise ValueError('Unsupported resampling-method convention')
        raw.resample(a['resample_hz'], verbose=False)
        raw.set_eeg_reference('average', projection=False, verbose=False)
        operations.append({'operation': 'resample_and_average_reference',
                           'sfreq_hz': raw.info['sfreq'], 'n_samples': int(raw.n_times),
                           'first_samp': int(raw.first_samp)})
        with open(source['events'], encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        levels = json.loads(Path(metadata['events_sidecar']).read_text(encoding="utf-8-sig"))['value']['Levels']
        selected = erp_core_conditions(plan['dataset']['bids_task_label'], rows, levels)
        samples = np.rint(np.asarray([r['onset_s'] for r in selected]) * raw.info['sfreq']).astype(int)
        keep = (samples > 0) & (samples < raw.n_times)
        labels = np.asarray([1 if r['condition'] == 'plus' else 2 for r in selected])
        events = np.column_stack([samples[keep] + raw.first_samp, np.zeros(keep.sum(), int), labels[keep]])
        if not len(events):
            raise ValueError(f'No planned event lies inside {subject}')
        epochs = mne.Epochs(raw, events.astype(int), event_id={'plus': 1, 'minus': 2},
                            tmin=a['epoch_s'][0], tmax=a['epoch_s'][1], baseline=tuple(a['baseline_s']),
                            reject=None, preload=True, on_missing='ignore', verbose=False)
        operations.append({'operation': 'epoch', 'epoch_s': a['epoch_s'], 'baseline_s': a['baseline_s'],
                           'event_count': len(events), 'retained_plus': len(epochs['plus']),
                           'retained_minus': len(epochs['minus']),
                           'event_rows_retained_for_epoching': [r['row'] for r,k in zip(selected,keep) if k]})
        save_subject_state(state_directory, subject, epochs, plan=plan, plus='plus', minus='minus')


def _group_statistics(plan, state, workspace, replay_rng=None):
    amplitudes = state['evidence']['roi_amplitudes_uv']
    if len(amplitudes) < 2:
        raise ValueError('Fewer than two eligible participants for the approved group tests')
    tests = plan['group_test']; t_plan = tests['t_test']; c = tests['cluster']
    if t_plan['test'] != 'two-sided one-sample t-test against zero':
        raise ValueError('Unsupported participant-level t-test')
    t_value, p_value = stats.ttest_1samp(amplitudes, 0., alternative='two-sided')
    threshold = c['threshold']
    if not isinstance(threshold, (float, int)):
        match = re.fullmatch(r'one-sided t quantile at ([0-9.]+) with n_subjects minus 1 degrees of freedom, signed as the tail', threshold)
        if match is None or c['tail'] not in (-1, 1):
            raise ValueError('Unsupported explicit cluster-forming threshold')
        threshold = float(stats.t.ppf(float(match[1]), len(amplitudes)-1)) * c['tail']
    significance = re.fullmatch(r'at least one cluster has p < ([0-9.]+)', c['significant_if'])
    if significance is None or c['function'] != 'mne.stats.spatio_temporal_cluster_1samp_test':
        raise ValueError('Unsupported explicit cluster significance rule or function')
    adjacency, names = mne.channels.find_ch_adjacency(state['info'], ch_type='eeg')
    if names != state['channels']:
        raise ValueError('Cluster adjacency does not follow the saved full scalp-channel order')
    rng_path = workspace / 'cluster_rng_before.json'
    restore = Path(replay_rng) if replay_rng else rng_path if rng_path.exists() else None
    if restore:
        saved = json.loads(restore.read_text(encoding="utf-8-sig"))
        np.random.set_state((saved['algorithm'], np.asarray(saved['keys'], np.uint32),
                             saved['position'], saved['has_gauss'], saved['cached_gaussian']))
    rng = np.random.get_state()
    if not rng_path.exists():
        _write(rng_path, {'algorithm':rng[0], 'keys':rng[1].tolist(), 'position':rng[2],
                          'has_gauss':rng[3], 'cached_gaussian':rng[4]})
    # No seed is invented when the public plan leaves MNE's seed unspecified.
    seed = c.get('seed')
    t_obs, clusters, p_clusters, h0 = mne.stats.spatio_temporal_cluster_1samp_test(
        state['cluster_data_uv'], threshold=threshold, tail=c['tail'],
        n_permutations=c['n_permutations'], adjacency=adjacency, n_jobs=1,
        seed=seed, out_type='indices', verbose=False)
    minimum_p = float(p_clusters.min()) if len(p_clusters) else 1.
    arrays = {'t_observed':t_obs, 'cluster_p_values':p_clusters, 'null_distribution':h0}
    for i,(times,channels) in enumerate(clusters):
        arrays[f'cluster_{i:03d}_time_indices'] = times
        arrays[f'cluster_{i:03d}_channel_indices'] = channels
    np.savez(workspace / 'cluster_evidence.npz', **arrays)
    actual = {'threshold':threshold, 'tail':c['tail'], 'n_permutations':c['n_permutations'],
              'seed_argument':seed, 'data_shape':list(state['cluster_data_uv'].shape),
              'channels':state['channels'], 'window_s':plan['analysis']['window_s'],
              'rng_state_before':'cluster_rng_before.json'}
    return {'ttest_t':float(t_value), 'ttest_p':float(p_value),
            'ttest_significant':bool(p_value < t_plan['alpha']),
            'cluster_min_p':minimum_p, 'cluster_significant':bool(minimum_p < float(significance[1])),
            'actual_cluster_arguments':actual}


def run_plan(plan, dataset_root, workspace, *, atol_uv, resume=False, replay_rng=None):
    _validate(plan)
    workspace = Path(workspace); workspace.mkdir(parents=True, exist_ok=True)
    execution_path = workspace / 'execution.json'
    now = lambda: datetime.now(timezone.utc).isoformat()
    if (workspace / 'FINAL_SUBMISSION.md').exists():
        raise FileExistsError('Completed delivery exists; preserve it and use a new workspace')
    if execution_path.exists():
        execution = json.loads(execution_path.read_text(encoding="utf-8-sig"))
        if not resume:
            raise FileExistsError('Execution exists; inspect it and explicitly resume only a stopped run')
        if execution['plan'] != plan or execution['dataset_root'] != str(Path(dataset_root).resolve()):
            raise ValueError('Resume requires the same plan and input root')
        if execution['status'] == 'running':
            if execution['hostname'] != socket.gethostname():
                raise RuntimeError('Inspect the recorded running host before resuming')
            try:
                os.kill(execution['coordinator_pid'], 0)
            except ProcessLookupError:
                pass
            else:
                raise RuntimeError('Recorded execution process is still running; do not start a duplicate')
        for relative in SOURCES:
            if (workspace/'executed-source'/relative).read_bytes() != (ROOT/relative).read_bytes():
                raise ValueError('Executing source changed; retain this attempt and use a new workspace')
    else:
        if any((workspace/name).exists() for name in ('result.json','analysis_evidence.npz','participant-state')):
            raise FileExistsError('Prior artifacts exist without this execution record')
        execution = {'plan':plan, 'dataset_root':str(Path(dataset_root).resolve()), 'steps':[],
                     'source_files':SOURCES, 'attempts':[], 'environment':{
                         'python':sys.version, 'mne':mne.__version__, 'numpy':np.__version__}}
        for relative in SOURCES:
            destination = workspace/'executed-source'/relative
            destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/relative,destination)
        _write(workspace/'APPROVED_PLAN.json', plan)
        _write(workspace/'PROCEDURES_USED.json', {
            'sources':{'skills/eeg-epoch/references/approved-erp.md':['Approved ERP execution','ERP CORE response coding when applicable','Approved ERP group statistics when applicable'],
                       'skills/eeg-erp/references/procedure.md':['Phase C per-subject averaging','Phase D approved mean amplitude','Phase F outputs'],
                       'skills/eeg-group-compare/references/procedure.md':['Phase A participant array','Phase C planned cluster test'],
                       'skills/eeg-stats/references/procedure.md':['Phase C per-claim execution']},
            'plan_overrides':'Explicit no-ICA/no-rejection plan, fixed mean ROI and window, full 30-channel cluster search, requested tests only. No recipe defaults, SME, effect-size CI or additional tests added.'})
    execution.update(status='running',hostname=socket.gethostname(),coordinator_pid=os.getpid())
    execution['attempts'].append({'started_at':now(),'argv':sys.argv.copy(),'resume':resume})
    _write(execution_path,execution)
    def start(name):
        execution['steps'].append({'name':name,'status':'running','started_at':now()})
        _write(execution_path,execution)
    def done():
        execution['steps'][-1].update(status='completed',finished_at=now())
        _write(execution_path,execution)
    try:
        start('event_metadata')
        metadata = inspect_inputs(plan,dataset_root)
        inputs = workspace/'ERP_INPUTS.json'
        if inputs.exists() and json.loads(inputs.read_text(encoding="utf-8-sig")) != metadata:
            raise ValueError('Existing input check differs from actual current metadata')
        if not inputs.exists(): _write(inputs,metadata)
        done()
        states = workspace/'participant-state'
        for subject in plan['subjects']:
            start('participant:'+subject)
            if (states/f'{subject}.npz').exists():
                if not resume: raise FileExistsError('Participant state already exists')
                execution['steps'][-1]['reused_saved_state'] = True
            else:
                operations=[]; execution['steps'][-1]['operations'] = operations
                _participant(plan,metadata,subject,states,operations)
            done()
        result={'status':'computed','component':plan['component'],'dataset_doi':plan['dataset']['doi'],
                'dataset_version':metadata['dataset_version'],
                'explanation':'Executed the supplied ERP plan in its approved order, with actual retained counts and saved participant evidence.'}
        start('assemble_measurements')
        if plan['request_kind']=='single_subject':
            subject=plan['subjects'][0]
            with np.load(states/f'{subject}.npz',allow_pickle=False) as saved:
                counts=saved['retained_counts'].tolist();eligible=bool(saved['eligible'].item())
                result.update(subject=subject,n_trials_plus=counts[0],n_trials_minus=counts[1])
                if not eligible:
                    result.update(status='ineligible',roi_amplitude_uv=None,
                                  explanation='Actual retained counts fall below at least one approved trial minimum.')
                    evidence={k:saved[k].copy() for k in ('times_s','amplitude_unit','sfreq_hz')}
            if eligible:
                state=load_group_state(states,plan=plan)
                result['roi_amplitude_uv']=state['result_fields']['group_mean_uv']
                evidence={k:state['evidence'][k] for k in ('times_s','amplitude_unit','sfreq_hz')}
                evidence['roi_difference_uv']=state['evidence']['grand_roi_difference_uv']
        else:
            state=load_group_state(states,plan=plan);result.update(state['result_fields']);evidence=state['evidence']
            group_file=workspace/'group_statistics.json'
            if group_file.exists():
                measured=json.loads(group_file.read_text(encoding="utf-8-sig"))
            else:
                measured=_group_statistics(plan,state,workspace,replay_rng);_write(group_file,measured)
            result.update({k:v for k,v in measured.items() if k!='actual_cluster_arguments'})
            mean=result['group_mean_uv'];result['effect_direction']='negative' if mean<0 else 'positive'
        done()
        start('derivatives')
        derivative=workspace/plan['derivatives']['root']
        if not (derivative/'dataset_description.json').exists():
            start_derivative(derivative,pipeline='AEA approved ERP entry',source_doi=plan['dataset']['doi'],source_version=metadata['dataset_version'])
        if result['status']=='ineligible':
            folder=derivative/result['subject']/'eeg';folder.mkdir(parents=True,exist_ok=True)
            path=folder/f"{result['subject']}_desc-ineligible_erp.json"
            if not path.exists():_write(path,{k:result[k] for k in ('status','n_trials_plus','n_trials_minus','explanation')})
        else:
            for i,subject in enumerate(state['result_fields']['subjects_included']):
                task=plan['dataset']['bids_task_label'];contrast=plan['derivatives']['contrast_label']
                path=derivative/subject/'eeg'/f'{subject}_task-{task}_desc-{contrast}_erp.tsv'
                if path.exists():
                    if not resume:raise FileExistsError(f'Prior derivative exists: {path}')
                    continue
                wave=state['differences_uv'][i,[state['channels'].index(x) for x in plan['analysis']['roi']]].mean(axis=0)
                write_subject_erp(derivative,subject=subject,task=task,contrast=contrast,times_s=evidence['times_s'],values_uv=wave)
        done()
        start('save_outputs')
        paths=[workspace/'result.json',workspace/'analysis_evidence.npz']
        if not any(p.exists() for p in paths):save_erp_outputs(workspace,result=result,evidence=evidence)
        elif not (resume and all(p.exists() for p in paths)):
            raise FileExistsError('Partial first output retained; use a new directory and the saved state')
        done();start('final_delivery_check')
        check=finalize_delivery(plan,workspace,atol_uv=atol_uv)
        if not check['passed']:raise ValueError('Final delivery check failed; inspect the retained numbered check')
        done();execution.update(status='completed',finished_at=now());execution['attempts'][-1]['finished_at']=now()
        _write(execution_path,execution)
        return json.loads((workspace/'result.json').read_text(encoding="utf-8-sig")),check
    except Exception as exc:
        execution.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)},finished_at=now())
        if execution['steps']:execution['steps'][-1].update(status='failed',error=execution['error'])
        execution['attempts'][-1].update(finished_at=now(),error=execution['error']);_write(execution_path,execution)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--dataset-root',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--atol-uv',type=float,required=True)
    parser.add_argument('--resume',action='store_true',help='Resume saved stages only after confirming the prior process stopped')
    parser.add_argument('--replay-rng',type=Path,help='Use the actual saved pre-cluster NumPy state for a new-directory replay')
    args=parser.parse_args()
    result,check=run_plan(json.loads(args.plan.read_text(encoding="utf-8-sig")),args.dataset_root,args.workspace,
                          atol_uv=args.atol_uv,resume=args.resume,replay_rng=args.replay_rng)
    print(json.dumps({'result':result,'delivery_check_passed':check['passed'],
                      'final_submission':str(args.workspace/'FINAL_SUBMISSION.md')},indent=2))


if __name__=='__main__':
    main()
