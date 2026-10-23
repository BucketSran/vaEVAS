#!/usr/bin/env python3
"""Final evaluation: public cases plus the final cases on the frozen candidate."""
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
import uwbtask as u  # noqa: E402
from final_cases import final_cases  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', default='/app/circuit.va')
    ap.add_argument('--output', default='/logs/verifier')
    a = ap.parse_args()
    cand, out = Path(a.candidate), Path(a.output)
    if not cand.is_file() or cand.stat().st_size == 0:
        # fixed footer: a missing or empty deliverable scores zero
        out.mkdir(parents=True, exist_ok=True)
        (out / 'reward.txt').write_text('0\n')
        print('missing or empty candidate: score 0')
        return 1
    return check.run_cases(contract.public_cases() + final_cases(), cand, out, final=True)


if __name__ == '__main__':
    sys.exit(main())
