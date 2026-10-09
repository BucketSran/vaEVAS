"""Compare a declared common voltage-constraint subset with ngspice.

The IR exporter checks the solver/transport boundary, not parser independence.
The generated circuits additionally have exact dyadic answers; the timer case
uses a separately written behavioral source and checks away from transitions.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import subprocess
import sys

EVAS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAS / 'src'))
from evas import Instance, compile_sources, solve, transient
from evas.ir import Affine, Binary, Power
from evas.manifest import parse_manifest


TIMER_SOURCE = '`include "disciplines.vams"\nmodule timer_count(y,r); output y; inout r; electrical y,r; integer n; analog begin @(initial_step) n=0; @(timer(0.25,0.25,1e-12)) n=n+1; V(y,r)<+n; end endmodule'

class Unsupported(ValueError):
    """The exporter has no established equivalence for this input."""


def expression(expr):
    if isinstance(expr, Affine):
        return '(' + '+'.join([f'({expr.constant:.17g})'] +
                             [f'({t.coefficient:.17g})*v(n{t.node})' for t in expr.terms if t.node]) + ')'
    if isinstance(expr, Binary):
        if expr.op not in {'add', 'multiply'}:
            raise Unsupported(f'unsupported binary operation: {expr.op}')
        op = '+' if expr.op == 'add' else '*'
        return f'({expression(expr.left)}{op}{expression(expr.right)})'
    if isinstance(expr, Power):
        # ngspice's behavioral power uses log/exp and can return NaN for a
        # negative base, even with an integer exponent. EVAS means x*x*...*x.
        if not 2 <= expr.exponent <= 32:
            raise Unsupported('only integer polynomial powers 2 through 32 are translated')
        return '(' + '*'.join([expression(expr.base)] * expr.exponent) + ')'
    raise Unsupported('only stateless affine/polynomial expressions are translated')


def relations(program, driven):
    if program.states or program.events or program.operators:
        raise Unsupported('state, event and operator programs require an independent reference model')
    fixed = {0, *(program.nodes.index(n) for n in driven)}
    groups = defaultdict(list)
    for contribution in program.contributions:
        groups[contribution.branch].append(contribution)
    outputs, lines = set(), []
    for index, contributions in enumerate(groups.values()):
        first = contributions[0]
        endpoints = {first.positive, first.negative} - fixed
        if len(endpoints) != 1 or endpoints & outputs:
            raise Unsupported('one independently constrained unknown output per branch is required')
        outputs |= endpoints
        rhs = '+'.join(expression(c.rhs) for c in contributions)
        node = lambda i: '0' if i == 0 else f'n{i}'
        lines.append(f'Eeq{index} {node(first.positive)} {node(first.negative)} value={{ {rhs} }}')
    if outputs != set(range(len(program.nodes))) - fixed:
        raise Unsupported('each unknown node needs one defining branch')
    return lines


def deck(program, driven, values, *, pwl=False, stop=1.0, max_step=.005, reference=None):
    lines = ['EVAS independent ngspice comparison', '.options reltol=1e-10 vntol=1e-12 abstol=1e-14']
    for index, (name, value) in enumerate(zip(driven, values)):
        node = program.nodes.index(name)
        stimulus = 'PWL(' + ' '.join(f'{x:.17g}' for pair in value for x in pair) + ')' if pwl else f'{value:.17g}'
        lines.append(f'Vin{index} n{node} 0 {stimulus}')
    lines.extend(reference if reference is not None else relations(program, driven))
    vectors = ' '.join(f'v(n{i})' for i in range(1, len(program.nodes)))
    lines += ['.control', 'set numdgt=17', 'set wr_singlescale',
              f'tran {max_step:.17g} {stop:.17g} 0 {max_step:.17g}' if pwl else 'op',
              f'wrdata waveform.txt {vectors}', 'quit', '.endc', '.end']
    return '\n'.join(lines) + '\n'


def execute(netlist, directory, ngspice):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'input.cir').write_text(netlist)
    result = subprocess.run([ngspice, '-n', '-b', 'input.cir'], cwd=directory,
                            capture_output=True, text=True, timeout=30)
    (directory / 'ngspice.log').write_text(result.stdout + result.stderr)
    if result.returncode or not (directory / 'waveform.txt').is_file():
        raise RuntimeError(f'ngspice produced no usable waveform (exit {result.returncode}): {directory}')
    rows = [[float(v) for v in line.split()] for line in (directory / 'waveform.txt').read_text().splitlines() if line.strip()]
    if not rows or len(rows[0]) < 2 or any(len(row) != len(rows[0]) or not all(math.isfinite(v) for v in row) for row in rows):
        raise ValueError('ngspice returned missing/nonfinite values')
    return rows


def interpolate(rows, time):
    times = [row[0] for row in rows]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('ngspice time grid is not strictly increasing')
    index = bisect_left(times, time)
    if index < len(rows) and times[index] == time:
        return [0.0, *rows[index][1:]]
    if index == 0 or index == len(rows):
        raise ValueError('observation is outside the ngspice time range')
    a, b = rows[index-1], rows[index]
    weight = (time-a[0])/(b[0]-a[0])
    return [0.0, *(x+weight*(y-x) for x, y in zip(a[1:], b[1:]))]


def compare(actual, reference, *, absolute=1e-12, relative=1e-10):
    if len(actual) != len(reference) or not actual:
        raise ValueError('voltage vector shape mismatch')
    ratios = []
    for a, b in zip(actual, reference):
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('nonfinite comparison value')
        ratios.append(abs(a-b)/(absolute+relative*max(abs(a), abs(b))))
    return max(ratios)


def generated(size, seed):
    rng = random.Random(seed)
    roots = [rng.randrange(-16, 17)/8 for _ in range(size)]
    ports = ['u', *(f'y{i}' for i in range(size)), 'r']
    equations = []
    for i in range(size):
        terms = [(j, rng.choice([-1, 1])/16) for j in rng.sample(range(size), min(3, size))]
        bias = roots[i] - sum(g*roots[j] for j, g in terms)
        rhs = f'({bias:.17g})+({1-sum(g for _,g in terms):.17g})*V(u,r)'
        rhs += ''.join(f'+({g:.17g})*V(y{j},r)' for j, g in terms)
        equations.append(f'V(y{i},r)<+{rhs};')
    source = '`include "disciplines.vams"\n'+f'module m({",".join(ports)}); input u; output {",".join(ports[1:-1])}; inout r; electrical {",".join(ports)}; analog begin {"".join(equations)} end endmodule'
    program = compile_sources({'generated.va': source}, [Instance('dut', 'm', {n: '0' if n == 'r' else n for n in ports})])
    return program, roots, source


def run_suite(kernel, ngspice, out):
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for size in (1, 4, 16, 64):
        program, roots, source = generated(size, 20261003+size)
        case = out/f'affine-{size}'
        case.mkdir()
        (case/'dut.va').write_text(source)
        (case/'program.json').write_text(json.dumps(program.to_dict(), sort_keys=True))
        samples = [[-.75], [0.0], [.625]]
        result = solve(program, ['u'], samples, kernel=kernel)
        (case/'evas.json').write_text(json.dumps(result))
        ratio = 0.0
        for index, (sample, solution) in enumerate(zip(samples, result['solutions'])):
            reference = [0.0, *execute(deck(program, ['u'], sample), case/f'op-{index}', ngspice)[0][1:]]
            ratio = max(ratio, compare(solution['voltages'], reference))
            for name, expected in [(f'y{i}', v+sample[0]) for i, v in enumerate(roots)]:
                position = program.nodes.index(name)
                ratio = max(ratio, compare([solution['voltages'][position]], [expected]), compare([reference[position]], [expected]))
        times = [0.0, .125, .25, .375, .5, .75, 1.0]
        points = [[0.0, 0.0], [.25, .5], [.5, -.25], [1.0, .75]]
        result = transient(program, {'u': points}, times, stop=1, max_step=.1, kernel=kernel)
        (case/'evas-transient.json').write_text(json.dumps(result))
        rows = execute(deck(program, ['u'], [points], pwl=True), case/'tran', ngspice)
        for time, solution in zip(times, result['solutions']):
            reference = interpolate(rows, time)
            ratio = max(ratio, compare(solution['voltages'], reference))
            # Independent piecewise-linear stimulus and known affine root.
            stimulus = interpolate(points, time)[1]
            for i, root in enumerate(roots):
                position = program.nodes.index(f'y{i}')
                ratio = max(ratio, compare([solution['voltages'][position]], [root + stimulus]),
                            compare([reference[position]], [root + stimulus]))
        records.append(dict(case=f'affine-{size}',static_samples=3,transient_samples=len(times),max_error_ratio=ratio,status='pass' if ratio <= 1 else 'fail'))

    # Process every smoke manifest; unsupported programs remain visible.
    for path in sorted((EVAS/'validation/smoke').glob('*.json')):
        manifest = parse_manifest(path.read_text())
        sources = {str((path.parent/p).resolve()):(path.parent/p).read_text() for p in manifest['models']}
        program = compile_sources(sources, [Instance(**i) for i in manifest['instances']])
        try:
            relations(program, manifest.get('driven', []))
        except Unsupported as exc:
            records.append(dict(case=path.name,status='unsupported',reason=str(exc)))
            continue
        result = solve(program, manifest['driven'], manifest['samples'], kernel=kernel)
        ratios = []
        for index, (values, solution) in enumerate(zip(manifest['samples'], result['solutions'])):
            rows = execute(deck(program, manifest['driven'], values), out/path.stem/f'op-{index}', ngspice)
            ratios.append(compare(solution['voltages'], [0.0, *rows[0][1:]]))
        records.append(dict(case=path.name,status='pass' if max(ratios) <= 1 else 'fail',max_error_ratio=max(ratios),static_samples=len(ratios)))

    source = TIMER_SOURCE
    program = compile_sources({'timer-reference.va': source}, [Instance('dut','timer_count',dict(y='y',r='0'))])
    times = [0, .125, .375, .625, .875]
    result = transient(program, {}, times, stop=1, max_step=.1, kernel=kernel)
    rows = execute(deck(program, [], [], pwl=True, reference=['Bcounter n1 0 v=floor(time/0.25)']), out/'timer-reference', ngspice)
    (out/'timer-reference'/'dut.va').write_text(source)
    (out/'timer-reference'/'evas.json').write_text(json.dumps(result))
    ratio = max(compare(solution['voltages'], interpolate(rows,time)) for time,solution in zip(times,result['solutions']))
    for time, solution in zip(times, result['solutions']):
        ratio = max(ratio, compare(solution['voltages'], [0.0, float(math.floor(time/.25))]))
    records.append(dict(case='fixed-timer-counter-away-from-edges',status='pass' if ratio <= 1 else 'fail',max_error_ratio=ratio,transient_samples=len(times)))
    version = subprocess.run([ngspice, '--version'],capture_output=True,text=True,check=True,timeout=10).stdout
    inventory = {str(p.relative_to(out)):sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
    report = dict(records=records, ngspice_version=version, kernel_sha256=sha256(Path(kernel).read_bytes()).hexdigest(),
                  driver_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),files=inventory,
                  comparison=dict(vabstol=1e-12,reltol=1e-10),raw_availability='local-only',
                  scope='Common algebraic voltage subset; affine PWL interpolation; fixed timer values away from edges. Not the original 31-condition matrix.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--ngspice', default='ngspice')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = run_suite(args.kernel.resolve(), args.ngspice, args.out.resolve())
    print(json.dumps(report['records'], indent=2))
    raise SystemExit(any(item['status']=='fail' for item in report['records']))
