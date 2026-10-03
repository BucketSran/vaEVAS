"""Parse models, bind flat instances and coordinate one compilation context."""
from dataclasses import dataclass, field
from typing import Mapping

from .ir import Program
from .elaboration import inline_functions
from .instance_compiler import Compilation, InstanceCompiler
from .syntax import (CompileError, Parser, contains_operator, Assignment as SyntaxAssignment,
                     Conditional as SyntaxConditional, ContributionStatement)


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
        model = inline_functions(Parser(text, path).parse())
        if model.name in models:
            raise CompileError(f"duplicate module {model.name!r}")
        models[model.name] = model
    for instance in instances:
        if (not isinstance(instance, Instance) or not isinstance(instance.name, str)
                or not isinstance(instance.module, str)):
            raise CompileError("instance name and module must be strings")
        if not isinstance(instance.connections, Mapping) or not isinstance(instance.parameters, Mapping):
            raise CompileError("instance connections and parameters must be mappings")
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
    # A separate instance may connect an operator output to a guard. Preserve
    # the whole program's structural voltage graph before numeric cancellation.
    def body_expressions(statements):
        for statement in statements:
            if isinstance(statement, ContributionStatement):
                yield statement.rhs
            elif isinstance(statement, SyntaxAssignment):
                yield statement.rhs
            else:
                yield statement.left
                yield statement.right
                yield from body_expressions(statement.then_body)
                yield from body_expressions(statement.else_body)

    has_operators = any(contains_operator(expr) for _, model, _ in bindings
                        for expr in (*body_expressions(model.analog),
                                     *(arg for event in model.events for leaf in event.triggers
                                       for arg in leaf.arguments if arg is not None)))
    def has_condition(body):
        return any(isinstance(statement, SyntaxConditional) for statement in body)

    has_conditions = any(has_condition(model.analog) or any(has_condition(event.body) for event in model.events)
                         for _, model, _ in bindings)
    names = ("0", *sorted({n for _, _, nets in bindings for n in nets.values()} - {"0"}))
    compilation = Compilation(names, has_operators or has_conditions)
    for instance, model, nets in bindings:
        InstanceCompiler(instance, model, nets, compilation).compile()
    return compilation.program()
