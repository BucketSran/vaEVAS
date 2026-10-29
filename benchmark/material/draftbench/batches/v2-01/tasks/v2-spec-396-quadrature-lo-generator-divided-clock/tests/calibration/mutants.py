"""Write the F01 scoring-start candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Only the output transition time changes; the state
sequence, the qualification count and the clears stay as in the reference.
Run `python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

OUTPUT = ", 0, tr, tr)"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert gold.count(OUTPUT) == 4
    wrong = {
        # The four outputs arrive at 1.3*tr, after the 1.15*tr scoring start.
        "late_transition_1p3tr": gold.replace(OUTPUT, ", 0, 1.3*tr, 1.3*tr)"),
    }
    correct = {
        # Arrival at 1.1*tr lies between the tr deadline and the scoring start: the accepted margin.
        "inwindow_transition_1p1tr": gold.replace(OUTPUT, ", 0, 1.1*tr, 1.1*tr)"),
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
