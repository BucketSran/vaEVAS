#!/usr/bin/env python3
"""Public checks for the seed-transmitter integration.

  python3 /app/testbench/check.py plan
  python3 /app/testbench/check.py run [--case NAME] [--candidate /app/circuit.va] [--output DIR]

`run` freezes the candidate together with a fresh copy of the module library,
checks the Deliverable rules, then launches the simulator once per case (see
README.md). Public results are diagnostics only; they do not produce a task
score.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parent / 'modules'
sys.path.insert(0, str(HERE))
import contract  # noqa: E402
import uwbtask as u  # noqa: E402

STANDARD = {'constants.vams', 'disciplines.vams'}


def va_code(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',
                  lambda m: m[0] if m[0].startswith('"') else ' ', text, flags=re.S)


def module_ports(text):
    """{module: [(port, is_bus)]} from simple Verilog-A module headers."""
    out = {}
    code = va_code(text)
    for m in re.finditer(r'\bmodule\s+(\w+)\s*\(([^)]*)\)\s*;(.*?)\bendmodule\b', code, re.S):
        ports = [p.strip() for p in m[2].split(',') if p.strip()]
        bus = set()
        for d in re.finditer(r'\b(?:input|output|inout|electrical)\s*\[\s*\d+\s*:\s*\d+\s*\]\s*([^;]+);', m[3]):
            bus.update(x.strip() for x in d[1].split(','))
        out[m[1]] = [(p, p in bus) for p in ports]
    return out


def split_args(s):
    args, depth, cur = [], 0, ''
    for ch in s:
        if ch == ',' and depth == 0:
            args.append(cur.strip())
            cur = ''
            continue
        depth += ch == '('
        depth -= ch == ')'
        cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def deliverable_rules(source: Path):
    """Deliverable rules on the frozen candidate; returns failure messages."""
    text = source.read_text(errors='replace')
    code = va_code(text)
    lib_files = sorted(p.name for p in LIBRARY.glob('*.va'))
    library = {}
    for name in lib_files:
        library.update(module_ports((LIBRARY / name).read_text()))
    bad = []
    for inc in re.findall(r'`include\s+"([^"]+)"', code):
        if inc not in STANDARD and inc not in {f'modules/{n}' for n in lib_files}:
            bad.append(f'include "{inc}" is not a standard header or modules/<library file>')
    own = module_ports(text)
    for name in own:
        if name in library:
            bad.append(f'module {name} redefines a library module')
    if 'uwb_tx_seed' not in own:
        bad.append('module uwb_tx_seed is missing')
    inst = re.compile(r'\b(\w+)\s*(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?(\w+)\s*\(((?:[^;()]|\([^()]*\))*)\)\s*;')
    for m in inst.finditer(code):
        if m[1] not in library:        # the bus rule is about the fixed library only
            continue
        ports = library[m[1]]
        args = split_args(m[3])
        if args and all(a.startswith('.') for a in args):
            conn = {}
            for a in args:
                mm = re.fullmatch(r'\.(\w+)\s*\(\s*(.*?)\s*\)', a)
                if mm:
                    conn[mm[1]] = mm[2]
        else:
            conn = {p: a for (p, _), a in zip(ports, args)}
        for port, is_bus in ports:
            if is_bus and port in conn and re.sub(r'\s+', '', conn[port]) != port:
                bad.append(f'{m[2]}: bus port {port} connected to "{conn[port]}", not to a bus net named {port}')
    return bad


def run_cases(cases, candidate, out_dir, *, final=False):
    protocol = json.loads((HERE / 'protocol.json').read_text())
    os.environ.setdefault('UWB_BACKEND', protocol['backend'])
    rows, errors = [], []
    try:
        frozen = u.freeze(Path(candidate), out_dir)
    except u.RunError as exc:
        return u.finish([], [str(exc)], out_dir, final=final)
    # the fixed library is taken from this testbench's baseline, not from the candidate
    shutil.copytree(LIBRARY, out_dir / 'modules', dirs_exist_ok=True)
    banned = u.preflight(frozen)
    broken = deliverable_rules(frozen)
    if banned or broken:
        if banned:
            rows.append(dict(case='preflight', specification='model is self-contained (Deliverable)',
                             limit='no file or process access', value=', '.join(banned), passed=False))
        if broken:
            rows.append(dict(case='preflight', specification='includes, library modules and bus nets (Deliverable)',
                             limit='rules of the Deliverable', value='; '.join(broken[:4]), passed=False))
        return u.finish(rows, [], out_dir, final=final, candidate_sha=u.digest(frozen))
    for case in cases:
        work = out_dir / case['name']
        try:
            res = u.simulate(contract.netlist(case, frozen, HERE, contract.stop_time(case)), work,
                             timeout=protocol['timeout_s_per_case'])
            waves = u.read_rows(res['rows'])
        except (u.RunError, OSError, KeyError, ValueError) as exc:
            errors.append(f"{case['name']}: {exc}")
            continue
        (work / 'wall_s.txt').write_text(f"{res['wall_s']:.1f}\n")
        for rep in contract.check(case, waves):
            rows += rep.rows
    return u.finish(rows, errors, out_dir, final=final, candidate_sha=u.digest(frozen))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['plan', 'run'])
    ap.add_argument('--case', action='append')
    ap.add_argument('--candidate', default='/app/circuit.va')
    ap.add_argument('--output', default='/tmp/uwb-integrate-public')
    a = ap.parse_args()
    cases = [c for c in contract.public_cases() if not a.case or c['name'] in a.case]
    if a.command == 'plan':
        for c in cases:
            print(f"{c['name']}: params {c['params']}, pol {c['pol']}, {len(c['symbols'])} symbols from "
                  f"{c['t_start'] * 1e9:.1f} ns, stop {c['stop'] * 1e9:.1f} ns")
        return 0
    return run_cases(cases, a.candidate, Path(a.output))


if __name__ == '__main__':
    sys.exit(main())
