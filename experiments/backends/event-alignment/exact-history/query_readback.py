"""Offline schema mapping and maintained-reader replay; never modify frozen inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from experiments.backends.evidence.archive import verify_archive_members

SHA = '74baa53c271f836833dba20e1efc2ab8971c43c2a3809bae632a52a22d370032'
MAPPING = {'reltol': 'reltol', 'vabstol': 'vabstol_V', 'iabstol': 'iabstol_A',
           'maxstep': 'maxstep_s', 'stop': 'stop_s', 'method': 'method',
           'precision': 'precision'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('collection', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    names = ['E3-fine', 'E5-fine']
    required = [f'spectre-output/runs/{name}/{file}' for name in names for file in
                ['requested_settings.json', 'RESULT.json', 'spectre.log', 'psf/tran.tran.tran']]
    members = verify_archive_members(args.collection, SHA, required)
    args.output.mkdir(parents=True, exist_ok=False)
    paper = ROOT / 'experiments/backends/paper'
    sys.path.insert(0, str(paper))
    spec = importlib.util.spec_from_file_location('query_probe_paper_runner', paper / 'runner.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    result = {'kind': 'offline mapped settings readback; original RESULT/FREEZE unchanged',
              'archive_sha256': SHA, 'regular_members_verified': len(members),
              'mapping': MAPPING, 'mapping_changes_values': False,
              'analyzer_sha256': sha(Path(__file__)),
              'maintained_runner_sha256': sha(paper / 'runner.py'),
              'maintained_reader_sha256': sha(paper / 'settings_readback.py'),
              'new_simulator_calls': 0, 'new_evas_calls': 0, 'cases': {}}
    for name in names:
        original = args.collection / 'spectre-output/runs' / name
        request = json.loads((original / 'requested_settings.json').read_text())
        assert set(request) == set(MAPPING), 'unexpected requested-settings schema'
        mapped = {MAPPING[key]: value for key, value in request.items()}
        work = args.output / name
        (work / 'psf').mkdir(parents=True)
        for file in ['spectre.log', 'psf/tran.tran.tran']:
            shutil.copyfile(original / file, work / file)
        (work / 'requested_settings.json').write_text(json.dumps(mapped, indent=2) + '\n')
        readback = runner.effective_settings(work, 'spectre')
        assert readback['status'] == 'readback_matches' and not readback['mismatches']
        assert readback['actual']['method'] == mapped['method']
        result['cases'][name] = {
            'original_requested': request, 'mapped_requested': mapped,
            'original_result_effective_settings': json.loads((original / 'RESULT.json').read_text())['effective_settings'],
            'fresh_readback': readback, 'method_matches': True,
            'precision_runtime_readback': 'I: this reader does not establish print precision',
            'original_files': {file: sha(original / file) for file in
                               ['requested_settings.json', 'RESULT.json', 'spectre.log', 'psf/tran.tran.tran']}}
    (args.output / 'analysis.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
