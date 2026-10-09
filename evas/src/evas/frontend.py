"""Parse models, bind flat instances and coordinate one compilation context."""
from dataclasses import dataclass, field
from typing import Mapping

from .ir import Program
from .elaboration import inline_functions
from .hierarchy import bind_hierarchy
from .preprocessor import preprocess_sources
from .instance_compiler import Compilation, InstanceCompiler
from .syntax import (CompileError, Parser, contains_operator, Assignment as SyntaxAssignment,
                     Conditional as SyntaxConditional, ContributionStatement, Loop)


@dataclass(frozen=True)
class Instance:
    name: str
    module: str
    connections: Mapping[str, str]
    parameters: Mapping[str, float] = field(default_factory=dict)


def parse_sources(sources: Mapping[str, str]):
    """Collect modules from independent compilation units and their include graphs."""
    models = {}
    for path, tokens in preprocess_sources(sources):
        for parsed in Parser('', path, tokens=tokens).parse_all():
            model = inline_functions(parsed)
            if model.name in models:
                raise CompileError(f"duplicate module {model.name!r}", code="duplicate_module",
                                   token=model.declaration_token)
            models[model.name] = model
    return models


def compile_sources(sources: Mapping[str, str], instances: list[Instance]) -> Program:
    """Compile source text and explicit flat instances; never import validation data."""
    models = parse_sources(sources)
    for instance in instances:
        if (not isinstance(instance, Instance) or not isinstance(instance.name, str)
                or not isinstance(instance.module, str)):
            raise CompileError("instance name and module must be strings")
        if not isinstance(instance.connections, Mapping) or not isinstance(instance.parameters, Mapping):
            raise CompileError("instance connections and parameters must be mappings")
    if not instances or len({i.name for i in instances}) != len(instances):
        raise CompileError("instances must be nonempty and have unique names")
    bindings = bind_hierarchy(models, instances, Instance)
    # A separate instance may connect an operator output to a guard. Preserve
    # the whole program's structural voltage graph before numeric cancellation.
    def body_expressions(statements):
        for statement in statements:
            if isinstance(statement, Loop):
                yield from (statement.start,statement.limit,statement.update)
                yield from body_expressions(statement.body)
            elif isinstance(statement, ContributionStatement):
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
        return any(isinstance(statement, SyntaxConditional) or isinstance(statement, Loop) and has_condition(statement.body)
                   for statement in body)

    has_conditions = any(has_condition(model.analog) or any(has_condition(event.body) for event in model.events)
                         for _, model, _ in bindings)
    names = ("0", *sorted({n for _, _, nets in bindings for n in nets.values()} - {"0"}))
    compilation = Compilation(names, has_operators or has_conditions)
    for instance, model, nets in bindings:
        try:
            InstanceCompiler(instance, model, nets, compilation).compile()
        except CompileError as error:
            error.diagnostic.setdefault("instance", instance.name)
            raise
    return compilation.program()
