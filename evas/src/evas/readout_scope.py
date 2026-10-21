"""Frontend scope for unread nonlinear decision outputs.

An ordinary decision outside the affine contract is deferred only as a
candidate. The complete Program admits it in exactly two shapes, both in
grounded, undriven, singly-owned output contributions that nothing reads:

1. Held-gain decision. Every occurrence of the decision in the Program is in
   such an output and is either affine or compares a held state or operator
   sample multiplied with a live circuit voltage, i.e. it becomes affine when
   held leaves are frozen. A decision over held values only (q*q>0) or over
   live voltages only (V(a)*V(b)>0) is not this shape.
2. Stateless algebraic instance. The decision's instance owns no state, event,
   operator or step bound, and every contribution of that instance is such an
   output reading no held leaf: its values are pure functions of live node
   voltages. Other instances of the Program may hold state.

The kernel re-audits the actual request with the same rules and evaluates each
row from certified node boxes. Anything else raises the original diagnostic.
"""
from dataclasses import fields, is_dataclass
import math

from .ir import Affine, Binary, OperatorRef, Power, Select, StateRef, Term
from .syntax import CompileError


def readout_tree(value):
    """Structural candidate: arithmetic, decisions, held state and operator leaves."""
    memo, pending = {}, [value]
    while pending:
        item = pending.pop()
        if id(item) in memo:
            continue
        memo[id(item)] = True
        if isinstance(item, Affine):
            if not math.isfinite(item.constant) or any(not math.isfinite(t.coefficient) for t in item.terms):
                return False
        elif isinstance(item, (StateRef, OperatorRef)):
            pass
        elif isinstance(item, Binary) and item.op in ("add", "multiply", "divide"):
            pending.extend((item.left, item.right))
        elif isinstance(item, Power):
            if not 1 <= item.exponent <= 32:
                return False
            pending.append(item.base)
        elif isinstance(item, Select):
            pending.extend((item.left, item.right, item.then_value, item.else_value))
        else:
            return False
    return True


def has_leaf(value):
    """Mirror of the kernel's leaf test: state or operator anywhere in the tree."""
    seen, pending = set(), [value]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, (StateRef, OperatorRef)):
            return True
        if isinstance(item, Select):
            pending.extend((item.left, item.right, item.then_value, item.else_value))
        elif isinstance(item, Binary):
            pending.extend((item.left, item.right))
        elif isinstance(item, Power):
            pending.append(item.base)
    return False


def _degree(item, memo):
    """Mirror of the kernel predicate degree: node-free 0, affine 1, else None."""
    key = id(item)
    if key in memo:
        return memo[key]
    if isinstance(item, Affine):
        result = int(bool(item.terms))
    elif isinstance(item, StateRef):
        result = 1
    elif isinstance(item, Binary) and item.op in ("add", "multiply"):
        a, b = _degree(item.left, memo), _degree(item.right, memo)
        if a is None or b is None:
            result = None
        else:
            result = max(a, b) if item.op == "add" else (a + b if a + b <= 1 else None)
    elif isinstance(item, Power):
        d = _degree(item.base, memo)
        result = d if d is not None and (d == 0 or item.exponent == 1) else None
    elif isinstance(item, Select):
        parts = [_degree(x, memo) for x in (item.left, item.right, item.then_value, item.else_value)]
        result = None if None in parts else max(parts)
    else:
        result = None
    memo[key] = result
    return result


def needs_readout(value):
    memo, seen, pending = {}, set(), [value]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, Select):
            if _degree(item.left, memo) is None or _degree(item.right, memo) is None:
                return True
            pending.extend((item.left, item.right, item.then_value, item.else_value))
        elif isinstance(item, Binary):
            pending.extend((item.left, item.right))
        elif isinstance(item, Power):
            pending.append(item.base)
    return False


def _scan(root, audit, origins, reads):
    """Collect Select origins and Term nodes in any IR object, all arms included."""
    seen, pending = set(), [root]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        audit.debit("readout_scope_visit")
        if isinstance(item, Term):
            reads.add(item.node)
        elif isinstance(item, Select):
            origins.add(item.origin)
        if isinstance(item, (tuple, list)):
            pending.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, f.name) for f in fields(item))


def _decisions(value, origin):
    """Every Select carrying `origin` in one expression, arms included."""
    found, pending = [], [value]
    while pending:
        item = pending.pop()
        if isinstance(item, Select):
            if item.origin == origin:
                found.append(item)
            pending.extend((item.left, item.right, item.then_value, item.else_value))
        elif isinstance(item, Binary):
            pending.extend((item.left, item.right))
        elif isinstance(item, Power):
            pending.append(item.base)
    return found


def live_node(value):
    """A tree that reads at least one live circuit voltage."""
    seen, pending = set(), [value]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, Affine):
            if item.terms:
                return True
        elif isinstance(item, Select):
            pending.extend((item.left, item.right, item.then_value, item.else_value))
        elif isinstance(item, Binary):
            pending.extend((item.left, item.right))
        elif isinstance(item, Power):
            pending.append(item.base)
    return False


def _held_gain_degree(item, memo):
    """Predicate degree with held states and operator samples frozen as gains."""
    key = id(item)
    if key in memo:
        return memo[key]
    if isinstance(item, Affine):
        result = int(bool(item.terms))
    elif isinstance(item, (StateRef, OperatorRef)):
        result = 0
    elif isinstance(item, Binary) and item.op in ("add", "multiply", "divide"):
        a, b = _held_gain_degree(item.left, memo), _held_gain_degree(item.right, memo)
        if a is None or b is None:
            result = None
        elif item.op == "add":
            result = max(a, b)
        elif item.op == "multiply":
            result = a + b if a + b <= 1 else None
        else:
            result = a if b == 0 else None
    elif isinstance(item, Power):
        d = _held_gain_degree(item.base, memo)
        result = None if d is None else 0 if d == 0 else d if item.exponent == 1 else None
    elif isinstance(item, Select):
        parts = [_held_gain_degree(x, memo) for x in (item.left, item.right, item.then_value, item.else_value)]
        result = None if None in parts else max(parts)
    else:
        result = None
    memo[key] = result
    return result


def nonaffine(select):
    return _degree(select.left, {}) is None or _degree(select.right, {}) is None


def held_gain_decision(select):
    """Shape 1: a nonaffine predicate that couples a held leaf with a live voltage
    and becomes affine when the held leaves are frozen."""
    left, right = select.left, select.right
    memo = {}
    return (nonaffine(select)
            and (has_leaf(left) or has_leaf(right))
            and (live_node(left) or live_node(right))
            and _held_gain_degree(left, memo) is not None
            and _held_gain_degree(right, memo) is not None)


def check(program, pending, audit):
    """Raise the first pending diagnostic that the complete Program does not admit."""
    def fail(origin, message):
        raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: {message}")
    if not (program.states or program.events or program.operators):
        fail(*pending[0])
    misses, reads = set(), set()
    _scan((program.states, program.events, program.operators, program.step_bounds), audit, misses, reads)
    for contribution in program.contributions:
        _scan(contribution.rhs, audit, set(), reads)
    touching = {}
    for contribution in program.contributions:
        for node in {contribution.positive, contribution.negative} - {0}:
            touching[node] = touching.get(node, 0) + 1

    def sink(contribution):
        target = max(contribution.positive, contribution.negative)
        return (min(contribution.positive, contribution.negative) == 0 and target != 0
                and touching.get(target) == 1 and target not in reads
                and readout_tree(contribution.rhs))

    sinks = [sink(contribution) for contribution in program.contributions]
    owners = ({state.instance for state in program.states}
              | {event.origin.instance for event in program.events}
              | {operator.origin.instance for operator in program.operators}
              | {bound.origin.instance for bound in program.step_bounds})
    stateless = {}

    def stateless_instance(instance):
        # Shape 2: the whole instance is an unread algebraic readout.
        if instance not in stateless:
            own = [index for index, contribution in enumerate(program.contributions)
                   if contribution.origin.instance == instance
                   or contribution.branch.instance == instance]
            stateless[instance] = (instance not in owners and bool(own)
                                   and all(sinks[index] and not has_leaf(program.contributions[index].rhs)
                                           for index in own)
                                   and any(needs_readout(program.contributions[index].rhs) for index in own))
        return stateless[instance]

    for origin, message in pending:
        if origin in misses:
            fail(origin, message)
        occurrences = [(index, decision) for index, contribution in enumerate(program.contributions)
                       for decision in _decisions(contribution.rhs, origin)]
        if any(not sinks[index] for index, _ in occurrences):
            fail(origin, message)
        if stateless_instance(origin.instance) and all(
                program.contributions[index].origin.instance == origin.instance
                or program.contributions[index].branch.instance == origin.instance
                for index, _ in occurrences):
            continue
        if not occurrences or not any(held_gain_decision(decision) for _, decision in occurrences):
            fail(origin, message)
        if any(nonaffine(decision) and not held_gain_decision(decision) for _, decision in occurrences):
            fail(origin, message)
