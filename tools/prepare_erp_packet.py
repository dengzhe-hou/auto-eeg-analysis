"""Select only task-matching procedures for the explicit approved ERP plan schema.

No reference answers, participant outcomes or experiment scoring files are read.
This prepares a new resource condition; it does not alter any frozen evaluation.
"""
import argparse
import json
from pathlib import Path

from prepare_skill_packet import prepare_packet


def prepare_erp_packet(root, plan):
    if plan['request_kind'] not in ('single_subject', 'group'):
        raise ValueError('Select single_subject or group for this ERP packet route')
    selections = [{'skill': 'eeg-epoch', 'section': 'Approved ERP execution',
                   'scripts': ['scripts/erp.py']}]
    contrast = plan['derivatives']['contrast_label']
    if plan['dataset']['name'] == 'ERP CORE' and contrast == 'errorminuscorrect':
        selections.append({'skill': 'eeg-epoch', 'section': 'ERP CORE response coding',
                           'scripts': ['scripts/erp_core_events.py']})
    if plan['request_kind'] == 'group':
        selections.append({'skill': 'eeg-epoch', 'section': 'Approved ERP group statistics'})
    packet, receipt = prepare_packet(Path(root), selections)
    sources = ['tools/check_erp_outputs.py']
    for source in sources:
        packet += f'\n\nAEA procedure: {source}\n\n' + (Path(root) / source).read_text(encoding='utf-8-sig')
    packet += ('\n\nAEA callable interface: tools/erp_execution.py\n'
               'Use the actual checkout, approved plan, dataset root and workspace paths from this task.\n')
    metadata_tasks = {'P3': 'rareminusfrequent', 'N170': 'facesminuscars',
                      'N400': 'unrelatedminusrelated', 'ERN': 'errorminuscorrect'}
    task = plan['dataset'].get('bids_task_label')
    if (plan['dataset']['name'] == 'ERP CORE' and task in metadata_tasks
            and metadata_tasks[task] == contrast):
        entry = ('AEA complete approved ERP entry\n'
                 'This plan is supported by the saved one-call runner. Execute it instead of rebuilding the pipeline in notebook cells:\n'
                 'python AEA_CHECKOUT/tools/run_erp_plan.py --plan APPROVED_PLAN.json '
                 '--dataset-root DATASET_ROOT --workspace RUN_DIRECTORY --atol-uv INTERNAL_TOLERANCE_UV\n'
                 'It checks actual event metadata, executes the supplied preprocessing in order, saves each participant, '
                 'uses the named ROI, runs only the requested group tests, writes actual evidence and derivative files, '
                 'and creates FINAL_SUBMISSION.md only after the delivery check passes. '
                 'Read the printed result and return the complete contents of FINAL_SUBMISSION.md. '
                 'A normal integer-sample epoch grid or a check not yet run is not a reason to stop. '
                 'If execution fails, inspect execution.json and the saved participant-state files. '
                 'After a timeout check its recorded PID before retrying. If the old process has stopped, '
                 'the same command with --resume reuses saved participant states without preprocessing them again. '
                 'Do not change the approved scientific settings or overwrite a completed delivery. '
                 'The source is available in the checkout for inspection, not preloaded here. '
                 'The lower-level interfaces below remain available when diagnosing a specific failure.\n\n')
        packet = entry + packet
        packet += ('Execute python AEA_CHECKOUT/tools/erp_execution.py preflight --plan APPROVED_PLAN.json '
                   '--dataset-root DATASET_ROOT --workspace RUN_DIRECTORY before implementing EEG processing. '
                   'This reads task sidecars and actual event rows, writes conditions/counts/version in ERP_INPUTS.json, '
                   'and identifies the next approved step. Pre-epoch counts do not replace retained-epoch eligibility.\n')
    if plan['request_kind'] == 'group':
        packet += ('From erp_execution import save_subject_state and load_group_state after adding AEA_CHECKOUT/tools to sys.path. '
                   'After each processed participant call save_subject_state(STATE_DIRECTORY, subject, epochs, '
                   'plan=plan, plus=plus_condition, minus=minus_condition). Before statistics use '
                   'state = load_group_state(STATE_DIRECTORY, plan=plan). It restores actual channel Info and provides '
                   'state["result_fields"], state["evidence"], state["info"] and state["cluster_data_uv"] '
                   '(subjects x approved-window samples x channels). It selects the named ROI and saves excluded counts. '
                   'Use only the approved tests and settings. Do not reset dictionaries or average all channels to recover a missing variable.\n')
    packet += ('After saving actual results, evidence and derivatives, run python AEA_CHECKOUT/tools/erp_execution.py '
               'finalize --plan APPROVED_PLAN.json --workspace RUN_DIRECTORY --atol-uv INTERNAL_TOLERANCE_UV. '
               'Only a successful check creates FINAL_SUBMISSION.md from the actual result.json. Return that file as the final response. '
               'A failed check preserves a numbered report. Fix implementation issues within the approved task; '
               'do not manufacture answers or treat a check not yet executed as a missing scientific choice. '
               'The callable helper source is on disk, not preloaded into this packet.\n')
    receipt.update(additional_sources=sources, packet_characters=len(packet),
                   execution_helper='tools/erp_execution.py', execution_helper_source_preloaded=False,
                   complete_entry=('tools/run_erp_plan.py' if plan['dataset']['name'] == 'ERP CORE'
                                   and metadata_tasks.get(task) == contrast else None),
                   request_kind=plan['request_kind'], contrast_label=contrast,
                   selection_basis='Public request kind, dataset and contrast only; no reference outcomes')
    return packet, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    packet, receipt = prepare_erp_packet(args.root, json.loads(args.plan.read_text(encoding="utf-8-sig")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(packet, encoding='utf-8')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
