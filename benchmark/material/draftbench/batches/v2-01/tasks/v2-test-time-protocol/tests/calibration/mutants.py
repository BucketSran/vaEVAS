"""Write the F01 timing-guard candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Only the report delay changes: each report keeps its
tr transition, and arming, counting, latching, overflow and the clears stay as
in the reference. A report that changes more than 40 ps before its event is
acausal, so that early control exists only as a synthetic waveform in the
author evidence. Run `python3 -B mutants.py <new or empty directory>` from any
directory.
"""
from pathlib import Path

REPORT = ",0,tr,tr)"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert gold.count(REPORT) == 10
    wrong = {
        # Every report starts to change 60 ps (guard + 20 ps) after its event.
        "late_report_delay_60ps": gold.replace(REPORT, ",60p,tr,tr)"),
    }
    correct = {
        # Reports start 10 ps after the event and settle at 30 ps, inside the 40 ps guard.
        "inwindow_report_delay_10ps": gold.replace(REPORT, ",10p,tr,tr)"),
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
