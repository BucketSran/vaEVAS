"""Run every IR-UWB TX check and the checker calibration; print a summary.

Usage: python3 run_all.py [--skip-mutants]
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = ['m1_data/check_m1.py', 'm2_clock/check_m2.py', 'm3_pulse/check_pg.py', 'm3_pulse/check_rf.py',
          'm4_chain/check_chain.py', 'system/check_system.py']


def main():
    runs = CHECKS + ([] if '--skip-mutants' in sys.argv else ['mutants.py'])
    rows, ok_all = [], True
    for script in runs:
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, str(HERE / script)], capture_output=True, text=True)
        dt = time.monotonic() - t0
        lines = p.stdout.strip().splitlines()
        summary = [l for l in lines if ': PASS' in l or ': FAIL' in l or 'killed' in l and '/' in l]
        ok = p.returncode == 0
        ok_all &= ok
        rows.append((script, 'PASS' if ok else 'FAIL', dt, '; '.join(s.split('  (')[0] for s in summary)[-200:]))
        print(f"{'PASS' if ok else 'FAIL'} {script} ({dt:.0f} s)", flush=True)
        if not ok:
            print('\n'.join(l for l in lines if l.startswith('FAIL'))[:2000] or p.stderr[-2000:])
    print('\n| check | result | wall time | scenarios |\n| --- | --- | ---: | --- |')
    for script, res, dt, summ in rows:
        print(f'| {script} | {res} | {dt:.0f} s | {summ} |')
    return ok_all


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
