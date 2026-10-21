"""Frontend scope for unread nonlinear decision outputs.

An ordinary decision outside the affine contract is deferred only as a
candidate. The complete Program must then show that every such decision lies
solely in grounded output contributions that nothing reads, and that at least
one of those outputs has a decision the kernel's readout route owns. The kernel
re-audits the actual request and evaluates each row from certified node boxes.
Anything else raises the original diagnostic.
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


def check(program, pending, audit):
    """Raise the first pending diagnostic that the complete Program does not admit."""
    def fail(origin, message):
        raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: {message}")
    if not (program.states or program.events or program.operators):
        fail(*pending[0])
    outside, reads = set(), set()
    _scan((program.states, program.events, program.operators, program.step_bounds), audit, outside, reads)
    per_contribution = []
    for contribution in program.contributions:
        origins, nodes = set(), set()
        _scan(contribution.rhs, audit, origins, nodes)
        per_contribution.append((origins, nodes))
        reads |= nodes
    touching = {}
    for contribution in program.contributions:
        for node in {contribution.positive, contribution.negative} - {0}:
            touching[node] = touching.get(node, 0) + 1
    sinks, engaged = set(), False
    for index, contribution in enumerate(program.contributions):
        target = max(contribution.positive, contribution.negative)
        if (min(contribution.positive, contribution.negative) == 0 and target != 0
                and touching.get(target) == 1 and target not in reads
                and readout_tree(contribution.rhs)):
            sinks.add(index)
            engaged |= needs_readout(contribution.rhs)
        else:
            outside |= per_contribution[index][0]
    for origin, message in pending:
        if origin in outside or not engaged:
            fail(origin, message)
