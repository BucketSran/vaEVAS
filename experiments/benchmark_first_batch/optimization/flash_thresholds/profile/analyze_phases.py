"""Read native phase timings from already verified actual flash archives; never run a solver."""
import argparse
import hashlib
import json
import re
import statistics
import tarfile
from pathlib import Path


def seconds(value, unit):
    return float(value) * {'s': 1, 'ms': 1e-3, 'us': 1e-6, 'ns': 1e-9}[unit]


def analyze(path):
    evidence = json.loads(Path(path).read_text())
    if evidence['kind'] != 'offline_analysis_of_actual_spectre_jobs':
        raise ValueError('requires actual archived solver evidence')
    rows = []
    for attempt, record in zip(evidence['attempts'], evidence['records'], strict=True):
        if record['task_id'] != 'optimize-flash-thresholds' or record['condition_id'] != 'bank-throughput':
            raise ValueError('unexpected workload')
        archive = Path(record['archive'])
        if hashlib.sha256(archive.read_bytes()).hexdigest() != record['archive_sha256']:
            raise ValueError('archive identity changed')
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if m.name.endswith('/bank-throughput/spectre.log')]
            if len(members) != 1 or not members[0].isfile():
                raise ValueError('ambiguous native log')
            data = tar.extractfile(members[0]).read()
        if hashlib.sha256(data).hexdigest() != record['native_statistics']['native_log_sha256']:
            raise ValueError('native log identity changed')
        log = data.decode()
        phases = {}
        for label in ['NDB Parsing', 'Elaboration', 'EDB Visiting', 'parsing']:
            matches = re.findall(r'Time for '+label+r': CPU = ([\d.e+-]+) (s|ms|us|ns), elapsed = ([\d.e+-]+) (s|ms|us|ns)\.', log)
            if len(matches) != 1:
                raise ValueError('missing/duplicate '+label)
            c, cu, w, wu = matches[0]
            phases[label] = {'cpu_s': seconds(c, cu), 'elapsed_s': seconds(w, wu)}
        compile_match = re.findall(r'Finished compilation in ([\d.e+-]+) (s|ms|us|ns) \(elapsed\) for offset_flash\.', log)
        if len(compile_match) != 1:
            raise ValueError('not exactly one cold compilation')
        accumulated = re.findall(r'Time accumulated: CPU = ([\d.e+-]+) (s|ms|us|ns), elapsed = ([\d.e+-]+) (s|ms|us|ns)\.', log)
        c, cu, w, wu = accumulated[-1]
        native = record['native_statistics']
        rows.append({
            'phase': attempt['phase'], 'pair': attempt['pair'], 'side': attempt['side'],
            'archive_sha256': record['archive_sha256'], 'native_log_sha256': native['native_log_sha256'],
            'functional_passed': record['functional_result']['passed'],
            'accepted_steps': native['accepted_steps'], 'native_errors': native['native_errors'],
            'cold_compile_elapsed_s': seconds(*compile_match[0]), 'phases': phases,
            'intrinsic_cpu_s': native['intrinsic_tran']['cpu_s'],
            'intrinsic_elapsed_s': native['intrinsic_tran']['elapsed_s'],
            'tran_elapsed_s': native['total_tran']['elapsed_s'],
            'last_accumulated_cpu_s': seconds(c, cu), 'last_accumulated_elapsed_s': seconds(w, wu),
            'solver_process_elapsed_s': record['solver_process_elapsed_s'],
            'process_minus_tran_elapsed_s': record['solver_process_elapsed_s'] - native['total_tran']['elapsed_s'],
            'process_minus_last_accumulated_elapsed_s': record['solver_process_elapsed_s'] - seconds(w, wu),
        })
    summary = {}
    for metric in ['cold_compile_elapsed_s', 'intrinsic_cpu_s', 'intrinsic_elapsed_s', 'tran_elapsed_s', 'last_accumulated_cpu_s', 'last_accumulated_elapsed_s', 'solver_process_elapsed_s', 'process_minus_tran_elapsed_s', 'process_minus_last_accumulated_elapsed_s']:
        summary[metric] = {}
        for side in ['baseline', 'reference']:
            values = [r[metric] for r in rows if r['side'] == side and r['phase'] != 'warmup']
            if len(values) != 5:
                raise ValueError('requires five measured pairs')
            summary[metric][side] = {'median': statistics.median(values), 'min': min(values), 'max': max(values), 'values': values}
    return {'kind': 'native_phase_analysis_of_actual_archives', 'new_simulations': False,
            'input_evidence_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'stream_layout': 'merged', 'aggregate_audit_elapsed_used': False,
            'compile_cache': 'all twelve logs explicitly compile; warmup is another cold job, not a cache warmup',
            'rows': rows, 'measured_summary': summary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence')
    parser.add_argument('output')
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(analyze(args.evidence), indent=2) + '\n')
