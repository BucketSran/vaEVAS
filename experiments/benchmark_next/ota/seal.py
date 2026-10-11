"""Freeze all task/scoring and author-candidate bytes before calibration."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent

def materials():
    paths=[ROOT/'benchmark/checkers/v2_next_ota.py']
    paths += [p for task in (ROOT/'benchmark/tasks').glob('v3-ota-*') for p in task.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [p for p in (HERE/'candidates').rglob('dut.va')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
if __name__=='__main__':
    (HERE/'material-manifest.json').write_text(json.dumps(materials(),indent=2)+'\n')
