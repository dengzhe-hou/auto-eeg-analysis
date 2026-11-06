"""Resume fixed assignments without replacing scientific failures or sessions."""
import argparse
import json
from pathlib import Path
import time

from run_validation import ROOT, AUTH, api_client, base, run
from grade_validation import grade


def progress():
    targets = [json.loads(p.read_text()) for p in (ROOT / 'sessions').glob('*/RESULT.json')]
    grades = list((ROOT / 'grades/primary').glob('*/GRADE.json'))
    state = api_client.budget_state()
    return {'target_results': len(targets), 'grades': len(grades),
            'target_statuses': {s: sum(r['status'] == s for r in targets) for s in {r['status'] for r in targets}},
            'shared_budget': state, 'stage_cost_estimate_usd': state['committed_usd'] - AUTH['budget_at_start']['committed_usd'],
            'incomplete_not_scientific_zero': [r['session'] for r in targets if r['status'] not in ('submitted', 'failed')]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['pilot', 'formal'], required=True)
    p.add_argument('--kind', choices=['all', 'single_subject', 'group'], default='all')
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--shards', type=int, default=1)
    a = p.parse_args()
    if a.phase == 'formal' and not AUTH.get('formal_authorized'):
        raise RuntimeError('formal_authorized is false; no formal session may start')
    requests = json.loads((ROOT / 'REQUESTS.json').read_text())
    lookup = {x['request_id']: x for x in requests['requests'] + requests['pilot_requests']}
    schedule = json.loads((ROOT / ('PILOT_SCHEDULE.json' if a.phase == 'pilot' else 'SCHEDULE.json')).read_text())['sessions']
    pairs = [schedule[i:i + 2] for i in range(0, len(schedule), 2)]
    assigned = [pair for pair in pairs if a.kind == 'all' or pair[0]['request_kind'] == a.kind]
    unresolved = []
    label = f'{a.phase}_{a.kind}_{a.shard}'
    admission_stop = ROOT / 'FORMAL_ADMISSION_STOP.json'
    for number, pair in enumerate(assigned):
        if number % a.shards != a.shard:
            continue
        for row in pair:
            if a.phase == 'formal' and admission_stop.exists():
                base.write_json(ROOT / f'WORKER_COMPLETE_{label}.json', {
                    'completed_at_unix': time.time(), 'assignments_complete': False,
                    'admission_stopped': True, 'retained_pending': unresolved})
                return
            item = lookup[row['request_id']]
            directory = ROOT / 'sessions' / row['session']
            result_file = directory / 'RESULT.json'
            if result_file.exists():
                result = json.loads(result_file.read_text())
            else:
                if directory.exists():
                    raise RuntimeError('Interrupted assignment retained for diagnosis: ' + str(directory))
                result = run(item, row)
            if result['status'] not in ('submitted', 'failed'):
                unresolved.append(directory.name)
                base.write_json(ROOT / f'PROGRESS_{label}.json', progress())
                if result['status'] == 'budget_blocked' or (a.phase == 'formal' and result['status'] == 'infrastructure_failure'):
                    if a.phase == 'formal':
                        try:
                            with admission_stop.open('x') as stream:
                                json.dump({'session': row['session'], 'status': result['status'],
                                           'failure_category': result.get('failure_category'),
                                           'error': result.get('error'),
                                           'reason': 'Stop admission on the shared runner/API failure; preserve in-flight sessions and all outputs'}, stream, indent=2)
                        except FileExistsError:
                            pass  # Another worker already retained the first shared failure.
                    base.write_json(ROOT / f'WORKER_COMPLETE_{label}.json', {'completed_at_unix': time.time(), 'assignments_complete': False,
                                                                             'budget_blocked': result['status'] == 'budget_blocked', 'retained_pending': unresolved})
                    return
                continue
            grade(item, result, directory)
            base.write_json(ROOT / f'PROGRESS_{label}.json', progress())
    base.write_json(ROOT / f'WORKER_COMPLETE_{label}.json', {'completed_at_unix': time.time(), 'assignments_complete': not unresolved, 'retained_pending': unresolved})


if __name__ == '__main__':
    main()
