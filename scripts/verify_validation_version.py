"""Verify a validation snapshot against Git objects and its frozen input hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    revision = manifest['source_commit']
    blobs = {}
    for name, expected in manifest['git_files'].items():
        data = subprocess.run(
            ['git', 'show', f'{revision}:{name}'], cwd=ROOT,
            check=True, capture_output=True,
        ).stdout
        if digest(data) != expected:
            raise ValueError(f'Git artifact hash mismatch: {name}')
        blobs[name] = data
    for name, expected in manifest['snapshot_files'].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError(f'Snapshot artifact hash mismatch: {name}')

    inputs = json.loads((ROOT / manifest['input_manifest']).read_text())
    for name, expected in inputs.items():
        if name in manifest['input_overrides']:
            data = (ROOT / manifest['input_overrides'][name]).read_bytes()
        else:
            data = blobs[name]
        if digest(data) != expected:
            raise ValueError(f'Original run input hash mismatch: {name}')
    print(
        f"{manifest['version']}: verified {len(blobs)} Git artifacts, "
        f"{len(manifest['snapshot_files'])} snapshot artifacts, "
        f"and {len(inputs)} original run inputs at {revision}."
    )
    print('Checks artifact identity only; does not certify simulator correctness or replay experiments.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--manifest', type=Path,
        default=ROOT / 'evas/validation/versions/v1/manifest.json',
    )
    args = parser.parse_args()
    try:
        verify(args.manifest)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Verification failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
