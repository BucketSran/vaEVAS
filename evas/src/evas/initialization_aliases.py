"""Bind source-ordered input expressions without manufacturing held state."""
from .lowering import lower
from .ir import Affine, Binary, Power
from .syntax import Assignment, Loop, CompileError, OPERATOR_NAMES
from .limits import check_ir


def bind_initial_voltage_aliases(compiler, writes):
    return _bind_input_aliases(compiler, writes)


def _bind_input_aliases(compiler, writes, *, body_names=None):
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
        if body_names is not None and statement.name not in body_names:
            continue
        if statement.name in compiler.constant_local_aliases:
            aliases[statement.name] = compiler.constant_local_aliases[statement.name]
            continue
        if compiler.model.variables[statement.name] != 'real' and body_names is None:
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
            if compiler.model.variables[statement.name] == 'integer':
                compiler.validate_integer_value(value, statement.token)
            if body_names is not None:
                check_ir(value)
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
    return {name: value for name, value in compiler.initial_voltage_aliases.items()
            if continuous(value)}


def bind_event_body_aliases(compiler, writes):
    """Bind only demanded single-writer input expressions for sampled bodies.

    Guards/settings retain the separate continuous alias map. Ordinary source
    types and every original decision arm are audited by the same lowerer as
    initialization; no initial value or persistent state substitutes an input.
    """
    def local_reads(root, seen):
        pending = [root]
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            if item.op == 'parameter' and item.value in compiler.local_variables:
                yield item.value
            pending.extend(item.args)

    known = compiler.constant_local_aliases | compiler.runtime_voltage_aliases
    demanded, seen = set(), set()
    pending = [statement for event in compiler.model.events for statement in event.body]
    while pending:
        statement = pending.pop()
        for field in ('rhs', 'left', 'right', 'index'):
            expression = getattr(statement, field, None)
            if expression is not None:
                demanded.update(local_reads(expression, seen))
        for expression in getattr(statement, 'args', ()):
            demanded.update(local_reads(expression, seen))
        for field in ('then_body', 'else_body', 'body'):
            pending.extend(getattr(statement, field, ()))
    demanded.difference_update(known)
    if not demanded or compiler.event_body_source_model is None:
        return {}
    # Electrical elaboration has already erased zero-trip loops before this
    # compiler sees its executable model. Read the retained original tree only
    # for a demanded new body alias, without changing legacy alias admission.
    source = compiler.event_body_source_model
    source_writers = {name: 1 for name in source.variable_initializers}
    pending = list(source.initial) + list(source.analog)
    pending.extend(statement for event in source.events for statement in event.body)
    while pending:
        statement = pending.pop()
        if isinstance(statement, (Assignment, Loop)):
            source_writers[statement.name] = source_writers.get(statement.name, 0) + 1
        for field in ('then_body', 'else_body', 'body'):
            pending.extend(getattr(statement, field, ()))
    scalar_names = {statement.name for statement in source.analog
                    if isinstance(statement, Assignment) and statement.index is None
                    and statement.name not in source.arrays and source_writers[statement.name] == 1}
    definitions = {statement.name: statement.rhs for statement in compiler.model.analog
                   if isinstance(statement, Assignment) and statement.index is None}
    pending, seen = list(demanded), set()
    while pending:
        name = pending.pop()
        expression = definitions.get(name)
        if expression is None:
            continue
        for dependency in local_reads(expression, seen):
            if dependency in definitions and dependency not in demanded:
                demanded.add(dependency)
                pending.append(dependency)
    # Every transitive definition needs its original scalar writer proof, not
    # just the final name. Legacy affine array aliases keep their separate map.
    demanded.intersection_update(scalar_names)
    result = _bind_input_aliases(compiler, writes, body_names=demanded)
    # This is a wire tree, even when transitive aliases share Python objects.
    # Count all retained bindings together before they enter any consumer.
    check_ir(result)
    return result
