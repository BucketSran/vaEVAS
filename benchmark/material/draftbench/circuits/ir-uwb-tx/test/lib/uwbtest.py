"""Shared helpers for the IR-UWB TX seed-chain checks.

Runs a Spectre-style testbench through EVAS, reads the edge records printed by
test/sources/edge_monitor.va, and provides the independent reference rules from
SPEC.md (Gray coding, DPPM recursion, de Bruijn codeword order). Nothing here
reads or imports the gold Verilog-A.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent.parent
REPO = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, text=True).strip())
# Current EVAS: this checkout by default; UWB_EVAS_REPO points at another
# checkout (for example an EVAS development worktree) whose evas/src and
# release kernel are used instead.
EVAS_REPO = Path(os.environ.get('UWB_EVAS_REPO', REPO))
KERNEL = EVAS_REPO / 'evas/rust_core/target/release/evas-kernel'
# Legacy EVAS 0.8.7 (the simulator vaBench r53 was certified on): an export of
# legacy/EVAS commit 6cb6fa7a plus a Python with numpy. See the family README.
LEGACY_SRC = Path(os.environ.get('UWB_LEGACY_SRC', '/tmp/legacy-run/src'))
LEGACY_PY = os.environ.get('UWB_LEGACY_PY', '/tmp/legacy-run/venv/bin/python')
BACKEND = os.environ.get('UWB_BACKEND', 'legacy')   # 'legacy' or 'evas'

# System constants (SPEC.md section 2)
F_REF = 48e6
F_RO = 672e6
TS = 1.0 / F_RO
DELTA0 = 1.0 / (32 * 336e6)
T_BIT = TS / 6
CARRIERS = [4.5e9 + k * 3e9 / 7 for k in range(8)]


def run_evas(tb: Path, out_dir: Path, timeout: float = 3600.0) -> dict:
    """Simulate tb with the selected backend; keep raw output in out_dir.

    Returns a dict with key 'records' (strobe text lines) and the backend name.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if BACKEND == 'legacy':
        return _run_legacy(tb, out_dir, timeout)
    env = dict(os.environ, PYTHONPATH=str(EVAS_REPO / 'evas/src'))
    cmd = [sys.executable, '-m', 'evas', 'simulate', str(tb), '--kernel', str(KERNEL),
           '--timeout', str(timeout)]
    start = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=EVAS_REPO)
    elapsed = time.monotonic() - start
    (out_dir / 'stderr.txt').write_text(proc.stderr)
    (out_dir / 'run.json').write_text(json.dumps(dict(cmd=cmd, returncode=proc.returncode,
                                                      wall_s=elapsed), indent=1))
    if proc.returncode != 0:
        raise RuntimeError(f'EVAS failed ({proc.returncode}): {proc.stderr[-2000:]}')
    (out_dir / 'result.json').write_text(proc.stdout)
    res = json.loads(proc.stdout)
    # same CSV layout as legacy EVAS's tran.csv: time column plus saved nodes
    saved = res['saved']
    tran = out_dir / 'tran.csv'
    with tran.open('w') as f:
        f.write(','.join(['time'] + saved['nodes']) + '\n')
        for t, row in zip(saved['times'], saved['values']):
            f.write(','.join(repr(float(x)) for x in [t] + list(row)) + '\n')
    return dict(backend='evas', records=[r['text'] for r in res['transient'].get('display_records', [])],
                tran=tran)


def _run_legacy(tb: Path, out_dir: Path, timeout: float) -> dict:
    # legacy EVAS rejects the 'options' statement used for the rebuilt EVAS
    deck = out_dir / 'tb_legacy.scs'
    deck.write_text(''.join(l for l in tb.read_text().splitlines(True) if ' options ' not in l))
    env = dict(os.environ, PYTHONPATH=str(LEGACY_SRC), MPLBACKEND='Agg')
    cmd = [LEGACY_PY, '-m', 'evas', 'simulate', str(deck), '-o', str(out_dir / 'sim')]
    start = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=out_dir, timeout=timeout)
    elapsed = time.monotonic() - start
    (out_dir / 'sim.log').write_text(proc.stdout[-200000:] + '\n---STDERR---\n' + proc.stderr)
    (out_dir / 'run.json').write_text(json.dumps(dict(cmd=cmd, returncode=proc.returncode,
                                                      wall_s=elapsed, backend='legacy-0.8.7'), indent=1))
    if proc.returncode != 0 or 'completes with 0 errors' not in proc.stdout:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-8:]
        raise RuntimeError('legacy EVAS failed: ' + ' | '.join(tail))
    strobe = out_dir / 'sim' / 'strobe.txt'
    lines = strobe.read_text().splitlines() if strobe.is_file() else []
    return dict(backend='legacy', records=lines, tran=out_dir / 'sim' / 'tran.csv')


@dataclass
class Edges:
    """Edge records per monitor id: lists of (time, direction)."""
    by_id: dict = field(default_factory=dict)
    initial: dict = field(default_factory=dict)   # level before the first kept edge

    def drop_startup(self, t_min: float = 5e-12) -> 'Edges':
        """Remove crossings before t_min (legacy EVAS ramps transition() outputs
        from 0 V at t = 0) and keep the level they leave as the initial level."""
        for ident, lst in self.by_id.items():
            early = [d for t, d in lst if t <= t_min]
            if early:
                self.initial[ident] = early[-1]
            self.by_id[ident] = [(t, d) for t, d in lst if t > t_min]
        return self

    def times(self, ident: int, direction: int | None = None) -> list[float]:
        return [t for t, d in self.by_id.get(ident, []) if direction is None or d == direction]

    def level(self, ident: int, t: float, initial: int | None = None) -> int:
        """Logic level of a monitored signal just after time t."""
        level = self.initial.get(ident, 0) if initial is None else initial
        for te, d in self.by_id.get(ident, []):
            if te <= t:
                level = d
            else:
                break
        return level


def parse_edges(result: dict) -> Edges:
    edges = Edges()
    for rec in result['records']:
        parts = rec.split()
        if len(parts) == 4 and parts[0] == 'EDGE':
            edges.by_id.setdefault(int(parts[1]), []).append((float(parts[3]), int(parts[2])))
    for lst in edges.by_id.values():
        lst.sort()
    return edges


def bus_value(edges: Edges, ids_lsb_first: list[int], t: float) -> int:
    return sum(edges.level(i, t) << k for k, i in enumerate(ids_lsb_first))


def gray(b: int) -> int:
    return b ^ (b >> 1)


def gray_to_bin(g: int) -> int:
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def de_bruijn(k: int, n: int) -> list[int]:
    """Ruskey's FKM construction: lexicographic concatenation of Lyndon words."""
    a = [0] * (k * n)
    seq: list[int] = []

    def db(t: int, p: int) -> None:
        if t > n:
            if n % p == 0:
                seq.extend(a[1:p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)

    db(1, 1)
    return seq


def codeword_sequence() -> list[int]:
    """Absolute codewords 8*P + F of bit_source mode 2: de Bruijn order 2, then 0."""
    seq = de_bruijn(64, 2)
    return seq + [seq[0]]


def symbols_for_codewords(codewords: list[int]) -> list[int]:
    """Input symbols that make the encoder emit the given absolute codewords."""
    out, p_prev = [], 0
    for cw in codewords:
        p, f = cw >> 3, cw & 7
        d = (p - p_prev) % 8
        p_prev = p
        out.append((gray(d) << 3) | gray(f))
    return out


class Report:
    """Collects named pass/fail checks and writes them as JSON."""

    def __init__(self, name: str):
        self.name = name
        self.checks: list[dict] = []

    def check(self, label: str, ok: bool, detail: str = '') -> bool:
        self.checks.append(dict(check=label, ok=bool(ok), detail=detail))
        print(f"{'PASS' if ok else 'FAIL'} {label}{(': ' + detail) if detail else ''}")
        return ok

    @property
    def ok(self) -> bool:
        return all(c['ok'] for c in self.checks)

    def write(self, out_dir: Path) -> None:
        (out_dir / 'checks.json').write_text(json.dumps(dict(bench=self.name, ok=self.ok,
                                                             checks=self.checks), indent=1))


def out_dir_for(bench: str) -> Path:
    base = Path(os.environ.get('UWB_OUT', REPO / 'runs/uwb-tx-vabench-20261022/evas'))
    return base / bench


# ---------------------------------------------------------------- stimulus ---

def fmt_ps(t: float) -> str:
    """Compact netlist time in picoseconds."""
    return f'{t * 1e12:.6f}'.rstrip('0').rstrip('.') + 'p'


def pwl_bits(bits: list[int], first_capture: float, period: float, edge: float = 2e-12,
             vdd: float = 1.0) -> str:
    """PWL wave for an NRZ bit stream sampled at first_capture + j*period.

    Bit j is valid from half a period before its capture to half a period after,
    so each change sits midway between two sampling edges.
    """
    pts = [(0.0, bits[0] * vdd)]
    for j in range(1, len(bits)):
        if bits[j] != bits[j - 1]:
            t = first_capture + (j - 0.5) * period
            pts.append((t - edge / 2, bits[j - 1] * vdd))
            pts.append((t + edge / 2, bits[j] * vdd))
    return '[' + ' '.join(f'{fmt_ps(t) if t else "0"} {v:g}' for t, v in pts) + ']'


def include_lines(*rel_paths: str) -> str:
    """ahdl_include lines; UWB_MODULE_DIR replaces module/ (used for mutants)."""
    mod_dir = os.environ.get('UWB_MODULE_DIR')
    out = []
    for p in rel_paths:
        path = (Path(mod_dir) / p[len('module/'):]) if mod_dir and p.startswith('module/') else FAMILY / p
        out.append(f'ahdl_include "{path.resolve()}"')
    return '\n'.join(out)


def monitor_lines(nodes_ids: dict[str, int]) -> str:
    return '\n'.join(f'Xmon_{n} ({n}) uwb_edge_monitor id={i}' for n, i in nodes_ids.items())
