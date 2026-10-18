"""Bind ordinary aliases for zero-time sampling without making them held state."""
from .lowering import lower
from .ir import Affine, Binary, Power
from .syntax import Assignment, CompileError, OPERATOR_NAMES


def bind_initial_voltage_aliases(compiler, writes):
    """Return source-ordered aliases; callers still apply lexical token scopes.

    A single unconditional writer prevents a later assignment from changing the
    meaning of an earlier alias. Runtime events retain their separate contract.
    """
    counts = {}
    for name in writes(compiler.model.analog):
        counts[name] = counts.get(name, 0) + 1
    aliases = {}
    for statement in compiler.model.analog:
        if (not isinstance(statement, Assignment) or statement.index is not None
                or statement.name not in compiler.local_variables
                or counts[statement.name] != 1):
            continue
        if statement.name in compiler.constant_local_aliases:
            aliases[statement.name] = compiler.constant_local_aliases[statement.name]
            continue
        if compiler.model.variables[statement.name] != 'real':
            continue
        pending = [statement.rhs]
        supported = True
        while pending:
            expression = pending.pop()
            if (expression.op in ('time', 'array', 'index', 'call')
                    or expression.op in OPERATOR_NAMES
                    or expression.op == 'parameter'
                    and expression.value not in compiler.model.parameters
                    and expression.value not in aliases):
                supported = False
                break
            pending.extend(expression.args)
        if not supported:
            continue
        try:
            resolve = compiler.typed_resolve(
                lambda name: aliases[name] if name in aliases else compiler.parameter(name))
            value = lower(statement.rhs, resolve, compiler.node_ids, compiler.model.source,
                          preserve_structure=True, decisions=compiler.initial_select,
                          validate_decision=compiler.validate_initial_operand,
                          node_declarations=True)
            compiler.validate_initial_operand(statement.rhs, value)
            aliases[statement.name] = value
        except CompileError as error:
            if error.diagnostic['code'] == 'resource_budget':
                raise
            # Only an actual initial read needs to diagnose this unsupported
            # alias. Ordinary execution keeps its existing lowering path.
    return aliases


def bind_runtime_voltage_aliases(compiler, writes):
    """Keep continuous input expressions, never their initial sampled values.

    The initializer binder already proves source order, declaration type and
    structural affinity against external inputs. Runtime aliases additionally
    exclude decisions so a cross guard stays one affine physical expression.
    """
    def continuous(expression):
        if isinstance(expression, Affine):
            return True
        if isinstance(expression, Binary):
            return (expression.op in ('add', 'multiply')
                    and continuous(expression.left) and continuous(expression.right))
        return (isinstance(expression, Power) and expression.exponent == 1
                and continuous(expression.base))
    return {name: value for name, value in bind_initial_voltage_aliases(compiler, writes).items()
            if continuous(value)}
