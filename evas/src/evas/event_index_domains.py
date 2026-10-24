"""Per-source-use integer flow facts for dynamic array index admission (N02).

The entry invariant is one exact integer interval per integer state, computed
over the default/initialization values, every event and final_step writer in
sequential use-site order, branch fork/join narrowing and weak dynamic-slot
updates. Iteration is bounded; interval endpoints that fail to converge are widened to the
corresponding signed-32 limit and the result is verified with an explicit
post-fixpoint check (every event transformer maps the reported invariant into
itself). TOP is an overapproximation for stored values, never a legal index.

N02 consumes these facts to admit event/final_step dynamic array indices.
N03 extends the same walker with loop header/exit facts instead of adding a
second analyzer; `flow`, `refine`, `Interval` and `FlowFacts` are that shared
interface. All arithmetic below runs on exact Python integers; clamping to the
signed-32 range models what a stored state can hold, while the existing typed
overflow obligations at the actual lowering site stay untouched.
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from .syntax import Assignment, Conditional, Display, Loop
from . import integer_bits, integer_arithmetic
from .condition_domains import compact_condition, compact_domains

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
    low, high = max(low, SIGNED32_MIN), min(high, SIGNED32_MAX)
    return BOTTOM if low > high else (low, high)


def within(interval, low, high):
    return interval[0] <= interval[1] and low <= interval[0] and interval[1] <= high


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
    """Reusable per-source-use facts (N02 admission; N03 loop extension).

    `entry`/`exit` map integer state names to intervals around this source
    statement; `index` is the evaluated interval of the index expression at
    this sequential position; `provenance` keeps the typed source origin.
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


def _charge(parameters, count=1):
    charge = getattr(parameters, 'integer_proof_work', None)
    if charge is not None:
        for _ in range(count):
            charge()


def _copy_env(env, parameters):
    _charge(parameters, len(env))
    return dict(env)


def evaluate(expr, env, parameters, arrays, on_read=None):
    """Interval of a typed-integer expression, or None when unknown.

    Unknown operands (real-typed or non-integer inputs) yield None, which the
    caller reports as TOP. Residual array reads overapproximate to the hull of
    every declared element; the index itself is irrelevant for soundness.
    """
    _charge(parameters)
    if expr is None:
        return None
    if expr.op == 'index':
        if on_read is not None:
            on_read(expr)
        elements = arrays.get(str(expr.value), ())
        result = BOTTOM
        if not elements:
            return None
        for k in elements:
            _charge(parameters)
            value = env.get(f'{expr.value}[{k}]')
            if value is None:
                return None
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
    # Visit every source operand above, including in unreachable branches.
    # Empty flow domains absorb arithmetic, not its source audit obligations.
    _charge(parameters, len(args))
    if any(arg is not None and arg[0] > arg[1] for arg in args):
        return BOTTOM
    if expr.op == 'floor':
        transfer = getattr(parameters, 'real_floor_bounds', None)
        return transfer(expr) if transfer is not None else None
    if expr.op in integer_bits.OPS:
        return integer_bits.bounds(expr.op, args)
    if expr.op in ('<', '<=', '>', '>=', '==', '!=', '&&', '||', 'unary!'):
        return (0, 1)
    if expr.op == 'ternary':
        if args[1] is None or args[2] is None:
            return None
        condition = expr.args[0]
        # Only simple operands get this optional precision improvement. Replaying
        # a nested condition here would duplicate its already evaluated tree.
        if (condition.op in ('<', '<=', '>', '>=') and
                all(arg.op in ('number', 'parameter') for arg in condition.args)):
            local = {}
            for arg in condition.args:
                _charge(parameters)
                if arg.op == 'parameter' and str(arg.value) in env:
                    local[str(arg.value)] = env[str(arg.value)]
            yes, no = refine(condition.op, *condition.args, local, parameters, arrays)
            def arm_bounds(arm, value, narrowed):
                _charge(parameters, len(narrowed))
                if any(low > high for low, high in narrowed.values()):
                    return BOTTOM
                if arm.op == 'parameter' and str(arm.value) in narrowed:
                    return narrowed[str(arm.value)]
                return value
            return hull(arm_bounds(expr.args[1], args[1], yes),
                        arm_bounds(expr.args[2], args[2], no))
        return hull(args[1], args[2])
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
        return integer_arithmetic.bounds(expr.op, args)
    return None


def refine(relation, left, right, env, parameters, arrays, *, on_read=None):
    """Narrow integer states against exact integer constants.

    First version keeps only the fully proven rule: one bare integer state
    compared with an exact integer constant (either operand order). All other
    conditions keep their entry domains; both branches and strict boundaries
    are covered, and an impossible branch becomes BOTTOM.
    """
    if compact_condition(relation, left, right):
        _charge(parameters, 10)  # two forwarding callbacks and references
        return compact_domains(relation, left, right, env,
            refine=lambda op,a,b,current: refine(op,a,b,current,parameters,arrays,on_read=on_read),
            hull=hull, work=lambda count: _charge(parameters,count),
            plan_cache=getattr(getattr(parameters, 'integer_proof_counter', None), 'condition_plans', None))
    if on_read is not None:
        _charge(parameters, 4)
        def read(expr):
            on_read(expr, env)
        evaluate(left, env, parameters, arrays, read)
        evaluate(right, env, parameters, arrays, read)
    yes, no = _copy_env(env, parameters), _copy_env(env, parameters)

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
        yes[name], no[name] = (BOTTOM if low > high else (low, high)
                               for low, high in arms)

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


def flow(statements, env, *, arrays, parameters, on_use=None, on_state=None, invariant_only=False):
    """Abstract one event body from `env`; returns the exit environment.

    Scalar assignments strong-update their target; dynamic array writes
    weak-update every possible slot (strong only for a proven singleton index).
    Conditionals fork narrowed environments and join on return. `on_use` receives
    every dynamic index use with the statement-local environment, which is how
    admission (and later N03 loop proofs) consume per-site facts.
    """
    env = _copy_env(env, parameters)

    def execute(statements, current):
        _charge(parameters)
        # This numerical reachability rule is restricted to invariant proof.
        # Source/read/index audits still walk original bodies without pruning.
        if invariant_only:
            _charge(parameters, len(current))
            if any(low > high for low, high in current.values()):
                _charge(parameters, len(current))
                return {name: BOTTOM for name in current}
        for statement in statements:
            charge = getattr(parameters, 'integer_proof_work', None)
            if charge is not None:
                charge()
            if on_state is not None:
                on_state(current)
            if isinstance(statement, Loop):
                # No static trip-count assumption. Every loop writer may hold
                # any signed32 value on a successful firing. Runtime checking
                # owns actual indices and the event-wide iteration budget.
                def writers(items):
                    for item in items:
                        if charge is not None:
                            charge()
                        if isinstance(item, Assignment):
                            if item.index is None:
                                yield item.name
                            else:
                                for k in arrays.get(item.name, ()):
                                    _charge(parameters)
                                    yield f'{item.name}[{k}]'
                        elif isinstance(item, Conditional):
                            yield from writers(item.then_body)
                            yield from writers(item.else_body)
                        elif isinstance(item, Loop):
                            yield item.name
                            yield from writers(item.body)
                for name in (statement.name, *writers(statement.body)):
                    _charge(parameters)
                    if name in current:
                        current[name] = TOP
                execute(statement.body, _copy_env(current, parameters))
            elif isinstance(statement, Conditional):
                reads = None
                if on_use is not None:
                    _charge(parameters, 4)
                    def reads(expr, narrowed):
                        on_use('read', expr, narrowed)
                yes, no = refine(statement.relation, statement.left, statement.right,
                                 current, parameters, arrays,on_read=reads)
                then_exit = execute(statement.then_body, yes)
                else_exit = execute(statement.else_body, no)
                joined = _copy_env(current, parameters)
                for name in joined:
                    _charge(parameters)
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
                        _charge(parameters)
                        name = f'{statement.name}[{element}]'
                        if name not in current:
                            continue
                        if singleton and element == index[0]:
                            current[name] = value
                        else:
                            current[name] = hull(current[name], value)
                elif statement.name in current:
                    current[statement.name] = TOP if value is None else clamp(value)
            if on_state is not None:
                on_state(current)
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
    from .integer_invariants import ProofWork, proof_parameters, widening_candidate
    work = getattr(parameters, 'integer_proof_counter', None) or ProofWork()
    parameters = proof_parameters(parameters, work)
    _charge(parameters)
    _charge(parameters, len(states))
    domains = {name: initial_bounds.get(name, TOP) for name in states}

    def step(current):
        joined = _copy_env(current, parameters)
        for body in event_bodies:
            _charge(parameters)
            exit_domains = flow(body, current, arrays=arrays, parameters=parameters, invariant_only=True)
            for name in joined:
                _charge(parameters)
                joined[name] = hull(joined[name], exit_domains.get(name, BOTTOM))
        return joined

    def verify(current, lookup=parameters):
        from .integer_invariants import verify_candidate
        return verify_candidate(event_bodies, initial_bounds, current,
                                arrays=arrays, parameters=lookup)

    widened = False
    for _ in range(passes):
        nxt = step(domains)
        _charge(parameters, len(domains))
        if nxt == domains:
            break
        domains = nxt
    else:
        # Preserve stable endpoints, e.g. a nonnegative counter stays nonnegative.
        # Only an endpoint still moving outwards is widened to its signed32 limit.
        probe = step(domains)
        _charge(parameters, len(domains))
        standard = {name: (SIGNED32_MIN if probe[name][0] < domains[name][0] else domains[name][0],
                           SIGNED32_MAX if probe[name][1] > domains[name][1] else domains[name][1])
                    for name in domains}
        candidate = widening_candidate(event_bodies, initial_bounds, domains, standard,
                                       states=states, arrays=arrays, parameters=parameters, work=work)
        lookup = parameters
        # One checked candidate replaces endpoint widening, never another
        # fixed-point iteration. A failed guess retains the original fallback;
        # all iterations and both checks share one bounded proof work counter.
        if candidate is not None and verify(candidate, lookup):
            return candidate, True
        domains = standard
        widened = True
        if candidate is not None:
            if not verify(domains, lookup):
                raise ValueError('event integer domains failed the post-fixpoint verification')
            return domains, widened
    if not verify(domains):
        raise ValueError('event integer domains failed the post-fixpoint verification')
    return domains, widened


def use_site_facts(event_bodies, entry, *, arrays, parameters, location_of, partitioned=None, reachable=None, on_state=None):
    """Walk every event body once and collect FlowFacts per dynamic use site.

    Keyed by `id()` of the residual index expression (writes: the statement's
    index expression). The returned pair list keeps the source nodes alive so
    ids stay valid while the compiler lowers the same tree.
    """
    _charge(parameters, 2)
    facts = {}
    holder = []

    def index_states(expr):
        _charge(parameters, 3)
        states = []
        pending = [expr]
        while pending:
            _charge(parameters)
            item = pending.pop()
            _charge(parameters, 2)
            if item.op == 'parameter' and str(item.value) in entry:
                _charge(parameters)
                states.append(str(item.value))
            _charge(parameters, 1 + len(item.args))
            pending.extend(reversed(item.args))
        _charge(parameters, 1 + len(states))
        return tuple(states)

    def record(access, key, site, states_expr, array, env, index):
        _charge(parameters, 2)
        previous = facts.get(id(key))
        if previous is not None:
            _charge(parameters, 1 + 3 * len(env))
            env = {name: hull(value, previous[1].entry[name]) for name, value in env.items()}
            index = hull(TOP if index is None else index, previous[1].index)
        states = index_states(states_expr)
        _charge(parameters, 6 + 2 * len(env))
        facts[id(key)] = (key, FlowFacts(
            entry=dict(env),
            exit=dict(env),
            index=TOP if index is None else index,
            provenance=IndexProvenance(
                array=array,
                access=access,
                location=location_of(site.token),
                states=states,
                constant_inputs=not states,
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
        _charge(parameters)
        flow(body, entry, arrays=arrays, parameters=parameters, on_use=on_use, on_state=on_state)
    if partitioned is not None:
        # The original-tree audit still checks unreachable syntax. Retain those
        # sites explicitly, using BOTTOM only after the closed invariant proves
        # that no path reaches the site, rather than borrowing a nearby proof.
        from dataclasses import replace
        original = facts
        _charge(parameters)
        facts = {}
        paths, execute = partitioned
        for body in event_bodies:
            _charge(parameters)
            execute(body, paths, on_use, reachable)
        for identity, (node, fact) in original.items():
            _charge(parameters, 2)
            if identity not in facts:
                _charge(parameters, 2)
                facts[identity] = (node, replace(fact, index=BOTTOM))
    _charge(parameters, 1 + 2 * len(facts))
    holder.extend(node for node, _ in facts.values())
    return facts, holder


def boolean_partitions(event_bodies, initial_bounds, *, arrays, parameters, states, passes=32):
    """Inductive finite partitions by source-proven boolean scalar states.

    Each partition retains intervals conditioned on its boolean key. Thus an
    event that sets a flag after incrementing a counter can communicate that
    counter's lower bound to a later event testing the flag. No event order or
    stimulus is assumed. All writers participate; at most six boolean states
    are selected, so the finite key space has at most 64 entries.
    """
    def contains_loop(body):
        for item in body:
            _charge(parameters)
            if isinstance(item, Loop):
                return True
            if isinstance(item, Conditional) and (contains_loop(item.then_body) or contains_loop(item.else_body)):
                return True
        return False
    for body in event_bodies:
        _charge(parameters)
        if contains_loop(body):
            return None
    _charge(parameters)
    writers = {}
    def collect(body):
        for item in body:
            _charge(parameters)
            if isinstance(item, Conditional):
                collect(item.then_body)
                collect(item.else_body)
            elif isinstance(item, Assignment) and item.index is None:
                _charge(parameters, 2)
                old = writers.get(item.name)
                if old is None:
                    _charge(parameters, 2)
                    old = []
                    writers[item.name] = old
                _charge(parameters)
                old.append(item.rhs)
    for body in event_bodies:
        _charge(parameters)
        collect(body)
    def boolean_value(expr):
        _charge(parameters)
        if expr.op in ('<','<=','>','>=','==','!=','&&','||','unary!'):
            return True
        if expr.op == 'ternary':
            return all(boolean_value(a) for a in expr.args[1:])
        if expr.op == 'checked':
            return boolean_value(expr.args[0])
        value = evaluate(expr, {}, parameters, arrays)
        return value is not None and within(value, 0, 1)
    _charge(parameters)
    selected = []
    for name in states:
        _charge(parameters, 2)
        if name in writers and within(initial_bounds.get(name, TOP), 0, 1) and all(boolean_value(rhs) for rhs in writers[name]):
            _charge(parameters)
            selected.append(name)
    _charge(parameters, 2 + min(len(selected), 6))
    keys = tuple(selected[:6])
    if not keys:
        return None

    def split(env):
        _charge(parameters, 2)
        result = [env]
        for name in keys:
            _charge(parameters)
            outgoing = []
            for path in result:
                for value in (0, 1):
                    _charge(parameters)
                    if path[name][0] <= value <= path[name][1]:
                        _charge(parameters, 2 + len(path))
                        outgoing.append({**path, name: (value, value)})
            result = outgoing
        return result

    def merge(paths):
        _charge(parameters)
        result = {}
        for env in paths:
            _charge(parameters, 3 + len(keys))
            key = tuple(env[name][0] for name in keys)
            old = result.get(key)
            _charge(parameters)
            if old is None:
                result[key] = env
            else:
                _charge(parameters, 1 + 3 * len(old))
                result[key] = {name: hull(old[name], env[name]) for name in old}
        return result

    def execute(body, paths, on_use=None, reachable=None):
        for item in body:
            _charge(parameters)
            if paths and reachable is not None:
                _charge(parameters)
                reachable.add(id(item))
            _charge(parameters)
            outgoing = []
            for env in paths:
                _charge(parameters)
                if isinstance(item, Conditional):
                    reads = None
                    if on_use is not None:
                        _charge(parameters, 4)
                        def reads(expr, narrowed):
                            on_use('read', expr, narrowed)
                    yes, no = refine(item.relation, item.left, item.right, env, parameters, arrays,on_read=reads)
                    for branch, narrowed in ((item.then_body, yes), (item.else_body, no)):
                        valid = True
                        for low, high in narrowed.values():
                            _charge(parameters)
                            if low > high:
                                valid = False
                                break
                        if valid:
                            _charge(parameters, 2)
                            new = execute(branch, [narrowed], on_use, reachable)
                            _charge(parameters, 1 + len(new))
                            outgoing.extend(new)
                else:
                    new = split(flow((item,), env, arrays=arrays, parameters=parameters, on_use=on_use))
                    _charge(parameters, 1 + len(new))
                    outgoing.extend(new)
            merged = merge(outgoing)
            _charge(parameters, 1 + len(merged))
            paths = list(merged.values())
        return paths

    _charge(parameters, 1 + len(states))
    initial = {name: initial_bounds.get(name, TOP) for name in states}
    invariant = merge(split(initial))
    for iteration in range(passes + 1):
        _charge(parameters, 1 + len(invariant))
        outgoing = list(invariant.values())
        for body in event_bodies:
            _charge(parameters, 1 + len(invariant))
            new = execute(body, list(invariant.values()))
            _charge(parameters, 1 + len(new))
            outgoing.extend(new)
        nxt = merge(outgoing)
        _charge(parameters, 1 + len(nxt) * (len(states) + 1))
        if nxt == invariant:
            _charge(parameters, 2 + len(invariant))
            return list(invariant.values()), execute
        if iteration == passes - 1:
            for key, env in nxt.items():
                _charge(parameters, 2)
                old = invariant.get(key)
                if old is not None:
                    _charge(parameters, 1 + 3 * len(env))
                    nxt[key] = {name: (SIGNED32_MIN if env[name][0] < old[name][0] else env[name][0],
                                       SIGNED32_MAX if env[name][1] > old[name][1] else env[name][1])
                                for name in env}
        invariant = nxt
    return None
