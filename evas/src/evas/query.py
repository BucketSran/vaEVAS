"""Read-only queries over an explicitly compiled model; no numerical evaluation."""
from dataclasses import asdict

from .ir import Program
from .syntax import Parser


def _references(value):
    """Collect dependencies from IR expressions, not from model text heuristics."""
    nodes, states, operators = set(), set(), set()
    if isinstance(value, dict):
        if value.get("op") == "affine":
            nodes.update(term["node"] for term in value["terms"])
        elif value.get("op") == "state":
            states.add(value["state"])
        elif value.get("op") == "operator":
            operators.add(value["operator"])
        for child in value.values():
            n, s, o = _references(child)
            nodes.update(n)
            states.update(s)
            operators.update(o)
    elif isinstance(value, list):
        for child in value:
            n, s, o = _references(child)
            nodes.update(n)
            states.update(s)
            operators.update(o)
    return nodes, states, operators


def static_index(program: Program, instances=(), sources=None):
    """Return actual source origins and connectivity. Indices belong to this IR."""
    modules = []
    for path, source in (sources or {}).items():
        model = Parser(source, path).parse()
        modules.append(dict(name=model.name, source=path, ports=list(model.ports),
                            local_nodes=sorted(model.nodes), parameters=list(model.parameters)))
    ir = program.to_dict()
    contributions = []
    for index, contribution in enumerate(ir["contributions"]):
        nodes, states, operators = _references(contribution["rhs"])
        contributions.append(dict(index=index, **contribution,
                                  input_nodes=sorted(nodes), states=sorted(states),
                                  operators=sorted(operators)))
    operators = []
    for index, operator in enumerate(ir["operators"]):
        nodes, states, dependencies = _references(operator)
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
