"""Finite signed32 bit operations (VAMS 2.4 §§4.2.9, 4.2.11).

Python's unbounded signed shifts are deliberately not the language operation.
The finite-domain helpers bound work before constructing any decision tree.
"""
OPS = frozenset(('&', '|', '^', 'unary~', '<<', '>>'))
MINIMUM, MAXIMUM, MASK = -2147483648, 2147483647, 0xffffffff
DOMAIN_BUDGET = 256


def evaluate(op, left, right=None):
    if not MINIMUM <= left <= MAXIMUM or right is not None and not MINIMUM <= right <= MAXIMUM:
        raise ValueError('bitwise operands must remain within signed 32-bit range')
    a = left & MASK
    if op == 'unary~':
        value = a ^ MASK
    elif op == '&':
        value = a & (right & MASK)
    elif op == '|':
        value = a | (right & MASK)
    elif op == '^':
        value = a ^ (right & MASK)
    elif op in ('<<', '>>'):
        # The LRM treats the shift count as unsigned. A count at least the
        # width discards every source bit; no huge Python shift is allocated.
        count = right & MASK
        value = 0 if count >= 32 else ((a << count) & MASK if op == '<<' else a >> count)
    else:
        raise ValueError('unknown bitwise operation')
    return value if value <= MAXIMUM else value - (MASK + 1)


def small_domain(bounds):
    size = 1
    for low, high in bounds:
        if low > high or low < MINIMUM or high > MAXIMUM:
            return False
        size *= high - low + 1
        if size > DOMAIN_BUDGET:
            return False
    return True


def bounds(op, operands):
    """Sound enclosure, with bounded exact transfer for small input domains."""
    if any(item is None for item in operands):
        return None
    if any(low > high for low, high in operands):
        return (1, 0)
    if small_domain(operands):
        left = range(operands[0][0], operands[0][1] + 1)
        right = [None] if len(operands) == 1 else range(operands[1][0], operands[1][1] + 1)
        values = [evaluate(op, a, b) for a in left for b in right]
        return min(values), max(values)
    # Every bit of x & a nonnegative constant is also a bit of that mask,
    # regardless of x's sign. This enclosure does not assume x's initial value.
    if op == '&':
        for low, high in operands:
            if low == high and 0 <= low <= MAXIMUM:
                return 0, low
    if op == 'unary~':
        low, high = operands[0]
        if MINIMUM <= low <= high <= MAXIMUM:
            return -high - 1, -low - 1
    return None


def integer_type(expr, variables, parameters, genvars=()):
    """Source integer typing shared by instance and parameter bit lowering."""
    if expr.result_type == 'real':
        return False
    if expr.result_type == 'integer':
        return True
    if expr.op == 'number':
        return expr.token.text.isdecimal() or expr.token.text in genvars
    if expr.op == 'parameter':
        return variables.get(expr.value) == 'integer' or parameters.get(expr.value) == 'integer'
    if expr.op == 'checked':
        return integer_type(expr.args[0], variables, parameters, genvars)
    if expr.op in ('<', '<=', '>', '>=', '==', '!=', '&&', '||', 'unary!'):
        return True
    args = expr.args[1:] if expr.op == 'ternary' else expr.args
    if expr.op == 'ternary' or expr.op in OPS or expr.op in ('+', '-', '*', '/', '%', 'unary+', 'unary-'):
        return all(integer_type(arg, variables, parameters, genvars) for arg in args)
    return False
