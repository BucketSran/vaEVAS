"""Write the F01 scoring-start candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Only the output transition time changes; the sampled
code and the output equations stay as in the reference. Run
`python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

OUTPUT = ", 0, tt, tt)"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert gold.count(OUTPUT) == 2
    wrong = {
        # Both outputs arrive at 1.3*tt, after the 1.15*tt scoring start.
        "late_transition_1p3tt": gold.replace(OUTPUT, ", 0, 1.3*tt, 1.3*tt)"),
    }
    correct = {
        # Arrival at 1.1*tt lies between the tt deadline and the scoring start: the accepted margin.
        "inwindow_transition_1p1tt": gold.replace(OUTPUT, ", 0, 1.1*tt, 1.1*tt)"),
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
