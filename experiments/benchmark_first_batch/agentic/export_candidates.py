"""Export reviewed frozen candidate bytes, never model traces or configuration.

A completed Trial is audited first. Candidate and package verification reuse the
configured harness; publishing performs no model or backend request. The caller
injects the known model token for a pre/post publication scan.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from audit import summarize, require

PATTERNS = {
    'bearer_token': rb'(?i)bearer\s+[A-Za-z0-9_.-]{16,}',
    'secret_key_format': rb'sk-[A-Za-z0-9_-]{16,}',
    'credential_assignment': rb'''(?i)(?:api[_-]?key|auth[_-]?token|password|secret)\s*[=:]\s*["']?[A-Za-z0-9_.-]{16,}''',
    'jwt': rb'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b',
}


def credential_scan(data, known_token):
    require(bool(known_token), 'inject known model token for publication scan')
    return {'known_token_hits': data.count(known_token),
            'generic_pattern_hits': {name: len(re.findall(pattern, data))
                                     for name, pattern in PATTERNS.items()
                                     if re.search(pattern, data)}}


def clean(scan):
    return scan['known_token_hits'] == 0 and not scan['generic_pattern_hits']


def harness_verifiers():
    sys.path.insert(0, os.environ['CIRCUIT_HARNESS'])
    from alphaapollo.common.execution.chips.candidate_bundle import verify_candidate
    from alphaapollo.common.execution.chips.benchmark_spectre import package_identity
    return verify_candidate, package_identity


def export(folder, destination_root, known_token):
    audited = summarize(folder)
    identity = json.loads((folder / 'identity.json').read_text())
    require(all(Path(identity[key]).name == identity[key] and identity[key] not in {'.', '..'}
                for key in ('task_id', 'model_requested')), 'nonportable publication identity')
    models = {row['model'] for row in audited['pi_recorded_models']}
    archives = audited['archives']
    candidates = list(folder.glob('jobs/*/*/public-session/candidate/manifest.json'))
    if not models:
        require(not archives and not candidates and
                not (audited['episode_end'] or {}).get('candidate_sha256'),
                'unobserved model has candidate/final evidence')
    else:
        require(models == {identity['model_requested']}, 'Pi configured model identity is not unique/matching')
    response_models = {row['model'] for row in audited.get('pi_response_models', [])}
    require(len(response_models) <= 1, 'conflicting server response model identities')
    destination = destination_root / identity['task_id'] / identity['model_requested']
    require(not destination.exists(), 'refuse overwriting published candidate')
    verify_candidate, package_identity = harness_verifiers()
    final = json.loads((folder / 'final-evaluation.json').read_text())
    package = package_identity(Path(final['task_package']), purpose='final')
    require(package['sha256'] == identity['final_task_package_sha256'], 'prepared final package changed')
    require(package['manifest']['task_id'] == identity['task_id'], 'final package task differs')
    require(len(archives) <= 1, 'multiple final evaluations')
    result = {'schema_version': 2, 'attempt': folder.name, 'task_id': identity['task_id'],
              'requested_model': identity['model_requested'],
              'pi_recorded_model': next(iter(models)) if models else None,
              'server_response_model': next(iter(response_models)) if response_models else None,
              'identity_evidence': {
                  'version': 'pi-response-model-distinction-v2',
                  'pi_model_assignment': 'configured model.id, not independently observed server model',
                  'response_model_assignment': 'response chunk.model retained only when different from configured ID',
                  'missing_response_model': 'equal and omitted server response model IDs cannot be distinguished',
                  'observed_response_model_messages': sum(row['assistant_messages'] for row in audited.get('pi_response_models', [])),
                  'response_id_message_count': audited.get('pi_response_id_message_count', 0),
                  'vendor_internal_routing': 'unknown'},
              'final_package_sha256': package['sha256'],
              'criteria_sha256': package['manifest']['criteria_sha256'],
              'original_final_job_id': archives[0]['job_id'] if archives else None,
              'final_archive_sha256': archives[0]['archive_sha256'] if archives else None,
              'candidate_final_score': archives[0]['score'] if archives else None,
              'phase_exception_type': (audited.get('exception') or {}).get('exception_type'),
              'copy_policy': 'original frozen bytes without edits',
              'new_model_or_solver_requests': 0}
    require(len(candidates) <= 1, 'multiple frozen candidates')
    files = {}
    if candidates:
        bundle = verify_candidate(candidates[0].parent)
        episode = audited['episode_end'] or {}
        require(bundle['candidate_sha256'] == episode.get('candidate_sha256'),
                'candidate differs from episode freeze')
        require(bundle['task_id'] == identity['task_id'] and
                bundle['task_version'] == identity['task_version'], 'candidate task identity differs')
        if archives:
            require(bundle['candidate_sha256'] == archives[0]['candidate_bundle_sha256'] and
                    bundle['files'] == archives[0]['candidate_files'], 'export/final candidate differs')
        result.update(candidate_bundle_sha256=bundle['candidate_sha256'],
                      candidate_files=bundle['files'], freeze_reason=bundle['reason'])
        files = {name: (candidates[0].parent / 'files' / name).read_bytes()
                 for name in bundle['files']}
        for name, data in files.items():
            require(hashlib.sha256(data).hexdigest() == bundle['files'][name]['sha256'] and
                    len(data) == bundle['files'][name]['bytes'], 'source changed after bundle verification')
        require('manifest.json' not in files, 'candidate overlaps export manifest')
        scans = {name: credential_scan(data, known_token) for name, data in files.items()}
        result['pre_export_credential_scan'] = scans
        if not all(clean(scan) for scan in scans.values()):
            result['availability'] = 'not_exported_credential_scan'
            files = {}
        else:
            result['availability'] = 'repository-contained'
    else:
        require(not archives and not (audited['episode_end'] or {}).get('candidate_sha256'),
                'frozen candidate evidence missing; cannot label no candidate')
        result.update(availability='none_no_frozen_candidate', candidate_bundle_sha256=None,
                      candidate_files={})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.candidate-export-', dir=destination.parent) as temporary:
        staging = Path(temporary)
        for name, data in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            require(path.read_bytes() == data, 'exported candidate bytes changed')
        result['post_export_credential_scan'] = {name: credential_scan((staging / name).read_bytes(), known_token)
                                                 for name in files}
        require(all(clean(scan) for scan in result['post_export_credential_scan'].values()),
                'post-export credential scan failed')
        serialized = json.dumps(result, indent=2).encode() + b'\n'
        require(clean(credential_scan(serialized, known_token)), 'export manifest credential scan failed')
        (staging / 'manifest.json').write_bytes(serialized)
        require(not destination.exists(), 'publication appeared during export')
        staging.rename(destination)
    for name, info in result['candidate_files'].items():
        if result['availability'] == 'repository-contained':
            data = (destination / name).read_bytes()
            require(hashlib.sha256(data).hexdigest() == info['sha256'] and len(data) == info['bytes'],
                    'published candidate identity differs')
            require(clean(credential_scan(data, known_token)), 'published candidate credential scan failed')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt')
    parser.add_argument('--destination', type=Path, default=Path(__file__).parent / 'candidates')
    args = parser.parse_args()
    require(Path(args.attempt).name == args.attempt, 'attempt must be one directory component')
    token = os.environ['BENCHMARK_MODEL_KEY'].encode()
    result = export(Path(os.environ['AGENTIC_OUTPUT']) / args.attempt, args.destination, token)
    print(result['task_id'], result['requested_model'], result['availability'])


if __name__ == '__main__':
    main()
