"""Parse models, bind flat instances and coordinate one compilation context."""
from dataclasses import dataclass, field
from typing import Mapping, Iterable

from .ir import Program
from .elaboration import inline_functions
from .loop_bounds import bound_loops
from .hierarchy import bind_hierarchy
from .preprocessor import preprocess_sources
from .instance_compiler import Compilation, InstanceCompiler
from .settled_integer_reads import isolated_output_encoder
from .syntax import (CompileError, Parser, contains_operator, Assignment as SyntaxAssignment,
                     Conditional as SyntaxConditional, ContributionStatement, BoundStep, Loop, Display, Event)


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
            model = bound_loops(inline_functions(parsed))
            if model.name in models:
                raise CompileError(f"duplicate module {model.name!r}", code="duplicate_module",
                                   token=model.declaration_token)
            models[model.name] = model
    return models


def compile_sources(sources: Mapping[str, str], instances: list[Instance], *, external_nodes: Iterable[str] = ()) -> Program:
    """Compile source text and explicit flat instances; never import validation data."""
    external_nodes = tuple(external_nodes)
    if any(not isinstance(n, str) or not n or n.startswith('$') for n in external_nodes):
        raise CompileError("external nodes must be nonempty ordinary node names")
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
            elif isinstance(statement, Display):
                yield from statement.args
            elif isinstance(statement, Event):
                yield from body_expressions(statement.body)
                yield from (arg for trigger in statement.triggers for arg in trigger.arguments if arg is not None)
            elif isinstance(statement, (ContributionStatement, BoundStep)):
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
    def uses_time(expr):
        return expr.op == 'time' or any(uses_time(arg) for arg in expr.args)
    has_time = any(uses_time(expr) for _, model, _ in bindings
                   for expr in (*body_expressions(model.analog), *body_expressions(model.initial),
                                *(expr for event in model.events for expr in body_expressions(event.body)),
                                *(arg for event in model.events for leaf in event.triggers
                                  for arg in leaf.arguments if arg is not None)))
    node_names = {n for _, _, nets in bindings for n in nets.values()} | set(external_nodes)
    if has_time:
        node_names.add('$abstime')
    names = ("0", *sorted(node_names - {"0"}))
    compilation = Compilation(names, has_operators or has_conditions,
                              settled_integer_reads=isolated_output_encoder(bindings))
    # Reuse the already-required whole-source operator-presence fact. This
    # reference does not scan again or confer semantic/typing eligibility.
    compilation.native_audit.debit("held_power2_operator_fact", 2)
    compilation.has_waveform_operators = has_operators
    # Borrow the complete bindings before compiling any instance. No semantic fact is cached.
    compilation.native_audit.debit("held_power2_bindings_reference", 4)
    compilation.held_power2_bindings = bindings
    compilation.held_power2_source_models = models
    for instance, model, nets in bindings:
        try:
            InstanceCompiler(instance, model, nets, compilation, source_model=models[model.name]).compile()
        except CompileError as error:
            error.diagnostic.setdefault("instance", instance.name)
            raise
    return compilation.program()
