"""Unroll event loops whose trip count a closed integer invariant proves.

`while (c) s` (Verilog-AMS LRM 2.4, procedural loop statements) and runtime-
controlled event `for` loops in modules with physical outputs have no runtime
loop execution path: the kernel runs runtime loops only in isolated numeric
observers. Such a loop is replaced by nested conditionals when a sound integer
interval analysis proves a maximal trip count B <= MAX_TRIPS for every
reachable entry state. The replacement is B+1 consecutive guarded trips
`if (c) s;`. It is exact: once c is false no statement runs before the next
identical test, so every later test is false too. The last trip is proven dead
but stays in the tree so that the existing structural audits still see it. Real-valued
conditions, unknown parameters and unproven bounds keep an explicit
`unsupported_loop_bound` diagnostic for `while`; such `for` loops keep the
existing runtime-loop diagnostics.

The invariant is computed per module, independently of instance parameters
(parameters are unknown), over default/initializer values, initialization and
every event writer. Integer variables written by ordinary analog statements are
not tracked. The fixpoint is checked post hoc: every body maps the invariant
into itself. Bounds are recorded only during that checking pass.
"""
from dataclasses import replace, is_dataclass

from .errors import CompileError
from .limits import MAX_IR_ITEMS
from . import event_index_domains as domains
from .syntax import (Assignment, BoundStep, Conditional, ContributionStatement, Display,
                     Event, Expr, Loop, Parser, Token, While)

#: Implementation bound on unrolled trips; the copies also obey the existing
#: expanded IR size limit.
MAX_TRIPS = 64
_RUNTIME_TRIGGERS = ("timer", "cross", "final_step")
_RELATIONS = ("<", "<=", ">", ">=")
_NEGATE = {"<": ">=", "<=": ">", ">": "<=", ">=": "<"}
_SWAP = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
_UNBOUNDED = object()


def condition_tree(expr, yes, no, token):
    # The parser's stateless Boolean lowering; identical to an `if` statement.
    return Parser('', token.source, tokens=[]).condition(expr, yes, no, token)


class _Abandon(Exception):
    """The optional proof cannot complete; no loop gains a bound."""


def _fail(model, token, message):
    raise CompileError(f"{token.source or model.source}:{token.line}:{token.column}: {message}",
                       code="unsupported_loop_bound", token=token)


def _walk(statements):
    for item in statements:
        yield item
        if isinstance(item, Conditional):
            yield from _walk(item.then_body)
            yield from _walk(item.else_body)
        elif isinstance(item, (Loop, While, Event)):
            yield from _walk(item.body)


def _runtime_event(event):
    return all(trigger.kind in _RUNTIME_TRIGGERS for trigger in event.triggers)


def bound_loops(model):
    """Return `model` unchanged unless it has a while or an unexecutable runtime for."""
    statements = (*model.analog, *model.initial, *model.events)
    if not any(isinstance(item, (While, Loop)) for item in _walk(statements)):
        return model

    def physical(items):
        # InstanceCompiler.numeric_observer_candidate applies this criterion
        # after static analog loops are unrolled, so descend into them too.
        for item in items:
            if isinstance(item, (ContributionStatement, BoundStep)):
                return True
            if isinstance(item, Conditional) and (physical(item.then_body) or physical(item.else_body)):
                return True
            if isinstance(item, Loop) and physical(item.body):
                return True
        return False
    observer = not physical(model.analog)

    def reads_variable(expr):
        pending = [expr]
        while pending:
            item = pending.pop()
            if item.op in ("parameter", "index") and item.value in model.variables:
                return True
            pending.extend(item.args)
        return False

    def candidate_for(loop):
        # Runtime fors in isolated observers keep the kernel runtime loop.
        return (not observer and model.variables.get(loop.name) == "integer"
                and loop.name not in model.arrays and loop.relation in _RELATIONS
                and (reads_variable(loop.start) or reads_variable(loop.limit))
                and not any(isinstance(item, Assignment) and item.name == loop.name
                            for item in _walk(loop.body)))

    has_while = any(isinstance(item, While) for item in _walk(statements))
    has_candidate = False
    events = []

    def collect(items, runtime):
        nonlocal has_candidate
        for item in items:
            if isinstance(item, Event):
                events.append(item)
                collect(item.body, _runtime_event(item))
            elif isinstance(item, Conditional):
                collect(item.then_body, runtime)
                collect(item.else_body, runtime)
            elif isinstance(item, (Loop, While)):
                has_candidate |= runtime and isinstance(item, Loop) and candidate_for(item)
                collect(item.body, runtime)
    collect(statements, False)
    if not has_while and not has_candidate:
        return model

    records = _prove(model, events)
    loop_sites = {}
    copied_items = 0

    def trip_copy(value, loop, iteration):
        # Source expansion is per original loop occurrence, never token-only.
        # Views sharing the original node receive the same expansion path.
        if id(loop) not in loop_sites:
            loop_sites[id(loop)] = (loop, len(loop_sites)+1)
        path = (('bounded_loop', loop_sites[id(loop)][1]),
                ('bounded_loop_trip', iteration))
        memo = {}
        def reserve(amount):
            nonlocal copied_items
            copied_items += amount
            if copied_items > MAX_IR_ITEMS:
                raise CompileError('bounded loop source expansion exceeds IR budget',
                                   code='resource_budget', token=loop.token)
        def copy(item):
            if isinstance(item, (Expr, Token, tuple, list)) or is_dataclass(item):
                old = memo.get(id(item))
                if old is not None:
                    return old[1]
            if isinstance(item, Expr):
                reserve(1+len(item.args)+len(item.expansion)+len(path))
                result = replace(item, token=copy(item.token), args=tuple(copy(arg) for arg in item.args),
                                 expansion=(*item.expansion, *path))
            elif isinstance(item, Token):
                reserve(1+len(item.expansion)+len(path))
                result = replace(item, expansion=(*item.expansion, *path))
            elif is_dataclass(item):
                schema = type(item).__dataclass_fields__
                reserve(1+len(schema))
                result = replace(item, **{name:copy(getattr(item,name)) for name in schema})
            elif isinstance(item, (tuple, list)):
                reserve(1+len(item))
                result = tuple(copy(child) for child in item)
            else:
                return item
            memo[id(item)] = (item, result)
            return result
        return copy(value)

    def transform(items, runtime):
        result = []
        for item in items:
            if isinstance(item, While):
                if not runtime:
                    _fail(model, item.token, "while loops are supported only in timer, cross or final_step event bodies")
                trips = records.get(id(item), (item, _UNBOUNDED))[1] if records is not None else _UNBOUNDED
                if trips is _UNBOUNDED:
                    _fail(model, item.token, f"while loop needs an integer trip-count bound <= {MAX_TRIPS} "
                          "proven from integer state invariants within the proof budget")
                body = transform(item.body, runtime)
                trip = condition_tree(item.condition, body, (), item.token)
                for iteration in range(trips + 1):
                    result.extend(trip_copy(trip, item, iteration))
            elif isinstance(item, Loop):
                trips = (records.get(id(item), (item, _UNBOUNDED))[1] if records is not None else _UNBOUNDED)
                if not (runtime and candidate_for(item)) or trips is _UNBOUNDED:
                    # Retained loops keep their existing paths; nested whiles
                    # still need their own bound, which covers every outer trip.
                    result.append(replace(item, body=transform(item.body, runtime)))
                    continue
                body = transform(item.body, runtime)
                control = Expr("parameter", item.name, (), item.token)
                update = Assignment(item.name, item.update, item.token)
                trip = Conditional(item.relation, control, item.limit, (*body, update), (), item.token)
                result.append(Assignment(item.name, item.start, item.token))
                for iteration in range(trips + 1):
                    result.append(trip_copy(trip, item, iteration))
            elif isinstance(item, Conditional):
                result.append(replace(item, then_body=transform(item.then_body, runtime),
                                      else_body=transform(item.else_body, runtime)))
            elif isinstance(item, Event):
                result.append(replace(item, body=transform(item.body, _runtime_event(item))))
            else:
                result.append(item)
        return tuple(result)

    return replace(model, analog=list(transform(model.analog, False)),
                   initial=list(transform(model.initial, False)),
                   procedure=transform(model.procedure, False),
                   events=list(transform(model.events, False)))


def _prove(model, events):
    """Map id(loop) -> (loop, max trips | _UNBOUNDED); None if the proof is abandoned."""
    used = 0

    def charge(amount=1):
        nonlocal used
        used += amount
        if used > MAX_IR_ITEMS:
            raise _Abandon()

    def unknown(name):
        # Instance parameters are not bound here; every parameter is unknown.
        raise KeyError(name)
    unknown.integer_proof_work = charge

    def integral(expr):
        if expr.result_type is not None:
            return expr.result_type == "integer"
        op = expr.op
        if op == "number":
            # Decimal literals, or the parser's zero for a nonrelational test.
            return expr.token.text.isdecimal() or expr.token.kind == "name" and expr.value == 0
        if op == "parameter":
            return (model.variables.get(expr.value) == "integer" and expr.value not in model.arrays
                    or model.parameter_types.get(expr.value) == "integer" or expr.value in model.genvars)
        if op in ("<", "<=", ">", ">=", "==", "!=", "&&", "||", "unary!"):
            return True
        if op == "checked":
            return integral(expr.args[0])
        if op == "ternary":
            return all(integral(arg) for arg in expr.args[1:])
        return op in ("+", "-", "*", "/", "%", "unary+", "unary-") and all(integral(arg) for arg in expr.args)

    def value(expr, env):
        charge()
        if not integral(expr):
            return None
        result = domains.evaluate(expr, env, unknown, {})
        return None if result is None or result == domains.BOTTOM else result

    # Integer scalars written outside events are not tracked (always unknown).
    ordinary = set()

    def ordinary_writes(items):
        for item in items:
            if isinstance(item, Event):
                continue
            if isinstance(item, Assignment):
                ordinary.add(item.name)
            elif isinstance(item, Loop):
                ordinary.add(item.name)
                ordinary_writes(item.body)
            elif isinstance(item, While):
                ordinary_writes(item.body)
            elif isinstance(item, Conditional):
                ordinary_writes(item.then_body)
                ordinary_writes(item.else_body)
    ordinary_writes(model.analog)
    tracked = sorted(name for name, kind in model.variables.items()
                     if kind == "integer" and name not in model.arrays and name not in ordinary)

    def join(a, b):
        if a is None:
            return None if b is None else dict(b)
        if b is None:
            return dict(a)
        charge(len(a))
        return {name: domains.hull(a[name], b[name]) for name in a}

    def narrow(env, name, relation, bound):
        low, high = env[name]
        if relation == "<":
            high = min(high, bound[1] - 1)
        elif relation == "<=":
            high = min(high, bound[1])
        elif relation == ">":
            low = max(low, bound[0] + 1)
        else:
            low = max(low, bound[0])
        env[name] = (low, high)

    def holds(relation, left, right, env):
        """Environment narrowed by `left relation right`, or None if impossible."""
        a, b = value(left, env), value(right, env)
        if a is not None and b is not None and {
                "<": a[0] >= b[1], "<=": a[0] > b[1],
                ">": a[1] <= b[0], ">=": a[1] < b[0]}[relation]:
            return None
        result = dict(env)
        charge(len(result))
        if b is not None and left.op == "parameter" and left.value in result:
            narrow(result, left.value, relation, b)
        if a is not None and right.op == "parameter" and right.value in result:
            narrow(result, right.value, _SWAP[relation], a)
        return None if any(low > high for low, high in result.values()) else result

    def havoc(env, items, extra=()):
        result = dict(env)
        for item in (*extra, *_walk(items)):
            charge()
            name = item if isinstance(item, str) else getattr(item, "name", None)
            if isinstance(item, (Assignment, Loop, str)) and name in result:
                result[name] = domains.TOP
        return result

    records = None
    marks, mark_ids = {}, set()

    def note(loop, trips):
        if records is None:
            return
        previous = records.get(id(loop), (loop, 0))[1]
        if previous is _UNBOUNDED or trips is _UNBOUNDED:
            records[id(loop)] = (loop, _UNBOUNDED)
        else:
            records[id(loop)] = (loop, max(previous, trips))

    def condition(loop, env):
        """Join of environments reaching the then/else sides of one loop test."""
        if id(loop) not in marks:
            yes, no = Display("", (), loop.token), Display("", (), loop.token)
            if isinstance(loop, While):
                tree = condition_tree(loop.condition, (yes,), (no,), loop.token)
            else:
                control = Expr("parameter", loop.name, (), loop.token)
                tree = (Conditional(loop.relation, control, loop.limit, (yes,), (no,), loop.token),)
            marks[id(loop)] = (loop, tree, yes, no)
            mark_ids.update((id(yes), id(no)))
        _, tree, yes, no = marks[id(loop)]
        reached = {}
        execute(tree, env, reached)
        return reached.get(id(yes)), reached.get(id(no))

    def iterate(loop, env, body):
        exits, current = None, env
        for trips in range(MAX_TRIPS + 1):
            yes, no = condition(loop, current)
            exits = join(exits, no)
            if yes is None:
                note(loop, trips)
                return exits
            if trips == MAX_TRIPS:
                break
            current = execute(body, yes)
            if current is None:
                note(loop, trips + 1)
                return exits
        # Nested loops were not visited for every possible trip.
        for inner in (loop, *_walk(loop.body)):
            if isinstance(inner, (Loop, While)):
                note(inner, _UNBOUNDED)
        return None

    def execute(items, env, reached=None):
        for item in items:
            charge()
            if env is None:
                return None
            if reached is not None and id(item) in mark_ids:
                reached[id(item)] = join(reached.get(id(item)), env)
                continue
            if isinstance(item, Conditional):
                if item.relation not in _RELATIONS:
                    raise _Abandon()
                yes = holds(item.relation, item.left, item.right, env)
                no = holds(_NEGATE[item.relation], item.left, item.right, env)
                env = join(execute(item.then_body, yes, reached) if yes is not None else None,
                           execute(item.else_body, no, reached) if no is not None else None)
            elif isinstance(item, Assignment):
                if item.index is None and item.name in env:
                    result = value(item.rhs, env)
                    env = {**env, item.name: domains.TOP if result is None else domains.clamp(result)}
            elif isinstance(item, While):
                exits = iterate(item, env, item.body)
                env = havoc(env, item.body) if exits is None else exits
            elif isinstance(item, Loop):
                added = item.name not in env
                start = value(item.start, env)
                current = {**env, item.name: domains.TOP if start is None else domains.clamp(start)}
                exits = iterate(item, current, (*item.body, Assignment(item.name, item.update, item.token)))
                env = havoc(current, item.body, (item.name,)) if exits is None else exits
                if added and env is not None:
                    env = {name: bounds for name, bounds in env.items() if name != item.name}
            elif isinstance(item, (Display, ContributionStatement, BoundStep)):
                continue
            else:
                raise _Abandon()
        return env

    try:
        initial = {}
        for name in tracked:
            expr = model.variable_initializers.get(name)
            bounds = (0, 0) if expr is None else value(expr, {})
            initial[name] = domains.TOP if bounds is None else domains.clamp(bounds)
        bodies = [tuple(model.initial), *(event.body for event in events)]

        def step(current):
            result = dict(current)
            for body in bodies:
                result = join(result, execute(body, current))
            return result

        invariant = dict(initial)
        for _ in range(32):
            following = step(invariant)
            if following == invariant:
                break
            invariant = following
        else:
            probe = step(invariant)
            invariant = {name: (domains.SIGNED32_MIN if probe[name][0] < low else low,
                                domains.SIGNED32_MAX if probe[name][1] > high else high)
                         for name, (low, high) in invariant.items()}
        records = {}
        for body in bodies:
            exit_env = execute(body, invariant)
            if exit_env is not None and any(
                    exit_env[name][0] < invariant[name][0] or exit_env[name][1] > invariant[name][1]
                    for name in invariant):
                return None
        return records
    except _Abandon:
        return None
