"""Bound recursive compiler work and the size of the expanded wire tree.

IR is a tree on the wire even when Python objects share subexpressions.
Measure that expansion with memoized, iterative traversal before allocating it.
These are implementation budgets, not Verilog-A language restrictions.
"""
from dataclasses import fields, is_dataclass

from .errors import CompileError

MAX_SOURCE_NESTING = 64
# Retain the existing 64-node star/dense circuits, including their enclosing
# arithmetic. Lowered IR gets its own container-depth check before transport.
MAX_EXPRESSION_DEPTH = 80
MAX_PARAMETER_DEPTH = 64
# Leave room for the enclosing request under serde_json's depth limit of 128.
MAX_IR_DEPTH = 96
MAX_IR_ITEMS = 100_000


def check_expression(expression, source):
    pending = [(expression, 1)]
    while pending:
        expr, depth = pending.pop()
        if depth > MAX_EXPRESSION_DEPTH:
            token = expr.token
            raise CompileError(f"{source}:{token.line}:{token.column}: expression depth limit ({MAX_EXPRESSION_DEPTH}) exceeded")
        pending.extend((arg, depth + 1) for arg in expr.args)


def _children(value):
    if is_dataclass(value):
        return [getattr(value, field.name) for field in fields(value)]
    if isinstance(value, (tuple, list)):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return None


def check_ir(value, origin=None):
    """Count expanded values/containers without expanding shared objects.

    Depth is JSON container depth, counting dataclasses as objects. A cached
    child's cost is added at *each* reference; memoization is not deduplication
    of the transmitted tree. Cycles are invalid even for manually built IR.
    """
    if origin is None:
        contributions = getattr(value, 'contributions', ())
        origin = contributions[0].origin if contributions else getattr(value, 'origin', None)
    location = f"{origin.source}:{origin.line}:{origin.column}" if origin else '<IR>:1:1'

    def fail(message):
        raise CompileError(f"{location}: {message}")

    memo, active = {}, set()
    pending = [(value, False)]
    while pending:
        item, exiting = pending.pop()
        identity = id(item)
        if identity in memo:
            continue
        children = _children(item)
        if children is None:
            memo[identity] = (0, 1)
            continue
        if not exiting:
            if identity in active:
                fail('cyclic IR exceeds the tree serialization limit')
            active.add(identity)
            pending.append((item, True))
            pending.extend((child, False) for child in reversed(children))
            continue
        depth = 1 + max((memo[id(child)][0] for child in children), default=0)
        size = 1 + sum(memo[id(child)][1] for child in children)
        if depth > MAX_IR_DEPTH:
            fail(f'generated IR depth limit ({MAX_IR_DEPTH}) exceeded')
        if size > MAX_IR_ITEMS:
            fail(f'expanded IR size limit ({MAX_IR_ITEMS} values/containers) exceeded')
        memo[identity] = (depth, size)
        active.remove(identity)
