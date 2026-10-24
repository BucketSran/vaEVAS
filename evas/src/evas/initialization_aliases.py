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
        owner = compiler.compilation.native_audit
        if compiler.model.functions:
            owner.debit('initial_alias_structure_container', 2, statement.rhs)
        pending = [statement.rhs]
        seen = {} if compiler.model.functions else None
        supported = True
        has_call, memo_eligible = False, bool(compiler.model.functions)
        while pending:
            if seen is not None:
                owner.debit('initial_alias_structure_pop', 2, statement.rhs)
            expression = pending.pop()
            if seen is not None:
                owner.debit('initial_alias_structure_lookup', 2, expression)
                if id(expression) in seen:
                    continue
                owner.debit('initial_alias_structure_insert', 2, expression)
                seen[id(expression)] = expression
                owner.debit('initial_alias_structure_kind', 3, expression)
                owner.debit('initial_alias_memo_qualification', 3, expression)
                has_call |= expression.source_call is not None
                memo_eligible &= expression.op in ('number', 'parameter', 'node', 'voltage', '+', '-', '*', '/',
                                                    'unary+', 'unary-', 'checked', 'function_assign')
                memo_eligible &= expression.op != 'function_assign' or expression.value == 'real'
            if (expression.op in ('time', 'array', 'index', 'call')
                    or expression.op in OPERATOR_NAMES
                    or expression.op == 'parameter'
                    and expression.value not in compiler.model.parameters
                    and expression.value not in aliases):
                supported = False
                break
            if seen is not None:
                owner.debit('initial_alias_structure_edges', 1+len(expression.args), expression)
            pending.extend(expression.args)
        if not supported:
            continue
        try:
            resolve = compiler.typed_resolve(
                lambda name: aliases[name] if name in aliases else compiler.parameter(name))
            memo = None
            if seen is not None and has_call and memo_eligible:
                # This compatibility view has no call/operator registration.
                # Its resolver closes over one fixed alias environment for this
                # one statement. Actual source calls execute later, uncached.
                from .lowering import _SourceAuditMemo
                memo = _SourceAuditMemo(owner.ir_work,
                    (None, compiler.initial_select, compiler.validate_initial_operand, None))
                memo.bind(resolve, compiler.node_ids, (True, False, True))
                resolve._source_audit_binding = memo.binding_token
            value = lower(statement.rhs, resolve, compiler.node_ids, compiler.model.source,
                          preserve_structure=True, decisions=compiler.initial_select,
                          validate_decision=compiler.validate_initial_operand,
                          node_declarations=True, memo=memo)
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
    # A routing hint, rebuilt by this mandatory demand walk; it is not an
    # eligibility proof and retains no source or lowered expression.
    compiler.event_body_prefix_demand = False

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
        if name not in scalar_names and not compiler.event_body_prefix_demand:
            # The old binder cannot supply this demanded ordinary local. Only
            # this new route pays to retain a hint; old aliases do no new walk,
            # allocate no hint container and incur no new owner charge.
            compiler.compilation.native_audit.extra(
                source.declaration_token, 'ordinary_prefix_demand_hint')
            compiler.event_body_prefix_demand = True
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
