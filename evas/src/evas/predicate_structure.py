"""Closed, memoized structural check for event predicates before expansion.

This does not bind runtime state or register operators/decisions. Each source
node is lowered once in a fixed environment. Ordinary lower's prohibition on
memoizing semantic callbacks remains unchanged.
"""
from dataclasses import replace

from .errors import CompileError
from .ir import Origin, Select
from .limits import MAX_IR_ITEMS, check_ir
from .lowering import lower
from .syntax import Expr, OPERATOR_NAMES, contains_decision


def lower_predicate_structure(expr, resolve, nodes, source):
    from .instance_compiler import _predicate_degree

    values, degree_memo = {}, {}
    pending = [(expr, False)]

    def fail(message, item, code="compile_error"):
        raise CompileError(message, code=code, token=item.token)

    def validate(item, value):
        if _predicate_degree(value, degree_memo) is None:
            fail("event conditions require affine voltage/state predicates", item)

    def select(item, relation, left, right, yes, no):
        for value in (left, right, yes, no):
            validate(item, value)
        origin = Origin(item.token.source or source, item.token.line,
                        item.token.column, None, expansion=item.expansion)
        return Select(relation, left, right, yes, no, origin)

    while pending:
        item, exiting = pending.pop()
        key = id(item)
        if key in values:
            continue
        if item.op in OPERATOR_NAMES:
            fail("event conditions do not support history/operator calls", item)
        if item.op == "checked" and contains_decision(item):
            # Keep the existing closed function-obligation boundary. Supporting
            # direct abs/min/max is not permission to drop discarded decisions.
            fail("event function obligations do not support decisions", item)
        children = () if item.op == "voltage" else item.args
        if not exiting:
            if len(values) + len(pending) >= MAX_IR_ITEMS:
                fail("event predicate structure budget exceeded", item, "resource_budget")
            pending.append((item, True))
            pending.extend((child, False) for child in children)
            continue
        if item.op == "checked":
            for child in children:
                validate(child, values[id(child)][1])
            value = values[id(children[0])][1]
        elif not children:
            value = lower(item, resolve, nodes, source, preserve_structure=True)
        else:
            # Use existing arithmetic/decision lowering on one shallow node;
            # its operands are already checked IR, never re-expanded source.
            bindings = {f"operand_{i}": values[id(child)][1]
                        for i, child in enumerate(children)}
            args = tuple(Expr("parameter", f"operand_{i}", (), child.token)
                         for i, child in enumerate(children))
            value = lower(replace(item, args=args), bindings.__getitem__, nodes,
                          source, preserve_structure=True, decisions=select,
                          validate_decision=validate)
        validate(item, value)
        values[key] = (item, value)
    result = values[id(expr)][1]
    check_ir(result)
    return result
