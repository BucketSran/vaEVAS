"""Write the F01 scoring-start candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Only the output transition time changes; the sample, the
region decision and the residue stay as in the reference. Run
`python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

OUTPUT = ", 0, tedge, tedge)"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert gold.count(OUTPUT) == 3
    wrong = {
        # The outputs arrive at 1.3*tedge, after the 1.15*tedge scoring start.
        "late_transition_1p3tedge": gold.replace(OUTPUT, ", 0, 1.3*tedge, 1.3*tedge)"),
    }
    correct = {
        # Arrival at 1.1*tedge lies between the tedge deadline and the scoring start: the accepted margin.
        "inwindow_transition_1p1tedge": gold.replace(OUTPUT, ", 0, 1.1*tedge, 1.1*tedge)"),
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
