"""Paired effect on the primary and each secondary endpoint, from saved grades only."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

STUDY = Path(__file__).resolve().parent
ENDPOINTS = {'answer_field_pass': 'primary', 'full_contract_pass': 'secondary', 'evidence_pass': 'secondary',
             'derivatives_pass': 'secondary', 'provenance_pass': 'secondary'}
ARMS = ('with_aea', 'without_aea')
SEED = 20261029
DRAWS = 10000


def interval(d, factors, seed=SEED):
    """Crossed exponential weights: each level of each factor gets one weight per draw."""
    rng = np.random.default_rng(seed)
    weights = np.ones((DRAWS, len(d)))
    for factor in factors:
        levels, index = np.unique(factor, return_inverse=True)
        weights *= rng.exponential(size=(DRAWS, len(levels)))[:, index]
    values = (weights @ d) / weights.sum(axis=1)
    return (100 * np.quantile(values, [.025, .975])).tolist()


def paired_effect(rows, endpoint, repetitions):
    requests = {}
    for r in rows:
        requests.setdefault(r['request_id'], {}).setdefault(r['repetition'], {})[r['arm']] = r
    per_request = []
    for request_id, reps in sorted(requests.items()):
        if len(reps) != repetitions or any(set(p) != set(ARMS) for p in reps.values()):
            raise ValueError('Incomplete pairs for ' + request_id)
        d = [int(p['with_aea'][endpoint]) - int(p['without_aea'][endpoint]) for p in reps.values()]
        first = next(iter(reps.values()))['with_aea']
        per_request.append({'request_id': request_id, 'component': first['component'], 'subject_factor': first['subject_factor'],
                            'request_kind': first['request_kind'], 'difference': float(np.mean(d))})
    d = np.array([x['difference'] for x in per_request])
    component = [x['component'] for x in per_request]
    subject = [x['subject_factor'] for x in per_request]
    counts = {arm: int(sum(r[endpoint] for r in rows if r['arm'] == arm)) for arm in ARMS}
    return {'endpoint': endpoint, 'with_aea_pass': counts['with_aea'], 'without_aea_pass': counts['without_aea'],
            'difference_pp': float(100 * d.mean()), 'ci95_crossed_component_subject': interval(d, [component, subject]),
            'ci95_component_only': interval(d, [component]), 'ci95_subject_only': interval(d, [subject]),
            'by_kind': {k: float(100 * d[[x['request_kind'] == k for x in per_request]].mean()) for k in sorted({x['request_kind'] for x in per_request})},
            'by_component': {k: float(100 * d[[x['component'] == k for x in per_request]].mean()) for k in sorted(set(component))},
            'by_repetition': {str(rep): float(100 * np.mean([int(requests[q][rep]['with_aea'][endpoint]) - int(requests[q][rep]['without_aea'][endpoint]) for q in requests])) for rep in sorted({r['repetition'] for r in rows})},
            'per_request': per_request}


def collect(root):
    schedule = json.loads((root / 'SCHEDULE.json').read_text())['sessions']
    rows = []
    for s in schedule:
        target = root / 'sessions' / s['session'] / 'RESULT.json'
        grade = root / 'grades/primary' / s['session'] / 'GRADE.json'
        if not target.exists() or not grade.exists():
            continue
        t, g = json.loads(target.read_text()), json.loads(grade.read_text())
        rows.append({**s, 'subject_factor': t['subject_factor'], 'status': t['status'], 'target_cost_usd': t['api_usage_cost_estimate_usd'],
                     'elapsed_seconds': t['elapsed_seconds'], 'answer_source': g.get('answer_source'),
                     **{k: int(bool(g[k])) for k in ENDPOINTS},
                     'code_mentions_reference_scripts': int(bool(g.get('adoption', {}).get('code_mentions_reference_scripts'))),
                     'self_check_file': int(bool(g.get('adoption', {}).get('self_check_file')))})
    return schedule, rows


def analyze(root, planned_sessions=144, repetitions=3, requests=24):
    schedule, rows = collect(root)
    if rows:
        with (root / 'RUN_METRICS.csv').open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    result = {'assigned_sessions': len(schedule), 'complete_sessions': len(rows), 'analysis_complete': len(rows) == planned_sessions == len(schedule),
              'primary_endpoint': 'answer_field_pass', 'statistic': 'Request mean of three paired differences; crossed exponential weights on component and subject factors; 10000 draws; seed 20261029',
              'endpoints': {}, 'arms': {}}
    for arm in ARMS:
        v = [r for r in rows if r['arm'] == arm]
        result['arms'][arm] = {'complete_sessions': len(v), 'target_cost_usd': sum(r['target_cost_usd'] for r in v), 'mean_elapsed_seconds': float(np.mean([r['elapsed_seconds'] for r in v])) if v else None,
                               'statuses': {s: sum(r['status'] == s for r in v) for s in {r['status'] for r in v}},
                               'sessions_mentioning_reference_scripts': sum(r['code_mentions_reference_scripts'] for r in v), 'sessions_with_self_check': sum(r['self_check_file'] for r in v)}
    if result['analysis_complete']:
        for endpoint, role in ENDPOINTS.items():
            result['endpoints'][endpoint] = {'role': role, **paired_effect(rows, endpoint, repetitions)}
        primary = result['endpoints']['answer_field_pass']
        result['stable_improvement_criterion_met'] = primary['difference_pp'] > 0 and primary['ci95_crossed_component_subject'][0] > 0
        assert len(primary['per_request']) == requests
    (root / 'RESULTS.json').write_text(json.dumps(result, indent=1) + '\n')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=STUDY)
    a = ap.parse_args()
    out = analyze(a.root)
    print(json.dumps({k: out[k] for k in ('assigned_sessions', 'complete_sessions', 'analysis_complete')}))
