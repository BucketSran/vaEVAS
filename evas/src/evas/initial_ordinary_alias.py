"""Initial-only real state keeps its seed and gets an ordinary total-write alias.

This is a role/dominance proof, not a new state or waveform evaluator. Every
accepted ordinary read still lowers at its original position through the existing
local environment. Initial statements, State slots and event consumers stay intact.
"""
from .errors import CompileError
from .syntax import (Assignment, Conditional, ContributionStatement, Display,
                     BoundStep, Loop, Event, OPERATOR_ARITIES, OPERATOR_NAMES)


def admit(compiler, name, persistent, analog_writers, source):
    owner = compiler.compilation.native_audit
    owner.activate(source.declaration_token)

    def charge(item, kind, amount=1):
        owner.extra(item, 'initial_ordinary_' + kind, amount)

    def fail(item, message):
        raise CompileError('initial-only ordinary alias ' + message,
                           code='unsupported_local_event', token=item.token,
                           instance=compiler.instance.name)

    charge(source.declaration_token, 'identity')
    if source.arrays or source.variables.get(name) != 'real':
        raise CompileError('initial-only ordinary alias requires an original real scalar without arrays',
                           code='unsupported_local_event', token=source.declaration_token,
                           instance=compiler.instance.name)

    # A port name does not certify an external physical source. Exclude a port
    # connected to another instance's declared output/inout before cancellation.
    charge(source.declaration_token, 'foreign_container')
    foreign = set()
    bindings = compiler.compilation.held_power2_bindings
    for instance, model, nets in bindings:
        charge(source.declaration_token, 'foreign_binding')
        if instance.name == compiler.instance.name:
            continue
        for port, direction in model.directions.items():
            charge(source.declaration_token, 'foreign_port')
            if direction in ('output', 'inout'):
                charge(source.declaration_token, 'foreign_element')
                foreign.add(compiler.compilation.indices[nets[port]])

    def expression(expr, env, *, ordinary=False, setting=False):
        if expr is None:
            return True, False
        charge(expr, 'expression')
        charge(expr, 'dependency', 1 + len(expr.args))
        dependent = False
        if expr.op == 'parameter':
            ref = expr.value
            if ref == name and ordinary and (ref not in env or not env[ref][0]):
                fail(expr, 'reads a prior evaluation or an uncertified dependency before its total write')
            dependent = ref == name
            if ref in env:
                safe = env[ref][0]
                dependent = dependent or env[ref][1]
            else:
                safe = (ref in source.parameters or
                        ref in persistent and ref not in analog_writers)
        elif expr.op == 'node':
            ref = expr.value
            # Original indexed probes have a vector base name, whereas node_ids
            # contains scalar bit names. This proof admits only scalar probes.
            safe = (not expr.args and
                    (ref == '0' or source.directions.get(ref) in ('input', 'inout')
                     and compiler.node_ids.get(ref) not in foreign))
        else:
            # $abstime and memoryless math keep the plain-local value contract;
            # history operators still need their own call-site/state proofs.
            safe = (expr.op not in OPERATOR_ARITIES and
                    expr.op not in ('index', 'array', 'call'))
        # Visit every arm/operand even when an earlier one is unsafe or zero.
        for index, child in enumerate(expr.args):
            child_safe, child_dependent = expression(
                child, env, ordinary=ordinary,
                setting=setting or expr.op in OPERATOR_NAMES and index > 0)
            safe = child_safe and safe
            dependent = child_dependent or dependent
        if setting and dependent:
            fail(expr, 'cannot enter a waveform or bound-step setting')
        charge(expr, 'expression_fact', 2)
        return safe, dependent

    charge(source.declaration_token, 'position_container')
    callback_positions = []

    def roles(body, *, initial=False):
        charge(source.declaration_token, 'role_roots', 1 + len(body))
        found = False
        for item in body:
            charge(item, 'role_statement')
            if initial or isinstance(item, Event):
                charge(item, 'position_copy')
                callback_positions.append(item.token)
            if isinstance(item, Assignment) and item.name == name:
                if not initial:
                    fail(item, 'has a runtime event writer')
                found = True
            for field in ('rhs', 'left', 'right', 'index', 'start', 'limit', 'update'):
                expr = getattr(item, field, None)
                if expr is not None:
                    # This audit detects the target in all runtime event roles;
                    # it does not replace initial lowering/type/operator checks.
                    pending = [expr]
                    charge(expr, 'role_container')
                    while pending:
                        value = pending.pop()
                        charge(value, 'role_expression')
                        if not initial and value.op == 'parameter' and value.value == name:
                            fail(value, 'cannot be read by a runtime event or setting')
                        charge(value, 'role_copy', len(value.args))
                        pending.extend(value.args)
            if isinstance(item, Display):
                for arg in item.args:
                    charge(arg, 'display_argument')
                    # Display is only supported by the existing initializer.
                    if not initial:
                        def check(value):
                            charge(value, 'display_expression')
                            if value.op == 'parameter' and value.value == name:
                                fail(value, 'cannot be read by a runtime event display')
                            for child in value.args:
                                check(child)
                        check(arg)
            if isinstance(item, Event):
                for trigger in item.triggers:
                    charge(trigger, 'trigger')
                    for arg in trigger.arguments:
                        if arg is not None:
                            # A setting uses no ordinary lexical environment.
                            def check(value):
                                charge(value, 'trigger_expression')
                                if value.op == 'parameter' and value.value == name:
                                    fail(value, 'cannot drive a runtime event trigger')
                                for child in value.args:
                                    check(child)
                            check(arg)
                roles(item.body)
            else:
                for field in ('then_body', 'else_body', 'body'):
                    child = getattr(item, field, ())
                    if child:
                        found = roles(child, initial=initial) or found
        return found

    if not roles(source.initial, initial=True):
        raise CompileError('initial-only ordinary alias has no original initial writer',
                           code='unsupported_local_event', token=source.declaration_token,
                           instance=compiler.instance.name)
    for event in source.events:
        roles((event,))

    def ordinary_events(body):
        for item in body:
            charge(item, 'event_position_statement')
            if isinstance(item, Event):
                charge(item, 'event_position_root')
                roles((item,))
            else:
                for field in ('then_body', 'else_body', 'body'):
                    ordinary_events(getattr(item, field, ()))

    ordinary_events(source.analog)

    def follows_callbacks(item):
        for position in callback_positions:
            charge(item, 'position_compare')
            if (item.token.source != position.source or
                    (item.token.line, item.token.column) <= (position.line, position.column)):
                return False
        return True

    def source_only(expr, env):
        # A source-only transitive definition has the same current value on
        # both sides of a callback. It reads no held state the callback changes.
        # The initial-only target itself still has to follow every callback.
        charge(expr, 'pure_source_expression', 1 + len(expr.args))
        if expr.op == 'parameter':
            safe = expr.value in source.parameters or expr.value in env and env[expr.value][3]
        elif expr.op == 'node':
            safe = (not expr.args and (expr.value == '0' or
                    source.directions.get(expr.value) in ('input', 'inout')
                    and compiler.node_ids.get(expr.value) not in foreign))
        else:
            safe = (expr.op not in OPERATOR_NAMES and
                    expr.op not in ('time', 'index', 'array', 'call', 'floor'))
        for child in expr.args:
            child_safe = source_only(child, env)
            safe = safe and child_safe
        return safe

    def flow(body, env, *, active_dependent=False):
        charge(source.declaration_token, 'environment_copy', 1 + len(env))
        env = dict(env)
        for item in body:
            charge(item, 'statement')
            if isinstance(item, Event):
                # Earlier role audit proves no event reads or writes this name.
                continue
            if isinstance(item, Loop):
                fail(item, 'does not support ordinary loop carry')
            if isinstance(item, Conditional):
                left = expression(item.left, env, ordinary=True)
                right = expression(item.right, env, ordinary=True)
                pure_guard = source_only(item.left, env)
                pure_guard = source_only(item.right, env) and pure_guard
                charge(item, 'guard_dependency')
                guard_dependent = active_dependent or left[1] or right[1]
                yes = flow(item.then_body, env, active_dependent=guard_dependent)
                no = flow(item.else_body, env, active_dependent=guard_dependent)
                charge(item, 'merge_container', 2 + len(yes) + len(no))
                merged = {}
                for ref in yes.keys() & no.keys():
                    charge(item, 'merge_element')
                    if yes[ref] is no[ref]:
                        merged[ref] = yes[ref]
                    else:
                        # Pure branch values alone do not certify a prefix:
                        # before callbacks, its selecting guard must be pure
                        # input too. Otherwise retain the original order gate.
                        safe = (left[0] and right[0] and yes[ref][0] and no[ref][0]
                                and (pure_guard or follows_callbacks(item)))
                        charge(item, 'merge_dependency')
                        dependent = (guard_dependent or yes[ref][1] or no[ref][1])
                        if ref == name and not safe:
                            fail(item, 'has an uncertified ordinary guard dependency')
                        charge(item, 'merge_binding', 4)
                        merged[ref] = (safe, dependent, item,
                                       pure_guard and yes[ref][3] and no[ref][3])
                env = merged
                continue
            if isinstance(item, Assignment):
                safe, dependent = expression(item.rhs, env, ordinary=True)
                pure = source_only(item.rhs, env)
                charge(item, 'binding_dependency')
                dependent = active_dependent or dependent
                ordered = follows_callbacks(item)
                if item.name == name and not ordered:
                    fail(item, 'requires its ordinary definitions after every initial/runtime callback')
                safe = safe and (ordered or pure)
                if item.index is not None:
                    _, index_dependent = expression(item.index, env, ordinary=True)
                    charge(item, 'index_dependency')
                    dependent = index_dependent or dependent
                    safe = False
                    pure = False
                if item.name == name and not safe:
                    fail(item, 'depends on time, history, an unresolved local, or a foreign/output/indexed node')
                charge(item, 'binding', 4)
                env[item.name] = (safe, dependent, item, pure)
            elif isinstance(item, (ContributionStatement, BoundStep)):
                expression(item.rhs, env, ordinary=True, setting=isinstance(item, BoundStep))
                if isinstance(item, BoundStep):
                    charge(item, 'setting_guard')
                    if active_dependent:
                        fail(item, 'cannot activate a bound-step setting')
            elif isinstance(item, Display):
                for arg in item.args:
                    expression(arg, env, ordinary=True)
            else:
                fail(item, 'requires a supported ordinary source statement')
        return env

    charge(source.declaration_token, 'environment_container')
    flow(source.analog, {})
    return True
