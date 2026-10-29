"""Write the F01 scoring-start candidates derived from the three solution files.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Each candidate is a directory with all three delivered
files. Only the output delay of synchronous_lp_state changes; the core, the top,
the filter law and the clears stay as in the reference. Run
`python3 -B mutants.py <new or empty directory>` from any directory.

In the reference a public output reaches its value 3.5*tr after an active chop
crossing: the notification starts 2*tr after it, crosses vth at 2.5*tr, and the
low-pass transition takes tr.
"""
from pathlib import Path

FILES = ("circuit.va", "chopper_gain_core.va", "synchronous_lp_state.va")
OUTPUT = ",0,tr,tr)"


def candidates():
    solution = Path(__file__).resolve().parents[2] / "solution"
    gold = {name: (solution / name).read_text() for name in FILES}
    lp = gold["synchronous_lp_state.va"]
    assert lp.count(OUTPUT) == 4
    variant = lambda delay: {**gold, "synchronous_lp_state.va": lp.replace(OUTPUT, f",{delay},tr,tr)")}  # noqa: E731
    wrong = {
        # The public outputs arrive 4.3*tr after the chop crossing, after the 4.1*tr scoring start.
        "late_lp_output_delay_0p8tr": variant("0.8*tr"),
    }
    correct = {
        # Arrival at 4.05*tr lies between the 4*tr deadline and the scoring start: the accepted margin.
        "inwindow_lp_output_delay_0p55tr": variant("0.55*tr"),
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
