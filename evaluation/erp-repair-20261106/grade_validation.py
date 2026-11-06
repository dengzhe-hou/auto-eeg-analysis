"""Deterministic grades for each saved first delivery; this study has no judge."""
from __future__ import annotations

import json
from pathlib import Path

from verify_contract import verify

ROOT = Path(__file__).resolve().parent
GRADER_VERSION = 'erp-deterministic-v1-20261101'


def adoption(directory, result):
    """Record what the session actually touched, from the same traces in both arms."""
    trace = directory / 'execution_trace.jsonl'
    code = ''
    if trace.exists():
        code = '\n'.join(json.loads(line).get('code') or '' for line in trace.read_text().splitlines())
    functions = set()
    workspace = Path(result.get('workspace', ''))
    function_trace = workspace / 'AEA_FUNCTION_TRACE.jsonl'
    if function_trace.exists():
        functions = {json.loads(line)['source'] for line in function_trace.read_text().splitlines()}
    return {'code_mentions_reference_scripts': any(word in code for word in ('tools/validation', 'validate_p3_group', 'validate_n170', 'validate_ern', 'validate_n400')),
            'code_mentions_benchmark_folder': 'tools/benchmark' in code,
            'aea_functions_returned': sorted(functions), 'self_check_file': (workspace / 'SELF_CHECK.json').is_file()}


def grade(item, result, directory):
    dest = ROOT / 'grades' / 'primary' / directory.name
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / 'GRADE.json').exists():
        return json.loads((dest / 'GRADE.json').read_text())
    if result['status'] == 'failed':
        value = {'answer_field_pass': False, 'full_contract_pass': False, 'evidence_pass': False, 'derivatives_pass': False,
                 'provenance_pass': False, 'derivative_records_doi': False, 'answer_source': None, 'checks': {},
                 'failure_category': result.get('failure_category'), 'llm_judge_called': False}
    elif result['status'] != 'submitted':
        raise RuntimeError('Infrastructure or budget failures remain pending: ' + str(result['status']))
    else:
        value = verify(item['request_id'], result['workspace'], (directory / 'FIRST_SUBMISSION.md').read_text())
    value.update(session=directory.name, request_id=item['request_id'], grader_version=GRADER_VERSION, target_status=result['status'], adoption=adoption(directory, result))
    (dest / 'GRADE.json').write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'session': directory.name, 'answer_field_pass': value['answer_field_pass'], 'full_contract_pass': value['full_contract_pass'],
                      'evidence_pass': value['evidence_pass'], 'derivatives_pass': value['derivatives_pass'], 'provenance_pass': value['provenance_pass']}), flush=True)
    return value
