"""Write the F01 timing-guard candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the
cases in ../cases.json. Each candidate changes one delay: the report delay
(offset_est, vinp, vinn, valid, status), the request delay, or the request
schedule. Every output keeps its tr transition, and the search law, the gap and
the timeout logic stay as in the reference. A report that changes more than 80 ps
before its event is acausal, so that early control exists only as a synthetic
waveform in the author evidence. Run `python3 -B mutants.py <new or empty directory>`
from any directory.
"""
from pathlib import Path

ESTIMATE = "transition(estimate,0,tr,tr)"   # vinp, vinn and offset_est
VALID = "transition((state==1)?1.0:0.0,0,tr,tr)"
STATUS = "transition(state,0,tr,tr)"
REQUEST = "transition(req,0,tr,tr)"
FIRST = "next_request=1n;"
NEXT = "next_request=$abstime+gap;"


def reports(gold, delay):
    return (gold.replace(ESTIMATE, f"transition(estimate,{delay},tr,tr)")
                .replace(VALID, f"transition((state==1)?1.0:0.0,{delay},tr,tr)")
                .replace(STATUS, f"transition(state,{delay},tr,tr)"))


def schedule(gold, advance):
    return gold.replace(FIRST, f"next_request=1n-{advance};").replace(NEXT, f"next_request=$abstime+gap-{advance};")


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert [gold.count(p) for p in (ESTIMATE, VALID, STATUS, REQUEST, FIRST, NEXT)] == [3, 1, 1, 1, 1, 1]
    wrong = {
        # Reports start to change 100 ps (guard + 20 ps) after the response or timeout.
        "late_report_delay_100ps": reports(gold, "100p"),
        # request rises and falls 100 ps late: its first crossing is 100 ps after 1.01 ns.
        "late_request_delay_100ps": gold.replace(REQUEST, "transition(req,100p,tr,tr)"),
        # Requests are issued 100 ps early: at 0.9 ns and 100 ps before response + gap.
        "early_request_100ps": schedule(gold, "100p"),
    }
    correct = {
        # Reports start 50 ps after the event and settle at 70 ps, inside the 80 ps allowance.
        "inwindow_report_delay_50ps": reports(gold, "50p"),
        # request is 50 ps late or early, inside the 80 ps request-time allowance.
        "inwindow_request_delay_50ps": gold.replace(REQUEST, "transition(req,50p,tr,tr)"),
        "inwindow_early_request_50ps": schedule(gold, "50p"),
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
