"""Read solver settings again from sealed executions without changing verdicts.

This audit never launches a simulator. A successful readback only supplies the
settings axis; it does not grant waveform, input or numerical qualification.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from settings_readback import ReadbackError, ngspice, spectre


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_lane(lane):
    manifest = json.loads((lane / 'FILE_MANIFEST.json').read_text())
    actual = {str(p.relative_to(lane)) for p in lane.rglob('*')
              if p.is_file() and p != lane / 'FILE_MANIFEST.json'}
    if actual != set(manifest):
        raise ValueError('execution inventory changed: ' + str(lane))
    for name, identity in manifest.items():
        path = lane / name
        if path.is_symlink() or not path.resolve().is_relative_to(lane.resolve()):
            raise ValueError('unsafe execution path: ' + name)
        if path.stat().st_size != identity['bytes'] or sha(path) != identity['sha256']:
            raise ValueError('execution identity changed: ' + name)
    return manifest


def audit(lanes):
    records = []
    sources = []
    for lane in lanes:
        manifest = verify_lane(lane)
        sources.append({'path': str(lane.resolve()), 'manifest_sha256': sha(lane / 'FILE_MANIFEST.json'),
                        'verified_files': len(manifest), 'availability': 'local-only'})
        for original in json.loads((lane / 'EXECUTION.json').read_text()):
            if original['backend'] not in ('openvaf_r_ngspice', 'spectre'):
                raise ValueError('unsupported backend for settings audit')
            work = lane / 'runs' / original['label']
            if not work.resolve().is_relative_to((lane / 'runs').resolve()):
                raise ValueError('unsafe execution label')
            result = {'backend': original['backend'], 'label': original['label'],
                      'original_execution': original['status'],
                      'original_result_sha256': sha(work / 'RESULT.json'),
                      'original_settings': original.get('effective_settings'),
                      'qualification': 'unchanged; this audit only reads settings'}
            if original['status'] != 'waveform_available':
                result['readback_status'] = 'not_applicable'
            else:
                try:
                    if original['backend'] == 'openvaf_r_ngspice':
                        result['readback'] = ngspice((work / 'simulate.log').read_text(),
                                                    (work / 'tb.cir').read_text())
                    else:
                        result['readback'] = spectre((work / 'spectre.log').read_text(),
                                                    (work / 'psf/tran.tran.tran').read_text())
                    result['readback_status'] = 'read'
                except ReadbackError as exc:
                    result.update(readback_status='unknown', reason=str(exc))
            records.append(result)
    return {'schema': 'settings-supplement-v1', 'analysis': 'new analysis of original executions',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'sources': sources,
            'analyzer_sha256': sha(Path(__file__)),
            'reader_sha256': sha(ROOT / 'experiments/backends/paper/settings_readback.py'),
            'records': records,
            'counts': dict(Counter(r['readback_status'] for r in records)),
            'limits': 'No numerical rescoring, exact-input proof, callback proof or new backend run.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.lane)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result['counts']))
