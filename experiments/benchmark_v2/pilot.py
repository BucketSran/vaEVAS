#!/usr/bin/env python3
"""V2 model pilot preparation. No simulator or agent loop lives here.

Every task is supplied explicitly, so the same entry covers the entire P1 set.
Agentic execution delegates to stock Harbor/Pi and circuit_harness. One-shot
passes the identical public bytes once to the selected provider without tools.
The coordinator reserves a Spectre slot before any Harbor run.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    path.chmod(0o600)


def file_hashes(root: Path):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def export_public(task: Path, destination: Path):
    """Export only the task's declared public directory and instruction."""
    public = task / 'environment/public'
    if not public.is_dir():
        public = task / 'environment/input'
    if not public.is_dir():
        raise ValueError('task requires declared environment/public or environment/input')
    for path in public.rglob('*'):
        if path.is_symlink():
            raise ValueError('public materials cannot contain symlinks')
        if path.name in {'solution', 'solutions', 'tests', '.git'}:
            raise ValueError('private-looking path in public materials')
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    shutil.copyfile(task / 'instruction.md', destination / 'instruction.md')
    shutil.copytree(public, destination / 'public')
    save(destination / 'public-identity.json', file_hashes(destination))


def candidate_paths(paths):
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('candidate paths must be nonempty and unique')
    for name in paths:
        path = PurePosixPath(name)
        if not name or path.is_absolute() or '..' in path.parts or str(path) != name or '\\' in name:
            raise ValueError('candidate paths must be canonical relative paths')
    return paths


def one_shot_prompt(materials: Path, paths):
    candidate_paths(paths)
    pieces = [(materials / 'instruction.md').read_text(),
              'Return only a JSON object {"files": {"relative/path": "complete file contents"}}. '
              'Submit exactly these paths: ' + json.dumps(paths) + '. No tools or execution feedback are available.']
    for path in sorted((materials / 'public').rglob('*')):
        if path.is_file():
            data = path.read_bytes()
            try:
                content = data.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                content = base64.b64encode(data).decode('ascii')
                encoding = 'base64'
            pieces.append(json.dumps({'public_path': str(path.relative_to(materials / 'public')),
                                      'encoding': encoding, 'contents': content}, ensure_ascii=False))
    return '\n\n'.join(pieces)


def save_one_shot_candidate(response: str, destination: Path, paths):
    candidate_paths(paths)
    # Preserve malformed responses too. They remain a submission-contract failure.
    with (destination / 'raw-response.txt').open('x', newline='') as stream:
        stream.write(response)
    # Markdown is a response envelope, not part of a submitted VA file. Accept
    # one complete outer JSON fence without selecting among proposed solutions.
    envelope = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', response.strip(), re.DOTALL)
    data = json.loads(envelope[1] if envelope else response)
    if set(data) != {'files'} or not isinstance(data['files'], dict) or set(data['files']) != set(paths):
        raise ValueError('response must submit exactly the declared candidate files')
    if any(not isinstance(content, str) for content in data['files'].values()):
        raise ValueError('candidate file contents must be strings')
    candidate = destination / 'candidate'
    candidate.mkdir(mode=0o700, exist_ok=False)
    for name in paths:
        path = candidate / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data['files'][name].encode('utf-8'))
    save(destination / 'candidate-identity.json', {'selection': 'only-response-no-best-of',
         'extraction_version': 'json-files-v2-optional-outer-fence',
         'raw_response_sha256': hashlib.sha256(response.encode('utf-8')).hexdigest(),
         'files_sha256': file_hashes(candidate), 'candidate_files': paths})


def run_process(argv, destination, *, env, timeout, cwd):
    save(destination / 'started.json', {'argv': list(map(str, argv)), 'started_epoch': time.time(),
                                        'automatic_retry': False})
    with (destination / 'stdout.log').open('xb') as out, (destination / 'stderr.log').open('xb') as err:
        process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=out, stderr=err,
                                   start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    result = {'returncode': process.returncode, 'timed_out': timed_out, 'finished_epoch': time.time()}
    save(destination / 'finished.json', result)
    return result


def prepare(args):
    public = json.loads(args.public_session.read_text())
    final = json.loads(args.final_config.read_text())
    if public.get('public_backend') != 'remote_spectre' or final.get('backend') != 'remote_spectre':
        raise ValueError('v2 pilot requires Spectre for public feedback and final evaluation')
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(mode=0o700, parents=True)
    exported = args.output / 'materials'
    export_public(args.task, exported)
    names = public['task']['candidate_files']
    if set(names).intersection(file_hashes(exported / 'public')):
        renamed = exported / 'public-project'
        (exported / 'public').rename(renamed)
        (exported / 'public').mkdir()
        renamed.rename(exported / 'public/project')
    (exported / 'public-identity.json').unlink()
    save(exported / 'public-identity.json', file_hashes(exported))
    public['task']['public_files'] = sorted(file_hashes(exported / 'public'))
    public['materials'] = str(exported / 'public')
    save(args.output / 'public-session.json', public)
    save(args.output / 'final-evaluation.json', final)
    public_task = args.output / 'task'
    public_task.mkdir()
    instruction = (exported / 'instruction.md').read_text()
    instruction += (
        '\nRuntime: use harness-public info to inspect the public session. Public tool names '
        'retain evas_ prefixes but the actual backend is Spectre. Use evas_read with an empty '
        'path to list public materials and candidate files. Write the complete contents of '
        'every final candidate file using evas_write. Required submission paths: '
        + json.dumps(names) + '. Local /work edits alone do not submit a candidate. '
        'The historical /tests/test.sh path is replaced by harness-public action with '
        'evas_simulate. Each new action needs a unique stable action_id. An uncertain '
        'action may only be queried using exactly its original action_id and arguments; '
        'do not resubmit it under another ID. The fixed netlist is available through '
        'evas_simulate. evas_testbench accepts a JSON string spec with netlist text and '
        'support_files mapping of temporary VA models. Temporary files do not change '
        'the submitted candidate.\n'
        'Example action JSON: {"action_id":"list-1","tool":"evas_read",'
        '"arguments":{"path":""}}. Pipe the object into harness-public action. '
        'For simulation use {"action_id":"simulate-1","tool":"evas_simulate",'
        '"arguments":{}}; submit with evas_submit.\n'
    )
    (public_task / 'instruction.md').write_text(instruction)
    shutil.copytree(exported / 'public', public_task / 'environment/public')
    (public_task / 'tests').mkdir()
    (public_task / 'tests/test.sh').write_text('#!/bin/sh\nexit 0\n')
    (public_task / 'task.toml').write_text(
        f'version="1.0"\n[agent]\ntimeout_sec={args.agent_timeout}\n'
        f'[verifier]\ntimeout_sec={args.verifier_timeout}\n[environment]\n'
        f'cpus=1\nmemory_mb=2048\nnetwork_mode="public"\ndocker_image="{args.agent_image}"\n')
    job = {'job_name': args.output.name, 'jobs_dir': str(args.output / 'jobs'),
           'n_attempts': 1, 'n_concurrent_trials': 1, 'retry': {'max_retries': 0},
           'tasks': [{'path': str(public_task)}],
           'environment': {'import_path': 'circuit_harness.harbor.docker_environment:CircuitDockerEnvironment',
                           'kwargs': {'session_config': str(args.output / 'public-session.json'),
                                      'gateway_bind_host': '0.0.0.0', 'gateway_host': args.gateway_host}},
           'verifier': {'import_path': 'circuit_harness.harbor.verifier:FrozenCandidateVerifier',
                        'override_timeout_sec': args.verifier_timeout,
                        'kwargs': {'config_path': str(args.output / 'final-evaluation.json')}}}
    save(args.output / 'job-template.json', job)
    catalog = json.loads(args.catalog.read_text())
    save(args.output / 'catalog.json', catalog)
    save(args.output / 'protocol.json', {'task_id': public['task']['task_id'],
         'model_configuration': args.model_config, 'protocol': args.protocol,
         'mode': 'agentic-stock-harbor-pi', 'attempts': 1, 'automatic_retry': False,
         'public_files_sha256': file_hashes(exported), 'candidate_selection': 'last-submitted-candidate',
         'agent_instruction_sha256': hashlib.sha256((public_task / 'instruction.md').read_bytes()).hexdigest(),
         'public_backend': 'remote_spectre', 'final_backend': 'remote_spectre'})
    compile_dir = args.output / 'compile'
    compile_dir.mkdir()
    result = run_process([args.python, '-B', '-m', 'circuit_harness.harbor.profiles',
         '--catalog', args.output / 'catalog.json', '--agent', 'pi', '--model', args.model_config,
         '--protocol', args.protocol, '--job', args.output / 'job-template.json',
         '--output', args.output / 'job.json'], compile_dir,
         env=harness_env(args), timeout=90, cwd=args.harness)
    if result['returncode']:
        raise RuntimeError('profile compilation failed; inspect compile/stderr.log')
    return args.output / 'job.json'


def harness_env(args):
    env = dict(os.environ)
    env['PYTHONPATH'] = str(args.harness)
    return env


def one_shot(args):
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    exported = args.output / 'materials'
    export_public(args.task, exported)
    paths = candidate_paths(args.candidate_file)
    prompt = one_shot_prompt(exported, paths)
    (args.output / 'prompt.txt').write_text(prompt)
    # A single standard provider request with no tools and no automatic retry.
    # The key is injected by the caller; never copied into any retained config.
    key = os.environ.get(args.key_env)
    if not key:
        raise ValueError('model key missing from caller environment')
    request_body = {'model': args.model, 'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': args.max_tokens, 'stream': False}
    save(args.output / 'request.json', request_body)
    save(args.output / 'started.json', {'started_epoch': time.time(), 'automatic_retry': False,
         'mode': 'one-shot-no-tools-no-feedback', 'requested_model': args.model,
         'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
         'public_files_sha256': file_hashes(exported)})
    request = urllib.request.Request(args.base_url.rstrip('/') + '/chat/completions',
        data=json.dumps(request_body).encode(), headers={'Authorization': 'Bearer ' + key,
                                                        'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as result:
            raw = result.read()
        (args.output / 'raw-provider-response.json').write_bytes(raw)
        data = json.loads(raw)
        response = data['choices'][0]['message']['content']
        save_one_shot_candidate(response, args.output, paths)
        save(args.output / 'finished.json', {'finished_epoch': time.time(), 'server_response_model': data.get('model'),
             'usage': data.get('usage'), 'finish_reason': data['choices'][0].get('finish_reason'),
             'status': 'candidate-frozen-not-graded'})
    except Exception as exc:
        save(args.output / 'failure.json', {'type': type(exc).__name__, 'finished_epoch': time.time(),
                                           'automatic_retry': False})
        raise



PUBLIC_CHECKER = r'''import hashlib, json, os, re, shutil, subprocess
from pathlib import Path, PurePosixPath
root = Path(__file__).resolve().parent
contract = json.loads((root / 'contract.json').read_text())
output = Path(os.environ['VERIFY_OUTPUT'])
output.mkdir(parents=True, exist_ok=True)
work = output / 'condition'
work.mkdir()
candidate = Path(os.environ['CANDIDATE'])
for name in contract['candidate_files']:
    target = work / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(candidate.parent / name, target)
for name in contract['public_files']:
    source = root / 'public' / name
    target = work / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
netlist = contract['netlist']
temporary = []
payload = candidate.parent / '.public-testbench.json'
if payload.is_file():
    spec = json.loads(payload.read_text())
    netlist = '.harness-public-testbench.scs'
    if (work / netlist).exists():
        raise ValueError('temporary netlist collides with public inputs')
    (work / netlist).write_text(spec['netlist'])
    for name, content in spec['support_files'].items():
        target = work / name
        if target.exists() or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('temporary model path collides with condition inputs')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        temporary.append(name)
# Resolve the task's virtual /work names only against declared inputs. The
# original package and candidate bytes remain untouched; effective decks are
# written only inside this job's private condition directory.
allowed = set(contract['candidate_files']) | set(contract['public_files']) | set(temporary)
aliases = {'/work/' + name: name for name in contract['candidate_files']}
aliases.update({'/work/public/' + name: name for name in contract['public_files']})
include = re.compile(r'(?m)^([ \t]*(?:ahdl_include|include)[ \t]+)(["\'])([^\r\n]*?)\2')
decks = sorted({name for name in contract['public_files'] if name.endswith('.scs')} | {netlist})
identities = {}
while decks:
    name = decks.pop(0)
    if name in identities:
        continue
    path = work / name
    original = path.read_bytes()
    text = original.decode('utf-8')
    def relocate(match):
        source = match[3]
        logical = PurePosixPath(source)
        if not source or '..' in logical.parts or '\\' in source or '\x00' in source:
            raise ValueError('unsafe public include path')
        if logical.is_absolute():
            if source not in aliases:
                raise ValueError('undeclared absolute public include path')
            target = aliases[source]
        else:
            target = str(PurePosixPath(name).parent / logical)
        if target not in allowed or not (work / target).is_file():
            raise ValueError('undeclared public include path')
        if re.match(r'include\b', match[1].lstrip()):
            decks.append(target)
        if not logical.is_absolute():
            return match[0]
        relative = os.path.relpath(work / target, path.parent)
        return match[1] + match[2] + relative + match[2]
    effective = include.sub(relocate, text)
    # Reject unquoted include syntax rather than passing an unchecked path to
    # Spectre. Options after a quoted include remain byte-identical.
    for line in text.splitlines():
        if re.match(r'^\s*(?:ahdl_include|include)\b', line) and not include.match(line):
            raise ValueError('unsupported public include syntax')
    data = effective.encode('utf-8')
    path.write_bytes(data)
    identities[name] = {'original_sha256': hashlib.sha256(original).hexdigest(),
                        'effective_sha256': hashlib.sha256(data).hexdigest()}
(output / 'netlist-identity.json').write_text(json.dumps(
    {'netlist': netlist, 'path_mapping': 'declared-work-aliases-v1', 'decks': identities}) + '\n')
argv = [os.environ['SPECTRE'], '-64', netlist, '+log', 'spectre.log',
        '-format', 'psfascii', '-raw', 'psf', '+lqtimeout', '5', '+mt=1']
result = subprocess.run(argv, cwd=work, capture_output=True, timeout=120)
rows = []
for waveform in (work / 'psf').glob('*.tran.tran'):
    active = False
    row = None
    for line in waveform.read_text().splitlines():
        if line.strip() == 'VALUE': active = True; continue
        if not active: continue
        if line.strip() == 'END':
            if row is not None: rows.append(row)
            break
        match = re.fullmatch(r'"([^\"]+)"\s+(\S+)', line.strip())
        if not match: raise ValueError('Unsupported public PSF value')
        key, value = match[1], float(match[2])
        if key == 'time':
            if row is not None: rows.append(row)
            row = {'time': value}
        elif row is None or key in row: raise ValueError('Invalid public PSF row')
        else: row[key] = value
    break
report = {'status': 'completed', 'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
          'diagnostics': {'spectre_returncode': result.returncode,
                          'stdout': result.stdout.decode(errors='replace')[-16384:],
                          'stderr': result.stderr.decode(errors='replace')[-16384:]},
          'observations': rows}
(output / 'report.json').write_text(json.dumps(report) + '\n')
'''


def public_package(task, destination, paths, netlist):
    """Package a publicly declared netlist. Never load hidden cases or solutions."""
    paths = candidate_paths(paths)
    candidate_paths([netlist])
    public = task / 'environment/public'
    if not public.is_dir():
        public = task / 'environment/input'
    if not (public / netlist).is_file():
        raise ValueError('requested netlist is not a public task asset')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    materials = destination / 'public'
    materials.mkdir()
    for source in sorted(public.rglob('*')):
        if source.is_symlink():
            raise ValueError('public package refuses symlinks')
        if source.is_file() and str(source.relative_to(public)) not in paths:
            target = materials / source.relative_to(public)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    (destination / 'public_feedback.py').write_text(PUBLIC_CHECKER)
    save(destination / 'contract.json', {'candidate_files': paths, 'netlist': netlist,
         'public_files': sorted(file_hashes(materials))})
    (destination / 'test.sh').write_text('#!/bin/sh\nset -eu\nexec python3.12 -B "$(dirname "$0")/public_feedback.py"\n')
    inventory = {name: {'sha256': digest, 'bytes': (destination / name).stat().st_size}
                 for name, digest in file_hashes(destination).items()}
    save(destination / 'manifest.json', {'schema_version': 1, 'task_id': task.name,
         'task_version': 'circuit-benchmark-v2-development',
         'criteria_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
         'condition_id': 'public-fixed-netlist-v1', 'task_set': 'extension', 'purpose': 'public',
         'entrypoint': 'test.sh', 'candidate_file': paths[0], 'report_path': 'verifier/report.json',
         'files': inventory, 'feedback_fields': ['diagnostics', 'observations']})
    return destination

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    q = commands.add_parser('public-package')
    q.add_argument('--task', type=Path, required=True)
    q.add_argument('--output', type=Path, required=True)
    q.add_argument('--candidate-file', action='append', required=True)
    q.add_argument('--netlist', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--task', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--public-session', type=Path, required=True)
    p.add_argument('--final-config', type=Path, required=True)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--model-config', required=True)
    p.add_argument('--protocol', default='openai-chat-completions')
    p.add_argument('--agent-image', required=True)
    p.add_argument('--gateway-host', required=True)
    p.add_argument('--agent-timeout', type=int, default=1800)
    p.add_argument('--verifier-timeout', type=int, default=1800)
    for name in ['preflight', 'run']:
        q = commands.add_parser(name)
        q.add_argument('--output', type=Path, required=True)
        q.add_argument('--timeout', type=int, default=5400 if name == 'run' else 180)
    for q in [p, commands.choices['preflight'], commands.choices['run']]:
        q.add_argument('--harness', type=Path, required=True)
        q.add_argument('--python', type=Path, required=True)
    q = commands.add_parser('one-shot')
    q.add_argument('--task', type=Path, required=True)
    q.add_argument('--output', type=Path, required=True)
    q.add_argument('--candidate-file', action='append', required=True)
    q.add_argument('--model', required=True)
    q.add_argument('--base-url', required=True)
    q.add_argument('--key-env', default='BENCHMARK_MODEL_KEY')
    q.add_argument('--max-tokens', type=int, default=32000)
    q.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    args.output = args.output.absolute()
    if args.command == 'public-package':
        print(public_package(args.task, args.output, args.candidate_file, args.netlist))
    elif args.command == 'prepare':
        print(prepare(args))
    elif args.command == 'one-shot':
        one_shot(args)
        print(args.output / 'candidate')
    else:
        if (args.output / 'withdrawn-before-run.json').exists():
            parser.error('attempt withdrawn before run; use its explicit successor')
        if args.command == 'run' and not os.environ.get('BENCHMARK_MODEL_KEY'):
            parser.error('inject BENCHMARK_MODEL_KEY before run')
        target = args.output / args.command
        target.mkdir(mode=0o700, exist_ok=False)
        if args.command == 'preflight':
            argv = [args.python, '-B', '-m', 'circuit_harness.harbor.deployment',
                    '--job', args.output / 'job.json']
        else:
            argv = [args.python.parent / 'harbor', 'run', '--config', args.output / 'job.json']
        result = run_process(argv, target, env=harness_env(args), timeout=args.timeout, cwd=args.harness)
        # Harbor can exit zero while its Trial failed. Retain those exceptions.
        if args.command == 'run':
            trials = []
            for path in sorted((args.output / 'jobs').glob('*/*/result.json')):
                data = json.loads(path.read_text())
                trials.append({'path': str(path), 'exception_info': data.get('exception_info'),
                               'verifier_result': data.get('verifier_result')})
            save(target / 'trial-summary.json', {'trials': trials, 'candidate_selection': 'last-submitted-candidate'})
            if not trials or any(t['exception_info'] or t['verifier_result'] is None for t in trials):
                sys.exit(2)
        sys.exit(result['returncode'] or (2 if result['timed_out'] else 0))


if __name__ == '__main__':
    main()
