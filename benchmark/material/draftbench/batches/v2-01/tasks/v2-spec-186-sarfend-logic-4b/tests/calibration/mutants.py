"""Write the F01 scoring-start candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Only the output delays change: every output keeps its
10 ps transition, and the handshake, pointer and test-override logic stay as in
the reference. Run `python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

DP = ",20p,10p,10p)"     # dp1..dp4 and dm1..dm4
DOUT = ",0,10p,10p)"     # dout0..dout3
CLKC = ",30p,10p,10p)"   # clkc


def delayed(gold, delay):
    return gold.replace(DP, f",{delay},10p,10p)").replace(DOUT, f",{delay},10p,10p)").replace(CLKC, f",{delay},10p,10p)")


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert (gold.count(DP), gold.count(DOUT), gold.count(CLKC)) == (8, 4, 1)
    wrong = {
        # Every output change completes 260 ps after its event, after the 230 ps scoring start.
        "late_output_delay_250ps": delayed(gold, "250p"),
    }
    correct = {
        # Completion at 220 ps lies between the 200 ps deadline and the scoring start: the accepted margin.
        "inwindow_output_delay_210ps": delayed(gold, "210p"),
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
