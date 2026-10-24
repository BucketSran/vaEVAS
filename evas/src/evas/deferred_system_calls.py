"""Represent one statically valid system call as a selected-path failure.

No random stream, sample, seed mutation or nominal result is implemented here.
The execution consumer resolves arguments, then rejects the enclosing candidate.
"""
from dataclasses import is_dataclass
from .errors import CompileError
from .syntax import Expr, Token
from .ir import Origin, UnsupportedSystemCall
from .lowering import lower, _conditional_lookup


def seed_storage(model, owner):
    """Seed lvalues retain storage even when declaration-only before the call."""
    if not model.deferred_system_calls:
        return frozenset()
    owner.debit('deferred_seed_scan_setup', 2)
    pending = [model.procedure] if model.procedure else [model.initial, model.analog, model.events]
    names, seen = set(), set()
    while pending:
        value = pending.pop()
        owner.debit('deferred_seed_scan_visit', 1, value)
        if id(value) in seen:
            continue
        if isinstance(value, (Expr, tuple, list)) or is_dataclass(value) and not isinstance(value, Token):
            owner.debit('deferred_seed_scan_identity', 2)
            seen.add(id(value))
        if isinstance(value, Expr) and value.op == 'unsupported_system_call' and value.value == 'rdist_normal':
            # Qualification checked source arity/type/lvalue in every arm.
            owner.debit('deferred_seed_storage_record', 2)
            names.add(str(value.args[0].value))
        if isinstance(value, Expr):
            owner.debit('deferred_seed_scan_arguments', len(value.args))
            pending.extend(value.args)
        elif isinstance(value, (tuple, list)):
            owner.debit('deferred_seed_scan_elements', len(value))
            pending.extend(value)
        elif is_dataclass(value) and not isinstance(value, Token):
            schema = type(value).__dataclass_fields__
            owner.debit('deferred_seed_scan_fields', len(schema))
            pending.extend(getattr(value, field.name) for field in schema.values() if field.name != 'token')
    owner.debit('deferred_seed_storage_freeze', 1+len(names))
    return frozenset(names)


def lower_unsupported(c, expr, parameters, nodes, source, operators,
                      preserve_structure, decisions, validate_decision,
                      decision_scope, indices, *, node_declarations):
    owner = c.compilation.native_audit
    owner.activate(expr.token)
    owner.debit('deferred_system_lower_signature', 5+len(expr.args), expr)
    def fail(message):
        raise CompileError(message, code='unsupported_system_function',
                           token=expr.token, instance=c.instance.name)
    if c.procedure_builder is None:
        fail('deferred system function requires a retained source procedure')
    if expr.value != 'rdist_normal' or len(expr.args) != 3:
        fail('unsupported system function or argument count')
    seed = expr.args[0]
    if (seed.op != 'parameter' or c.model.variables.get(seed.value) != 'integer'
            or seed.value not in c.state_ids or seed.value in c.model.arrays):
        fail('$rdist_normal seed requires a writable same-instance scalar integer state')
    # The seed is an lvalue identity; never lower it into a copied numeric value.
    # Mean then sigma remain exact source expressions/RN operations and effects.
    parameters = _conditional_lookup(parameters)
    args = tuple(lower(argument, parameters, nodes, source,
        lambda item:c.waveform(item, parameters), True,
        decisions, validate_decision, decision_scope, indices,
        node_declarations=node_declarations) for argument in expr.args[1:])
    origin = c.make_ir(Origin, expr.token.source or source, expr.token.line,
        expr.token.column, c.instance.name, expr.expansion)
    return c.make_ir(UnsupportedSystemCall, 'rdist_normal', c.state_ids[str(seed.value)], args, origin)
