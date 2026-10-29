"""Write the calibration candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the checker on the cases in ../cases.json
(and the public case in ../../environment/starter/testbench/cases.json), as listed in
expected.json. Every wrong candidate is the reference with one checked text change.
alt_difference_state is a full text kept from the historical author calibration. Run
`python3 -B mutants.py <new or empty directory>` from any directory.

Attribution: the one-zero, two-pole CTLE topic of this task follows Brian Li, verilogaLib
ctle.va (https://github.com/ShabbyGayBar/verilogaLib, commit a6cdb370), Copyright (c) 2025
Brian Li, MIT License. The reference and these candidates are this repository's state-equation
rewrite of the public contract; no verilogaLib code is copied here.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
X1 = "V(a) <+ idt(2*`M_PI*fp1*(V(u)-V(a)),x1init);\n"
X2 = "V(b) <+ idt(2*`M_PI*fp2*(V(a)-V(b)),x2init);\n"
Y = "V(y) <+ gain*(V(b)+fp2/fz*(V(a)-V(b)));\n"

# Historical alternative (experiments/benchmark_next/filter/candidates/v3-filter-ctle/
# alternative/dut.va, sha256 3aba928f...): the difference state d = x1 - x2 instead of x2.
ALT_DIFFERENCE_STATE = """`include "constants.vams"
`include "disciplines.vams"
module ctle(u,y);
inout u,y;
electrical u,y;
parameter real fz=1000, fp1=4000, fp2=12000, gain=1, x1init=0, x2init=0;
electrical a,d;
analog begin
V(a) <+ idt(2*`M_PI*fp1*(V(u)-V(a)),x1init);
V(d) <+ idt(2*`M_PI*fp1*(V(u)-V(a))-2*`M_PI*fp2*V(d),x1init-x2init);
V(y) <+ gain*(V(a)+(fp2/fz-1)*V(d));
end
endmodule
"""


def sub(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def candidates():
    gold = (HERE.parents[1] / "solution/circuit.va").read_text()
    wrong = {
        # The pole frequencies in hertz are used as rad/s: no 2*pi (historical hz-as-radians).
        "hz_as_radians": sub(sub(gold, X1, X1.replace("2*`M_PI*", "")), X2, X2.replace("2*`M_PI*", "")),
        # Both integrators start at 0; x1init and x2init are never read (historical zero-initval).
        "zero_initval": sub(sub(gold, X1, X1.replace(",x1init)", ",0)")), X2, X2.replace(",x2init)", ",0)")),
        # The corner frequencies are fixed at the default 1, 4 and 12 kHz; fz, fp1 and fp2 overrides are ignored.
        "corner_frequencies_hardcoded": sub(sub(sub(gold, X1, X1.replace("*fp1*", "*4000.0*")),
                                                X2, X2.replace("*fp2*", "*12000.0*")),
                                            Y, Y.replace("fp2/fz", "12000.0/1000.0")),
        # The zero term is normalized by the first pole instead of the second: the zero lands at
        # fz*fp2/fp1 (3 kHz instead of 1 kHz with the defaults) and the peaking is too low.
        "zero_normalized_to_first_pole": sub(gold, Y, Y.replace("fp2/fz", "fp1/fz")),
    }
    correct = {
        "alt_difference_state": ALT_DIFFERENCE_STATE,
    }
    return wrong, correct


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="new or empty directory")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"{args.output}: output must be a new or empty directory")
    wrong, correct = candidates()
    for group, items in (("wrong", wrong), ("correct", correct)):
        (args.output / group).mkdir(parents=True, exist_ok=True)
        for name, source in items.items():
            (args.output / group / (name + ".va")).write_text(source)
