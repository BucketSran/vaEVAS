"""Report point-solve error relative to exact binary64 PWL; never freeze a wrong answer."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evas/src"))
from evas import Instance, KernelError, compile_sources, transient

SOURCE = """module m(u,y,r);
input u; output y; inout r;
electrical u,y,r;
analog begin
V(y,r)<+1e16*(V(u,r)-1);
end
endmodule
"""


def diagnostic(kernel, output):
    program = compile_sources({"high-gain.va": SOURCE}, [Instance("dut", "m", dict(u="u", y="y", r="0"))])
    points = [[0.0, 1.0], [3.0, 2.0]]
    time = 1.0
    vabstol = 1e-12
    # Exact arithmetic over the submitted binary64 numbers and original relation.
    t0, u0 = map(Fraction, points[0])
    t1, u1 = map(Fraction, points[1])
    source_value = u0 + (u1 - u0) * (Fraction(time) - t0) / (t1 - t0)
    answer = Fraction(1e16) * (source_value - 1)
    result = dict(
        evidence_use="one new local diagnostic; exact-PWL reference; not a new matrix condition",
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source=SOURCE, source_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
        kernel_sha256=hashlib.sha256(kernel.read_bytes()).hexdigest(),
        diagnostic_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs={"u": points}, output_times=[time], stop=3.0, max_step=3.0,
        vabstol=vabstol, reltol=0.0, exact_source=str(source_value), exact_output=str(answer),
        unresolved_scope="input interpolation and full arithmetic error amplification are not certified",
    )
    try:
        response = transient(program, {"u": points}, [time], stop=3.0, max_step=3.0,
                             kernel=kernel, vabstol=vabstol, reltol=0.0)
        solution = response["solutions"][0]
        observed = solution["voltages"][response["nodes"].index("y")]
        error = abs(Fraction(observed) - answer)
        result.update(status="accepted", observed=observed, solution=solution,
                      exact_absolute_error=str(error),
                      meets_exact_pwl_voltage_budget=error <= Fraction(vabstol))
    except KernelError as error:
        result.update(status="kernel_rejected", reason=str(error), kernel_error=error.detail)
    with output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    diagnostic(args.kernel.resolve(), args.output)
