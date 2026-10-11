"""Audit delivery against immutable preparations without executing a simulator."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
CHECKPOINT = '6d58982006c215ff02842ac83deae4e78f22f42b'
UNIT_NOTE = '测量题各电气报告端口的电压数值就是指标数值，例如0.5LSB用0.5V、20dB用20V，valid用0或1V。'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(final):
    snapshot = json.loads((OUT/'task-snapshot.json').read_text())
    archive = ROOT/snapshot['archive']
    assert sha(archive.read_bytes()) == snapshot['archive_sha256']
    with tarfile.open(archive) as tar:
        assert {m.name for m in tar.getmembers()} == set(snapshot['files'])
        for name, identity in snapshot['files'].items():
            data = tar.extractfile(name).read()
            assert sha(data) == identity['sha256'] == sha((ROOT/name).read_bytes()), name
            assert len(data) == identity['bytes']
    tasks = []
    for tid in sorted({r['task'] for r in final}):
        task = ROOT / 'benchmark/tasks' / tid
        current = (task / 'instruction.md').read_bytes()
        checkpoint = subprocess.check_output(['git', 'show', f'{CHECKPOINT}:benchmark/tasks/{tid}/instruction.md'], cwd=ROOT)
        assert current.decode() == checkpoint.decode().replace('输入及固定器件只读。', '输入及固定器件只读。' + UNIT_NOTE)
        groups = {}
        comparisons = []
        for run in [r for r in final if r['task'] == tid]:
            prepared = ROOT / run['prepared']
            record = json.loads((prepared / 'preparation.json').read_text())
            old = record['source_identity']['instruction.md']
            groups.setdefault(old, []).append(dict(variant=run['variant'], prepared=run['prepared'], preparation_sha256=sha((prepared / 'preparation.json').read_bytes())))
            matches = {}
            for name in ['v2_next_converter.py', 'cases.json', 'contract.json', 'verify.py', 'v2_runtime.py', 'adc_linearity.py']:
                actual = sha((task / 'tests' / name).read_bytes())
                assert actual == record['source_identity'][name], (tid, run['variant'], name)
                matches[name] = actual
            comparisons.append(dict(variant=run['variant'], matched_scoring_assets=matches, prepared_test_sh_sha256=record['source_identity']['test.sh'], delivered_test_sh_sha256=sha((task/'tests/test.sh').read_bytes()), entrypoint_difference='The harness froze a python3.12 -B wrapper with candidate/output environment variables. The delivered shell invokes the same verify.py with explicit candidate/output/tests arguments and defaults. The isolated check executes the delivered original shell, without the prepare wrapper.'))
        instruction_versions = []
        for old, runs in groups.items():
            identical = old == sha(current)
            recovered = identical or old == sha(checkpoint)
            assert recovered, (tid, old, 'unrecoverable instruction cannot be final evidence')
            instruction_versions.append(dict(old_sha256=old, new_sha256=sha(current), preparations=runs,
                old_text_recovered=recovered,
                exact_difference=({'text_identical': True} if identical else {'added_sentence': UNIT_NOTE, 'other_text_identical': True}),
                old_text_limit=None if recovered else 'Only the original instruction SHA was retained. The exact early DAC wording cannot be reconstructed from these preparations; do not infer an exact text diff.',
                intermediate_checkpoint_sha256=sha(checkpoint),
                delivered_scoring_assets_unchanged=True,
                reuse_reason=('Current complete task-source snapshot was retained and the reference executed all formal conditions under this exact instruction identity.' if identical else 'Author calibration used no model or instruction interpretation. All six executable scoring assets match the immutable preparation byte for byte. The delivered metric-voltage sentence explains the numerical representation already used by the calibrated reference, independent checker and waveform outputs. Packaging supplies the same runtime and PSF reader bytes; it changes no circuit contract or formal condition. No interpretation or executable behavior changed.')))
        with tempfile.TemporaryDirectory(prefix='converter-delivery-') as temp:
            isolated = Path(temp) / 'tests'
            shutil.copytree(task / 'tests', isolated, ignore=shutil.ignore_patterns('__pycache__'))
            env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            proc = subprocess.run(['/bin/sh', str(isolated / 'test.sh'), '--help'], cwd=temp, env=env, capture_output=True, text=True)
            assert proc.returncode == 0 and '--candidate' in proc.stdout and '--tests' in proc.stdout, proc.stderr
        tasks.append(dict(task=tid, instruction_versions=instruction_versions, scoring_comparisons=comparisons,
            original_entrypoint_check=dict(entrypoint='tests/test.sh --help', isolated_tests_directory=True, repository_pythonpath=False, returncode=proc.returncode, stdout_sha256=sha(proc.stdout.encode()), stderr_sha256=sha(proc.stderr.encode()), test_sh_sha256=sha((task/'tests/test.sh').read_bytes())),
            runtime_bundle_additions={n:sha((task/'tests'/n).read_bytes()) for n in ['v2_runtime.py', 'adc_linearity.py']}))
    body = dict(schema_version=1, analysis_kind='offline delivery reuse audit', analysis_source_sha256=sha(Path(__file__).read_bytes()), checkpoint=CHECKPOINT, task_source_archive_sha256=snapshot['archive_sha256'], snapshot_archive_verified=True, tasks=tasks, preparation_count=sum(len(g['preparations']) for t in tasks for g in t['instruction_versions']), executable_asset_comparisons=sum(len(t['scoring_comparisons'])*6 for t in tasks), no_simulator_execution=True, no_model_experiments=True,
        limits=['test.sh --help proves isolated import and argument entry only; it does not prove a full Harbor container Trial', 'Targeted negative calibration is not a full formal-condition matrix'])
    body['analysis_identity'] = sha(json.dumps(body, sort_keys=True, ensure_ascii=False).encode())
    return body


def write(final):
    result = audit(final)
    target = OUT / 'delivery-reuse.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return dict(path=str(target.relative_to(ROOT)), sha256=sha(target.read_bytes()), analysis_identity=result['analysis_identity'], tasks=result['tasks'], preparation_count=result['preparation_count'], executable_asset_comparisons=result['executable_asset_comparisons'], limits=result['limits'])
