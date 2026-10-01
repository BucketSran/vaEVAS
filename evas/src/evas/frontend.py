"""Bind parsed models and lower voltage contributions and event state to the shared IR.

Parameter evaluation, instance/node binding, and expression lowering belong here;
syntax.py owns tokenization and syntax trees.
"""

from dataclasses import dataclass, field
import math
from typing import Mapping

from .ir import (Affine, Assignment, Conditional, Binary, BranchIdentity, Contribution, CrossTrigger, Event, TimerTrigger, OrTrigger,
                 Origin, Program, Power, Select, State, StateRef, OperatorRef, Transition, AbsDelay, Slew, Idt, LaplaceNd, IdtMod, Sin, Ddt)
from .lowering import lower, scale
from .syntax import CompileError, Expr, Parser, Assignment as SyntaxAssignment, Conditional as SyntaxConditional, ContributionStatement


@dataclass(frozen=True)
class Instance:
    name: str
    module: str
    connections: Mapping[str, str]
    parameters: Mapping[str, float] = field(default_factory=dict)


def _predicate_degree(expression):
    """Structural scope: node-free constant (0), affine/select (1), or unsupported.

    No cancellation removes a dependency. Input-selected constants count as
    input-dependent, so only a node-free scalar can multiply a predicate.
    """
    if isinstance(expression, Affine):
        return int(bool(expression.terms))
    if isinstance(expression, Binary):
        left, right = _predicate_degree(expression.left), _predicate_degree(expression.right)
        if left is None or right is None:
            return None
        degree = max(left, right) if expression.op == "add" else left + right
        return degree if degree <= 1 else None
    if isinstance(expression, Power):
        degree = _predicate_degree(expression.base)
        return degree if degree == 0 or expression.exponent == 1 else None
    if isinstance(expression, Select):
        degrees = [_predicate_degree(value) for value in
                   (expression.left, expression.right, expression.then_value, expression.else_value)]
        return None if None in degrees else max(degrees)
    return None


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
        return expr.op in ("transition", "absdelay", "slew", "idt", "laplace_nd", "idtmod", "ddt", "sin") or any(contains_operator(arg) for arg in expr.args)

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
            if expr.op in ("voltage", "array") or contains_operator(expr) or (expr.op == "parameter" and expr.value not in model.parameters):
                raise CompileError(f"{model.source}:{expr.token.line}: invalid parameter default")
            for arg in expr.args:
                validate_default(arg)

        for expr in model.parameters.values():
            validate_default(expr)
        for name in model.parameters:
            parameter(name)
        node_ids = {n: indices[net] for n, net in nets.items()}
        local_variables = set(model.variables) if not model.initial and not model.events else set()
        if local_variables and any(model.variables[name] != "real" for name in local_variables):
            raise CompileError(f"{model.source}: ordinary analog local assignments only support real variables")
        # Local assignment arithmetic must be preserved even when there is no
        # conditional, or the last conditional disappears during optimization.
        # Plain models without locals retain their existing affine lowering.
        preserve_analog_structure = has_operators or has_conditions or bool(local_variables)
        state_names = tuple(name for name in model.variables if name not in local_variables)
        state_ids = {name: len(states) + index for index, name in enumerate(state_names)}
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
        states.extend(State(instance.name, name, model.variables[name], initials[name]) for name in state_names)

        def symbol(name):
            if name in local_variables:
                raise CompileError(f"{model.source}: local real {name!r} is not assigned before use")
            return StateRef(state_ids[name]) if name in state_ids else parameter(name)

        # Integer assignments are restricted to integral state arithmetic; do
        # not silently substitute a different real-to-integer rounding rule.
        def integral(expression):
            if isinstance(expression, Affine):
                return not expression.terms and expression.constant.is_integer()
            if isinstance(expression, StateRef):
                return states[expression.state].kind == "integer"
            return isinstance(expression, Binary) and integral(expression.left) and integral(expression.right)

        def waveform(expr, resolve):
            input_nodes = {} if expr.op == "transition" else node_ids
            value = lower(expr.args[0], resolve, input_nodes, model.source,
                          (lambda nested: waveform(nested, resolve)) if expr.op in ("sin", "idt", "laplace_nd", "ddt") else None,
                          preserve_structure=True)
            if expr.op == "laplace_nd":
                def coefficients(array):
                    if array.op != "array":
                        raise CompileError(f"{model.source}:{array.token.line}:{array.token.column}: laplace_nd coefficients must use standard constant array literals")
                    result = []
                    for item in array.args:
                        value = lower(item, parameter, {}, model.source)
                        if not isinstance(value, Affine) or value.terms:
                            raise CompileError(f"{model.source}:{item.token.line}:{item.token.column}: laplace_nd coefficients must be instance constants")
                        result.append(value.constant)
                    return tuple(result)
                numerator = coefficients(expr.args[1])
                denominator = coefficients(expr.args[2])
                if not numerator or not 2 <= len(denominator) <= 9 or len(numerator) > len(denominator):
                    raise CompileError("laplace_nd requires a proper rational filter of order 1 through 8")
                settings = ()
            else:
                setting_args = expr.args[1:2] if expr.op == "idt" else expr.args[1:]
                settings = [lower(arg, parameter, {}, model.source) for arg in setting_args]
                if any(not isinstance(v, Affine) or v.terms for v in settings):
                    raise CompileError(f"{expr.op} settings must be instance constants")
            origin = Origin(model.source, expr.token.line, expr.token.column, instance.name)
            index = len(operators)
            if expr.op == "idt":
                reset = lower(expr.args[2], resolve, {}, model.source, preserve_structure=True) if len(expr.args) == 3 else None
                operators.append(Idt(value, settings[0].constant, origin, reset))
            elif expr.op == "ddt":
                operators.append(Ddt(value, origin))
            elif expr.op == "laplace_nd":
                operators.append(LaplaceNd(value, numerator, denominator, origin))
            elif expr.op == "idtmod":
                ic, modulus, offset = (v.constant for v in settings)
                if modulus <= 0:
                    raise CompileError("idtmod requires positive explicit modulus")
                operators.append(IdtMod(value, ic, modulus, offset, origin))
            elif expr.op == "sin":
                operators.append(Sin(value, origin))
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

        for event in model.events:
            def trigger(leaf):
                def setting(arg):
                    value = lower(arg, parameter, {}, model.source)
                    if not isinstance(value, Affine) or value.terms:
                        raise CompileError(f"{leaf.kind} settings must be instance constants")
                    return value.constant

                if leaf.kind == "cross":
                    settings = [0.0, 1e-12, 1e-9]
                    for index, arg in enumerate(leaf.arguments[1:]):
                        settings[index] = setting(arg)
                    direction, time_tol, expr_tol = settings
                    if direction not in (-1, 0, 1) or time_tol <= 0 or expr_tol <= 0:
                        raise CompileError("cross requires direction -1/0/1 and positive tolerances")
                    result = CrossTrigger(lower(leaf.arguments[0], symbol, node_ids, model.source, lambda expr: waveform(expr, symbol), preserve_structure=True),
                                           int(direction), time_tol, expr_tol)
                else:
                    start = setting(leaf.arguments[0])
                    period = 0.0 if leaf.arguments[1] is None else setting(leaf.arguments[1])
                    time_tol = setting(leaf.arguments[2])
                    enabled = setting(leaf.arguments[3]) != 0 if len(leaf.arguments) == 4 else True
                    if start < 0 or time_tol <= 0:
                        raise CompileError("timer requires nonnegative start and positive time_tol")
                    result = TimerTrigger(start, period, time_tol, enabled)
                return result

            triggers = tuple(trigger(leaf) for leaf in event.triggers)
            event_trigger = triggers[0] if len(triggers) == 1 else OrTrigger(triggers)
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
                        # Reset feedback checks need voltage dependencies even
                        # when a coefficient cancels or underflows to zero.
                        value = lower(statement.rhs, symbol, node_ids, model.source, preserve_structure=True)
                        if model.variables[statement.name] == "integer" and not integral(value):
                            raise CompileError("integer assignment requires integral state arithmetic")
                        result.append(Assignment(state_ids[statement.name], value))
                return tuple(result)

            origin = Origin(model.source, event.token.line, event.token.column, instance.name)
            events.append(Event(event_trigger, body(event.body), origin))

        local_env = {}
        allowed_condition_nodes = {0}
        for port, direction in model.directions.items():
            if direction in ("input", "inout"):
                allowed_condition_nodes.add(node_ids[port])

        def expression_nodes(expression):
            if isinstance(expression, Affine):
                return {term.node for term in expression.terms}
            if isinstance(expression, Binary):
                return expression_nodes(expression.left) | expression_nodes(expression.right)
            if hasattr(expression, "base"):
                return expression_nodes(expression.base)
            if isinstance(expression, Select):
                return (expression_nodes(expression.left) | expression_nodes(expression.right)
                        | expression_nodes(expression.then_value) | expression_nodes(expression.else_value))
            return set()

        def local_symbol(env):
            def resolve(name):
                if name in env:
                    return env[name]
                if name in local_variables:
                    raise CompileError(f"{model.source}: local real {name!r} is not assigned before use")
                return symbol(name)
            return resolve

        def lower_local(expr, env, *, preserve_structure=False):
            resolve = local_symbol(env)
            return lower(expr, resolve, node_ids, model.source,
                         lambda op: waveform(op, resolve), preserve_structure)

        relation = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}

        def execute_analog(statements, env, conditional=False):
            result = dict(env)
            emitted = []
            for statement in statements:
                if isinstance(statement, ContributionStatement):
                    emitted.append((statement, lower_local(statement.rhs, result, preserve_structure=preserve_analog_structure)))
                elif isinstance(statement, SyntaxConditional):
                    if contains_operator(statement.left) or contains_operator(statement.right):
                        raise CompileError(f"{model.source}:{statement.token.line}: ordinary analog if predicates do not support waveform operators")
                    origin = Origin(model.source, statement.token.line, statement.token.column, instance.name)
                    left = lower_local(statement.left, result, preserve_structure=True)
                    right = lower_local(statement.right, result, preserve_structure=True)
                    if not expression_nodes(left).issubset(allowed_condition_nodes) or not expression_nodes(right).issubset(allowed_condition_nodes):
                        raise CompileError(f"{model.source}:{statement.token.line}: ordinary analog if predicates must depend only on input/inout ports")
                    if _predicate_degree(left) is None or _predicate_degree(right) is None:
                        raise CompileError(f"{model.source}:{statement.token.line}: ordinary analog if predicates must be affine or input-selected piecewise-affine; nonlinear products and powers are unsupported")
                    then_env, then_emitted = execute_analog(statement.then_body, result, conditional=True)
                    else_env, else_emitted = execute_analog(statement.else_body, result, conditional=True)
                    if then_emitted or else_emitted:
                        raise CompileError(f"{model.source}:{statement.token.line}: ordinary analog if contributions are unsupported in this slice")
                    for name in sorted(set(then_env) | set(else_env) | set(result)):
                        if name not in local_variables:
                            continue
                        if name not in then_env or name not in else_env:
                            raise CompileError(f"{model.source}:{statement.token.line}: ordinary analog if leaves local real {name!r} unassigned")
                        if then_env[name] is else_env[name]:
                            result[name] = then_env[name]
                            continue
                        result[name] = Select(relation[statement.relation], left, right, then_env[name], else_env[name], origin)
                else:
                    if statement.name not in local_variables:
                        raise CompileError(f"{model.source}:{statement.token.line}: ordinary analog assignment target must be a local real")
                    if conditional and contains_operator(statement.rhs):
                        raise CompileError(f"{model.source}:{statement.token.line}: waveform call sites must be unconditional")
                    result[statement.name] = lower_local(statement.rhs, result, preserve_structure=preserve_analog_structure)
            return result, emitted

        local_env, analog_contributions = execute_analog(model.analog, local_env)

        bound_branches = {}
        for branch_statement, expression in analog_contributions:
            branch = branch_statement.branch
            lower(branch, parameter, node_ids, model.source)  # validates both target nodes
            local_p, local_n = (str(arg.value) for arg in branch.args)
            pair = tuple(sorted((local_p, local_n)))
            p, n = (node_ids[name] for name in pair)
            bound_pair = tuple(sorted((p, n)))
            if bound_pair in bound_branches and bound_branches[bound_pair] != pair:
                raise CompileError(f"{model.source}:{branch.token.line}: distinct local contribution branches alias after connection; not supported in this slice")
            bound_branches[bound_pair] = pair
            sign = 1.0 if (local_p, local_n) == pair else -1.0
            origin = Origin(model.source, branch.token.line, branch.token.column, instance.name)
            identity = BranchIdentity(instance.name, *pair)
            contributions.append(Contribution(identity, p, n, scale(expression, sign), origin))
    return Program(names, tuple(contributions), tuple(states), tuple(events), tuple(operators))
