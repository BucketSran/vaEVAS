"""Finite real-valued floor tables proved from preceding source clamps.

Unknown voltages have no assumed magnitude range. A table is installed only
after all original expression structure has been checked by its binding owner.
"""
import math
from fractions import Fraction as F

from .errors import CompileError
from .ir import Affine, Binary, Power, Select, StateRef, RealBinary, RealBoundary, RealLocal
from .integer_bits import DOMAIN_BUDGET, MINIMUM, MAXIMUM, evaluate
from .limits import check_ir


def _constant(value):
    if isinstance(value, Affine) and not value.terms and math.isfinite(value.constant):
        return F.from_float(value.constant)
    return None


def _binary_scale(value):
    return value == 0 or math.isfinite(value) and math.frexp(abs(value))[0] == .5


def real_bounds(expression, state_bounds=None, *, local_facts=None, work=None):
    """Return exact rational endpoints, with None for an unbounded endpoint.

    Clamp recognition uses the same bound operand in the predicate and value
    arm. The environment owner supplies these shared source-ordered bindings.
    This does not infer a lifetime range from a state initial value or a deck.
    """
    memo = {}

    active = set()
    def visit(value):
        if work is not None:
            work('floor_range_visit', 1)
        if id(value) in active:
            return None, None
        if id(value) not in memo:
            active.add(id(value))
            memo[id(value)] = (value, compute(value))
            active.remove(id(value))
        return memo[id(value)][1]

    def compute(value):
        constant = _constant(value)
        if constant is not None:
            return constant, constant
        if isinstance(value, Affine):
            return None, None
        if isinstance(value, StateRef):
            return (state_bounds or {}).get(value.state, (None, None))
        if isinstance(value, RealBoundary):
            return rounded(visit(value.value))
        if isinstance(value, RealLocal):
            fact = (local_facts or {}).get(id(value))
            if fact is None or fact[0] is not value:
                return None, None
            if len(fact[1]) == 1:
                return visit(fact[1][0])
            # A merged read retains both predicate operands and both values.
            # Reuse the clamp recognizer without replacing the executable read.
            if len(fact[1]) == 4:
                if work is not None:
                    work('floor_range_merge', 5)
                return selection(fact[2], *fact[1])
            return None, None
        if isinstance(value, RealBinary):
            a, b = visit(value.left), visit(value.right)
            op = value.operation
            if op == 'add':
                bounds = (a[0]+b[0] if a[0] is not None and b[0] is not None else None,
                          a[1]+b[1] if a[1] is not None and b[1] is not None else None)
            elif op == 'subtract':
                bounds = (a[0]-b[1] if a[0] is not None and b[1] is not None else None,
                          a[1]-b[0] if a[1] is not None and b[0] is not None else None)
            elif op in ('multiply', 'divide') and all(x is not None for x in (*a, *b)):
                if op == 'divide' and b[0] <= 0 <= b[1]:
                    return None, None
                values = [x*y if op == 'multiply' else x/y for x in a for y in b]
                bounds = min(values), max(values)
            else:
                return None, None
            # RN is monotone. Convert each exact endpoint to binary64 at this
            # actual source operation, including underflow and overflow.
            return rounded(bounds)
        if isinstance(value, Select):
            return selection(value.relation, value.left, value.right, value.then_value, value.else_value)
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

    def rounded(bounds):
        if work is not None:
            work('floor_range_round', 3)
        result = []
        for bound in bounds:
            if bound is None:
                result.append(None)
                continue
            try:
                number = float(bound)
            except OverflowError:
                return None, None
            if not math.isfinite(number):
                return None, None
            result.append(F.from_float(number))
        return tuple(result)

    def selection(relation, left, right, yes, no):
        rb, yb = visit(right), visit(yes)
        limit = rb[0] if rb[0] is not None and rb[0] == rb[1] else None
        if limit is not None and yb == (limit, limit) and no is left:
            low, high = visit(left)
            if relation in ('lt', 'le'):
                return max(low, limit) if low is not None else limit, max(high, limit) if high is not None else None
            if relation in ('gt', 'ge'):
                return min(low, limit) if low is not None else None, min(high, limit) if high is not None else limit
        a, b = yb, visit(no)
        return (min(a[0], b[0]) if a[0] is not None and b[0] is not None else None,
                max(a[1], b[1]) if a[1] is not None and b[1] is not None else None)

    return visit(expression)


def floor_table(argument, origin, *, state_bounds=None, constant_value=None, factory=None, local_facts=None, work=None):
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
        if work is not None:
            work('floor_shape_visit', 1)
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, Affine):
            if not math.isfinite(value.constant):
                fail('bounded floor requires finite exact binary-power scalar arithmetic')
            for term in value.terms:
                # Each coefficient is inspected by this invocation, even if
                # another source audit already checked the same Affine leaf.
                if work is not None:
                    work('floor_shape_term', 1)
                if not _binary_scale(term.coefficient):
                    fail('bounded floor requires finite exact binary-power scalar arithmetic')
        elif isinstance(value, RealBoundary):
            pending.append(value.value)
        elif isinstance(value, RealLocal):
            fact = (local_facts or {}).get(id(value))
            if fact is None or fact[0] is not value:
                fail('bounded floor requires a source-position binding')
            pending.extend(fact[1])
        elif isinstance(value, RealBinary) and value.operation in ('add', 'subtract', 'multiply', 'divide'):
            if value.operation in ('multiply', 'divide'):
                for operand in (value.left, value.right):
                    factor = _constant(operand)
                    if factor is not None and not _binary_scale(float(factor)):
                        fail('bounded floor requires exact binary-power scalar arithmetic')
                if value.operation == 'divide':
                    denominator = _constant(value.right)
                    if denominator is None or denominator == 0:
                        fail('bounded floor requires an exact binary-power constant denominator')
            # This source tree executes each RN operation in the kernel. Its
            # complete finite range is derived below, never folded or inlined.
            pending.extend((value.left, value.right))
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

    low, high = real_bounds(argument, state_bounds, local_facts=local_facts, work=work)
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
