"""Bind parsed models and lower voltage contributions and event state to the shared IR.

Parameter evaluation, instance/node binding, and expression lowering belong here;
syntax.py owns tokenization and syntax trees.
"""

from dataclasses import dataclass, field
import math
from typing import Mapping

from .ir import (Affine, Assignment, Conditional, Binary, BranchIdentity, Contribution, CrossTrigger, Event, TimerTrigger,
                 Origin, Program, State, StateRef, OperatorRef, Transition, AbsDelay, Slew, Idt)
from .lowering import lower, scale
from .syntax import CompileError, Expr, Parser, Conditional as SyntaxConditional


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
    def contains_operator(expr):
        return expr.op in ("transition", "absdelay", "slew", "idt") or any(contains_operator(arg) for arg in expr.args)

    # A separate instance may connect an operator output to a guard. Preserve
    # the whole program's structural voltage graph before numeric cancellation.
    has_operators = any(contains_operator(rhs) for _, model, _ in bindings
                        for _, rhs in model.contributions)
    def has_condition(body):
        return any(isinstance(statement, SyntaxConditional) for statement in body)

    has_conditions = any(has_condition(event.body) for _, model, _ in bindings for event in model.events)
    names = ("0", *sorted({n for _, _, nets in bindings for n in nets.values()} - {"0"}))
    indices = {n: i for i, n in enumerate(names)}
    contributions, states, events, operators = [], [], [], []
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
        state_ids = {name: len(states) + index for index, name in enumerate(model.variables)}
        initials = {}
        for statement in model.initial:
            if statement.name not in state_ids or statement.name in initials:
                raise CompileError(f"{model.source}:{statement.token.line}: initial_step must initialize each declared state exactly once")
            value = lower(statement.rhs, parameter, {}, model.source)
            if not isinstance(value, Affine) or value.terms:
                raise CompileError("initial_step values must be instance constants")
            if model.variables[statement.name] == "integer" and not (-2147483648 <= value.constant <= 2147483647 and value.constant.is_integer()):
                raise CompileError("integer initialization must be an exact signed 32-bit integer")
            initials[statement.name] = value.constant
        if set(initials) != set(state_ids):
            raise CompileError(f"{model.source}: every state requires one constant initial_step assignment")
        states.extend(State(instance.name, name, kind, initials[name]) for name, kind in model.variables.items())

        def symbol(name):
            return StateRef(state_ids[name]) if name in state_ids else parameter(name)

        # Integer assignments are restricted to integral state arithmetic; do
        # not silently substitute a different real-to-integer rounding rule.
        def integral(expression):
            if isinstance(expression, Affine):
                return not expression.terms and expression.constant.is_integer()
            if isinstance(expression, StateRef):
                return states[expression.state].kind == "integer"
            return isinstance(expression, Binary) and integral(expression.left) and integral(expression.right)

        for event in model.events:
            def setting(arg):
                value = lower(arg, parameter, {}, model.source)
                if not isinstance(value, Affine) or value.terms:
                    raise CompileError(f"{event.kind} settings must be instance constants")
                return value.constant

            if event.kind == "cross":
                settings = [0.0, 1e-12, 1e-9]
                for index, arg in enumerate(event.arguments[1:]):
                    settings[index] = setting(arg)
                direction, time_tol, expr_tol = settings
                if direction not in (-1, 0, 1) or time_tol <= 0 or expr_tol <= 0:
                    raise CompileError("cross requires direction -1/0/1 and positive tolerances")
                trigger = CrossTrigger(lower(event.arguments[0], symbol, node_ids, model.source, preserve_structure=True),
                                       int(direction), time_tol, expr_tol)
            else:
                start = setting(event.arguments[0])
                period = 0.0 if event.arguments[1] is None else setting(event.arguments[1])
                time_tol = setting(event.arguments[2])
                enabled = setting(event.arguments[3]) != 0 if len(event.arguments) == 4 else True
                if start < 0 or time_tol <= 0:
                    raise CompileError("timer requires nonnegative start and positive time_tol")
                trigger = TimerTrigger(start, period, time_tol, enabled)
            def body(statements):
                result = []
                for statement in statements:
                    origin = Origin(model.source, statement.token.line, statement.token.column, instance.name)
                    if isinstance(statement, SyntaxConditional):
                        # Predicate state references are rejected even if their
                        # numeric coefficients would cancel. The kernel also
                        # proves independence through the voltage network.
                        left = lower(statement.left, parameter, node_ids, model.source, preserve_structure=True)
                        right = lower(statement.right, parameter, node_ids, model.source, preserve_structure=True)
                        result.append(Conditional({"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation],
                                                  left, right, body(statement.then_body), body(statement.else_body), origin))
                    else:
                        if statement.name not in state_ids:
                            raise CompileError(f"{model.source}:{statement.token.line}: assignment target must be an instance state")
                        value = lower(statement.rhs, symbol, node_ids, model.source)
                        if model.variables[statement.name] == "integer" and not integral(value):
                            raise CompileError("integer assignment requires integral state arithmetic")
                        result.append(Assignment(state_ids[statement.name], value))
                return tuple(result)

            origin = Origin(model.source, event.token.line, event.token.column, instance.name)
            events.append(Event(trigger, body(event.body), origin))

        def waveform(expr):
            input_nodes = {} if expr.op == "transition" else node_ids
            value = lower(expr.args[0], symbol, input_nodes, model.source, preserve_structure=True)
            settings = [lower(arg, parameter, {}, model.source) for arg in expr.args[1:]]
            if any(not isinstance(v, Affine) or v.terms for v in settings):
                raise CompileError(f"{expr.op} settings must be instance constants")
            origin = Origin(model.source, expr.token.line, expr.token.column, instance.name)
            index = len(operators)
            if expr.op == "idt":
                operators.append(Idt(value, settings[0].constant, origin))
            elif expr.op == "absdelay":
                delay = settings[0].constant
                if delay < 0:
                    raise CompileError("absdelay requires nonnegative delay; zero is an EVAS extension")
                operators.append(AbsDelay(value, delay, origin))
            elif expr.op == "transition":
                delay, rise, fall = (v.constant for v in settings)
                if delay < 0 or rise <= 0 or fall <= 0:
                    raise CompileError("transition requires nonnegative delay and positive explicit edge times")
                operators.append(Transition(value, delay, rise, fall, origin))
            else:
                rise, fall = (v.constant for v in settings)
                if rise <= 0 or fall >= 0:
                    raise CompileError("slew requires explicit rise > 0 and fall < 0")
                operators.append(Slew(value, rise, fall, origin))
            return OperatorRef(index)

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
            expression = lower(rhs, symbol, node_ids, model.source, waveform, has_operators or has_conditions)
            sign = 1.0 if (local_p, local_n) == pair else -1.0
            origin = Origin(model.source, branch.token.line, branch.token.column, instance.name)
            identity = BranchIdentity(instance.name, *pair)
            contributions.append(Contribution(identity, p, n, scale(expression, sign), origin))
    return Program(names, tuple(contributions), tuple(states), tuple(events), tuple(operators))
