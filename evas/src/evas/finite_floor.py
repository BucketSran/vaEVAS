"""Finite real-valued floor tables proved from preceding source clamps.

Unknown voltages have no assumed magnitude range. A table is installed only
after all original expression structure has been checked by its binding owner.
"""
import math
from fractions import Fraction as F

from .errors import CompileError
from .ir import Affine, Binary, Power, Select, StateRef
from .integer_bits import DOMAIN_BUDGET, MINIMUM, MAXIMUM, evaluate
from .limits import check_ir


def _constant(value):
    if isinstance(value, Affine) and not value.terms and math.isfinite(value.constant):
        return F.from_float(value.constant)
    return None


def _binary_scale(value):
    return value == 0 or math.isfinite(value) and math.frexp(abs(value))[0] == .5


def real_bounds(expression, state_bounds=None):
    """Return exact rational endpoints, with None for an unbounded endpoint.

    Clamp recognition uses the same bound operand in the predicate and value
    arm. The environment owner supplies these shared source-ordered bindings.
    This does not infer a lifetime range from a state initial value or a deck.
    """
    memo = {}

    def visit(value):
        if id(value) not in memo:
            memo[id(value)] = (value, compute(value))
        return memo[id(value)][1]

    def compute(value):
        constant = _constant(value)
        if constant is not None:
            return constant, constant
        if isinstance(value, Affine):
            return None, None
        if isinstance(value, StateRef):
            return (state_bounds or {}).get(value.state, (None, None))
        if isinstance(value, Select):
            limit = _constant(value.right)
            if (limit is not None and _constant(value.then_value) == limit
                    and value.else_value is value.left):
                low, high = visit(value.left)
                if value.relation in ('lt', 'le'):
                    return max(low, limit) if low is not None else limit, max(high, limit) if high is not None else None
                if value.relation in ('gt', 'ge'):
                    return min(low, limit) if low is not None else None, min(high, limit) if high is not None else limit
            a, b = visit(value.then_value), visit(value.else_value)
            return (min(a[0], b[0]) if a[0] is not None and b[0] is not None else None,
                    max(a[1], b[1]) if a[1] is not None and b[1] is not None else None)
        if isinstance(value, Binary):
            a, b = visit(value.left), visit(value.right)
            if value.op == 'add':
                return (a[0]+b[0] if a[0] is not None and b[0] is not None else None,
                        a[1]+b[1] if a[1] is not None and b[1] is not None else None)
            if value.op == 'multiply':
                if a == (0, 0) or b == (0, 0):
                    return F(0), F(0)
                if all(endpoint is not None for endpoint in (*a, *b)):
                    products = [x*y for x in a for y in b]
                    return min(products), max(products)
        if isinstance(value, Power) and value.exponent == 1:
            return visit(value.base)
        return None, None

    return visit(expression)


def floor_table(argument, origin, *, state_bounds=None, constant_value=None, factory=None):
    """Build a real-valued Select table without changing source integer typing."""
    def fail(message, code='unsupported_floor'):
        raise CompileError(message, code=code, token=origin, instance=origin.instance)

    if isinstance(argument, Affine) and not argument.terms:
        if not math.isfinite(argument.constant):
            fail('floor requires a finite argument')
        return Affine(float(math.floor(argument.constant)), ())

    if constant_value is not None:
        if not math.isfinite(constant_value):
            fail('floor requires a finite argument')
        make = factory if factory is not None else lambda cls, *args: cls(*args)
        result = make(Affine, float(math.floor(constant_value)), ())
        # A closed source-rounded operand still executes as written. Both
        # arms return its independently established floor; the original tree
        # remains a real guard operand, rather than an unrounded replacement.
        return make(Select, 'lt', argument, result, result, result, origin)

    # This first slice admits exact binary scaling, including reciprocals of
    # powers of two. A previously rounded reciprocal must not move a floor cut.
    pending, seen = [argument], set()
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, Affine):
            if (not math.isfinite(value.constant)
                    or any(not _binary_scale(term.coefficient) for term in value.terms)):
                fail('bounded floor requires finite exact binary-power scalar arithmetic')
        elif isinstance(value, Binary) and value.op in ('add', 'multiply'):
            if value.op == 'multiply':
                for operand in (value.left, value.right):
                    factor = _constant(operand)
                    if factor is not None and not _binary_scale(float(factor)):
                        fail('bounded floor requires exact binary-power scalar arithmetic')
            pending.extend((value.left, value.right))
        elif isinstance(value, Power) and value.exponent == 1:
            pending.append(value.base)
        elif isinstance(value, Select):
            pending.extend((value.left, value.right, value.then_value, value.else_value))
        elif isinstance(value, StateRef):
            bound = (state_bounds or {}).get(value.state)
            if bound is None or any(x is None for x in bound) or bound[0] > bound[1]:
                fail('event floor state needs a finite range proved before this source use')
        else:
            fail('bounded floor requires source-clamped piecewise-affine input expressions')

    low, high = real_bounds(argument, state_bounds)
    if low is None or high is None:
        fail('floor requires a finite range proved before the call; later clamps and deck ranges are not proofs')
    first, last = math.floor(low), math.floor(high)
    if first < MINIMUM or last > MAXIMUM:
        fail('bounded floor values must remain within signed 32-bit range')
    if last-first+1 > DOMAIN_BUDGET:
        fail('bounded floor exceeds partition budget (256)', 'resource_budget')

    def tree(start, end):
        if start == end:
            return Affine(float(start), ())
        middle = (start+end+1)//2
        return Select('lt', argument, Affine(float(middle), ()),
                      tree(start, middle-1), tree(middle, end), origin)

    result = tree(first, last)
    if first == last:
        result = Select('lt', argument, Affine(first+.5, ()), result, result, origin)
    check_ir(result, origin)
    return result


def map_integer_leaves(expression, operation, constant):
    """Compose a constant mask/shift with an existing integer-valued table.

    The caller still audits original source types, all arithmetic operands,
    signed ranges and resource limits. Every guard and its origin survives.
    """
    if (operation not in ('&', '<<', '>>') or not isinstance(expression, Select)
            or not isinstance(constant, Affine) or constant.terms
            or not constant.constant.is_integer()):
        return None
    right = int(constant.constant)
    if not MINIMUM <= right <= MAXIMUM:
        return None
    memo = {}

    def visit(value):
        if id(value) in memo:
            return memo[id(value)][1]
        if isinstance(value, Select):
            then, other = visit(value.then_value), visit(value.else_value)
            if then is None or other is None:
                return None
            result = Select(value.relation, value.left, value.right, then, other, value.origin)
        elif (isinstance(value, Affine) and not value.terms
              and math.isfinite(value.constant) and value.constant.is_integer()
              and MINIMUM <= value.constant <= MAXIMUM):
            result = Affine(float(evaluate(operation, int(value.constant), right)), ())
        else:
            return None
        memo[id(value)] = value, result
        return result

    return visit(expression)
