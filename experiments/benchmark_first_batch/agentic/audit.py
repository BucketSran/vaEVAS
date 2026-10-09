#!/usr/bin/env python3
"""Audit one actual Trial, including failures, without contacting a backend."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from runtime import ROOT, REPO, save
sys.path.insert(0, str(REPO))
from experiments.benchmark_first_batch.verification_measurement.regrade_measurement import (
    SealedArchive, verify_seal, require, digest, load_module,
)


PARSER = load_module(REPO / 'benchmark/checkers/adc_linearity.py', 'agentic_audit_parser')
ROW_VALIDATOR = load_module(REPO / 'benchmark/checkers/circuit_task.py', 'agentic_audit_row_validator')

def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()



def verify_translation(original, executed, receipt, outputs, case_name):
    require(receipt.get('version') == 'circuit-output-paths-v1' and
            receipt.get('inverse_verified') is True, 'missing output translation contract')
    pieces, cursor = [], 0
    for edit in receipt.get('edits', []):
        start, end = edit['start'], edit['end']
        require(type(start) is int and type(end) is int and cursor <= start < end <= len(original),
                'invalid or overlapping output translation span')
        literal = edit['original_literal'].encode()
        replacement = edit['executed_literal'].encode()
        require(original[start:end] == literal, 'original output literal differs')
        original_path, executed_path = json.loads(literal), json.loads(replacement)
        require(original_path in {'/work/output/' + name for name in outputs},
                'translation of undeclared output')
        name = original_path[len('/work/output/'):]
        require(isinstance(executed_path, str) and Path(executed_path).is_absolute() and
                '..' not in Path(executed_path).parts and
                executed_path.endswith('/' + case_name + '/output/' + name),
                'executed output path differs from declared case output')
        pieces.extend([original[cursor:start], replacement])
        cursor = end
    pieces.append(original[cursor:])
    require(b''.join(pieces) == executed, 'relocation changed bytes outside declared literals')
    # The checked original spans and complete forward byte equality prove the inverse.


def audit_archive(receipt_path, evaluations, frozen_identity):
    receipt = read(receipt_path)
    archive = SealedArchive(receipt_path.parent / 'job.tar.gz', receipt)
    try:
        sealed_result = archive.json('run/result.json')
        wrapper = {'result': sealed_result, 'job_id': receipt['request']['job_id'],
                   'condition_id': sealed_result['condition_id']}
        result, package, candidate = verify_seal(archive, wrapper)
        require(result['task_package_sha256'] == frozen_identity['final_task_package_sha256'],
                'sealed/frozen package identity mismatch')
        matching = [e for e in evaluations if e.get('candidate_sha256') == candidate['candidate_sha256']]
        require(len(matching) == 1, 'expected one matching final evaluation')
        require(matching[0].get('state') == 'completed', 'evaluation is not completed')
        require({k: v for k, v in matching[0].items() if k != 'state'} == result,
                'evaluation differs from sealed result')
        if result.get('execution') != 'ok':
            require(result.get('score') is None and result.get('verdict') == 'not_evaluated',
                    'infrastructure receipt carries an invalid task score')
            for name, info in candidate['files'].items():
                original = archive.read('run/work/candidate/' + name)
                require(digest(original) == info['sha256'] and len(original) == info['bytes'] and
                        original == archive.read('candidate/files/' + name),
                        'infrastructure receipt candidate bytes differ')
            return {'archive_sha256':receipt['package']['sha256'], 'bytes':receipt['package']['bytes'],
                    'job_id':wrapper['job_id'], 'candidate_bundle_sha256':candidate['candidate_sha256'],
                    'candidate_files':candidate['files'], 'task_package_sha256':result['task_package_sha256'],
                    'criteria_sha256':package['criteria_sha256'],
                    'verified_archive_members':len(archive.members), 'seal_and_result_artifacts_verified':True,
                    'actual_candidate_and_case_bytes_verified':False,
                    'actual_working_candidate_bytes_verified':True,
                    'case_execution_identity_verified_count':0, 'graded_waveform_verified_count':0,
                    'report_status':'not_evaluated', 'score':None, 'complete_pass':False,
                    'execution':result['execution'], 'cases':[]}
        report = archive.json('run/work/verifier/report.json')
        bindings = {'cases_sha256': 'cases.json', 'contract_sha256': 'contract.json',
                    'checker_sha256': 'verify.py', 'runtime_sha256': 'circuit_task.py',
                    'parser_sha256': 'adc_linearity.py'}
        for key, name in bindings.items():
            require(report.get(key) == digest(archive.read('run/work/tests/' + name)),
                    'report source identity differs: ' + key)
        cases = archive.json('run/work/tests/cases.json')
        contract = archive.json('run/work/tests/contract.json')
        expected = {c['name']: c for c in cases}
        require(len(expected) == len(cases) and bool(expected), 'invalid frozen case set')
        sources = {}
        for name, info in candidate['files'].items():
            original = archive.read('run/work/candidate/' + name)
            require(digest(original) == info['sha256'] and len(original) == info['bytes'],
                    'working candidate bytes differ: ' + name)
            require(original == archive.read('candidate/files/' + name),
                    'working/frozen candidate bytes differ: ' + name)
            sources[name] = original
        require(report.get('candidate_sha256') == candidate['files'][package['candidate_file']]['sha256'],
                'report main candidate identity differs')
        top_files = report.get('candidate_files')
        if top_files is not None:
            require(set(top_files) == set(sources), 'report candidate inventory differs')
            for name, declared in top_files.items():
                require((declared.get('sha256') if isinstance(declared, dict) else declared) == digest(sources[name]),
                        'report candidate SHA differs: ' + name)
        records = report.get('cases', [])
        names = [c['name'] for c in records]
        require(len(names) == len(set(names)) and set(names) <= set(expected),
                'duplicate or unknown reported case')
        status, reward = report.get('status'), report.get('reward')
        require(status in {'completed', 'submission_contract_violation', 'infrastructure_error'},
                'unsupported formal report status')
        require(reward == result.get('score'), 'report/sealed score differs')
        require(result.get('benchmark_status') == status, 'report/sealed status differs')
        if status != 'infrastructure_error':
            require(type(result.get('score')) in (int,float) and result['score'] in (0,1) and
                    result.get('execution') == 'ok' and
                    result.get('verdict') == ('pass' if reward == 1 else 'fail'),
                    'sealed execution/verdict is not a valid binary evaluation')
        if status == 'completed':
            require(type(reward) is int and reward in (0, 1), 'completed report requires binary integer reward')
            require(set(names) == set(expected) and top_files is not None, 'completed report missing cases/source identity')
            require(all(c.get('status') == 'graded' and type(c.get('passed')) is bool for c in records),
                    'completed report contains ungraded case')
            require(reward == int(all(c['passed'] for c in records)), 'completed score/cases differ')
        elif status == 'submission_contract_violation':
            require(type(reward) is int and reward == 0 and result.get('verdict') == 'fail',
                    'submission rejection must be a graded zero')
            require(bool(report.get('reason')), 'submission rejection lacks reason')
        else:
            require(reward is None, 'infrastructure error is not a task score')
        for record in records:
            name = record['name']
            prefix = 'run/work/verifier/' + name + '/'
            identities = record.get('candidate_files', {})
            require(set(identities) == set(sources), 'case candidate inventory differs')
            for filename, identity in identities.items():
                original = archive.read(prefix + 'original/' + filename)
                executed = archive.read(prefix + filename)
                require(original == sources[filename] and digest(original) == identity['original_sha256'],
                        'case original candidate differs: ' + filename)
                require(digest(executed) == identity['executed_sha256'], 'case executed candidate differs: ' + filename)
                verify_translation(original, executed, identity['output_translation'],
                                   contract.get('output_files', []), name)
            require(digest(archive.read(prefix + 'tb.scs')) == record['netlist_sha256'] ==
                    digest(expected[name]['netlist'].encode()), 'executed netlist differs')
            for filename, text in expected[name].get('support', {}).items():
                require(archive.read(prefix + filename) == text.encode(), 'executed support differs')
            graded = record.get('status') == 'graded'
            if graded:
                require(record.get('returncode') == 0 and record.get('waveform_sha256') and
                        type(record.get('waveform_rows')) is int and record['waveform_rows'] >= 2,
                        'graded result lacks complete actual waveform')
            if record.get('waveform_sha256'):
                raw = archive.read(prefix + 'psf/tran.tran.tran')
                require(digest(raw) == record['waveform_sha256'] and raw.rstrip().endswith(b'END'),
                        'report waveform identity/completeness differs')
                with tempfile.TemporaryDirectory(prefix='agentic-audit-psf-') as scratch:
                    path = Path(scratch) / 'waveform.psf'
                    path.write_bytes(raw)
                    rows = PARSER.read_psf(path)
                require(len(rows) == record.get('waveform_rows'), 'reported/actual waveform rows differ')
                case = dict(expected[name])
                if 'signals' not in case:
                    case['signals'] = contract['signals']
                ROW_VALIDATOR.validate_rows(rows, case)
        return {'archive_sha256': receipt['package']['sha256'], 'bytes': receipt['package']['bytes'],
                'job_id': wrapper['job_id'], 'candidate_bundle_sha256': candidate['candidate_sha256'],
                'candidate_files': candidate['files'], 'task_package_sha256': result['task_package_sha256'],
                'criteria_sha256': package['criteria_sha256'],
                'verified_archive_members': len(archive.members), 'seal_and_result_artifacts_verified': True,
                'actual_candidate_and_case_bytes_verified': True,
                'case_execution_identity_verified_count':len(records),
                'graded_waveform_verified_count':sum(c.get('status')=='graded' for c in records),
                'audit_parser_sha256':digest((REPO/'benchmark/checkers/adc_linearity.py').read_bytes()),
                'audit_row_validator_sha256':digest((REPO/'benchmark/checkers/circuit_task.py').read_bytes()), 'report_status': status, 'score': reward,
                'all_cases_present': set(names) == set(expected),
                'complete_pass': status == 'completed' and reward == 1,
                'checker_inventory_verified': list(package['files']),
                'spectre_version': report.get('spectre_version', '').strip(),
                'cases': [{k: v for k, v in c.items() if k not in {'argv', 'log_tail'}} for c in records]}
    finally:
        archive.close()

def summarize(root):
    trials = [x for x in (root / 'jobs' / root.name).iterdir()
              if x.is_dir() and (x / 'result.json').is_file()]
    if len(trials) != 1:
        raise ValueError('expected exactly one completed Trial result')
    trial = trials[0]
    result = read(trial / 'result.json')
    models, response_models, usage, stops, calls, actions = Counter(), Counter(), Counter(), Counter(), [], []
    response_id_messages = 0
    transcripts = sorted((trial / 'agent/pi/sessions').glob('*.jsonl'))
    for transcript in transcripts:
        for line in transcript.read_text().splitlines():
            message = json.loads(line).get('message', {})
            if message.get('role') != 'assistant':
                continue
            models[(message.get('provider'), message.get('model'))] += 1
            if isinstance(message.get('responseModel'), str) and message['responseModel']:
                response_models[message['responseModel']] += 1
            if isinstance(message.get('responseId'), str) and message['responseId']:
                response_id_messages += 1
            stops[message.get('stopReason')] += 1
            for key, value in (message.get('usage') or {}).items():
                if isinstance(value, (int, float)):
                    usage[key] += value
            calls.extend({'id': c.get('id'), 'name': c.get('name'),
                          'argument_keys': sorted((c.get('arguments') or {}).keys())}
                         for c in message.get('content', []) if c.get('type') == 'toolCall')
    for directory in sorted((trial / 'public-session/actions').glob('*')):
        request = directory / 'request.json'
        response = directory / 'response.json'
        if request.exists():
            q = read(request)
            actions.append({'action_id': q.get('action_id'), 'tool': q.get('tool'),
                            'response': read(response) if response.exists() else None,
                            'request_sha256': sha(request.read_bytes())})
    evaluations = [read(p) for p in (trial / 'verifier').glob('**/evaluation.json')]
    frozen_identity = read(root / 'identity.json')
    for evaluation in evaluations:
        require(evaluation['task_package_sha256'] == frozen_identity['final_task_package_sha256'],
                'evaluation/frozen package identity mismatch')
    archives = [audit_archive(receipt_path, evaluations, frozen_identity)
                for receipt_path in (trial / 'verifier').glob('**/archive/receipt.json')]
    verifier = result.get('verifier_result')
    if verifier is not None:
        require(len(evaluations)==1 and len(archives)==1,
                'verifier result lacks exactly one sealed final evaluation')
        require(archives[0]['report_status'] in {'completed','submission_contract_violation'},
                'verifier result is not a completed pass/rejection')
        rewards = verifier.get('rewards', {})
        require(set(rewards)=={'reward'} and type(rewards['reward']) in (int,float) and
                rewards['reward']==archives[0]['score']==evaluations[0]['score'],
                'verifier/evaluation/sealed report reward differs')
    episode = trial / 'public-session/episode-end.json'
    budget = trial / 'agent/output-budget.jsonl'
    return {'attempt': root.name, 'trial_directory': str(trial), 'trial_id': result['id'],
            'requested_agent': result.get('agent_info'), 'exception': result.get('exception_info'),
            'agent_execution': result.get('agent_execution'),
            'reported_agent_result': result.get('agent_result'),
            'verifier_result': result.get('verifier_result'),
            'pi_recorded_models': [{'provider': k[0], 'model': k[1], 'assistant_messages': v}
                                   for k, v in models.items()],
            'pi_response_models': [{'model': model, 'assistant_messages': count}
                                   for model, count in response_models.items()],
            'pi_response_id_message_count': response_id_messages,
            'model_identity_evidence_version': 'pi-response-model-distinction-v2',
            'model_identity_limit': 'Pi assistant.model records the configured request ID. '
                'The observed Pi OpenAI transport writes responseModel only when the response model differs. '
                'Without responseModel, equal and omitted server response IDs cannot be distinguished. '
                'Vendor internal routing is not independently verified.',
            'actual_transcript_token_fields': dict(usage), 'assistant_stop_reasons': dict(stops),
            'cost_limit': 'Harbor cost_usd null is unknown billing; Pi zero cost may lack price metadata.',
            'pi_tool_calls': calls, 'public_tool_actions': actions,
            'transcript_files': [{'path': str(p), 'sha256': sha(p.read_bytes())} for p in transcripts],
            'episode_end': read(episode) if episode.exists() else None,
            'evaluations': evaluations, 'archives': archives,
            'output_budget': [json.loads(x) for x in budget.read_text().splitlines()] if budget.exists() else [],
            'automatic_retry': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if Path(args.name).name != args.name or args.name in {'.', '..'}:
        parser.error('attempt name must be one directory component')
    root = ROOT / args.name
    report = summarize(root)
    target = args.output or root / 'audit.json'
    save(target, report)
    print(target)
    # A graded rejection is a valid completed evaluation; an exception is not.
    if report['exception'] or report['verifier_result'] is None:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
