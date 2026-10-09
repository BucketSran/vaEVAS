"""Recheck retained Flash archives without launching a simulator."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

from compact_receipts import native_clock_times, sha

HERE = Path(__file__).resolve().parent
FAMILY = HERE / 'flash_thresholds'
sys.path.insert(0, str(HERE.parents[2] / 'benchmark/checkers'))
from adc_linearity import read_psf
from first_batch_optimization import validate_solver_evidence


def functional_proof(run_root, scratch):
    checker = FAMILY / 'evaluate.py'
    cases_file = FAMILY / 'cases.json'
    spec = importlib.util.spec_from_file_location('current_flash_oracle', checker)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    cases = {c['name']: c for c in json.loads(cases_file.read_text())}
    rows = []
    directories = {
        'baseline': run_root / 'calibration/optimize-flash-thresholds-baseline-v2',
        'reference': run_root / 'flash-event-only-function-v1',
    }
    for role, directory in directories.items():
        source = (FAMILY / (role + '.va')).read_bytes()
        for archive in sorted((directory / 'remote').glob('*/archive/job.tar.gz')):
            with tarfile.open(archive) as tar:
                report_data = tar.extractfile('run/work/verifier/report.json').read()
                report = json.loads(report_data)
                if report['status'] != 'completed' or report['reward'] != 1:
                    raise ValueError('original functional execution did not pass')
                for actual in report['cases']:
                    name = actual['name']
                    prefix = 'run/work/verifier/' + name
                    if any(tar.extractfile(prefix + '/' + path).read() != source
                           for path in ('original/dut.va', 'dut.va')):
                        raise ValueError('current candidate differs from executed source')
                    netlist = tar.extractfile(prefix + '/tb.scs').read()
                    if netlist != cases[name]['netlist'].encode():
                        raise ValueError('current functional netlist differs')
                    native = tar.extractfile(prefix + '/spectre.log').read()
                    merged = tar.extractfile(prefix + '/stdout.log').read()
                    stats = validate_solver_evidence(source, actual['returncode'], native,
                                                     merged, None, stream_layout='merged')
                    waveform = tar.extractfile(prefix + '/psf/tran.tran.tran').read()
                    if sha(waveform) != actual['waveform_sha256']:
                        raise ValueError('original report waveform identity mismatch')
                    local = scratch / 'wave.psf'
                    local.write_bytes(waveform)
                    replay = oracle.evaluate(read_psf(local), cases[name])
                    if replay['passed'] is not True:
                        raise ValueError('current full-raw functional oracle failed')
                    rows.append(dict(task_id='optimize-flash-thresholds', role=role,
                                     case=name, candidate_sha256=sha(source),
                                     archive_sha256=sha(archive.read_bytes()),
                                     report_sha256=sha(report_data), waveform_sha256=sha(waveform),
                                     netlist_sha256=sha(netlist), native_log_sha256=sha(native),
                                     executed_checker_sha256=report['checker_sha256'],
                                     executed_cases_sha256=report['cases_sha256'],
                                     executed_runtime_sha256=report['runtime_sha256'],
                                     executed_contract_sha256=report['contract_sha256'],
                                     replay_checker_sha256=sha(checker.read_bytes()),
                                     replay_cases_sha256=sha(cases_file.read_bytes()),
                                     replay=replay, native_statistics=stats,
                                     local_archive_locator=str(archive.relative_to(run_root))))
    required = {(r, c) for r in directories for c in cases}
    if len(rows) != 6 or {(r['role'], r['case']) for r in rows} != required:
        raise ValueError('exactly three conditions per source required')
    return dict(kind='actual_waveform_replay_not_new_va_execution', new_simulations=False,
                raw_artifact_availability='local-only; archive hashes are not download links', records=rows)


def quiet_proof(run_root):
    directory = run_root / 'flash-event-only-pairs-v2'
    analysis = directory / 'analysis.json'
    data = analysis.read_bytes()
    document = json.loads(data)
    if document['kind'] != 'offline_analysis_of_actual_spectre_jobs':
        raise ValueError('actual execution analysis required')
    rows = []
    for attempt, record in zip(document['attempts'], document['records'], strict=True):
        if record['task_id'] != 'optimize-flash-thresholds':
            raise ValueError('unexpected task')
        source = (FAMILY / (attempt['side'] + '.va')).read_bytes()
        if record['source_sha256'] != sha(source):
            raise ValueError('quiet source differs from new candidate identity')
        archive = Path(record['archive'])
        if sha(archive.read_bytes()) != record['archive_sha256']:
            raise ValueError('quiet archive changed')
        with tarfile.open(archive) as tar:
            prefix = 'run/work/verifier/' + record['condition_id']
            report_data = tar.extractfile('run/work/verifier/report.json').read()
            report = json.loads(report_data)
            actual = next(c for c in report['cases'] if c['name'] == record['condition_id'])
            if sha(report_data) != record['report_sha256'] or actual['passed'] is not True:
                raise ValueError('quiet original functional report differs or failed')
            if any(tar.extractfile(prefix + '/' + p).read() != source
                   for p in ('original/dut.va', 'dut.va')):
                raise ValueError('quiet original/executed source mismatch')
            if sha(tar.extractfile(prefix + '/tb.scs').read()) != record['netlist_sha256']:
                raise ValueError('quiet netlist mismatch')
            native = tar.extractfile(prefix + '/spectre.log').read()
            merged = tar.extractfile(prefix + '/stdout.log').read()
            stats = validate_solver_evidence(source, actual['returncode'], native, merged,
                                             None, stream_layout='merged')
            if stats != record['native_statistics']:
                raise ValueError('reparsed native statistics differ')
            if sha(tar.extractfile(prefix + '/psf/tran.tran.tran').read()) != record['waveform_sha256']:
                raise ValueError('quiet waveform changed')
        start, end = native_clock_times(native.decode())
        rows.append({**{key: record[key] for key in (
            'task_id', 'condition_id', 'job_id', 'archive_sha256', 'candidate_bundle_sha256',
            'source_sha256', 'criteria_sha256', 'netlist_sha256', 'native_host_identity_sha256',
            'report_sha256', 'waveform_sha256', 'solver_process_elapsed_s', 'source_identity',
            'native_statistics', 'functional_result', 'solver_argv')},
            'phase': attempt['phase'], 'pair': attempt['pair'], 'role': attempt['side'],
            'native_start_clock': start, 'native_end_clock': end})
    if len(rows) != 12:
        raise ValueError('warmup plus five pairs required')
    return dict(kind='compact_subset_of_verified_actual_quiet_pairs', new_simulations=False,
                input_analysis_sha256=sha(data), input_manifest_sha256=document['manifest_sha256'],
                source_analysis='runs/benchmark-first-batch-20261008/flash-event-only-pairs-v2/analysis.json',
                prospective_hypothesis_sha256=sha((directory / 'hypothesis.json').read_bytes()),
                host_start_sha256=sha((directory / 'host-start.txt').read_bytes()),
                host_end_sha256=sha((directory / 'host-end.txt').read_bytes()),
                raw_artifact_availability='local-only; hashes are not downloadable URLs',
                native_clock_timezone=None, native_clock_precision_s=1,
                native_clock_window=dict(first_start=min(r['native_start_clock'] for r in rows),
                                         last_end=max(r['native_end_clock'] for r in rows)),
                records=rows, paired_summaries=document['paired_summaries'],
                scope='separate frozen quiet packets, not formal same-job verifier execution')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    for filename, document in (
        ('current_reference_fullraw_proof.json', functional_proof(args.run_root, args.scratch)),
        ('event_only_quiet_receipt.json', quiet_proof(args.run_root)),
    ):
        (FAMILY / 'profile' / filename).write_text(json.dumps(document, indent=2) + '\n')


if __name__ == '__main__':
    main()
