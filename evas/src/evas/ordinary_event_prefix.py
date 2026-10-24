"""Bind a pure-input ordinary prefix separately at each runtime event site.

Source scalar reals and closed exact signed32 integer aliases without
initial/event/loop writers enter this path.
The returned trees read current physical inputs; no local becomes held state.
"""
from .errors import CompileError
from .ir import Affine, Origin, Select
from .lowering import lower
from .syntax import Assignment, Conditional, Event, Loop, OPERATOR_NAMES


def bind(compiler, writes):
    # The old mandatory alias demand walk supplies only a syntactic hint.
    # Qualification below still scans the current event bodies and original
    # source afresh; no previously accepted expression is trusted here.
    if not compiler.event_body_prefix_demand:
        return None
    owner = compiler.compilation.native_audit

    def charge(item, kind, count=1):
        owner.extra(item, 'ordinary_prefix_' + kind, count)

    # Legacy aliases keep their existing route. Inspect only actual new body
    # demands; trigger, direction, tolerance and timer settings never use this map.
    owner.debit('ordinary_prefix_demand_map')
    demands = {}
    for event in compiler.model.events:
        charge(event, 'legacy_alias_copy',
               6 + len(compiler.constant_local_aliases)
               + len(compiler.runtime_voltage_aliases) + len(compiler.event_body_aliases)
               + len(compiler.model.local_alias_scopes.get(event.token, ())))
        known = compiler.aliases_at(event.token, body=True)
        charge(event, 'demand_set')
        missing = set()
        charge(event, 'demand_container', 2 + len(event.body))
        pending = list(event.body)
        while pending:
            item = pending.pop()
            charge(item, 'demand_statement')
            for field in ('rhs', 'left', 'right', 'index'):
                expr = getattr(item, field, None)
                if expr is None:
                    continue
                charge(expr, 'demand_expression_container')
                expressions = [expr]
                while expressions:
                    expr = expressions.pop()
                    charge(expr, 'demand_expression')
                    if (expr.op == 'parameter' and expr.value in compiler.local_variables
                            and expr.value not in known):
                        charge(expr, 'demand_binding')
                        missing.add(expr.value)
                    charge(expr, 'demand_children', len(expr.args))
                    expressions.extend(expr.args)
            for field in ('then_body', 'else_body', 'body'):
                children = getattr(item, field, ())
                charge(item, 'demand_statement_children', len(children))
                pending.extend(children)
        if missing:
            charge(event, 'demand_event')
            demands[event.token] = missing
    if not demands or compiler.event_body_source_model is None:
        return {}
    source = compiler.event_body_source_model
    owner.activate(source.declaration_token)
    if source.arrays:
        return {}

    charge(source.declaration_token, 'forbidden_container')
    forbidden = set()

    def forbid(body):
        for item in body:
            charge(item, 'writer_statement')
            if isinstance(item, (Assignment, Loop)):
                charge(item, 'writer_binding')
                forbidden.add(item.name)
            for field in ('then_body', 'else_body', 'body'):
                forbid(getattr(item, field, ()))

    forbid(source.initial)
    for event in source.events:
        charge(event, 'writer_event')
        forbid(event.body)

    def event_and_loop_writers(body):
        for item in body:
            charge(item, 'original_statement')
            if isinstance(item, (Event, Loop)):
                if isinstance(item, Loop):
                    charge(item, 'loop_binding')
                    forbidden.add(item.name)
                forbid(item.body)
            else:
                for field in ('then_body', 'else_body'):
                    event_and_loop_writers(getattr(item, field, ()))

    event_and_loop_writers(source.analog)
    charge(source.declaration_token, 'foreign_container')
    foreign = set()
    for instance, model, nets in compiler.compilation.held_power2_bindings:
        charge(source.declaration_token, 'foreign_instance')
        if instance.name == compiler.instance.name:
            continue
        for port, direction in model.directions.items():
            charge(source.declaration_token, 'foreign_port')
            if direction in ('output', 'inout'):
                charge(source.declaration_token, 'foreign_binding')
                foreign.add(compiler.compilation.indices[nets[port]])

    def admissible(expr, env):
        charge(expr, 'original_expression', 1 + len(expr.args))
        if expr.op == 'parameter':
            safe = expr.value in source.parameters or expr.value in env
        elif expr.op == 'node':
            safe = (not expr.args and (expr.value == '0' or
                    source.directions.get(expr.value) in ('input', 'inout')
                    and compiler.node_ids.get(expr.value) not in foreign))
        else:
            safe = (expr.op not in OPERATOR_NAMES and
                    expr.op not in ('time', 'index', 'array', 'call', 'floor'))
        # No cancellation, constant branch or zero coefficient bypasses audit.
        for child in expr.args:
            child_safe = admissible(child, env)
            safe = safe and child_safe
        return safe

    def expression(expr, env):
        if not admissible(expr, env):
            return None
        try:
            resolve = compiler.typed_resolve(
                lambda name: env[name] if name in env else compiler.parameter(name),
                program_real=True)
            value = lower(expr, resolve, compiler.node_ids, compiler.model.source,
                          preserve_structure=True, decisions=compiler.initial_select,
                          validate_decision=compiler.validate_initial_operand,
                          node_declarations=True)
            compiler.validate_initial_operand(expr, value)
            compiler.checked_ir(value, expr.token)
            return value
        except CompileError as error:
            if error.diagnostic['code'] == 'resource_budget':
                raise
            return None

    charge(source.declaration_token, 'snapshot_container')
    snapshots = {}

    def flow(body, previous, *, callbacks=True):
        charge(source.declaration_token, 'environment_copy', 1 + len(previous))
        env = dict(previous)
        for item in body:
            charge(item, 'flow_statement')
            if isinstance(item, Event):
                if callbacks and item.token in demands:
                    missing = demands[item.token]
                    charge(item, 'snapshot_copy', 1 + len(missing))
                    snapshots[item.token] = {name: env[name] for name in missing if name in env}
            elif isinstance(item, Assignment):
                kind = source.variables.get(item.name)
                if (item.name in forbidden or kind not in ('real','integer')
                        or item.index is not None):
                    env.pop(item.name, None)
                    continue
                value = expression(item.rhs, env)
                if value is not None and kind == 'integer':
                    # Only an existing closed exact signed32 value can be an
                    # integer alias. Its original evaluation is retained by
                    # the procedure producer, not moved to this later read.
                    fact = compiler.program_real_closed(value)
                    if (fact.closed and fact.finite and fact.value.is_integer()
                            and -2147483648 <= fact.value <= 2147483647):
                        value = compiler.make_ir(Affine,fact.value,())
                    else:
                        value = None
                if value is None:
                    env.pop(item.name, None)
                else:
                    charge(item, 'binding')
                    env[item.name] = value
            elif isinstance(item, Conditional):
                left = expression(item.left, env)
                right = expression(item.right, env)
                yes = flow(item.then_body, env, callbacks=False)
                no = flow(item.else_body, env, callbacks=False)
                relation = {'<': 'lt', '<=': 'le', '>': 'gt', '>=': 'ge'}.get(item.relation)
                charge(item, 'merge_container', 2 + len(yes) + len(no))
                merged = {}
                for name in yes.keys() & no.keys():
                    charge(item, 'merge_binding')
                    # Keep source condition dependencies even for shared/equal
                    # leaves: a proved value is not a closed source program.
                    if left is not None and right is not None and relation is not None:
                        origin = compiler.make_ir(Origin, item.token.source or source.source,
                            item.token.line, item.token.column, compiler.instance.name,
                            item.token.expansion)
                        value = compiler.make_ir(Select, relation, left, right,
                                                 yes[name], no[name], origin)
                        compiler.checked_ir(value, origin)
                        merged[name] = value
                env = merged
        return env

    flow(source.analog, {})
    # Account each retained wire occurrence, including aliases sharing objects.
    compiler.checked_ir(snapshots, source.declaration_token)
    return snapshots
