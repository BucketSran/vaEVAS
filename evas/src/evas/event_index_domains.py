"""Per-source-use integer flow facts for dynamic array index admission (N02).

The entry invariant is one exact integer interval per integer state, computed
over the default/initialization values, every event and final_step writer in
sequential use-site order, branch fork/join narrowing and weak dynamic-slot
updates. Iteration is bounded; states that fail to converge are widened to the
full signed-32 TOP interval and the result is verified with an explicit
post-fixpoint check (every event transformer maps the reported invariant into
itself). TOP is an overapproximation for stored values, never a legal index.

N02 consumes these facts to admit event/final_step dynamic array indices.
N03 must extend this walker with statement exit, checked-intermediate and
loop header/exit proofs before runtime-loop admission. The current index-use
facts are not that complete interface. All arithmetic below runs on exact Python integers; clamping to the
signed-32 range models what a stored state can hold, while the existing typed
overflow obligations at the actual lowering site stay untouched.
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from .syntax import Assignment, Conditional, Display

SIGNED32_MIN, SIGNED32_MAX = -2147483648, 2147483647
#: Conservative domain of a successfully stored integer state.
TOP = (SIGNED32_MIN, SIGNED32_MAX)
#: Empty domain (an unreachable branch); lo > hi by convention.
BOTTOM = (1, 0)


def hull(a, b):
    """Join two intervals; BOTTOM is the identity."""
    if a == BOTTOM:
        return b
    if b == BOTTOM:
        return a
    return (min(a[0], b[0]), max(a[1], b[1]))


def clamp(interval):
    low, high = interval
    return (max(low, SIGNED32_MIN), min(high, SIGNED32_MAX))


def within(interval, low, high):
    return interval != BOTTOM and low <= interval[0] and interval[1] <= high


@dataclass(frozen=True)
class IntervalDomain:
    """Immutable interval with the report's exact-integer operations."""
    low: int
    high: int


@dataclass(frozen=True)
class IndexProvenance:
    """Source classification of one dynamic index use site."""
    array: str
    access: str                     # 'read' or 'write'
    location: str                   # '<source>:<line>:<column>'
    #: Integer states the index expression reads, in source order.
    states: tuple[str, ...]
    #: Whether the index also reads integer parameters or literals only.
    constant_inputs: bool


@dataclass(frozen=True)
class FlowFacts:
    """Index-use facts for N02 admission, not statement-transfer certificates.

    `entry` and `exit` both hold the environment at index evaluation. The latter
    is reserved for a future interface and does not certify the post-assignment
    state. `index` is the evaluated interval at this sequential position;
    `provenance` records the source and state dependencies. N03 additionally
    needs actual statement exits and checked integer intermediate ranges.
    """
    entry: Mapping[str, tuple[int, int]]
    exit: Mapping[str, tuple[int, int]]
    index: tuple[int, int]
    provenance: IndexProvenance


def _literal(expr):
    text = expr.token.text
    if text.isdecimal() or expr.token.kind == 'name':
        value = expr.value
        if isinstance(value, (int, float)) and float(value).is_integer():
            return int(value)
    return None


def evaluate(expr, env, parameters, arrays, on_read=None):
    """Interval of a typed-integer expression, or None when unknown.

    Unknown operands (real-typed or non-integer inputs) yield None, which the
    caller reports as TOP. Residual array reads overapproximate to the hull of
    every declared element; the index itself is irrelevant for soundness.
    """
    if expr is None:
        return None
    if expr.op == 'index':
        if on_read is not None:
            on_read(expr)
        elements = arrays.get(str(expr.value), ())
        values = [env.get(f'{expr.value}[{k}]') for k in elements]
        if any(value is None for value in values) or not values:
            return None
        result = BOTTOM
        for value in values:
            result = hull(result, value)
        return result
    if expr.op == 'number':
        value = _literal(expr)
        return None if value is None else (value, value)
    if expr.op == 'parameter':
        name = str(expr.value)
        if name in env:
            return env[name]
        try:
            value = parameters(name)
        except Exception:
            return None
        if isinstance(value, (int, float)) and float(value).is_integer():
            value = int(value)
            return (value, value)
        return None
    if expr.op == 'checked':
        return evaluate(expr.args[0], env, parameters, arrays, on_read)
    args = [evaluate(arg, env, parameters, arrays, on_read) for arg in expr.args]
    if expr.op == 'unary+':
        return args[0]
    if expr.op == 'unary-':
        return None if args[0] is None else (-args[0][1], -args[0][0])
    if expr.op == '+':
        return None if None in args else (args[0][0] + args[1][0], args[0][1] + args[1][1])
    if expr.op == '-':
        return None if None in args else (args[0][0] - args[1][1], args[0][1] - args[1][0])
    if expr.op == '*':
        if None in args:
            return None
        products = [x * y for x in args[0] for y in args[1]]
        return (min(products), max(products))
    if expr.op in ('/', '%'):
        if None in args:
            return None
        (dlow, dhigh) = args[1]
        if dlow != dhigh or dlow == 0:
            return None
        divisor = dlow
        low, high = args[0]
        # Truncation toward zero, matching the existing quotient lowering.
        def quotient(value):
            magnitude = abs(value) // abs(divisor)
            return -magnitude if (value < 0) != (divisor < 0) else magnitude
        first, last = quotient(low), quotient(high)
        quotient_domain = (min(first, last), max(first, last))
        if expr.op == '/':
            return quotient_domain
        # remainder = numerator - divisor * quotient, as an interval product.
        products = [divisor * y for y in quotient_domain]
        return (low - max(products), high - min(products))
    return None


def refine(relation, left, right, env, parameters, arrays):
    """Narrow integer states against exact integer constants.

    First version keeps only the fully proven rule: one bare integer state
    compared with an exact integer constant (either operand order). All other
    conditions keep their entry domains; both branches and strict boundaries
    are covered, and an impossible branch becomes BOTTOM.
    """
    yes, no = dict(env), dict(env)

    def interval_of(expr):
        value = evaluate(expr, env, parameters, arrays)
        if value is None or value == BOTTOM or value[0] != value[1]:
            return None
        return value[0]

    def apply(name, relation, threshold):
        current = env.get(name)
        if current is None or current == BOTTOM:
            return
        low, high = current
        if relation == '<':
            arms = (low, min(high, threshold - 1)), (max(low, threshold), high)
        elif relation == '<=':
            arms = (low, min(high, threshold)), (max(low, threshold + 1), high)
        elif relation == '>':
            arms = (max(low, threshold + 1), high), (low, min(high, threshold))
        else:
            arms = (max(low, threshold), high), (low, min(high, threshold - 1))
        yes[name], no[name] = arms

    swapped = {'<': '>', '<=': '>=', '>': '<', '>=': '<='}
    if left.op == 'parameter' and str(left.value) in env:
        threshold = interval_of(right)
        if threshold is not None:
            apply(str(left.value), relation, threshold)
    elif right.op == 'parameter' and str(right.value) in env:
        threshold = interval_of(left)
        if threshold is not None:
            apply(str(right.value), swapped[relation], threshold)
    return yes, no


def flow(statements, env, *, arrays, parameters, on_use=None):
    """Abstract one event body from `env`; returns the exit environment.

    Scalar assignments strong-update their target; dynamic array writes
    weak-update every possible slot (strong only for a proven singleton index).
    Conditionals fork narrowed environments and join on return. `on_use` receives
    every dynamic index use with the statement-local environment, which is how
    admission (and later N03 loop proofs) consume per-site facts.
    """
    env = dict(env)

    def execute(statements, current):
        for statement in statements:
            if isinstance(statement, Conditional):
                def branch_reads(expr, env=current):
                    if on_use is not None:
                        on_use('read', expr, env)
                evaluate(statement.left, current, parameters, arrays, branch_reads)
                evaluate(statement.right, current, parameters, arrays, branch_reads)
                yes, no = refine(statement.relation, statement.left, statement.right,
                                 current, parameters, arrays)
                then_exit = execute(statement.then_body, yes)
                else_exit = execute(statement.else_body, no)
                joined = dict(current)
                for name in joined:
                    joined[name] = hull(then_exit.get(name, BOTTOM), else_exit.get(name, BOTTOM))
                current = joined
            elif isinstance(statement, Display):
                def display_reads(expr, env=current):
                    if on_use is not None:
                        on_use('read', expr, env)
                for arg in statement.args:
                    evaluate(arg, current, parameters, arrays, display_reads)
            elif isinstance(statement, Assignment):
                def rhs_reads(expr, env=current):
                    if on_use is not None:
                        on_use('read', expr, env)
                if statement.index is not None:
                    index = evaluate(statement.index, current, parameters, arrays)
                    if on_use is not None:
                        on_use('write', statement, current, index)
                value = evaluate(statement.rhs, current, parameters, arrays, rhs_reads)
                if statement.index is not None:
                    elements = arrays.get(statement.name, ())
                    value = TOP if value is None else clamp(value)
                    singleton = index is not None and index != BOTTOM and index[0] == index[1]
                    for element in elements:
                        name = f'{statement.name}[{element}]'
                        if name not in current:
                            continue
                        if singleton and element == index[0]:
                            current[name] = value
                        else:
                            current[name] = hull(current[name], value)
                elif statement.name in current:
                    current[statement.name] = TOP if value is None else clamp(value)
        return current

    return execute(statements, env)


def entry_domains(event_bodies, initial_bounds, *, arrays, parameters,
                  states, passes=32):
    """Global entry invariant over defaults, initialization and all writers.

    Returns `(domains, widened)`. Iteration is bounded by `passes`; states that
    keep changing are widened to TOP and one further pass runs the explicit
    post-fixpoint verification `T_e(R) ⊆ R` for every event body. A model that
    still fails verification is rejected rather than reported as proven.
    """
    domains = {name: initial_bounds.get(name, TOP) for name in states}

    def step(current):
        joined = dict(current)
        for body in event_bodies:
            exit_domains = flow(body, current, arrays=arrays, parameters=parameters)
            for name in joined:
                joined[name] = hull(joined[name], exit_domains.get(name, BOTTOM))
        return joined

    def verify(current):
        for body in event_bodies:
            exit_domains = flow(body, current, arrays=arrays, parameters=parameters)
            for name, value in exit_domains.items():
                if name in current and hull(current[name], value) != current[name]:
                    return False
        return True

    widened = False
    for _ in range(passes):
        nxt = step(domains)
        if nxt == domains:
            break
        domains = nxt
    else:
        # Budget exhausted without closure: widen every still-moving state.
        probe = step(domains)
        domains = {name: TOP if probe[name] != domains[name] else domains[name]
                   for name in domains}
        widened = True
    if not verify(domains):
        raise ValueError('event integer domains failed the post-fixpoint verification')
    return domains, widened


def use_site_facts(event_bodies, entry, *, arrays, parameters, location_of):
    """Walk every event body once and collect FlowFacts per dynamic use site.

    Keyed by `id()` of the residual index expression (writes: the statement's
    index expression). The returned pair list keeps the source nodes alive so
    ids stay valid while the compiler lowers the same tree.
    """
    facts = {}
    holder = []

    def index_states(expr):
        states = []

        def visit(item):
            if item.op == 'parameter' and str(item.value) in entry:
                states.append(str(item.value))
            for arg in item.args:
                visit(arg)

        visit(expr)
        return tuple(states)

    def record(access, key, site, states_expr, array, env, index):
        facts[id(key)] = (key, FlowFacts(
            entry=dict(env),
            exit=dict(env),
            index=TOP if index is None else index,
            provenance=IndexProvenance(
                array=array,
                access=access,
                location=location_of(site.token),
                states=index_states(states_expr),
                constant_inputs=not index_states(states_expr),
            )))

    def on_use(access, node, env, index=None):
        if access == 'write':
            record('write', node.index, node.index, node.index, str(node.name), env, index)
        else:
            # Key and interval are the residual read's index expression, which
            # is exactly what `_dynamic_index` looks up; the read token itself
            # names the source site and array.
            record('read', node.args[0], node, node.args[0], str(node.value), env,
                   evaluate(node.args[0], env, parameters, arrays))

    for body in event_bodies:
        flow(body, entry, arrays=arrays, parameters=parameters, on_use=on_use)
    holder.extend(node for node, _ in facts.values())
    return facts, holder
