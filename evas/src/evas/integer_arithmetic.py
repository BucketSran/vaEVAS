"""Exact interval transfer for integer division and signed remainder.

VAMS division truncates toward zero, and remainder has the numerator's sign.
These bounds describe mathematical results, not approval of source arithmetic:
callers must retain the separate signed32 checks on every original operand and
intermediate. Divisor enumeration uses the existing domain budget; execution
tables must independently bound their complete joint state domain.
"""
from .integer_bits import small_domain


def truncating_division(numerator, divisor):
    """Integer quotient without converting signed integers to floating point."""
    if divisor == 0:
        raise ValueError('integer division requires a nonzero divisor')
    magnitude = abs(numerator) // abs(divisor)
    return -magnitude if (numerator < 0) != (divisor < 0) else magnitude


def bounds(op, operands):
    """Exact interval hull for / or % by at most 256 nonzero divisors.

    Unknown operands, zero or an oversized divisor domain have no result.
    Empty input domains remain empty. A signed remainder repeats at each multiple of |divisor|;
    retaining that correlation avoids the spurious n-d*q interval expansion.
    """
    if op not in ('/', '%') or len(operands) != 2 or any(x is None for x in operands):
        return None
    (low, high), (dlow, dhigh) = operands
    if low > high or dlow > dhigh:
        return (1, 0)
    if dlow != dhigh:
        # Range transfer is bounded independently of a producer's complete
        # state grid. Execution admission must still check that joint grid.
        if dlow <= 0 <= dhigh or not small_domain([(dlow, dhigh)]):
            return None
        values = [bounds(op, [(low, high), (divisor, divisor)])
                  for divisor in range(dlow, dhigh + 1)]
        return min(value[0] for value in values), max(value[1] for value in values)
    if dlow == 0:
        return None
    divisor = dlow
    if op == '/':
        first = truncating_division(low, divisor)
        last = truncating_division(high, divisor)
        return min(first, last), max(first, last)
    width = abs(divisor)

    def nonnegative(first, last):
        if first // width == last // width:
            return first % width, last % width
        return 0, width - 1

    if low >= 0:
        return nonnegative(low, high)
    if high <= 0:
        first, last = nonnegative(-high, -low)
        return -last, -first
    negative = nonnegative(0, -low)
    positive = nonnegative(0, high)
    return -negative[1], positive[1]
