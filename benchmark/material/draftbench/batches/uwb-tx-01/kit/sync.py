#!/usr/bin/env python3
"""Copy the kit files into every task's public testbench and check they match.

  python3 kit/sync.py          # copy
  python3 kit/sync.py --check  # report tasks whose copies differ
"""
import filecmp
from pathlib import Path
import shutil
import sys

KIT = Path(__file__).resolve().parent
FILES = ['uwbtask.py', 'edge_monitor.va', 'clock_source.va']


def main():
    check = '--check' in sys.argv
    bad = []
    for task in sorted((KIT.parent / 'tasks').iterdir()):
        tb = task / 'environment/starter/testbench'
        if not tb.is_dir():
            continue
        for name in FILES:
            dst = tb / name
            if check:
                if dst.exists() and not filecmp.cmp(KIT / name, dst, shallow=False):
                    bad.append(str(dst))
            elif dst.exists() or name == 'uwbtask.py':
                shutil.copyfile(KIT / name, dst)
    for b in bad:
        print('differs:', b)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
