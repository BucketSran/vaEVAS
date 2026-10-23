"""Shared runner for the uwb-tx-01 task packages (one identical copy per task).

It writes Spectre-style netlists, runs one fixed simulator backend, reads the
edge records printed by edge_monitor.va and the saved waveforms, and reports
checks as Specification | Limit | Value | Pass/Fail rows. Importing this
module never launches a process.

Backends (selected by the task protocol, overridable with UWB_BACKEND):
  evas    current EVAS: `python -m evas simulate <netlist>`; EVAS_PYTHONPATH
          (directory containing the evas package) and EVAS_KERNEL select it.
  legacy  EVAS 0.8.7: `python -m evas simulate <netlist> -o <dir>`;
          LEGACY_EVAS_SRC and LEGACY_EVAS_PY select it.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent


class RunError(RuntimeError):
    """The simulator did not produce a result; this is not a circuit verdict."""


# ------------------------------------------------------------------ helpers --

def fmt_ps(t: float) -> str:
    return f'{t * 1e12:.6f}'.rstrip('0').rstrip('.') + 'p'


def pwl(points) -> str:
    return '[' + ' '.join(f'{fmt_ps(t) if t else "0"} {v:g}' for t, v in points) + ']'


def pwl_levels(changes, edge=2e-12, vdd=1.0) -> str:
    """changes: [(t, level)] with the first at t = 0; edges of `edge` centred on t."""
    pts = [(0.0, changes[0][1] * vdd)]
    for t, v in changes[1:]:
        if v * vdd != pts[-1][1]:
            pts.append((t - edge / 2, pts[-1][1]))
            pts.append((t + edge / 2, v * vdd))
    return pwl(pts)


def digest(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(candidate: Path, workdir: Path) -> Path:
    """Copy the candidate once; later edits to /app do not change this run."""
    workdir.mkdir(parents=True, exist_ok=True)
    frozen = workdir / 'candidate.va'
    if not candidate.is_file() or candidate.stat().st_size == 0:
        raise RunError(f'missing or empty candidate {candidate}')
    shutil.copyfile(candidate, frozen)
    return frozen


FORBIDDEN = re.compile(r'\$(?:fopen|fclose|fwrite|fdisplay|fstrobe|system|table_model)\b')


def preflight(source: Path) -> list[str]:
    """Obvious external file or process use in the submitted model."""
    text = source.read_text(errors='replace')
    return sorted(set(FORBIDDEN.findall(text)))


# ------------------------------------------------------------------ backend --

def backend() -> str:
    return os.environ.get('UWB_BACKEND', 'evas')


def simulate(netlist: str, workdir: Path, timeout: float = 1800.0) -> dict:
    """Run one netlist. Returns {'records': [...], 'rows': csv path, 'wall_s': s}."""
    workdir.mkdir(parents=True, exist_ok=True)
    deck = workdir / 'tb.scs'
    deck.write_text(netlist)
    which = backend()
    start = time.monotonic()
    try:
        if which == 'legacy':
            result = _legacy(deck, workdir, timeout)
        elif which == 'evas':
            result = _evas(deck, workdir, timeout)
        else:
            raise RunError(f'unknown backend {which}')
    except subprocess.TimeoutExpired as exc:
        raise RunError(f'{which} timed out after {timeout} s') from exc
    result['wall_s'] = time.monotonic() - start
    result['backend'] = which
    return result


def _evas(deck: Path, workdir: Path, timeout: float) -> dict:
    env = dict(os.environ)
    if os.environ.get('EVAS_PYTHONPATH'):
        env['PYTHONPATH'] = os.environ['EVAS_PYTHONPATH']
    cmd = [os.environ.get('EVAS_PYTHON', 'python3'), '-m', 'evas', 'simulate', str(deck)]
    if os.environ.get('EVAS_KERNEL'):
        cmd += ['--kernel', os.environ['EVAS_KERNEL']]
    cmd += ['--timeout', str(timeout)]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=workdir, timeout=timeout + 60)
    (workdir / 'stderr.txt').write_text(proc.stderr)
    if proc.returncode != 0:
        raise RunError(f'evas exit {proc.returncode}: {proc.stderr.strip()[-600:]}')
    res = json.loads(proc.stdout)
    saved = res['saved']
    rows = workdir / 'tran.csv'
    with rows.open('w') as f:
        f.write(','.join(['time'] + saved['nodes']) + '\n')
        for t, row in zip(saved['times'], saved['values']):
            f.write(','.join(repr(float(x)) for x in [t] + list(row)) + '\n')
    return dict(records=[r['text'] for r in res['transient'].get('display_records', [])], rows=rows)


def _legacy(deck: Path, workdir: Path, timeout: float) -> dict:
    # EVAS 0.8.7 rejects the options statement that the current EVAS needs
    legacy_deck = workdir / 'tb_legacy.scs'
    legacy_deck.write_text(''.join(l for l in deck.read_text().splitlines(True) if ' options ' not in l))
    env = dict(os.environ, MPLBACKEND='Agg',
               PYTHONPATH=os.environ.get('LEGACY_EVAS_SRC', '/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/legacy-evas-0.8.7/src'))
    cmd = [os.environ.get('LEGACY_EVAS_PY', '/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/legacy-evas-0.8.7/venv/bin/python'), '-m', 'evas',
           'simulate', str(legacy_deck), '-o', str(workdir / 'sim')]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=workdir, timeout=timeout)
    (workdir / 'sim.log').write_text(proc.stdout[-100000:] + '\n---STDERR---\n' + proc.stderr[-20000:])
    if proc.returncode != 0 or 'completes with 0 errors' not in proc.stdout:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-6:]
        raise RunError(f'legacy exit {proc.returncode}: ' + ' | '.join(tail))
    strobe = workdir / 'sim' / 'strobe.txt'
    return dict(records=strobe.read_text().splitlines() if strobe.is_file() else [],
                rows=workdir / 'sim' / 'tran.csv')


def read_rows(path: Path) -> dict[str, list[float]]:
    with open(path) as f:
        rows = list(csv.DictReader(f))
    out = {k: [] for k in rows[0]} if rows else {}
    for r in rows:
        for k, v in r.items():
            out[k].append(float(v))
    return out


# -------------------------------------------------------------------- edges --

class Edges:
    """Threshold crossings printed by edge_monitor.va: id -> [(time, dir)]."""

    def __init__(self, records, t_min=5e-12):
        self.by_id: dict[int, list] = {}
        self.initial: dict[int, int] = {}
        for rec in records:
            parts = rec.split()
            if len(parts) == 4 and parts[0] == 'EDGE':
                self.by_id.setdefault(int(parts[1]), []).append((float(parts[3]), int(parts[2])))
        # EVAS 0.8.7 ramps every transition() output from 0 V at t = 0; a
        # crossing before t_min is a start-up level, not a circuit edge
        for ident, lst in self.by_id.items():
            lst.sort()
            early = [d for t, d in lst if t <= t_min]
            if early:
                self.initial[ident] = early[-1]
            self.by_id[ident] = [(t, d) for t, d in lst if t > t_min]

    def times(self, ident, direction=None):
        return [t for t, d in self.by_id.get(ident, []) if direction is None or d == direction]

    def level(self, ident, t):
        level = self.initial.get(ident, 0)
        for te, d in self.by_id.get(ident, []):
            if te <= t:
                level = d
            else:
                break
        return level

    def bus(self, ids_lsb_first, t):
        return sum(self.level(i, t) << k for k, i in enumerate(ids_lsb_first))


def monitors(nodes_ids: dict) -> str:
    return '\n'.join(f'Xmon_{n} ({n}) uwb_edge_monitor id={i}' for n, i in nodes_ids.items())


# ------------------------------------------------------------------ reports --

class Report:
    """Specification | Limit | Value | Pass/Fail rows for one case."""

    def __init__(self, case: str):
        self.case = case
        self.rows: list[dict] = []

    def add(self, spec: str, limit: str, value: str, ok: bool):
        self.rows.append(dict(case=self.case, specification=spec, limit=limit, value=value, passed=bool(ok)))
        return ok

    def times_match(self, spec, got, exp, tol):
        """Compare edge times one to one; counts must match."""
        n = min(len(got), len(exp))
        worst = max((abs(a - b) for a, b in zip(got[:n], exp[:n])), default=0.0)
        ok = len(got) == len(exp) and worst <= tol
        return self.add(spec, f'{len(exp)} edges, |error| <= {tol*1e12:g} ps',
                        f'{len(got)} edges, worst {worst*1e12:.3f} ps', ok)

    @property
    def ok(self):
        return all(r['passed'] for r in self.rows)


def table(rows) -> str:
    out = ['| Case | Specification | Limit | Value | Pass/Fail |', '| --- | --- | --- | --- | --- |']
    for r in rows:
        out.append(f"| {r['case']} | {r['specification']} | {r['limit']} | {r['value']} | "
                   f"{'PASS' if r['passed'] else 'FAIL'} |")
    return '\n'.join(out)


def finish(rows, errors, out_dir: Path, *, final: bool, candidate_sha: str | None = None) -> int:
    """Write results.json/results.md; for the final run also reward.txt.

    A run error leaves the score undecided (no reward written): it is an
    execution problem, not proof of a wrong model.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    executed = not errors
    passed = executed and bool(rows) and all(r['passed'] for r in rows)
    score = (1 if passed else 0) if executed else None
    summary = dict(status='executed' if executed else 'not_executed', score=score,
                   backend=backend(), candidate_sha256=candidate_sha, errors=errors, checks=rows)
    (out_dir / 'results.json').write_text(json.dumps(summary, indent=1, allow_nan=False) + '\n')
    (out_dir / 'results.md').write_text(table(rows) + '\n')
    if final and executed:
        (out_dir / 'reward.txt').write_text(f'{score}\n')
    print(table(rows))
    for e in errors:
        print('RUN ERROR:', e)
    print(f"status={summary['status']} score={score}")
    return 0 if passed else (2 if not executed else 1)
