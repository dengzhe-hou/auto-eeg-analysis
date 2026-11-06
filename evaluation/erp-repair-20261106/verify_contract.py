"""Deterministic grading of a delivered ERP session. No model or judge is ever called.

Primary endpoint, answer fields: single-subject ROI amplitude within 0.1 uV of the frozen
reference; group-level effect direction and both significance judgements equal to it.
Secondary endpoints are recorded separately: evidence arrays, BIDS validator on the
derivative dataset, recorded dataset version and DOI, and the full contract.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import subprocess

import numpy as np

from contracts import AMPLITUDE_TOLERANCE_UV, DERIVATIVES_ROOT, WAVE_RMS_TOLERANCE_UV

ROOT = Path(__file__).resolve().parent
DOI_TEXT = '10.18115/d5jw4r'
DATASET_VERSION = '1.0'  # Stated in the dataset's CHANGES file on OSF: "version 1.0 - 20 Jul 2020".
VALIDATOR = {'deno': ROOT / 'tools_bids/node_modules/.bin/deno', 'module': 'jsr:@bids/validator@3.0.2',
             'cwd': ROOT / 'tools_bids/deno-work', 'deno_dir': ROOT / 'tools_bids/deno-cache'}


def json_report(text):
    decoder = json.JSONDecoder()
    for m in re.finditer(r'\{', text or ''):
        try:
            value, _ = decoder.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and 'status' in value:
            return value
    return None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def close(value, expected, tolerance=AMPLITUDE_TOLERANCE_UV):
    return number(value) and abs(value - expected) <= tolerance


def bids_validate(root):
    """Run the schema validator with its cached modules; errors decide, warnings do not."""
    env = {**os.environ, 'DENO_DIR': str(VALIDATOR['deno_dir']), 'DENO_NO_UPDATE_CHECK': '1',
           'HOME': str(ROOT / 'tools_bids/home'), 'XDG_CACHE_HOME': str(ROOT / 'tools_bids/cache')}
    run = subprocess.run([str(VALIDATOR['deno']), 'run', '-A', '--no-config', '--cached-only', VALIDATOR['module'], str(root), '--json'],
                         cwd=VALIDATOR['cwd'], env=env, capture_output=True, text=True, timeout=300)
    try:
        issues = json.loads(run.stdout)['issues']['issues']
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(f'BIDS validator did not produce a report: {run.stderr[-500:]}') from exc
    errors = [{'code': i.get('code'), 'location': i.get('location')} for i in issues if i.get('severity') == 'error']
    return {'passed': not errors, 'errors': errors[:40], 'n_errors': len(errors), 'validator': VALIDATOR['module'],
            'n_warnings': sum(i.get('severity') == 'warning' for i in issues)}


def primary(reference, answer):
    """Answer-field checks only."""
    if reference['request_kind'] == 'single_subject':
        v = answer.get('roi_amplitude_uv')
        return [{'name': 'answer.roi_amplitude_uv', 'passed': close(v, reference['roi_amplitude_uv']),
                 'detail': f'reported={v!r}; tolerance={AMPLITUDE_TOLERANCE_UV} uV'}]
    return [{'name': 'answer.' + key, 'passed': type(answer.get(key)) is type(reference[key]) and answer.get(key) == reference[key],
             'detail': f'reported={answer.get(key)!r}'} for key in ('effect_direction', 'ttest_significant', 'cluster_significant')]


def extra_answer_checks(reference, answer):
    out = []
    def add(name, ok, detail=''):
        out.append({'name': name, 'passed': bool(ok), 'detail': detail})
    if reference['request_kind'] == 'single_subject':
        for key in ('n_trials_plus', 'n_trials_minus'):
            add('counts.' + key, answer.get(key) == reference[key], f'reported={answer.get(key)!r}')
    else:
        add('group.subjects_included', answer.get('subjects_included') == reference['subjects_included'])
        add('group.subjects_excluded', answer.get('subjects_excluded') == reference['subjects_excluded'])
        add('group.n_subjects', answer.get('n_subjects') == reference['n_subjects'])
        add('group.group_mean_uv', close(answer.get('group_mean_uv'), reference['group_mean_uv']), f"reported={answer.get('group_mean_uv')!r}")
        per = answer.get('per_subject_amplitude_uv')
        add('group.per_subject_amplitudes', isinstance(per, dict) and set(per) == set(reference['per_subject_amplitude_uv'])
            and all(close(per[s], v) for s, v in reference['per_subject_amplitude_uv'].items()))
        # A t statistic moves with the rounding of the frozen script's inputs; p values only in the judgement.
        add('group.ttest_t', number(answer.get('ttest_t')) and abs(answer['ttest_t'] - reference['ttest_t']) <= 0.2, f"reported={answer.get('ttest_t')!r}")
        add('group.ttest_p', number(answer.get('ttest_p')) and (answer['ttest_p'] < .05) == reference['ttest_significant'])
        add('group.cluster_min_p', number(answer.get('cluster_min_p')) and (answer['cluster_min_p'] < .05) == reference['cluster_significant'])
    return out


def evidence_checks(workspace, directory, reference):
    out = []
    def add(name, ok, detail=''):
        out.append({'name': name, 'passed': bool(ok), 'detail': detail})
    path = Path(workspace) / 'analysis_evidence.npz'
    add('evidence.file', path.is_file())
    if not path.is_file():
        return out
    with np.load(directory / 'reference.npz', allow_pickle=False) as ref:
        wave = 'roi_difference_uv' if reference['request_kind'] == 'single_subject' else 'grand_roi_difference_uv'
        try:
            with np.load(path, allow_pickle=False) as got:
                add('evidence.times_s.present', 'times_s' in got)
                add(f'evidence.{wave}.present', wave in got)
                if 'times_s' in got:
                    t = got['times_s']
                    same = t.shape == ref['times_s'].shape and np.allclose(t, ref['times_s'], rtol=0, atol=1e-6)
                    add('evidence.times_s.values', same, f"{t.shape} vs {ref['times_s'].shape}")
                if wave in got:
                    x = got[wave]
                    add(f'evidence.{wave}.shape', x.shape == ref[wave].shape, f'{x.shape} vs {ref[wave].shape}')
                    if x.shape == ref[wave].shape:
                        rms = float(np.sqrt(np.mean((x.astype(float) - ref[wave]) ** 2)))
                        add(f'evidence.{wave}.rms', rms <= WAVE_RMS_TOLERANCE_UV, f'rms={rms:g} uV; tolerance={WAVE_RMS_TOLERANCE_UV}')
                if reference['request_kind'] == 'group':
                    add('evidence.subjects', 'subjects' in got and got['subjects'].astype(str).tolist() == ref['subjects'].astype(str).tolist())
                    if 'roi_amplitudes_uv' in got and got['roi_amplitudes_uv'].shape == ref['roi_amplitudes_uv'].shape:
                        add('evidence.roi_amplitudes_uv', np.all(np.abs(got['roi_amplitudes_uv'].astype(float) - ref['roi_amplitudes_uv']) <= AMPLITUDE_TOLERANCE_UV))
                    else:
                        add('evidence.roi_amplitudes_uv', False, 'absent or wrong shape')
        except (ValueError, TypeError, OSError) as exc:
            add('evidence.readable', False, str(exc))
    return out


def derivative_checks(workspace, reference, validate=bids_validate):
    out = []
    root = Path(workspace) / DERIVATIVES_ROOT
    description = root / 'dataset_description.json'
    out.append({'name': 'derivatives.dataset_description', 'passed': description.is_file(), 'detail': ''})
    report = None
    has_doi = False
    if description.is_file():
        report = validate(root)
        out.append({'name': 'derivatives.bids_validator', 'passed': report['passed'], 'detail': json.dumps(report['errors'][:5])})
        try:
            value = json.loads(description.read_text())
            has_doi = DOI_TEXT in json.dumps(value.get('SourceDatasets', '')).lower()
        except json.JSONDecodeError:
            has_doi = False
    subjects = [reference['subject']] if reference['request_kind'] == 'single_subject' else reference['subjects_included']
    present = [s for s in subjects if (root / s).is_dir() and any(p.is_file() for p in (root / s).rglob('*'))]
    out.append({'name': 'derivatives.subject_outputs', 'passed': len(present) == len(subjects), 'detail': f'{len(present)}/{len(subjects)} subjects'})
    return out, report, has_doi


def verify(request_id, workspace, submission, validate=bids_validate):
    directory = ROOT / 'references_frozen' / request_id
    reference = json.loads((directory / 'reference.json').read_text())
    workspace = Path(workspace)
    checks, source, answer, report_json = [], None, None, json_report(submission)
    path = workspace / 'result.json'
    if path.is_file():
        try:
            answer = json.loads(path.read_text())
            source = 'result.json'
        except json.JSONDecodeError as exc:
            checks.append({'name': 'result_json_readable', 'passed': False, 'detail': str(exc)})
    if not isinstance(answer, dict):
        answer, source = (report_json, 'first_final_report') if report_json else (None, None)
    answer_checks = primary(reference, answer or {})
    answer_pass = bool(answer) and all(c['passed'] for c in answer_checks)
    extra = extra_answer_checks(reference, answer or {})
    evidence = evidence_checks(workspace, directory, reference)
    derivative, validator_report, derivative_doi = derivative_checks(workspace, reference, validate)
    provenance = [
        {'name': 'provenance.dataset_doi', 'passed': DOI_TEXT in str((answer or {}).get('dataset_doi', '')).lower(), 'detail': repr((answer or {}).get('dataset_doi'))},
        {'name': 'provenance.dataset_version', 'passed': bool(re.search(r'(?<![\d.])' + re.escape(DATASET_VERSION) + r'(?:\.0)*(?![\d.])', str((answer or {}).get('dataset_version', '')))), 'detail': repr((answer or {}).get('dataset_version'))}]
    consistency = [{'name': 'result_file_present', 'passed': source == 'result.json', 'detail': ''},
                   {'name': 'first_report_json_present', 'passed': report_json is not None, 'detail': ''},
                   {'name': 'explanation_present', 'passed': isinstance((answer or {}).get('explanation'), str) and bool(answer['explanation'].strip()), 'detail': ''}]
    if report_json is not None and source == 'result.json':
        fields = [c['name'].split('.', 1)[1] for c in answer_checks]
        consistency.append({'name': 'report_matches_file', 'passed': all(report_json.get(k) == answer.get(k) for k in fields), 'detail': ''})
    derivative_pass = all(c['passed'] for c in derivative)
    evidence_pass = all(c['passed'] for c in evidence)
    provenance_pass = all(c['passed'] for c in provenance)
    full = (answer_pass and all(c['passed'] for c in extra + consistency) and evidence_pass and derivative_pass and provenance_pass and derivative_doi)
    return {'request_id': request_id, 'answer_field_pass': answer_pass, 'answer_source': source, 'full_contract_pass': bool(full),
            'evidence_pass': evidence_pass, 'derivatives_pass': derivative_pass, 'bids_validator_report': validator_report,
            'provenance_pass': provenance_pass, 'derivative_records_doi': derivative_doi,
            'checks': {'answer': answer_checks, 'other_answer': extra, 'consistency': consistency, 'evidence': evidence, 'derivatives': derivative, 'provenance': provenance},
            'reported': answer, 'llm_judge_called': False}
