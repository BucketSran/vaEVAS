"""Bound long direct argument chains inside their existing caller activation.

Child activations keep their original slots and body. Only their numeric
copy-out is bound in a caller-owned temporary, before the next actual argument.
"""
from .syntax import Assignment
from .limits import MAX_IR_DEPTH
from .ir import (RealCall, RealBind, RealBoundary, RealLocal, RealBinding,
                 ProcedureStep)

# One serialized argument nesting adds Call.body -> tuple -> Step.action ->
# Bind.value -> Boundary.value, five levels. Reserve ten levels for the
# program/contribution shell and the leaf/Origin shape. The ordinary depth
# check still governs any additional surrounding expression structure.
_ARGUMENT_WRAPPER_DEPTH = 5
_ARGUMENT_CHAIN_LIMIT = max(2, (MAX_IR_DEPTH-10)//_ARGUMENT_WRAPPER_DEPTH)


def bind_argument_chain(c, result, function):
    owner = c.compilation.native_audit
    owner.debit('real_call_chain_qualification', 4+len(function.body), result)
    if (function.return_type != 'real' or len(function.inputs) != 1
            or function.variable_types[function.inputs[0]] != 'real'
            or not all(isinstance(s, Assignment) for s in function.body)):
        return result
    facts = getattr(c, '_real_call_argument_chains', None)
    if facts is None:
        owner.debit('real_call_chain_context', 1, result)
        c._real_call_argument_chains = facts = {}
    owner.debit('real_call_chain_shape', 5, result)
    first = result.body[0].action
    child = first.value.value if isinstance(first, RealBind) and isinstance(first.value, RealBoundary) and first.value.kind == 'argument' else None
    owner.debit('real_call_chain_lookup', 2, result)
    known = facts.get(id(child)) if isinstance(child, RealCall) else None
    depth = 1+(known[1] if known is not None else 0)
    owner.debit('real_call_chain_insert', 3, result)
    facts[id(result)] = (result, depth, True)
    if depth < _ARGUMENT_CHAIN_LIMIT:
        return result
    return _bind_chain(c, result, facts)


def _bind_chain(c, root, facts):
    owner = c.compilation.native_audit
    builder = c.procedure_builder
    owner.debit('real_call_chain_pending', 2, root)
    calls = [root]
    current = root
    while True:
        owner.debit('real_call_chain_collect', 6, current)
        first = current.body[0].action
        child = first.value.value
        known = facts.get(id(child)) if isinstance(child, RealCall) else None
        if known is None:
            break
        owner.debit('real_call_chain_append', 1, child)
        calls.append(child)
        if not known[2]:
            break
        current = child
    # This scan uses only a completed structural fact from this instance. No
    # call result or parameter/state value is inspected or remembered.
    owner.debit('real_call_chain_output', 2, root)
    prefix, temporaries = [], []
    read = None
    leaf_depth = facts[id(calls[-1])][1]

    def metadata(old, new):
        owner.debit('real_call_chain_metadata', 6, old)
        degree = builder.degree_facts[id(old)][1]
        builder.degree_facts[id(new)] = (new, degree)
        c.real_call_nodes[id(new)] = c.real_call_nodes[id(old)]

    def replace_argument(call, argument):
        owner.debit('real_call_chain_body_copy', 1+len(call.body), call)
        body = list(call.body)
        step = body[0]
        action = step.action
        value = c.make_ir(RealBoundary, argument, action.value.kind, action.value.origin)
        body[0] = c.make_ir(ProcedureStep, step.expanded_statement_ordinal,
                            c.make_ir(RealBind, action.binding, value, action.origin))
        owner.debit('real_call_chain_body_freeze', 1+len(body), call)
        new = c.make_ir(RealCall, call.origin, call.bindings, tuple(body), call.result)
        metadata(call, new)
        return new

    # Reversed indexing avoids allocating another source/call list. Each
    # copied child remains an independent activation with its original slots.
    owner.debit('real_call_chain_range', 1, root)
    for position in range(len(calls)-1, 0, -1):
        owner.debit('real_call_chain_child', 2, root)
        child = calls[position]
        copied = child if read is None else replace_argument(child, read)
        binding = len(c.compilation.real_bindings)
        # Decimal formatting and concatenation precede three list insertions.
        owner.debit('real_call_chain_temp_name', len('__argument_copyout_')+2*max(1, binding.bit_length())+5, child)
        name = '__argument_copyout_'+str(binding)
        c.compilation.real_bindings.append(c.make_ir(RealBinding,
            builder.procedure_id, name, child.origin, 'call'))
        temporaries.append(binding)
        boundary = c.make_ir(RealBoundary, copied, 'argument', child.origin)
        action = c.make_ir(RealBind, binding, boundary, child.origin)
        prefix.append(action)
        read = c.make_ir(RealLocal, binding)
        owner.debit('real_call_chain_read_metadata', 4, child)
        builder.degree_facts[id(read)] = (read, builder.degree_facts[id(child)][1])
        c.program_facts.record_read(read, (copied,))
        dependencies = c.real_call_nodes[id(child)]
        owner.debit('real_call_chain_dependencies', 1+len(dependencies), child)
        builder.binding_nodes[binding] = set(dependencies)
    replacement = replace_argument(root, read)
    owner.debit('real_call_chain_root_body', 2+len(prefix)+2*len(replacement.body), root)
    actions = [*prefix, *(step.action for step in replacement.body)]
    owner.debit('real_call_chain_ordinals', 2+len(actions), root)
    body = tuple(c.make_ir(ProcedureStep, index, action) for index, action in enumerate(actions))
    owner.debit('real_call_chain_root_bindings', 2+len(root.bindings)+2*len(temporaries), root)
    bindings = root.bindings+tuple(temporaries)
    new = c.make_ir(RealCall, root.origin, bindings, body, root.result)
    metadata(root, new)
    owner.debit('real_call_chain_insert', 3, new)
    facts[id(new)] = (new, leaf_depth+1, False)
    return new
