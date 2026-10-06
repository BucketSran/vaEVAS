"""Compile one bound instance while sharing explicit program output tables.

Parameter/local/state environments belong to this instance. Global node indices,
operator/state IDs and output order belong to Compilation; no loop-captured state.
"""
from dataclasses import dataclass, field
import math
from fractions import Fraction
from typing import TYPE_CHECKING

from .ir import (Affine, Assignment, Conditional, Binary, BranchIdentity, Contribution, CrossTrigger, Event, TimerTrigger, HeldTimerTrigger, OrTrigger,
                 Origin, Program, Power, Select, State, StateRef, OperatorRef, Transition, AbsDelay, Slew, Idt, LaplaceNd, IdtMod, Sin, Ddt)
from .lowering import lower, scale
from .limits import check_ir
from .parameters import bind_parameters
from .elaboration import unroll_loops
from .array_elaboration import scalarize_arrays
from .syntax import (CompileError, Model, contains_operator,
                     Conditional as SyntaxConditional, ContributionStatement)

if TYPE_CHECKING:
    from .frontend import Instance


@dataclass
class Compilation:
    nodes: tuple[str, ...]
    preserve_structure: bool
    contributions: list[Contribution] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    operators: list[Transition | AbsDelay | Slew | Idt | LaplaceNd | IdtMod | Sin | Ddt] = field(default_factory=list)
    indices: dict[str, int] = field(init=False)

    def __post_init__(self):
        self.indices = {name: i for i, name in enumerate(self.nodes)}

    def program(self) -> Program:
        result = Program(self.nodes, tuple(self.contributions), tuple(self.states), tuple(self.events), tuple(self.operators))
        check_ir(result)
        return result


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


class InstanceCompiler:
    def __init__(self, instance: "Instance", model: Model, nets: dict[str, str], compilation: Compilation):
        self.instance = instance
        self.model = model
        self.compilation = compilation
        self.cache: dict[str, float] = {}
        self.node_ids = {name: compilation.indices[net] for name, net in nets.items()}
        self.initials = {}
        self.allowed_condition_nodes = {0} | {self.node_ids[port] for port, direction in model.directions.items()
                                             if direction in ("input", "inout")}

    def compile(self):
        self.cache = bind_parameters(self.model, self.instance.parameters, self.instance.name)
        self.model = scalarize_arrays(self.model, self.parameter)
        self.local_variables = set(self.model.variables) if not self.model.initial and not self.model.events else set()
        self.preserve_analog_structure = self.compilation.preserve_structure or bool(self.local_variables)
        self.state_names = tuple(name for name in self.model.variables if name not in self.local_variables)
        self.state_ids = {name: len(self.compilation.states) + index for index, name in enumerate(self.state_names)}
        self.initialize_states()
        for event in self.model.events:
            triggers = tuple(self.trigger(leaf) for leaf in event.triggers)
            event_trigger = triggers[0] if len(triggers) == 1 else OrTrigger(triggers)
            origin = Origin(event.token.source or self.model.source, event.token.line, event.token.column, self.instance.name, event.token.expansion)
            self.compilation.events.append(Event(event_trigger, self.body(event.body), origin))
        _, contributions = self.execute_analog(unroll_loops(self.model, self.parameter), {})
        self.emit_contributions(contributions)

    def initialize_states(self):
        if self.local_variables and any(self.model.variables[name] != "real" for name in self.local_variables):
            raise CompileError(f"{self.model.source}: ordinary analog local assignments only support real variables")
        for statement in self.model.initial:
            if statement.name not in self.state_ids or statement.name in self.initials:
                raise CompileError(f"{self.model.source}:{statement.token.line}: initial_step must initialize each declared state exactly once")
            try:
                value = lower(statement.rhs, self.parameter, {}, self.model.source)
            except CompileError as exc:
                raise CompileError(f'initial_step values must be instance constants: {exc}',
                                   code='unsupported_initial_event', token=statement.token) from exc
            if not isinstance(value, Affine) or value.terms:
                raise CompileError("initial_step values must be instance constants")
            if self.model.variables[statement.name] == "integer" and not (-2147483648 <= value.constant <= 2147483647 and value.constant.is_integer()):
                raise CompileError("integer initialization must be an exact signed 32-bit integer")
            self.initials[statement.name] = value.constant
        if set(self.initials) != set(self.state_ids):
            raise CompileError(f"{self.model.source}: every state requires one constant initial_step assignment")
        self.compilation.states.extend(State(self.instance.name, name, self.model.variables[name], self.initials[name]) for name in self.state_names)

    def parameter(self, name):
        if name not in self.model.parameters:
            raise CompileError(f"{self.model.source}: unknown parameter {name!r}")
        return self.cache[name]

    def symbol(self, name):
        if name in self.local_variables:
            raise CompileError(f"{self.model.source}: local real {name!r} is not assigned before use")
        return StateRef(self.state_ids[name]) if name in self.state_ids else self.parameter(name)

    def integral(self, expression):
        # Do not introduce an implicit real-to-integer rounding rule.
        if isinstance(expression, Affine):
            return not expression.terms and expression.constant.is_integer()
        if isinstance(expression, StateRef):
            return self.compilation.states[expression.state].kind == "integer"
        return isinstance(expression, Binary) and self.integral(expression.left) and self.integral(expression.right)

    def waveform(self, expr, resolve):
        if expr.op == "laplace_np" and len(expr.args) != 3:
            raise CompileError(f"{self.model.source}:{expr.token.line}:{expr.token.column}: laplace_np epsilon is unsupported; omit the tolerance argument")
        input_nodes = {} if expr.op == "transition" else self.node_ids
        def nested_delay(nested):
            if nested.op != "absdelay":
                raise CompileError("absdelay nesting is limited to fixed absdelay stages")
            return self.waveform(nested, resolve)
        value = lower(expr.args[0], resolve, input_nodes, self.model.source,
                      (lambda nested: self.waveform(nested, resolve)) if expr.op in ("sin", "idt", "laplace_nd", "laplace_np", "ddt") else nested_delay if expr.op == "absdelay" else None,
                      preserve_structure=True)
        if expr.op in ("laplace_nd", "laplace_np"):
            def coefficients(array):
                if array.op != "array":
                    raise CompileError(f"{self.model.source}:{array.token.line}:{array.token.column}: {expr.op} coefficients must use standard constant array literals")
                result = []
                for item in array.args:
                    value = lower(item, self.parameter, {}, self.model.source)
                    if not isinstance(value, Affine) or value.terms:
                        raise CompileError(f"{self.model.source}:{item.token.line}:{item.token.column}: {expr.op} coefficients must be instance constants")
                    result.append(value.constant)
                return tuple(result)
            numerator = coefficients(expr.args[1])
            denominator = coefficients(expr.args[2])
            if expr.op == "laplace_np":
                if len(numerator) != 1 or len(denominator) != 2:
                    raise CompileError("laplace_np supports one constant numerator and one real pole pair")
                pole, imaginary = denominator
                if not math.isfinite(numerator[0]) or not math.isfinite(pole) or pole >= 0 or imaginary != 0:
                    raise CompileError("laplace_np requires a finite numerator and one finite negative real pole with zero imaginary part")
                coefficient = -1.0 / pole
                # A rounded product can equal -1 even for an inexact reciprocal
                # (e.g. pole=-3). Compare the original binary64 rationals.
                if (not math.isfinite(coefficient) or coefficient <= 0 or
                        Fraction(coefficient) != -1 / Fraction(pole)):
                    raise CompileError("laplace_np reciprocal coefficient must be exactly representable as finite positive binary64")
                denominator = (1.0, coefficient)
            elif not numerator or not 2 <= len(denominator) <= 9 or len(numerator) > len(denominator):
                raise CompileError("laplace_nd requires a proper rational filter of order 1 through 8")
            settings = ()
        else:
            setting_args = expr.args[1:2] if expr.op == "idt" else expr.args[1:]
            settings = [lower(arg, self.parameter, {}, self.model.source) for arg in setting_args]
            if any(not isinstance(v, Affine) or v.terms for v in settings):
                raise CompileError(f"{expr.op} settings must be instance constants")
        origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column, self.instance.name, expr.expansion)
        index = len(self.compilation.operators)
        if expr.op == "idt":
            reset = lower(expr.args[2], resolve, {}, self.model.source, preserve_structure=True) if len(expr.args) == 3 else None
            self.compilation.operators.append(Idt(value, settings[0].constant, origin, reset))
        elif expr.op == "ddt":
            self.compilation.operators.append(Ddt(value, origin))
        elif expr.op in ("laplace_nd", "laplace_np"):
            self.compilation.operators.append(LaplaceNd(value, numerator, denominator, origin))
        elif expr.op == "idtmod":
            ic, modulus, offset = (v.constant for v in settings)
            if modulus <= 0:
                raise CompileError("idtmod requires positive explicit modulus")
            self.compilation.operators.append(IdtMod(value, ic, modulus, offset, origin))
        elif expr.op == "sin":
            self.compilation.operators.append(Sin(value, origin))
        elif expr.op == "absdelay":
            delay = settings[0].constant
            if delay < 0:
                raise CompileError("absdelay requires nonnegative delay; zero is an EVAS extension")
            self.compilation.operators.append(AbsDelay(value, delay, origin))
        elif expr.op == "transition":
            delay, rise, fall = (v.constant for v in settings)
            if delay < 0 or rise <= 0 or fall <= 0:
                raise CompileError("transition requires nonnegative delay and positive explicit edge times")
            self.compilation.operators.append(Transition(value, delay, rise, fall, origin))
        elif expr.op == "slew":
            rise, fall = (v.constant for v in settings)
            if rise <= 0 or fall >= 0:
                raise CompileError("slew requires explicit rise > 0 and fall < 0")
            self.compilation.operators.append(Slew(value, rise, fall, origin))
        else:
            raise CompileError(f"unsupported waveform operator {expr.op!r}")
        return OperatorRef(index)

    def trigger(self, leaf):
        if leaf.kind == 'timer':
            pending = [arg for arg in leaf.arguments if arg is not None]
            while pending:
                expr = pending.pop()
                if expr.op == 'voltage' or contains_operator(expr):
                    raise CompileError(
                        f'{self.model.source}:{expr.token.line}:{expr.token.column}: timer parameters cannot depend on continuous voltage or operator history',
                        code='unsupported_timer_dependency', token=expr.token, instance=self.instance.name)
                pending.extend(expr.args)
        def setting(arg):
            value = lower(arg, self.parameter, {}, self.model.source)
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
            result = CrossTrigger(lower(leaf.arguments[0], self.symbol, self.node_ids, self.model.source, lambda expr: self.waveform(expr, self.symbol), preserve_structure=True),
                                   int(direction), time_tol, expr_tol)
        else:
            # Lower optional source arguments into the existing explicit IR.
            # 1 ps is EVAS policy, not a prescribed LRM or Spectre default.
            arguments = leaf.arguments + (None,) * (4-len(leaf.arguments))
            start_arg, period_arg, tolerance_arg, enable_arg = arguments
            time_tol = 1e-12 if tolerance_arg is None else setting(tolerance_arg)
            if time_tol <= 0:
                raise CompileError("timer requires nonnegative start and positive time_tol")
            values = [lower(arg, self.symbol, {}, self.model.source, preserve_structure=True) if arg is not None else Affine(0., ())
                      for arg in (start_arg, period_arg, enable_arg)]
            if enable_arg is None:
                values[2] = Affine(1., ())
            if all(isinstance(value, Affine) and not value.terms for value in values):
                start, period, enabled = (value.constant for value in values)
                if start < 0:
                    raise CompileError("timer requires nonnegative start and positive time_tol")
                result = TimerTrigger(start, period, time_tol, enabled != 0)
            else:
                result = HeldTimerTrigger(values[0], values[1], time_tol, values[2])
        return result

    def body(self, statements):
        result = []
        for statement in statements:
            origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
            if isinstance(statement, SyntaxConditional):
                # Predicate state references are rejected even if their
                # numeric coefficients would cancel. The kernel also
                # proves independence through the voltage network.
                left = lower(statement.left, self.parameter, self.node_ids, self.model.source, preserve_structure=True)
                right = lower(statement.right, self.parameter, self.node_ids, self.model.source, preserve_structure=True)
                result.append(Conditional({"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation],
                                          left, right, self.body(statement.then_body), self.body(statement.else_body), origin))
            else:
                if statement.name not in self.state_ids:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: assignment target must be an instance state")
                # Reset feedback checks need voltage dependencies even
                # when a coefficient cancels or underflows to zero.
                value = lower(statement.rhs, self.symbol, self.node_ids, self.model.source, preserve_structure=True)
                if self.model.variables[statement.name] == "integer" and not self.integral(value):
                    raise CompileError("integer assignment requires integral state arithmetic")
                result.append(Assignment(self.state_ids[statement.name], value))
        return tuple(result)

    def expression_nodes(self, expression):
        if isinstance(expression, Affine):
            return {term.node for term in expression.terms}
        if isinstance(expression, Binary):
            return self.expression_nodes(expression.left) | self.expression_nodes(expression.right)
        if hasattr(expression, "base"):
            return self.expression_nodes(expression.base)
        if isinstance(expression, Select):
            return (self.expression_nodes(expression.left) | self.expression_nodes(expression.right)
                    | self.expression_nodes(expression.then_value) | self.expression_nodes(expression.else_value))
        return set()

    def local_symbol(self, env):
        def resolve(name):
            if name in env:
                return env[name]
            if name in self.local_variables:
                raise CompileError(f"{self.model.source}: local real {name!r} is not assigned before use")
            return self.symbol(name)
        return resolve

    def lower_local(self, expr, env, *, preserve_structure=False):
        resolve = self.local_symbol(env)
        return lower(expr, resolve, self.node_ids, self.model.source,
                     lambda op: self.waveform(op, resolve), preserve_structure)

    def execute_analog(self, statements, env, conditional=False):
        result = dict(env)
        emitted = []
        for statement in statements:
            if isinstance(statement, ContributionStatement):
                emitted.append((statement, self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure)))
            elif isinstance(statement, SyntaxConditional):
                if contains_operator(statement.left) or contains_operator(statement.right):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates do not support waveform operators")
                origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
                left = self.lower_local(statement.left, result, preserve_structure=True)
                right = self.lower_local(statement.right, result, preserve_structure=True)
                check_ir(left, origin)
                check_ir(right, origin)
                if not self.expression_nodes(left).issubset(self.allowed_condition_nodes) or not self.expression_nodes(right).issubset(self.allowed_condition_nodes):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates must depend only on input/inout ports")
                if _predicate_degree(left) is None or _predicate_degree(right) is None:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates must be affine or input-selected piecewise-affine; nonlinear products and powers are unsupported")
                then_env, then_emitted = self.execute_analog(statement.then_body, result, conditional=True)
                else_env, else_emitted = self.execute_analog(statement.else_body, result, conditional=True)
                if then_emitted or else_emitted:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if contributions are unsupported in this slice")
                for name in sorted(set(then_env) | set(else_env) | set(result)):
                    if name not in self.local_variables:
                        continue
                    if name not in then_env or name not in else_env:
                        raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if leaves local real {name!r} unassigned")
                    if then_env[name] is else_env[name]:
                        result[name] = then_env[name]
                        continue
                    result[name] = Select({"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation], left, right, then_env[name], else_env[name], origin)
                    check_ir(result[name], origin)
            else:
                if statement.name not in self.local_variables:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog assignment target must be a local real")
                if conditional and contains_operator(statement.rhs):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: waveform call sites must be unconditional")
                value = self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure)
                check_ir(value, Origin(self.model.source, statement.token.line, statement.token.column, self.instance.name))
                result[statement.name] = value
        return result, emitted

    def emit_contributions(self, analog_contributions):
        bound_branches = {}
        for branch_statement, expression in analog_contributions:
            branch = branch_statement.branch
            lower(branch, self.parameter, self.node_ids, self.model.source)  # validates both target nodes
            local_p, local_n = (str(arg.value) for arg in branch.args)
            pair = tuple(sorted((local_p, local_n)))
            p, n = (self.node_ids[name] for name in pair)
            bound_pair = tuple(sorted((p, n)))
            if bound_pair in bound_branches and bound_branches[bound_pair] != pair:
                raise CompileError(f"{self.model.source}:{branch.token.line}: distinct local contribution branches alias after connection; not supported in this slice")
            bound_branches[bound_pair] = pair
            sign = 1.0 if (local_p, local_n) == pair else -1.0
            origin = Origin(branch.token.source or self.model.source, branch.token.line, branch.token.column, self.instance.name, branch.expansion)
            identity = BranchIdentity(self.instance.name, *pair)
            self.compilation.contributions.append(Contribution(identity, p, n, scale(expression, sign), origin))
