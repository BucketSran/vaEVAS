"""Per-use real range facts from prior assignments in the same event body.

Each callback starts unknown. These facts are not a stored-state invariant or
an initial-value substitution. Original assignments and numerical boxes remain
in the executable program; only finite floor partition construction uses them.
"""
from fractions import Fraction as F
from dataclasses import fields, is_dataclass
import math

from .errors import CompileError
from .limits import MAX_IR_ITEMS
from .integer_arithmetic import truncating_division
from .syntax import Assignment, Conditional, Display, Loop
from .condition_domains import compact_condition, compact_domains

UNKNOWN = (None, None)
MAX_BITS = 4096


def _bounded(value):
    return value if value.numerator.bit_length() <= MAX_BITS and value.denominator.bit_length() <= MAX_BITS else None


def _edge(value, upper):
    """Include binary64 rounding, including folding of constant source trees."""
    if _bounded(value) is None:
        return None
    try:
        nominal = float(value)
    except OverflowError:
        return None
    if not math.isfinite(nominal):
        return None
    exact = F.from_float(nominal)
    if upper and exact < value:
        nominal = math.nextafter(nominal, math.inf)
    elif not upper and exact > value:
        nominal = math.nextafter(nominal, -math.inf)
    return F.from_float(nominal) if math.isfinite(nominal) else None


def _hull(a, b):
    return (min(a[0], b[0]) if a[0] is not None and b[0] is not None else None,
            max(a[1], b[1]) if a[1] is not None and b[1] is not None else None)


def floor_use_sites(bodies, names, parameters, *, integer_type):
    """Return per-use source environments and argument bounds, joining shared uses."""
    facts, work = {}, 0

    def has_floor(body):
        pending, seen = [body], set()
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            if getattr(item, 'op', None) == 'floor':
                return True
            if is_dataclass(item):
                pending.extend(getattr(item, field.name) for field in fields(item))
            elif isinstance(item, (tuple, list)):
                pending.extend(item)
            elif isinstance(item, dict):
                pending.extend(item.values())
        return False

    def tick():
        nonlocal work
        work += 1
        if work > MAX_IR_ITEMS:
            raise CompileError('event real range audit exceeds source budget', code='resource_budget')

    def bounds(root, env):
        memo = {}
        def visit(expr):
            if id(expr) in memo:
                return memo[id(expr)]
            tick()
            value = UNKNOWN
            if expr.op in ('number', 'parameter'):
                if expr.op == 'parameter' and str(expr.value) in env:
                    value = env[str(expr.value)]
                else:
                    try:
                        number = float(expr.value if expr.op == 'number' else parameters(str(expr.value)))
                        if math.isfinite(number):
                            exact = F.from_float(number)
                            value = exact, exact
                    except (CompileError, TypeError, ValueError, OverflowError):
                        pass
            elif expr.op == 'checked':
                value = visit(expr.args[0])
            elif expr.op == 'unary+':
                value = visit(expr.args[0])
            elif expr.op == 'unary-':
                low, high = visit(expr.args[0])
                value = (-high if high is not None else None, -low if low is not None else None)
            elif expr.op == 'ternary':
                value = _hull(visit(expr.args[1]), visit(expr.args[2]))
            elif expr.op in ('+', '-', '*', '/'):
                a, b = visit(expr.args[0]), visit(expr.args[1])
                if expr.op in ('+', '-'):
                    if expr.op == '-':
                        b = (-b[1] if b[1] is not None else None, -b[0] if b[0] is not None else None)
                    value = (_edge(a[0]+b[0], False) if a[0] is not None and b[0] is not None else None,
                             _edge(a[1]+b[1], True) if a[1] is not None and b[1] is not None else None)
                elif all(v is not None for v in (*a, *b)):
                    if expr.op == '*':
                        products = [_bounded(x*y) for x in a for y in b]
                    elif b[0] == b[1] and b[0] != 0:
                        if integer_type(expr):
                            try:
                                products = [F(truncating_division(int(x), int(b[0])))
                                            for x in a] if all(x.denominator == 1 for x in (*a, *b)) else []
                            except ValueError:
                                products = []
                        else:
                            products = [_bounded(x/b[0]) for x in a]
                    else:
                        products = []
                    if products and all(v is not None for v in products):
                        value = _edge(min(products), False), _edge(max(products), True)
            memo[id(expr)] = value
            return value
        return visit(root)

    def collect(root, env):
        pending, seen = [root], set()
        while pending:
            expr = pending.pop()
            if id(expr) in seen:
                continue
            seen.add(id(expr))
            tick()
            if expr.op == 'floor':
                previous = facts.get(id(expr))
                referenced, operands = set(), list(expr.args)
                visited = set()
                while operands:
                    operand = operands.pop()
                    if id(operand) in visited:
                        continue
                    visited.add(id(operand))
                    if operand.op == 'parameter' and str(operand.value) in env:
                        referenced.add(str(operand.value))
                    operands.extend(operand.args)
                current = {name: env[name] for name in referenced}
                if previous is not None:
                    current = {name: _hull(value, previous[1][name]) for name, value in current.items()}
                argument = bounds(expr.args[0], env) if len(expr.args) == 1 else UNKNOWN
                if previous is not None:
                    argument = _hull(argument, previous[2])
                facts[id(expr)] = expr, current, argument
            pending.extend(expr.args)

    def refine(statement, env):
        return refine_operands(statement.relation, statement.left, statement.right, env)

    def refine_operands(relation, left, right, env):
        if compact_condition(relation, left, right):
            for _ in range(3):
                tick()  # forwarding callback and captured references
            def work(count):
                for _ in range(count):
                    tick()
            return compact_domains(relation,left,right,env,
                refine=refine_operands,hull=_hull,work=work)
        collect(left, env)
        collect(right, env)
        yes, no = dict(env), dict(env)
        if left.op != 'parameter' or str(left.value) not in env:
            left, right = right, left
            relation = {'<': '>', '<=': '>=', '>': '<', '>=': '<='}[relation]
        if left.op != 'parameter' or str(left.value) not in env:
            return yes, no
        point = bounds(right, env)
        if point[0] is None or point[0] != point[1]:
            return yes, no
        name, limit = str(left.value), point[0]
        low, high = env[name]
        lower = max(low, limit) if low is not None else limit
        upper = min(high, limit) if high is not None else limit
        below, above = (low, upper), (lower, high)
        arms = (below, above) if relation in ('<', '<=') else (above, below)
        # Closed endpoints conservatively include strict real boundaries.
        # Impossible branches retain no range proof; never use a dead arm to
        # fabricate a finite partition or skip its original source audit.
        for target, value in zip((yes, no), arms):
            target[name] = UNKNOWN if all(x is not None for x in value) and value[0] > value[1] else value
        return yes, no

    def flow(items, env):
        env = dict(env)
        for statement in items:
            tick()
            if isinstance(statement, Conditional):
                yes, no = refine(statement, env)
                a, b = flow(statement.then_body, yes), flow(statement.else_body, no)
                env = {name: _hull(a[name], b[name]) for name in env}
            elif isinstance(statement, Assignment):
                collect(statement.rhs, env)
                if statement.index is not None:
                    collect(statement.index, env)
                    # Dynamic/array slot facts are outside this scalar slice.
                    for name in env:
                        if name.startswith(statement.name+'['):
                            env[name] = UNKNOWN
                elif statement.name in env:
                    env[statement.name] = bounds(statement.rhs, env)
            elif isinstance(statement, Display):
                for arg in statement.args:
                    collect(arg, env)
            elif isinstance(statement, Loop):
                for arg in (statement.start, statement.limit, statement.update):
                    collect(arg, env)
                flow(statement.body, {name: UNKNOWN for name in env})
                # No trip-count or fixed-point assumption for a real loop.
                env = {name: UNKNOWN for name in env}
        return env

    for body in bodies:
        if has_floor(body):
            flow(body, {name: UNKNOWN for name in names})
    return facts


def integer_floor_bounds(facts, expr):
    """Value-range transfer only; floor retains its real source type."""
    fact = facts.get(id(expr))
    if fact is None or fact[0] is not expr:
        return None
    low, high = fact[2]
    if low is None or high is None or low > high:
        return None
    return math.floor(low), math.floor(high)
