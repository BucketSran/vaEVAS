"""Keep physical execution accuracy separate from an extra root-reference check."""
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction


class Verdict(Enum):
    PASS = 'pass'
    FAIL = 'fail'
    UNKNOWN = 'unknown'
    REJECTED = 'rejected'


@dataclass(frozen=True)
class LayeredVerdict:
    physical: Verdict
    root_reference: Verdict


def assess_layers(response, *, physical_expected, root_expected, budget, node='y'):
    """Assess independent answers; None explicitly means no such certificate.

    Physical PASS also requires the published enclosure to contain the answer
    and fit the original budget around the actual returned voltage. The extra
    root-reference verdict uses its own unchanged answer and the same budget.
    """
    if response is None:
        return LayeredVerdict(Verdict.REJECTED, Verdict.UNKNOWN)
    nominal = Fraction(response['solutions'][-1]['voltages'][response['nodes'].index(node)])
    allowance = Fraction(budget)
    physical = Verdict.UNKNOWN
    if physical_expected is not None:
        expected = Fraction(physical_expected)
        evidence = response['observation_evidence']
        lo, hi = map(Fraction, evidence['voltage_bounds_V'][-1][evidence['nodes'].index(node)])
        physical = Verdict.PASS if (lo <= expected <= hi
            and abs(nominal-expected) <= allowance
            and max(abs(nominal-lo), abs(hi-nominal)) <= allowance) else Verdict.FAIL
    root = Verdict.UNKNOWN if root_expected is None else (
        Verdict.PASS if abs(nominal-Fraction(root_expected)) <= allowance else Verdict.FAIL)
    return LayeredVerdict(physical, root)
