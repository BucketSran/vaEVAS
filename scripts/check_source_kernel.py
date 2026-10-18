"""Check a newly built source kernel through public APIs, without installation."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


def verify(result, expected):
    column = result['nodes'].index('y')
    rows = result['solutions']
    if len(rows) != len(expected):
        raise ValueError('unexpected number of source-kernel observations')
    for row, answer in zip(rows, expected):
        if not math.isclose(row['voltages'][column], answer, rel_tol=0, abs_tol=1e-9):
            raise ValueError('source kernel disagrees with independent affine/integral answer')


def check(kernel):
    from evas import Instance, compile_sources, solve, transient

    kernel = kernel.resolve(strict=True)
    identity = json.loads(subprocess.check_output(
        [str(kernel), '--version', '--json'], text=True, timeout=30))
    source = ('`include "disciplines.vams"\nmodule m(u,y); input u; output y; '
              'electrical u,y; analog begin V(y)<+2*V(u)+0.25; end endmodule')
    program = compile_sources({'m.va': source}, [Instance('dut', 'm', {'u': 'u', 'y': 'y'})])
    verify(solve(program, ['u'], [[-.5], [0], [.75]], kernel=kernel,
                 reltol=0, vabstol=1e-9), [-.75, .25, 1.75])
    source = ('`include "disciplines.vams"\nmodule m(y); output y; electrical y; '
              'analog begin V(y)<+idt(1,0.25); end endmodule')
    program = compile_sources({'m.va': source}, [Instance('dut', 'm', {'y': 'y'})])
    verify(transient(program, sources={}, output_times=[0, .25, .5], stop=.5,
                     max_step=.5, kernel=kernel, reltol=0, vabstol=1e-9), [.25, .5, .75])
    return dict(successful=True, kernel=str(kernel),
                kernel_sha256=hashlib.sha256(kernel.read_bytes()).hexdigest(),
                reported_identity=identity, observations=6,
                scope='Explicit source kernel; no installed-wheel or platform claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.kernel)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print('Source kernel: PASS; independent affine/integral observations=6')


if __name__ == '__main__':
    main()
