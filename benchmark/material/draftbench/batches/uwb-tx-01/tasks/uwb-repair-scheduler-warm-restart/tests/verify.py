#!/usr/bin/env python3
"""Final evaluation: public cases plus the final cases on the frozen module directory."""
import argparse
from pathlib import Path
import sys

TASK = Path(__file__).resolve().parents[1]
PUBLIC = TASK / 'environment/starter/testbench'
if not PUBLIC.is_dir():
    PUBLIC = Path('/app/testbench')       # fresh baseline in the separate verifier
sys.path[:0] = [str(PUBLIC), str(Path(__file__).resolve().parent)]
import check  # noqa: E402
import contract  # noqa: E402
from final_cases import final_cases  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', default='/app/modules')
    ap.add_argument('--output', default='/logs/verifier')
    ap.add_argument('--case', action='append', help='run only these cases (author use)')
    a = ap.parse_args()
    cand, out = Path(a.candidate), Path(a.output)
    if not cand.is_dir() or not any(p.is_file() and p.stat().st_size > 0 for p in cand.glob('*.va')):
        # fixed footer: a missing or empty deliverable scores zero
        out.mkdir(parents=True, exist_ok=True)
        (out / 'reward.txt').write_text('0\n')
        print('missing or empty module directory: score 0')
        return 1
    cases = [c for c in contract.public_cases() + final_cases() if not a.case or c['name'] in a.case]
    return check.run_cases(cases, cand, out, final=True)


if __name__ == '__main__':
    sys.exit(main())
