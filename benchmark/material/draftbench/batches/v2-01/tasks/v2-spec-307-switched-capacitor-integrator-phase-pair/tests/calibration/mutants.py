"""Write the F01 scoring-start candidates derived from the three solution files.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Each candidate is a directory with all three delivered
files. Only the output transition time of integrator_state_cell changes; the
sampler, the top and the integration law stay as in the reference. Run
`python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

FILES = ("circuit.va", "integrator_state_cell.va", "sample_phase_cell.va")
OUTPUT = ", 0, tr, tr)"


def candidates():
    solution = Path(__file__).resolve().parents[2] / "solution"
    gold = {name: (solution / name).read_text() for name in FILES}
    integrator = gold["integrator_state_cell.va"]
    assert integrator.count(OUTPUT) == 3
    variant = lambda scale: {**gold, "integrator_state_cell.va":  # noqa: E731
                             integrator.replace(OUTPUT, f", 0, {scale}*tr, {scale}*tr)")}
    wrong = {
        # The public outputs arrive at 1.3*tr, after the 1.15*tr scoring start.
        "late_integrator_transition_1p3tr": variant("1.3"),
    }
    correct = {
        # Arrival at 1.1*tr lies between the tr deadline and the scoring start: the accepted margin.
        "inwindow_integrator_transition_1p1tr": variant("1.1"),
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
        for name, files in items.items():
            (args.output / group / name).mkdir(parents=True)
            for file_name, source in files.items():
                (args.output / group / name / file_name).write_text(source)
