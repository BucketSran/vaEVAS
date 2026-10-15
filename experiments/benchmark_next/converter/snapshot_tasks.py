"""Retain all current task bytes, including public inputs and instructions."""
from pathlib import Path
import argparse
import hashlib
import json
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    assets = sorted(p for task in (ROOT/'benchmark/material/draftbench/batches/v3-01/tasks').glob('v3-converter-*') for p in task.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    archive = target/'task-source.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for path in assets:
            tar.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    manifest = dict(schema_version=1, scope='complete six converter task source trees', archive=str(archive.relative_to(ROOT)), archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), files={str(p.relative_to(ROOT)):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size) for p in assets})
    (target/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (OUT/'task-snapshot.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(file_count=len(assets), archive=manifest['archive'], archive_sha256=manifest['archive_sha256'])))

if __name__ == '__main__':
    main()
