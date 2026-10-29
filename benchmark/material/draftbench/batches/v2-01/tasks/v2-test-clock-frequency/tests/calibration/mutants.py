"""Write the F01 timing-guard candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Only the report delay changes: each report keeps its
tr transition, and the period measurement, history and clears stay as in the
reference. A report that changes more than 80 ps before its event is acausal, so
that early control exists only as a synthetic waveform in the author evidence.
Run `python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

REPORT = ",0,tr,tr)"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert gold.count(REPORT) == 3
    wrong = {
        # Every report starts to change 100 ps (guard + 20 ps) after its event.
        "late_report_delay_100ps": gold.replace(REPORT, ",100p,tr,tr)"),
    }
    correct = {
        # Reports start 50 ps after the event and settle at 70 ps, inside the 80 ps guard.
        "inwindow_report_delay_50ps": gold.replace(REPORT, ",50p,tr,tr)"),
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
