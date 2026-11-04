"""Paired ERP sessions on the unchanged upstream CodeAct loop and the shared API ledger."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
FORMAL = ROOT.parent / 'brainbench-formal-20261022'
sys.path.insert(0, str(FORMAL))
import run_formal as base
import api_client
api_client.LEDGER = FORMAL / 'api_usage.jsonl'
AUTH = json.loads((ROOT / 'EXECUTION_AUTHORIZATION.json').read_text())
api_client.CAP = AUTH['effective_shared_committed_ceiling_usd']
RUN = json.loads((ROOT / 'RUN_PARAMETERS.json').read_text())
from brainbench.codeact import engine, process
from brainbench.codeact.sandbox import CodeActSandboxConfig, create_run_root, prepare_case_context
from study_apptainer import stop_kernel
from observed_kernel import ObservedKernel
from components import MOUNT, RAW_ROOT
from contracts import DERIVATIVES_ROOT
SNAPSHOT = ROOT / AUTH['resource_version']
sys.path.insert(0, str(SNAPSHOT / 'tools'))
from load_skill import check_packet_in_request

OriginalMeasuredClient = api_client.MeasuredClient
PILOT_PREFIX = 'devpilot8__'


class StudyClient(OriginalMeasuredClient):
    """Target model only. This study has no judge, so any other role is a programming error."""

    def __init__(self, **kwargs):
        if kwargs.get('role') != 'target':
            raise RuntimeError('Judge calls are disabled in this study: role ' + str(kwargs.get('role')))
        super().__init__(**kwargs)

    def create(self, **request):
        api_client.CAP = AUTH['effective_shared_committed_ceiling_usd']
        if self.session.startswith(PILOT_PREFIX):
            api_client.CAP = min(api_client.CAP, AUTH['budget_at_start']['committed_usd'] + AUTH['pilot_api_cap_usd'])
        if '__with_aea__' in self.session:
            from brainbench.codeact.transport import _anthropic_request
            packet = (ROOT / 'sessions' / self.session / 'SKILL_PACKET.md').read_text()
            receipt = check_packet_in_request(_anthropic_request(request), packet)
            with (ROOT / 'sessions' / self.session / 'PACKET_REQUEST_CHECKS.jsonl').open('a') as f:
                f.write(json.dumps(receipt) + '\n')
        return super().create(**request)


api_client.MeasuredClient = StudyClient


def utc():
    return datetime.now(timezone.utc).isoformat()


COMMON = f'''
This is an unattended execution of the supplied approved research plan.
PUBLIC_CONTRACT.json resolves the scientific choices identically in both study conditions.
Do not add unrequested steps and do not change a setting to obtain a particular result.
Write /workspace/result.json with every key under required_results, using full-precision
JSON numbers. Save /workspace/analysis_evidence.npz with every array under required_evidence.
Write the BIDS-Derivatives dataset to /workspace/{DERIVATIVES_ROOT} as the plan describes.
Record the dataset DOI and the dataset version in result.json.
The final <solution> must include a JSON result object with the same numeric and categorical
values as result.json. Preserve your code in /workspace.
External verification happens after the first final submission; no live researcher or
evaluator feedback is available. Do not search for reference answers.
Use bare Python in <execute>, not Markdown fences. RUNTIME_ENVIRONMENT.json describes this
actual execution image. There is no network access.
'''


def build_query(rewritten, public, arm, packet=None):
    query = base.build_agent_query(rewritten) + COMMON + '\nPublic analysis plan:\n' + json.dumps(public, ensure_ascii=False)
    if arm == 'with_aea':
        if not packet:
            raise ValueError('AEA requires the selected procedure packet')
        query += '\nAEA resources are in /workspace/aea.\n' + packet
        query += ('\nApply these selected procedures and run python /workspace/aea/tools/check_erp_outputs.py --plan /workspace/PUBLIC_CONTRACT.json '
                  '--workspace /workspace before final delivery. Save the procedure and helper paths actually used. Preserve the approved scientific choices.\n')
    elif arm != 'without_aea':
        raise ValueError('Unknown condition')
    return query


def worker(connection, **arguments):
    label = arguments['run_context'].audit['formal_session']
    out = ROOT / 'sessions' / label
    os.environ['CODEACT_EXECUTION_TRACE'] = str(out / 'execution_trace.jsonl')
    engine.make_llm_client = lambda **kw: api_client.MeasuredClient(session=label, role='target', trace_path=out / 'native_requests.jsonl', **kw)
    process.DockerKernel = ObservedKernel
    base.ORIGINAL_WORKER(connection, **arguments)


def run(item, row):
    label = row['session']
    out = ROOT / 'sessions' / label
    pilot = label.startswith(PILOT_PREFIX)
    if pilot and not AUTH.get('pilot_authorized'):
        raise RuntimeError('Pilot sessions are not authorized')
    if not pilot and not AUTH.get('formal_authorized'):
        raise RuntimeError('Formal sessions are not authorized: formal_authorized is false')
    if not (ROOT / 'VERIFIER_READY.json').exists():
        raise RuntimeError('Verifiers not ready; no model request allowed')
    if not pilot and not (ROOT / 'PROTOCOL_FROZEN.json').exists():
        raise RuntimeError('Protocol not publicly frozen; no formal session allowed')
    out.mkdir(parents=True, exist_ok=False)
    cpus = int(os.environ.get('SLURM_CPUS_PER_TASK', '2'))
    mem = int(os.environ.get('SLURM_MEM_PER_NODE', '16384'))
    limit = RUN['session_limits']
    config = CodeActSandboxConfig(runs_root=out / 'sandbox', max_completion_tokens=RUN['model']['max_completion_tokens'],
                                  allowed_input_roots=(RAW_ROOT,), cpu_count=float(cpus), memory_limit=f'{mem}m',
                                  execution_timeout_sec=float(limit['execution_timeout_sec']), case_timeout_sec=float(limit['case_timeout_sec']))
    ctx, rewritten = prepare_case_context(config=config, run_root=create_run_root(config), workspace_root=base.PILOT,
                                          instance_id=item['request_id'], agent_input={'instruction': item['instruction']})
    runtime_root = ROOT / 'rt'
    runtime_root.mkdir(exist_ok=True)
    ctx = replace(ctx, input_mounts={RAW_ROOT: MOUNT}, runtime_dir=Path(tempfile.mkdtemp(prefix='', dir=runtime_root)))
    ctx.audit.update(formal_session=label, AEA_condition=row['arm'], repetition=row['repetition'], bids_mount=MOUNT,
                     source_bids_root=str(RAW_ROOT), contract_version='erp-explicit-plan-20261101')
    public = json.loads(Path(item['public_contract_path']).read_text())
    base.write_json(ctx.host_workspace / 'PUBLIC_CONTRACT.json', public)
    env = json.loads((FORMAL / 'RUNTIME_ENVIRONMENT.json').read_text())
    env.update(slurm_cpus=cpus, slurm_memory_gib=mem / 1024, cell_time_limit_seconds=limit['execution_timeout_sec'], session_time_limit_seconds=limit['case_timeout_sec'])
    base.write_json(ctx.host_workspace / 'RUNTIME_ENVIRONMENT.json', env)
    packet = None
    if row['arm'] == 'with_aea':
        shutil.copytree(SNAPSHOT, ctx.host_workspace / 'aea')
        packet = (ROOT / 'packets' / f"{item['component']}.md").read_text()
        (out / 'SKILL_PACKET.md').write_text(packet)
    query = build_query(rewritten, public, row['arm'], packet)
    (ctx.host_workspace / 'ANALYSIS_PLAN.md').write_text(query)
    (out / 'agent_query.txt').write_text(query)
    base.write_json(out / 'public_agent_input.json', rewritten)
    info = {'session': label, 'request_id': item['request_id'], 'component': item['component'], 'request_kind': item['request_kind'],
            'subject_factor': item['subject_factor'], 'arm': row['arm'], 'repetition': row['repetition'], 'model': api_client.EXECUTION_MODEL,
            'status': 'started', 'started_at_utc': utc(), 'workspace': str(ctx.host_workspace), 'bids_mount': MOUNT,
            'slurm_job_id': os.environ.get('SLURM_JOB_ID'), 'slurm_node_list': os.environ.get('SLURM_JOB_NODELIST'), 'slurm_cpus': cpus,
            'slurm_memory_gib': mem / 1024, 'external_feedback_repairs': 0, 'human_interventions': 0,
            'execution_condition': 'preloaded_procedures' if row['arm'] == 'with_aea' else 'no_aea'}
    base.write_json(out / 'START.json', {**info, 'runtime_dir': str(ctx.runtime_dir)})
    process._codeact_worker = worker
    started = time.monotonic()
    try:
        response, tokens = process.run_codeact_case_isolated(
            query=query, api_key=Path('/home/hou/.config/aea/anthropic_api_key').read_text().strip(), base_url='https://api.anthropic.com',
            llm_model=api_client.EXECUTION_MODEL, api_protocol='anthropic', run_context=ctx, sandbox_config=config)
        (out / 'FIRST_SUBMISSION.md').write_text(response + '\n')
        info.update(status='submitted', official_runner_tokens=tokens)
    except engine.CodeActExecutionError as exc:
        diagnostics = str(ctx.audit.get('codeact_worker_error', {})).lower() + ' ' + str(exc).lower()
        trace = out / 'execution_trace.jsonl'
        executed = trace.exists() and any(json.loads(s).get('code') for s in trace.read_text().splitlines())
        program_death = exc.category == 'kernel_error' and executed and any(
            word in diagnostics for word in ('deadkernelerror', 'kernel died', 'out of memory', 'memoryerror', 'oom'))
        infra = exc.category.startswith('api_') or exc.category in ('worker_error', 'kernel_error') and not program_death
        info.update(status='infrastructure_failure' if infra else 'failed', failure_category=exc.category, error=str(exc))
    except engine.SandboxSetupError as exc:
        info.update(status='infrastructure_failure', failure_category='sandbox', error=str(exc))
    finally:
        stop_kernel(ctx.runtime_dir)
        es = [e for e in api_client.events() if e['session'] == label and e['event'] in ('settled', 'not_sent')]
        if any(e.get('error_type') == 'BudgetStop' for e in es):
            info['status'] = 'budget_blocked'
        trace = ctx.audit.get('codeact_trace', [])
        info.update(elapsed_seconds=time.monotonic() - started, finished_at_utc=utc(),
                    api_usage_cost_estimate_usd=sum(e.get('api_usage_cost_estimate_usd') or 0 for e in es),
                    provider_invoiced_cost_usd=None, api_request_attempts=len(es),
                    execute_actions=sum(e.get('action') == 'execute' for e in trace), tool_errors=sum(e.get('status') in ('error', 'repeated_failure') for e in trace),
                    sonnet_requests=sum(e.get('requested_model') != api_client.EXECUTION_MODEL for e in es))
        base.write_json(out / 'AUDIT.json', ctx.audit)
        base.write_json(out / 'RESULT.json', info)
    print(json.dumps({k: info[k] for k in ('session', 'status', 'elapsed_seconds', 'api_usage_cost_estimate_usd', 'api_request_attempts')}), flush=True)
    return info
