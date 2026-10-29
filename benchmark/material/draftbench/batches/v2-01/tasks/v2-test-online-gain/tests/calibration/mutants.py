"""Write the online-gain calibration candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the cases in
../cases.json. The F01 pair adds one delay to both report transitions; each output keeps
its tedge transition. skip_start_sample changes only the comparison that admits a timer
instant into the round. probe/ holds strict_start_no_margin, the c485de86 reference byte for
byte: its verdict depends on whether the backend's time point for the 20 ns timer compares
below start_time, so it is a backend-dependent probe, not a calibration candidate (see
expected.json conditions and README.md). A report that changes more than 350 ps before its
event is acausal, so that early control exists only as a synthetic waveform in the author
evidence. Run `python3 -B mutants.py <new or empty directory>` from any directory.
"""
import hashlib
from pathlib import Path

OUTPUT = ", 0, tedge, tedge)"
START = ("            // Half a sample period of margin: the sample at start_time itself counts.\n"
         "            if ($abstime >= start_time - 0.5*sample_period) begin\n")
C485DE86_REFERENCE_SHA256 = "f67567f9056e65f3ffb3f606c62065334c8b9f2e9f7a24f28cae2d7caa30ae26"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert [gold.count(p) for p in (OUTPUT, START)] == [2, 1]
    strict = gold.replace(START, "            if ($abstime >= start_time) begin\n")
    assert hashlib.sha256(strict.encode()).hexdigest() == C485DE86_REFERENCE_SHA256
    wrong = {
        # Both reports start to change 370 ps (guard + 20 ps) after their sample or begin_round event.
        "late_report_delay_370ps": gold.replace(OUTPUT, ", 370p, tedge, tedge)"),
        # Drops the sample at start_time: the first sample is taken one period late.
        "skip_start_sample": gold.replace(START, "            // Drops the sample at start_time.\n"
                                                 "            if ($abstime >= start_time + 0.5*sample_period) begin\n"),
    }
    correct = {
        # Reports start 100 ps after the event and settle at 300 ps, inside the 350 ps guard.
        "inwindow_report_delay_100ps": gold.replace(OUTPUT, ", 100p, tedge, tedge)"),
    }
    # The c485de86 reference comparison, without the margin; see expected.json conditions.
    probe = {"strict_start_no_margin": strict}
    return wrong, correct, probe


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="new or empty directory")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"{args.output}: output must be a new or empty directory")
    wrong, correct, probe = candidates()
    for group, items in (("wrong", wrong), ("correct", correct), ("probe", probe)):
        (args.output / group).mkdir(parents=True, exist_ok=True)
        for name, source in items.items():
            (args.output / group / (name + ".va")).write_text(source)
