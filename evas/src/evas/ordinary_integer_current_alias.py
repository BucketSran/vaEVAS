"""Prove a total current-input integer write separately from its event State."""
from .errors import CompileError
from .lowering import lower
from .syntax import Assignment, Event, Loop, OPERATOR_NAMES


def admit(compiler, name, source):
    owner = compiler.compilation.native_audit
    owner.activate(source.declaration_token)

    def charge(item, kind, count=1):
        owner.extra(item, 'integer_current_' + kind, count)

    def fail(item, message):
        raise CompileError('ordinary current integer alias ' + message,
                           code='unsupported_local_event', token=getattr(item, 'token', source.declaration_token),
                           instance=compiler.instance.name)

    charge(source.declaration_token, 'identity')
    if source.arrays or source.variables.get(name) != 'integer' or name in source.variable_initializers:
        fail(source, 'requires an original scalar integer without declaration initialization')
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

    def expression(expr):
        charge(expr, 'expression', 1 + len(expr.args))
        reads = expr.op == 'parameter' and expr.value == name
        if expr.op == 'parameter':
            safe = expr.value in source.parameters
        elif expr.op == 'node':
            safe = (not expr.args and (expr.value == '0' or
                    source.directions.get(expr.value) in ('input', 'inout')
                    and compiler.node_ids.get(expr.value) not in foreign))
        else:
            safe = (expr.op not in OPERATOR_NAMES and
                    expr.op not in ('time', 'index', 'array', 'call', 'floor', 'checked'))
        # All original operands and arms are visited before accepting a proof.
        for child in expr.args:
            child_reads, child_safe = expression(child)
            reads = reads or child_reads
            safe = safe and child_safe
        return reads, safe

    candidate = None
    ordinary_writes = 0

    def walk(body, assigned=False, *, event=False, top=False):
        nonlocal candidate, ordinary_writes
        charge(source.declaration_token, 'body_roots', 1 + len(body))
        for item in body:
            charge(item, 'statement')
            if isinstance(item, Loop):
                fail(item, 'does not admit original source loops')
            if isinstance(item, Event):
                for trigger in item.triggers:
                    charge(item, 'trigger')
                    for arg in trigger.arguments:
                        if arg is not None and expression(arg)[0]:
                            fail(item, 'cannot enter event triggers or settings')
                walk(item.body, event=True)
                continue
            target = isinstance(item, (Assignment, Loop)) and item.name == name
            for field in ('rhs', 'left', 'right', 'index', 'start', 'limit', 'update', 'branch'):
                expr = getattr(item, field, None)
                if expr is not None:
                    reads, _ = expression(expr)
                    if reads and (event or not assigned):
                        fail(item, 'has an event read or an ordinary read before its total write')
            for expr in getattr(item, 'args', ()):
                if expression(expr)[0] and (event or not assigned):
                    fail(item, 'has an event read or an ordinary read before its total write')
            if target and not event:
                ordinary_writes += 1
                if not top or isinstance(item, Loop) or item.index is not None or ordinary_writes != 1:
                    fail(item, 'requires exactly one unconditional top-level ordinary writer')
                _, safe = expression(item.rhs)
                if not safe:
                    fail(item, 'requires an original pure current-input right hand side')
                charge(item, 'candidate_binding')
                candidate = item
                assigned = True
            for field in ('then_body', 'else_body', 'body'):
                children = getattr(item, field, ())
                if children:
                    walk(children, assigned, event=event)
        return assigned

    # Source events may live inside analog before executable extraction. Scan
    # both original representations, without deduplicating or trusting lowering.
    walk(source.initial, event=True)
    for event in source.events:
        walk((event,), event=True)
    walk(source.analog, top=True)
    if candidate is None:
        fail(source, 'has no original unconditional ordinary writer')
    value = lower(candidate.rhs, compiler.typed_resolve(compiler.parameter),
                  compiler.node_ids, compiler.model.source, preserve_structure=True,
                  decisions=compiler.initial_select,
                  validate_decision=compiler.validate_initial_operand,
                  node_declarations=True)
    compiler.validate_initial_operand(candidate.rhs, value)
    compiler.checked_ir(value, candidate.token)
    compiler.validate_integer_value(value, candidate.token)
    return True
