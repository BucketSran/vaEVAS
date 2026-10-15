"""Harbor adapter for the unchanged canonical VA07 mathematical oracle.

The common circuit task owns source validation, Spectre and archive handling.
Only a structurally complete waveform's BehavioralRejection becomes graded false;
all structural/data errors propagate as checker errors through that boundary.
"""
import triangle_oscillator as oracle


def evaluate(rows, case, work=None):
    try:
        return oracle.evaluate(rows, case)
    except oracle.BehavioralRejection as exc:
        return dict(passed=False, failures=[str(exc)])
