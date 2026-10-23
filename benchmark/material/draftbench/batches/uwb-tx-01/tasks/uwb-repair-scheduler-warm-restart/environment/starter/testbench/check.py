#!/usr/bin/env python3
"""Public checks for the IR-UWB transmit chain.

  python3 /app/testbench/check.py plan
  python3 /app/testbench/check.py run [--case NAME] [--candidate /app/modules] [--output DIR]

`run` freezes a copy of the module directory, builds the fixed chain netlist
for each case, launches the simulator once per case (see README.md) and
prints one row per check. Public results are diagnostics only; they do not
produce a task score.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract  # noqa: E402
import uwbtask as u  # noqa: E402


def freeze_dir(candidate: Path, out_dir: Path):
    """Copy the module directory once; later edits to /app do not change this run."""
    if not candidate.is_dir():
        raise u.RunError(f'missing candidate directory {candidate}')
    frozen = out_dir / 'candidate'
    if frozen.exists():
        shutil.rmtree(frozen)
    frozen.mkdir(parents=True)
    for src in sorted(candidate.glob('*.va')):
        if src.is_file():
            shutil.copyfile(src, frozen / src.name)
    return frozen


def digest_dir(frozen: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(frozen.glob('*.va')):
        h.update(f'{f.name}\0{u.digest(f)}\n'.encode())
    return h.hexdigest()


def run_cases(cases, candidate, out_dir, *, final=False):
    protocol = json.loads((HERE / 'protocol.json').read_text())
    os.environ.setdefault('UWB_BACKEND', protocol['backend'])
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, errors, timing = [], [], {}
    try:
        frozen = freeze_dir(Path(candidate), out_dir)
    except u.RunError as exc:
        return u.finish([], [str(exc)], out_dir, final=final)
    sha = digest_dir(frozen)
    files = sorted(frozen.glob('*.va'))
    missing = [n for n in contract.MODULE_FILES if not (frozen / n).is_file() or (frozen / n).stat().st_size == 0]
    if missing:
        rows.append(dict(case='preflight', specification='the nine module files are present (Deliverable)',
                         limit=', '.join(contract.MODULE_FILES), value='missing or empty: ' + ', '.join(missing),
                         passed=False))
        return u.finish(rows, [], out_dir, final=final, candidate_sha=sha)
    banned = sorted({b for f in files for b in u.preflight(f)})
    if banned:
        rows.append(dict(case='preflight', specification='models are self-contained (Deliverable)',
                         limit='no file or process access', value=', '.join(banned), passed=False))
        return u.finish(rows, [], out_dir, final=final, candidate_sha=sha)
    for case in cases:
        work = out_dir / case['name']
        stop = contract.stop_time(case)
        try:
            res = u.simulate(contract.netlist(case, files, HERE, stop), work,
                             timeout=protocol['timeout_s_per_case'])
            data = u.read_rows(res['rows'])
        except (u.RunError, OSError, KeyError, ValueError) as exc:
            errors.append(f"{case['name']}: {exc}")
            continue
        timing[case['name']] = round(res['wall_s'], 2)
        rows += contract.check(case, u.Edges(res['records']), data, stop).rows
    (out_dir / 'timing.json').write_text(json.dumps(dict(wall_s_per_case=timing), indent=1) + '\n')
    return u.finish(rows, errors, out_dir, final=final, candidate_sha=sha)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['plan', 'run'])
    ap.add_argument('--case', action='append')
    ap.add_argument('--candidate', default='/app/modules')
    ap.add_argument('--output', default='/tmp/uwb-chain-public')
    a = ap.parse_args()
    cases = [c for c in contract.public_cases() if not a.case or c['name'] in a.case]
    if a.command == 'plan':
        for c in cases:
            b = contract.bench(c)
            stop = contract.stop_time(c)
            st = contract.expected(c, stop)['replay']['stats']
            print(f"{c['name']}: {len(c['words'])} words, n_pre={b['n_pre']}, t_tail={b['t_tail'] * 1e12:g} ps, "
                  f"t_hold={b['t_hold'] * 1e12:g} ps, stop={stop * 1e9:.3f} ns; expected paths: "
                  + ', '.join(f'{k}={v}' for k, v in st.items()))
        return 0
    return run_cases(cases, a.candidate, Path(a.output))


if __name__ == '__main__':
    sys.exit(main())
