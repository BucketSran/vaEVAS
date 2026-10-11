"""Execute original reference scripts in their pinned image, without networking."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(task, work):
    image = (task / 'environment/Dockerfile').read_text().splitlines()[0].removeprefix('FROM ')
    if '@sha256:' not in image:
        raise ValueError('reference image must be pinned')
    work.mkdir(parents=True, exist_ok=True)
    command = ['docker', 'create', '--network', 'none', '-v', str(task / 'solution') + ':/solution:ro', '-v', str(work) + ':/work', '--entrypoint', 'sh', image, '/solution/solve.sh']
    started = datetime.now(timezone.utc).isoformat()
    container = subprocess.check_output(command, text=True).strip()
    try:
        actual = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
        if actual['HostConfig']['NetworkMode'] != 'none':
            raise ValueError('reference container networking must be disabled')
        details = json.loads(subprocess.check_output(['docker', 'image', 'inspect', actual['Image']], text=True))[0]
        result = subprocess.run(['docker', 'start', '-a', container], capture_output=True, text=True)
        state = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]['State']
        if result.returncode or state['ExitCode']:
            raise RuntimeError(result.stderr or result.stdout)
        receipt = dict(task=task.name, requested_image=image, actual_image_id=actual['Image'], repo_digests=details['RepoDigests'], architecture=details['Architecture'], container_id=container, network_mode=actual['HostConfig']['NetworkMode'], command=command, start_command=['docker', 'start', '-a', container], started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(), container_started_at=state['StartedAt'], container_finished_at=state['FinishedAt'], exit_code=state['ExitCode'], script_sha256=sha(task / 'solution/solve.sh'), solution_sha256=sha(task / 'solution/dut.va'), output_sha256=sha(work / 'dut.va'), stdout=result.stdout, stderr=result.stderr)
        (work / 'entry-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    finally:
        subprocess.run(['docker', 'rm', container], check=True, capture_output=True)


if __name__ == '__main__':
    report = dict(schema_version=1, purpose='Supplemental reference-entry execution; does not reconstruct earlier image identity', earlier_entry_image_identity='unknown: historical tag-based invocation retained no Docker image receipt', command_path_notation='${CHECKOUT} denotes repository root; raw absolute command receipts remain in ignored runs', entry_tool_sha256=sha(Path(__file__)), final_calibration_sha256=sha(HERE / 'final-calibration.json'), delivery_material_manifest_sha256=sha(HERE / 'material-manifest.json'), records=[])
    calibration = json.loads((HERE / 'final-calibration.json').read_text())
    for task in sorted((ROOT / 'benchmark/tasks').glob('v3-ota-*')):
        receipt = run(task, ROOT / 'runs/ota-reference-entry-pinned' / task.name)
        expected = sha(HERE / 'candidates' / task.name / 'reference/dut.va')
        assert receipt['output_sha256'] == expected
        bindings = [r for r in calibration['records'] if r['task'] == task.name and r['variant'] == 'reference']
        assert len(bindings) == 3
        assert all(c['candidate_files']['dut.va'] == expected for r in bindings for c in r['cases'])
        receipt['spectre_reference_jobs'] = [r['job_id'] for r in bindings]
        receipt['matches_final_spectre_candidate'] = True
        receipt['command'] = [s.replace(str(ROOT), '${CHECKOUT}') for s in receipt['command']]
        report['records'].append(receipt)
    (HERE / 'reference-entry-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
