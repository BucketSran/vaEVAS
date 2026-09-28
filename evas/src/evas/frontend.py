"""Bind parsed models and lower static voltage contributions to the shared IR.

Parameter evaluation, instance/node binding, and expression lowering belong here;
syntax.py owns tokenization and syntax trees.
"""

from dataclasses import dataclass, field
import math
from typing import Mapping

from .ir import BranchIdentity, Contribution, Origin, Program
from .lowering import lower, scale
from .syntax import CompileError, Expr, Parser


@dataclass(frozen=True)
class Instance:
    name: str
    module: str
    connections: Mapping[str, str]
    parameters: Mapping[str, float] = field(default_factory=dict)


def compile_sources(sources: Mapping[str, str], instances: list[Instance]) -> Program:
    """Compile source text and explicit flat instances; never import validation data."""
    models = {}
    for path, text in sources.items():
        model = Parser(text, path).parse()
        if model.name in models:
            raise CompileError(f"duplicate module {model.name!r}")
        models[model.name] = model
    if not instances or len({i.name for i in instances}) != len(instances):
        raise CompileError("instances must be nonempty and have unique names")
    bindings = []
    for instance in instances:
        if not instance.name or not instance.module or instance.module not in models:
            raise CompileError(f"unknown module or empty instance identity: {instance}")
        model = models[instance.module]
        if set(instance.connections) != set(model.ports):
            raise CompileError(f"{instance.name}: connections must exactly match {model.ports}")
        if any(not isinstance(n, str) or not n or ":" in n for n in instance.connections.values()):
            raise CompileError("net names must be nonempty strings without ':' (reserved for internal nodes)")
        if ":" in instance.name:
            raise CompileError("instance names cannot contain ':'")
        if not set(instance.parameters) <= model.parameters.keys():
            raise CompileError(f"{instance.name}: unknown parameter override")
        nets = {n: instance.connections.get(n, f"{instance.name}:{n}") for n in model.nodes}
        nets["0"] = "0"
        bindings.append((instance, model, nets))
    names = ("0", *sorted({n for _, _, nets in bindings for n in nets.values()} - {"0"}))
    indices = {n: i for i, n in enumerate(names)}
    contributions = []
    for instance, model, nets in bindings:
        cache, active = {}, set()

        def parameter(name):
            if name not in model.parameters:
                raise CompileError(f"{model.source}: unknown parameter {name!r}")
            if name in active:
                raise CompileError(f"{model.source}: cyclic parameter defaults involving {name!r}")
            if name not in cache:
                active.add(name)
                if name in instance.parameters:
                    value = instance.parameters[name]
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise CompileError(f"{instance.name}: parameter {name!r} must be numeric")
                    try:
                        value = float(value)
                    except OverflowError as exc:
                        raise CompileError(f"{instance.name}: nonfinite parameter {name!r}") from exc
                else:
                    value = lower(model.parameters[name], parameter, {}, model.source).constant
                if not math.isfinite(value):
                    raise CompileError(f"{instance.name}: nonfinite parameter {name!r}")
                cache[name] = value
                active.remove(name)
            return cache[name]

        # Check every default's structure; evaluate only the effective graph
        # after overrides. Replaced arithmetic and dependency edges are not used.
        def validate_default(expr):
            if expr.op == "voltage" or (expr.op == "parameter" and expr.value not in model.parameters):
                raise CompileError(f"{model.source}:{expr.token.line}: invalid parameter default")
            for arg in expr.args:
                validate_default(arg)

        for expr in model.parameters.values():
            validate_default(expr)
        for name in model.parameters:
            parameter(name)
        node_ids = {n: indices[net] for n, net in nets.items()}
        bound_branches = {}
        for branch, rhs in model.contributions:
            lower(branch, parameter, node_ids, model.source)  # validates both target nodes
            local_p, local_n = (str(arg.value) for arg in branch.args)
            pair = tuple(sorted((local_p, local_n)))
            p, n = (node_ids[name] for name in pair)
            bound_pair = tuple(sorted((p, n)))
            if bound_pair in bound_branches and bound_branches[bound_pair] != pair:
                raise CompileError(f"{model.source}:{branch.token.line}: distinct local contribution branches alias after connection; not supported in this slice")
            bound_branches[bound_pair] = pair
            expression = lower(rhs, parameter, node_ids, model.source)
            sign = 1.0 if (local_p, local_n) == pair else -1.0
            origin = Origin(model.source, branch.token.line, branch.token.column, instance.name)
            identity = BranchIdentity(instance.name, *pair)
            contributions.append(Contribution(identity, p, n, scale(expression, sign), origin))
    return Program(names, tuple(contributions))
