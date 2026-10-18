"""Conservative whole-program proof that encoded outputs cannot feed writers.

Entry invariants bound completed events, not every intermediate assignment.
The first consumer deliberately accepts only one isolated, grounded output
encoder. Any observer, alias or unresolved analog network keeps lifetime facts.
"""
from dataclasses import fields, is_dataclass

from .syntax import ContributionStatement, Expr


def _voltage_reads(value):
    result, seen, pending = set(), set(), [value]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, Expr):
            if item.op == "voltage":
                result.update(str(arg.value) for arg in item.args if str(arg.value) != "0")
            pending.extend(item.args)
        elif is_dataclass(item):
            pending.extend(getattr(item, field.name) for field in fields(item))
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, (tuple, list)):
            pending.extend(item)
    return result


def isolated_output_encoder(bindings):
    """Certify after hierarchy/net binding, before any instance is compiled.

    Multiple flattened instances include passive observers. Rejecting them
    avoids assuming that a module's output direction prevents outside reads.
    Runtime requests still own their existing topology and source validation.
    """
    if len(bindings) != 1:
        return False
    _, model, nets = bindings[0]
    inputs = {name for name, direction in model.directions.items() if direction == "input"}
    outputs = {name for name, direction in model.directions.items() if direction == "output"}
    if inputs | outputs != set(model.ports):
        return False
    input_nets = {nets[name] for name in inputs}
    output_nets = [nets[name] for name in outputs]
    if (input_nets.intersection(output_nets) or "0" in output_nets
            or len(set(output_nets)) != len(output_nets)):
        return False
    if model.nodes - set(model.ports) - {"0"}:
        return False
    # This includes initial/final_step, trigger arguments, displays, aliases
    # and declaration initializers before initial_step can overwrite a seed.
    if not _voltage_reads((model.initial, model.events, model.variable_initializers)) <= inputs:
        return False
    written = set()
    for statement in model.analog:
        if not isinstance(statement, ContributionStatement):
            return False
        terminals = [str(arg.value) for arg in statement.branch.args]
        if len(terminals) == 1:
            terminals.append("0")
        live = [name for name in terminals if name != "0"]
        if (len(live) != 1 or live[0] not in outputs or live[0] in written
                or not _voltage_reads(statement.rhs) <= inputs):
            return False
        written.add(live[0])
    return written == outputs and bool(outputs)
