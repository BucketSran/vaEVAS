#!/usr/bin/env python3
"""Task-owned preparation and local probes using the existing harness only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import signal
import time
from public_protocol import append_note

# Deployment paths are explicit environment inputs; no credentials are read from disk.
ROOT = Path(os.environ.get('AGENTIC_OUTPUT', 'runs/agentic')).resolve()
REPO = Path(__file__).resolve().parents[3]
HARNESS = Path(os.environ.get('CIRCUIT_HARNESS', '')).resolve()
# Keep the venv launcher path: resolving its symlink loses its site-packages.
PYTHON = Path(os.path.abspath(os.environ.get('HARBOR_PYTHON', sys.executable)))
PUBLIC_CHECKOUT = Path(os.environ.get('EVAS_PUBLIC_CHECKOUT', '')).resolve()
CODEX = Path(os.environ.get('EVAS_PUBLIC_CODEX', '')).resolve()

os.umask(0o077)
sys.path.insert(0, str(HARNESS))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    path.chmod(0o600)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(argv, output, *, env=None, timeout=90, cwd=HARNESS):
    if any(output.with_suffix(suffix).exists() for suffix in ['.json','.stdout','.stderr','.started.json']):
        raise ValueError('operation evidence already exists; refuse implicit retry')
    save(output.with_suffix('.started.json'), {'argv':[str(x) for x in argv],'started_epoch':time.time(),
                                              'automatic_retry':False})
    process = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=env, start_new_session=True,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    timed_out = False
    try:
        stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid,signal.SIGTERM)
        try:
            stdout,stderr=process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            stdout,stderr=process.communicate()
    result = subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.stdout').write_bytes(result.stdout)
    output.with_suffix('.stderr').write_bytes(result.stderr)
    save(output.with_suffix('.json'), {'argv': [str(x) for x in argv], 'returncode': result.returncode,'timed_out':timed_out,
                                     'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                                     'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()})
    return result

def runtime_env(credentials=False):
    env = dict(os.environ)
    env['PYTHONPATH'] = str(HARNESS)
    if credentials and not env.get('BENCHMARK_MODEL_KEY'):
        raise RuntimeError('set BENCHMARK_MODEL_KEY in the caller environment')
    return env

def prepare(args):
    if args.max_output_tokens is not None and args.max_output_tokens <= 0:
        raise ValueError('output token limit must be positive')
    if not args.name or Path(args.name).name != args.name or args.name in {'.','..'}:
        raise ValueError('attempt name must be one directory component')
    destination = ROOT / args.name
    destination.mkdir(mode=0o700, exist_ok=False)
    declaration = json.loads(Path(args.declaration).read_text())
    package = Path(args.final_package).resolve()
    from alphaapollo.common.execution.chips.benchmark_spectre import package_identity
    identity = package_identity(package, purpose='final')
    if any(identity['manifest'][key] != declaration[key] for key in ['task_id', 'task_version']):
        raise ValueError('public/final identity mismatch')
    session = {'schema_version': 1, 'task': declaration, 'materials': str(Path(args.materials).resolve()),
               'checkout': str(PUBLIC_CHECKOUT), 'kernel': str(Path(args.kernel).resolve()),
               'public_backend': args.backend, 'image': args.public_image if args.backend == 'docker' else None,
               'max_actions': args.max_actions, 'max_simulations': args.max_simulations,
               'simulation_timeout_s': args.simulation_timeout, 'max_output_bytes': 16777216}
    if args.backend == 'native_codex_sandbox':
        if 'experiments' in declaration:
            raise ValueError('Python experiments require matched Linux kernel and Docker public backend')
        session.update(public_codex=str(CODEX), public_python=str(PYTHON.resolve()))
    save(destination/'public-session.json', session)
    operator = json.loads(Path(args.remote_config).read_text())
    remote = operator['remote']
    if args.optimization_final or declaration['task_id'].startswith(('optimize-', 'opt-')):
        if args.verifier_timeout < 1200 or operator.get('job_wait_timeout_s', 0) < 1200:
            raise ValueError('optimization requires performance operator config with job_wait_timeout_s>=1200 and verifier timeout>=1200')
    save(destination/'operator-selection.json', {'config_sha256':digest(Path(args.remote_config)),
         'job_wait_timeout_s':operator.get('job_wait_timeout_s'),
         'harbor_verifier_timeout_s':args.verifier_timeout,
         'wait_behavior':'FrozenCandidateVerifier polls under Harbor phase deadline; operator calibration wait is not an extra FinalEvaluationConfig field'})
    save(destination/'final-evaluation.json', {'backend':'remote_spectre', 'task_package':str(package), 'remote':remote})
    task = destination/'task'
    task.mkdir()
    instruction = (Path(args.materials)/'instruction.md').read_text()
    instruction = append_note(instruction)
    (task/'instruction.md').write_text(instruction)
    (task/'environment').mkdir()
    shutil.copytree(Path(args.materials), task/'environment/public')
    (task/'environment/README.md').write_text('Existing local immutable Agent image. No private task materials.\n')
    (task/'tests').mkdir()
    (task/'tests/test.sh').write_text('#!/bin/sh\nexit 0\n')
    (task/'task.toml').write_text(f'version = "1.0"\n[agent]\ntimeout_sec = {args.agent_timeout}\n[verifier]\ntimeout_sec = {args.verifier_timeout}\n[environment]\nbuild_timeout_sec = 120\ncpus = 1\nmemory_mb = 1024\nnetwork_mode = "public"\ndocker_image = "{args.agent_image}"\n')
    job = {'job_name':args.name,'jobs_dir':str(destination/'jobs'),'n_attempts':1,'n_concurrent_trials':1,
           'retry':{'max_retries':0},'tasks':[{'path':str(task)}],
           'environment':{'import_path':'alphaapollo.workflows.harbor_chips.docker_environment:CircuitDockerEnvironment',
                          'kwargs':{'session_config':str(destination/'public-session.json'),
                                    'gateway_bind_host':'0.0.0.0','gateway_host':args.gateway_host}},
           'verifier':{'import_path':'alphaapollo.workflows.harbor_chips.verifier:FrozenCandidateVerifier',
                       'override_timeout_sec':args.verifier_timeout,'kwargs':{'config_path':str(destination/'final-evaluation.json')}}}
    save(destination/'job-template.json', job)
    connection = {'protocol': 'openai-chat-completions', 'model': args.model,
                  'base_url': args.base_url, 'key_env': 'BENCHMARK_MODEL_KEY'}
    catalog = {'schema_version': 1,
               'agents': {'pi': {'name': 'pi', 'override_timeout_sec': args.agent_timeout,
                          'override_setup_timeout_sec': 600,
                          'kwargs': {'version': args.pi_version, 'thinking': args.thinking}}},
               'models': {'endpoint': {'connections': [connection]}}}
    save(destination/'catalog.json', catalog)
    result = run([PYTHON,'-B','-m','alphaapollo.workflows.harbor_chips.profiles','--catalog',destination/'catalog.json',
                  '--agent','pi','--model','endpoint','--protocol','openai-chat-completions','--job',destination/'job-template.json',
                  '--output',destination/'job.json'], destination/'compile', env=runtime_env())
    if result.returncode:
        raise RuntimeError('profile compilation failed; inspect private compile stderr')
    if args.max_output_tokens is not None:
        compiled = json.loads((destination/'job.json').read_text())
        compiled['agents'][0].setdefault('env', {})['AGENTIC_MAX_OUTPUT_TOKENS'] = str(args.max_output_tokens)
        (destination/'job.json').write_text(json.dumps(compiled, indent=2)+'\n')
        save(destination/'output-budget.json', {'max_output_tokens':args.max_output_tokens,
             'mechanism':'stock Pi before_provider_request extension; requires budget-enabled image',
             'changes_prompts_tools_or_agent_loop':False})
    for name in ['public-session.json','final-evaluation.json','catalog.json','job-template.json','job.json']:
        (destination/name).chmod(0o600)
    save(destination/'identity.json',{'task_id':declaration['task_id'],'task_version':declaration['task_version'],
         'harness_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=HARNESS,text=True).strip(),
         'benchmark_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
         'kernel_sha256':digest(Path(args.kernel)),'python':str(PYTHON),'agent_image':args.agent_image,
         'public_backend':args.backend,'public_image':session['image'],'model_requested':args.model,
         'final_task_package_sha256':identity['sha256'], 'execution_started_at_preparation':False,'source_files_sha256':{str(x.relative_to(package)):digest(x) for x in package.rglob('*') if x.is_file()}})
    print(destination/'job.json')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare')
    p.add_argument('--name',required=True)
    p.add_argument('--declaration',required=True,help='public task declaration JSON')
    p.add_argument('--materials',required=True)
    p.add_argument('--final-package',required=True)
    p.add_argument('--remote-config',required=True)
    p.add_argument('--backend',choices=['docker','native_codex_sandbox'],default='native_codex_sandbox')
    p.add_argument('--kernel',required=True)
    p.add_argument('--public-image')
    p.add_argument('--agent-image',required=True)
    p.add_argument('--gateway-host',required=True)
    p.add_argument('--model',required=True)
    p.add_argument('--base-url',required=True)
    p.add_argument('--max-output-tokens',type=int)
    p.add_argument('--pi-version',default='0.87.0')
    p.add_argument('--thinking',default='medium',choices=['off','minimal','low','medium','high','xhigh'])
    p.add_argument('--agent-timeout',type=int,default=1200)
    p.add_argument('--verifier-timeout',type=int,default=600)
    p.add_argument('--optimization-final',action='store_true',help='require the performance operator wait and verifier bounds')
    p.add_argument('--max-actions',type=int,default=80)
    p.add_argument('--max-simulations',type=int,default=16)
    p.add_argument('--simulation-timeout',type=int,default=120)
    for name in ['preflight','run']:
        q=commands.add_parser(name);q.add_argument('--name',required=True)
        if name=='run':q.add_argument('--run-timeout',type=int,default=3600)
        if name=='preflight':q.add_argument('--check-environment',action='store_true')
    args=parser.parse_args()
    for key in ['CIRCUIT_HARNESS','HARBOR_PYTHON','EVAS_PUBLIC_CHECKOUT','EVAS_PUBLIC_CODEX']:
        if not os.environ.get(key):
            parser.error(f'set {key} explicitly')
    if args.command=='prepare':prepare(args);return
    if Path(args.name).name != args.name or args.name in {'.','..'}:
        parser.error('attempt name must be one directory component')
    destination=ROOT/args.name
    if (destination/'withdrawn-before-run.json').exists():
        parser.error('prepared attempt withdrawn; preserve evidence and prepare an explicit new attempt')
    if args.command=='preflight':
        argv=[PYTHON,'-B','-m','alphaapollo.workflows.harbor_chips.deployment','--job',destination/'job.json']
        if args.check_environment:argv += ['--check-environment','--timeout-s','60','--cleanup-timeout-s','30']
        result=run(argv,destination/('preflight-environment' if args.check_environment else 'preflight-static'),env=runtime_env(),timeout=150)
    else:
        # This is the only path that starts a model and the independent final verifier.
        result=run([PYTHON.parent/'harbor','run','--config',destination/'job.json'],destination/'harbor-run',
                   env=runtime_env(credentials=True),timeout=args.run_timeout)
    print('harbor_returncode' if args.command=='run' else 'returncode',result.returncode)
    if args.command=='run' and result.returncode==0:
        from audit import summarize
        report=summarize(destination)
        save(destination/'automatic-audit.json',report)
        if report['exception'] or report['verifier_result'] is None:
            print('Trial incomplete or failed; see automatic-audit.json')
            sys.exit(2)
    sys.exit(result.returncode)

if __name__=='__main__':main()
