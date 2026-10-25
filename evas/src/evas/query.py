"""Read-only queries over an explicitly compiled model; no numerical evaluation."""
from dataclasses import asdict

from .ir import Program
from .frontend import parse_sources


def _binding_sources(ir):
    """Structural definitions, including control edges and inactive writes.

    This is an overapproximation for connectivity, never a numerical local
    substitution. Binding indices are unique across the validated Program.
    """
    sources, captures = {}, {}
    pending = [(ir, ())]
    while pending:
        value, guards = pending.pop()
        if isinstance(value, dict):
            if value.get('kind') == 'real_bind':
                sources.setdefault(value['binding'], []).extend((value['value'], *guards))
            elif value.get('kind') == 'contribution_capture':
                captures.setdefault(value['contribution'], []).extend(guards)
            if value.get('kind') in ('procedure_if', 'procedure_loop'):
                guards = (*guards, value['left'], value['right'])
            pending.extend((child, guards) for child in value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend((child, guards) for child in value)
    return sources, captures


def _references(value, bindings):
    """Collect structural dependencies, retaining zero terms and source locals."""
    nodes, states, operators = set(), set(), set()
    pending, seen_bindings = [value], set()
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("op") == "affine":
                nodes.update(term["node"] for term in value["terms"])
            elif value.get("op") == "state":
                states.add(value["state"])
            elif value.get("op") == "operator":
                operators.add(value["operator"])
            elif value.get("op") == "real_local":
                binding = value['binding']
                if binding not in seen_bindings:
                    seen_bindings.add(binding)
                    pending.extend(bindings.get(binding, ()))
            pending.extend(value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend(value)
    return nodes, states, operators


def static_index(program: Program, instances=(), sources=None):
    """Return actual source origins and connectivity. Indices belong to this IR."""
    modules = []
    for model in parse_sources(sources or {}).values():
        modules.append(dict(name=model.name, source=model.source, ports=list(model.ports),
                            local_nodes=sorted(model.nodes), parameters=list(model.parameters)))
    ir = program.to_dict()
    bindings, captures = _binding_sources(ir)
    contributions = []
    for index, contribution in enumerate(ir["contributions"]):
        nodes, states, operators = _references((contribution["rhs"], captures.get(index, ())), bindings)
        contributions.append(dict(index=index, **contribution,
                                  input_nodes=sorted(nodes), states=sorted(states),
                                  operators=sorted(operators)))
    operators = []
    for index, operator in enumerate(ir["operators"]):
        nodes, states, dependencies = _references(operator, bindings)
        operators.append(dict(index=index, **operator, input_nodes=sorted(nodes),
                              states=sorted(states), dependencies=sorted(dependencies)))
    instance_rows = [asdict(instance) if not isinstance(instance, dict) else dict(instance)
                     for instance in instances]
    return dict(schema_version=ir["schema_version"], modules=modules, instances=instance_rows,
                nodes=[dict(index=index, name=name,
                            contributions=[c["index"] for c in contributions
                                           if index in (c["positive"], c["negative"])],
                            readers=[c["index"] for c in contributions if index in c["input_nodes"]])
                       for index, name in enumerate(ir["nodes"])],
                contributions=contributions, operators=operators,
                states=ir["states"], events=ir["events"])


def query_static(index, section, *, start=0, limit=100):
    if section not in ("modules", "instances", "nodes", "contributions", "operators", "states", "events"):
        raise ValueError("unknown static section")
    if type(start) is not int or start < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("start must be nonnegative; limit must be between 1 and 1000")
    rows = index[section]
    stop = min(start + limit, len(rows))
    return dict(items=rows[start:stop], total=len(rows),
                next_start=stop if stop < len(rows) else None)
