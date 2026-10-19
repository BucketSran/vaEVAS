"""Keep bounded source-only event choices as their original expression tree.

This is a frontend candidate check. The kernel still audits the whole bound
physical event against its actual driven inputs and certifies every source box.
It does not enable the isolated observer, integer or array execution paths.
"""
from .input_rational_scope import input_rational_tree
from .ir import Affine, Binary, Select
from .limits import check_ir


# Start with explicit source ternaries. Other decision producers, typed integer
# tables and unused mathematical resource surrogates retain their own budgets.
SOURCE_OPS = frozenset(('number', 'parameter', 'voltage', 'checked',
                        '+', '-', '*', '/', 'unary+', 'unary-',
                        'ternary', '<', '<=', '>', '>='))



def _exceeds_legacy_expansion(value):
    """Whether the old assignment expander would visit more than4096 nodes.

    Each split creates two children, hence nodes=2*leaves-1. Arithmetic choices
    multiply; a Select first expands choices in both predicate operands, then
    chooses one of its value arms. Cache subtree costs, but add/multiply them at
    every wire reference. Saturating at2049 leaves avoids allocating the old
    Cartesian tree or performing any rejected work that would need a refund.
    """
    cap = 2049
    memo = {}

    def leaves(item):
        key = id(item)
        if key in memo:
            return memo[key]
        if isinstance(item, Select):
            value_arms = min(cap, leaves(item.then_value)+leaves(item.else_value))
            count = min(cap, leaves(item.left)*leaves(item.right)*value_arms)
        elif isinstance(item, Binary):
            count = min(cap, leaves(item.left)*leaves(item.right))
        else:
            count = 1
        memo[key] = count
        return count

    return leaves(value) == cap


def compact_source_assignment(compiler, statement, value, origin):
    """Whether this scalar real assignment can retain a compact source tree.

    Retain the legacy Conditional path whenever its4096-node expansion fits.
    Inspect the original source as well as IR: an audit-only opaque surrogate
    must not masquerade as a supported mathematical expression. No runtime
    branch is selected here, and every original checked operand is inspected.
    """
    if (not getattr(compiler, 'runtime_event_checks', False)
            or statement.index is not None
            or compiler.model.variables.get(statement.name) != 'real'):
        return False
    allowed = compiler.allowed_condition_nodes - {compiler.node_ids.get('$abstime')}
    pending, seen = [statement.rhs], set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if item.op == "function_assign":
            compiler.compilation.native_audit.extra(item, "function_assignment_compact_metadata", 4)
            if (item.value != "real" or item.result_type != "real" or len(item.args) != 1):
                return False
        elif item.op not in SOURCE_OPS:
            return False
        if item.op == 'voltage':
            # Include ground and same-node reads: cancellation must not turn an
            # internal/output dependency into an admissible source operand.
            if any(compiler.node_ids.get(str(arg.value)) not in allowed for arg in item.args):
                return False
            continue
        if item.op == 'parameter':
            original = compiler.symbol(str(item.value))
            if isinstance(original, (int, float)):
                original = Affine(float(original), ())
            if input_rational_tree(original, allowed) is None:
                return False
        pending.extend(item.args)
    # Count the actual expanded wire tree before parameter dead-code pruning.
    # input_rational_tree is only a structural walk, never a domain proof.
    check_ir(value, origin)
    return (input_rational_tree(value, allowed) is not None
            and _exceeds_legacy_expansion(value))
