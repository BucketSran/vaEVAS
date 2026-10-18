"""Exact finite mathematical tables lowered into the existing Select IR.

The current contract is a positive binary-power constant base and a separately
proven source-integer exponent in [-32,32]. Every leaf is an exactly representable
binary64 power of two. No general real pow approximation or new opcode is used.
"""
import math

from .integer_bits import small_domain
from .ir import Affine, Select
from .limits import check_ir


def power(base, exponent, bounds, origin):
    """Return a finite real-valued pow table, or None outside this contract.

    The caller owns source integer typing, original operand validation and the
    sound lifetime bound. This function never infers a bound from a deck or an
    initial value. A nonconstant singleton keeps its original exponent read.
    """
    if not isinstance(base, Affine) or base.terms or bounds is None:
        return None
    value = base.constant
    if not math.isfinite(value) or value <= 0:
        return None
    fraction, binary_exponent = math.frexp(value)
    if fraction != 0.5:
        return None
    low, high = bounds
    if (not isinstance(low, (int, float)) or not isinstance(high, (int, float))
            or low > high or low < -32 or high > 32
            or not math.isfinite(low) or not math.isfinite(high)
            or not float(low).is_integer() or not float(high).is_integer()):
        return None
    low, high = int(low), int(high)
    if low < -32 or high > 32 or not small_domain([(low, high)]):
        return None
    values = {}
    for number in range(low, high + 1):
        exact_exponent = (binary_exponent - 1) * number
        if not -1074 <= exact_exponent <= 1023:
            raise ValueError('finite pow table requires every original value to remain finite and exactly representable')
        values[number] = Affine(math.ldexp(1.0, exact_exponent), ())

    def tree(first, last):
        if first == last:
            return values[first]
        middle = (first + last + 1) // 2
        return Select('lt', exponent, Affine(float(middle), ()),
                      tree(first, middle - 1), tree(middle, last), origin)

    result = tree(low, high)
    if low == high and not (isinstance(exponent, Affine) and not exponent.terms):
        result = Select('lt', exponent, Affine(low + 0.5, ()), result, result, origin)
    check_ir(result, origin)
    return result
