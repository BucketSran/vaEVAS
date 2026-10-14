"""Compile one bound instance while sharing explicit program output tables.

Parameter/local/state environments belong to this instance. Global node indices,
operator/state IDs and output order belong to Compilation; no loop-captured state.
"""
from dataclasses import dataclass, field, replace
import math
from fractions import Fraction
from typing import TYPE_CHECKING

from .ir import (Affine, Assignment, Conditional, Binary, BranchIdentity, Contribution, CrossTrigger, Event, TimerTrigger, HeldTimerTrigger, OrTrigger,
                 Origin, Program, Power, Select, State, StateRef, OperatorRef, Transition, AbsDelay, Slew, Idt, LaplaceNd, IdtMod, Sin, MathFunction, Ddt, StepBound, Display, FinalStepTrigger, InitialStepTrigger)
from .lowering import lower, scale
from .limits import check_ir
from .parameters import bind_parameters
from .elaboration import unroll_loops
from .array_elaboration import scalarize_arrays
from .syntax import (CompileError, Model, contains_operator, contains_decision,
                     Assignment as SyntaxAssignment, Conditional as SyntaxConditional, Display as SyntaxDisplay,
                     Loop, ContributionStatement, BoundStep, OPERATOR_NAMES, DECISION_NAMES)

if TYPE_CHECKING:
    from .frontend import Instance


@dataclass
class Compilation:
    nodes: tuple[str, ...]
    preserve_structure: bool
    contributions: list[Contribution] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    operators: list[Transition | AbsDelay | Slew | Idt | LaplaceNd | IdtMod | Sin | MathFunction | Ddt] = field(default_factory=list)
    step_bounds: list[StepBound] = field(default_factory=list)
    indices: dict[str, int] = field(init=False)

    def __post_init__(self):
        self.indices = {name: i for i, name in enumerate(self.nodes)}

    def program(self) -> Program:
        result = Program(self.nodes, tuple(self.contributions), tuple(self.states), tuple(self.events), tuple(self.operators),
                         step_bounds=tuple(self.step_bounds))
        check_ir(result)
        return result


def _predicate_degree(expression):
    """Structural scope: node-free constant (0), affine/select (1), or unsupported.

    No cancellation removes a dependency. Input-selected constants count as
    input-dependent, so only a node-free scalar can multiply a predicate.
    """
    if isinstance(expression, StateRef):
        return 1
    if isinstance(expression, Affine):
        return int(bool(expression.terms))
    if isinstance(expression, Binary):
        if expression.op == "divide":
            return None
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
        if "$abstime" in compilation.indices:
            self.node_ids["$abstime"] = compilation.indices["$abstime"]
        self.initials = {}
        self.expression_decision_origins = set()
        self.allowed_condition_nodes = {0} | ({self.node_ids["$abstime"]} if "$abstime" in self.node_ids else set()) | {self.node_ids[port] for port, direction in model.directions.items()
                                             if direction in ("input", "inout")}

    def compile(self):
        self.cache = bind_parameters(self.model, self.instance.parameters, self.instance.name)
        self.model = scalarize_arrays(self.model, self.parameter)
        # A declaration does not become held state just because another variable
        # has an event writer. Walk writes (including conditional/loop bodies),
        # so event targets retain the VA declaration default of zero.
        def writes(statements):
            for statement in statements:
                if isinstance(statement, SyntaxAssignment):
                    yield statement.name
                elif isinstance(statement, SyntaxConditional):
                    yield from writes(statement.then_body)
                    yield from writes(statement.else_body)
                elif isinstance(statement, Loop):
                    yield from writes(statement.body)

        persistent = set(writes(self.model.initial))
        for event in self.model.events:
            persistent.update(writes(event.body))
        self.local_variables = set(writes(self.model.analog)) - persistent
        self.preserve_analog_structure = self.compilation.preserve_structure or bool(self.local_variables)
        def expression_reads(expr):
            if expr is None:
                return set()
            names = {expr.value} if expr.op == "parameter" else set()
            for arg in expr.args:
                names.update(expression_reads(arg))
            return names
        def reads(statements):
            names = set()
            for statement in statements:
                for field in ("rhs", "left", "right", "start", "limit", "update"):
                    if hasattr(statement, field):
                        names.update(expression_reads(getattr(statement, field)))
                if isinstance(statement, SyntaxDisplay):
                    for arg in statement.args:
                        names.update(expression_reads(arg))
                for field in ("then_body", "else_body", "body"):
                    if hasattr(statement, field):
                        names.update(reads(getattr(statement, field)))
            return names
        referenced = reads(self.model.initial) | reads(self.model.analog)
        for event in self.model.events:
            referenced.update(reads(event.body))
            for trigger in event.triggers:
                for argument in trigger.arguments:
                    referenced.update(expression_reads(argument))
        # Read-only declarations retain VA's default zero, but an unused
        # declaration must not turn a stateless solve into a state program.
        self.state_names = tuple(name for name in self.model.variables
                                 if name not in self.local_variables and (name in persistent or name in referenced))
        self.state_ids = {name: len(self.compilation.states) + index for index, name in enumerate(self.state_names)}
        self.initialize_states()
        self.infer_integer_state_ranges()
        for event in self.model.events:
            triggers = tuple(self.trigger(leaf) for leaf in event.triggers)
            event_trigger = triggers[0] if len(triggers) == 1 else OrTrigger(triggers)
            origin = Origin(event.token.source or self.model.source, event.token.line, event.token.column, self.instance.name, event.token.expansion)
            self.compilation.events.append(Event(event_trigger, self.body(event.body), origin))
        statements = unroll_loops(self.model, self.parameter)
        self.validate_branch_presence(statements)
        _, contributions = self.execute_analog(statements, {})
        self.emit_contributions(contributions)

    def validate_branch_presence(self, statements):
        # An absent potential contribution is a zero-flow/open branch in VA,
        # not a zero-voltage source. Only lower conditional contributions when
        # each local branch remains a potential source on every control path.
        def branches(body):
            possible, definite = set(), set()
            for statement in body:
                if isinstance(statement, ContributionStatement):
                    pair = tuple(sorted(str(a.value) for a in statement.branch.args))
                    possible.add(pair)
                    definite.add(pair)
                elif isinstance(statement, SyntaxConditional):
                    yp, yd = branches(statement.then_body)
                    np, nd = branches(statement.else_body)
                    possible |= yp | np
                    definite |= yd & nd
            return possible, definite
        possible, definite = branches(statements)
        if possible != definite:
            raise CompileError(f'{self.model.source}: conditional voltage branch may be inactive; switching to a zero-flow branch is unsupported')

    def initialize_states(self):
        # Initial procedural execution uses a symbolic environment. Each write
        # replaces the previous value, and branch merges preserve source order.
        env = {name: Affine(0., ()) for name in self.state_names}
        def resolve(values):
            return self.typed_resolve(lambda name: values[name] if name in values else self.parameter(name))
        def execute(statements, values):
            values = dict(values)
            for statement in statements:
                if isinstance(statement, SyntaxConditional):
                    left = lower(statement.left, resolve(values), self.node_ids, self.model.source,
                                 preserve_structure=True, decisions=self.initial_select, node_declarations=True)
                    right = lower(statement.right, resolve(values), self.node_ids, self.model.source,
                                  preserve_structure=True, decisions=self.initial_select, node_declarations=True)
                    self.validate_initial_operand(statement.left, left)
                    self.validate_initial_operand(statement.right, right)
                    yes, no = execute(statement.then_body, values), execute(statement.else_body, values)
                    for name in values:
                        if yes[name] is not no[name]:
                            values[name] = self.initial_select(statement.left,
                                {"<":"lt", "<=":"le", ">":"gt", ">=":"ge"}[statement.relation],
                                left, right, yes[name], no[name])
                else:
                    if not isinstance(statement, SyntaxAssignment) or statement.name not in self.state_ids:
                        raise CompileError("initial_step requires declared state assignments")
                    value = lower(statement.rhs, resolve(values), self.node_ids, self.model.source,
                                  preserve_structure=True, decisions=self.initial_select,
                                  validate_decision=self.validate_initial_operand, node_declarations=True)
                    self.validate_initial_operand(statement.rhs, value)
                    def constant_arms(item):
                        if isinstance(item, Affine):
                            return not item.terms
                        if isinstance(item, Select):
                            return constant_arms(item.then_value) and constant_arms(item.else_value)
                        if isinstance(item, Binary):
                            return item.op in ("add", "multiply") and constant_arms(item.left) and constant_arms(item.right)
                        return isinstance(item, Power) and constant_arms(item.base)
                    if not constant_arms(value):
                        raise CompileError("initial_step values require constant-valued arms selected by input predicates")
                    if self.model.variables[statement.name] == "integer":
                        self.validate_integer_value(value, statement.token, initial=True)
                    values[statement.name] = value
            return values
        try:
            env = execute(self.model.initial, env)
        except CompileError as exc:
            if exc.diagnostic['code'] == 'resource_budget':
                raise
            token = self.model.initial[0].token if self.model.initial else None
            raise CompileError(f'unsupported initial_step value: {exc}',
                               code='unsupported_initial_event', token=token,
                               instance=self.instance.name) from exc
        for name, value in env.items():
            if isinstance(value, Affine) and not value.terms:
                value = value.constant
                if self.model.variables[name] == "integer" and not -2147483648 <= value <= 2147483647:
                    raise CompileError("integer initialization must be an exact signed 32-bit integer")
            self.initials[name] = value
        self.compilation.states.extend(State(self.instance.name, name, self.model.variables[name], self.initials[name]) for name in self.state_names)

    def validate_initial_operand(self, expr, value):
        # Check all lowered function obligations, including dead branches.
        if _predicate_degree(value) is None:
            raise CompileError("initial comparison operands must be structurally affine")
        if not self.expression_nodes(value).issubset(self.allowed_condition_nodes):
            raise CompileError("initial comparison depends on a non-input voltage")

    def initial_select(self, expr, relation, left, right, then_value, else_value):
        self.validate_initial_operand(expr, left)
        self.validate_initial_operand(expr, right)
        origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        result = Select(relation, left, right, then_value, else_value, origin)
        check_ir(result, origin)
        return result

    def parameter(self, name):
        if name not in self.model.parameters:
            raise CompileError(f"{self.model.source}: unknown parameter {name!r}")
        return self.cache[name]

    def symbol(self, name):
        if name in self.local_variables:
            raise CompileError(f"{self.model.source}: event expressions cannot read ordinary analog local variable {name!r}; use direct input or persistent state expressions",
                               code='unsupported_local_event', instance=self.instance.name)
        return StateRef(self.state_ids[name]) if name in self.state_ids else self.parameter(name)

    def event_parameter(self, name):
        # Conditions and settings keep their constant-only/state-independent
        # restrictions, while local aliases get the same explicit boundary.
        if name in self.local_variables:
            return self.symbol(name)
        if name in self.state_ids:
            raise CompileError(f"{self.model.source}: event predicates and constant settings cannot depend on persistent state {name!r}",
                               code='unsupported_event_state_dependency', instance=self.instance.name)
        return self.parameter(name)

    def lower_event(self, expr, resolve, nodes, *args, **kwargs):
        assignment_root = kwargs.pop("integer_assignment_root", False)
        try:
            return lower(expr, self.typed_resolve(resolve, allow_integer_assignment_root=assignment_root), nodes, self.model.source, *args, **kwargs)
        except CompileError as error:
            if (error.diagnostic['code'] in ('unsupported_local_event', 'unsupported_event_state_dependency')
                    and 'location' not in error.diagnostic):
                raise CompileError(str(error), code=error.diagnostic['code'], token=expr.token,
                                   instance=self.instance.name) from error
            raise

    def integral(self, expression):
        # Do not introduce an implicit real-to-integer rounding rule.
        if isinstance(expression, Affine):
            return not expression.terms and expression.constant.is_integer()
        if isinstance(expression, StateRef):
            return self.compilation.states[expression.state].kind == "integer"
        if isinstance(expression, Select):
            return self.integral(expression.then_value) and self.integral(expression.else_value)
        if isinstance(expression, Power):
            return self.integral(expression.base) and expression.exponent >= 0
        return isinstance(expression, Binary) and expression.op in ("add", "multiply") and self.integral(expression.left) and self.integral(expression.right)

    def integral_bounds(self, expression):
        if isinstance(expression, Affine) and not expression.terms:
            return expression.constant, expression.constant
        if isinstance(expression, StateRef):
            return getattr(self, "integer_state_ranges", {}).get(expression.state, (-2147483648, 2147483647))
        if isinstance(expression, Select):
            a, b = self.integral_bounds(expression.then_value), self.integral_bounds(expression.else_value)
            return min(a[0], b[0]), max(a[1], b[1])
        if isinstance(expression, Binary) and expression.op in ("add", "multiply"):
            a, b = self.integral_bounds(expression.left), self.integral_bounds(expression.right)
            if expression.op == "add":
                return a[0]+b[0], a[1]+b[1]
            products = [x*y for x in a for y in b]
            return min(products), max(products)
        if isinstance(expression, Power):
            low, high = self.integral_bounds(expression.base)
            endpoints = [low**expression.exponent, high**expression.exponent]
            if low <= 0 <= high and expression.exponent:
                endpoints.append(0)
            return min(endpoints), max(endpoints)
        raise CompileError("integer expression lacks a finite integral bound")

    def validate_integer_value(self, expression, token, *, initial=False):
        if not self.integral(expression):
            raise CompileError("integer assignment requires provably integral arithmetic",
                               token=token, instance=self.instance.name)
        low, high = self.integral_bounds(expression)
        if low < -2147483648 or high > 2147483647:
            context = "initial" if initial else "ordinary local"
            raise CompileError(f"{context} integer intermediate may exceed signed 32-bit range",
                               token=token, instance=self.instance.name)

    def typed_resolve(self, resolve, *, allow_integer_assignment_root=False):
        def lookup(name):
            return resolve(name)
        lookup.integer_arithmetic = self.integer_arithmetic
        lookup.validate_integer_operation = self.validate_integer_operation
        lookup.allow_integer_assignment_root = allow_integer_assignment_root
        return lookup

    def validate_integer_operation(self, expr, value, *, root):
        # The recursive lowerer invokes this before a parent can fold away the
        # result. Assignment-only checks miss (n+1)-1 and (n+1)>0.
        if expr.op not in ("+", "-", "*", "/", "%", "unary-", "unary+") or not self.integer_type(expr):
            return
        if not self.integral(value):
            return
        low, high = self.integral_bounds(value)
        if -2147483648 <= low <= high <= 2147483647:
            return
        def unknown_state(item):
            if isinstance(item, StateRef):
                return getattr(self, "integer_state_ranges", {}).get(item.state, (-2147483648, 2147483647)) == (-2147483648, 2147483647)
            if isinstance(item, Binary):
                return unknown_state(item.left) or unknown_state(item.right)
            if isinstance(item, Select):
                return any(unknown_state(c) for c in (item.then_value, item.else_value))
            return isinstance(item, Power) and unknown_state(item.base)
        # A complete assignment retains the kernel's final signed32 check.
        # A hidden intermediate could be folded/normalized away, so it needs
        # an independent range proof even when the final result is in range.
        if unknown_state(value) and low <= 2147483647 and high >= -2147483648:
            if root:
                return
            raise CompileError("integer intermediate signed 32-bit range is unproven",
                               token=expr.token, instance=self.instance.name)
        raise CompileError("integer intermediate may exceed signed 32-bit range",
                           token=expr.token, instance=self.instance.name)

    def integer_type(self, expr):
        if expr.result_type == "real":
            return False
        if expr.result_type == "integer":
            return True
        if expr.op == "number":
            text = expr.token.text
            return text.isdecimal() or text in self.model.genvars
        if expr.op == "parameter":
            return (self.model.variables.get(expr.value) == "integer" or
                    self.model.parameter_types.get(expr.value) == "integer")
        if expr.op == "checked":
            return self.integer_type(expr.args[0])
        if expr.op in ("<", "<=", ">", ">=", "==", "!=", "&&", "||", "unary!"):
            return True
        if expr.op == "ternary":
            return self.integer_type(expr.args[1]) and self.integer_type(expr.args[2])
        if expr.op in ("+", "-", "*", "/", "%", "unary+", "unary-"):
            return all(self.integer_type(arg) for arg in expr.args)
        return False

    def infer_integer_state_ranges(self):
        # Only state-independent writers tighten a declaration's full domain.
        # A copied/cyclic/accumulating state remains conservatively signed32.
        ranges = {}
        def contains_state(expr):
            if isinstance(expr, StateRef):
                return True
            if isinstance(expr, Binary):
                return contains_state(expr.left) or contains_state(expr.right)
            if isinstance(expr, Select):
                return any(contains_state(part) for part in (expr.left, expr.right, expr.then_value, expr.else_value))
            return isinstance(expr, Power) and contains_state(expr.base)
        def writes(statements):
            for statement in statements:
                if isinstance(statement, SyntaxAssignment):
                    yield statement
                elif isinstance(statement, SyntaxConditional):
                    yield from writes(statement.then_body)
                    yield from writes(statement.else_body)
        writers = [statement for event in self.model.events for statement in writes(event.body)]
        for name in self.state_names:
            if self.model.variables[name] != "integer":
                continue
            state = self.state_ids[name]
            initial = self.initials[name]
            initial = Affine(initial, ()) if isinstance(initial, (int, float)) else initial
            bounds = [self.integral_bounds(initial)]
            for statement in writers:
                if statement.name != name:
                    continue
                try:
                    value = self.lower_event(statement.rhs, self.symbol, self.node_ids,
                        preserve_structure=True, decisions=self.expression_select, node_declarations=True)
                    if contains_state(value) or not self.integral(value):
                        raise CompileError("state-dependent integer bound")
                    bounds.append(self.integral_bounds(value))
                except CompileError:
                    bounds = [(-2147483648, 2147483647)]
                    break
            ranges[state] = min(a for a, _ in bounds), max(b for _, b in bounds)
        self.integer_state_ranges = ranges

    def integer_arithmetic(self, expr, numerator, denominator):
        if not all(self.integer_type(arg) for arg in expr.args):
            return None
        def fail(message):
            raise CompileError(message, token=expr.token, instance=self.instance.name,
                               code="unsupported_integer_arithmetic")
        if (not isinstance(denominator, Affine) or denominator.terms or
                not denominator.constant.is_integer() or denominator.constant == 0):
            fail("integer division/modulo requires a nonzero constant integer divisor")
        if not self.integral(numerator):
            fail("integer division/modulo numerator must be provably integral")
        divisor = int(denominator.constant)
        if not -2147483648 <= divisor <= 2147483647:
            fail("integer divisor must remain within signed 32-bit range")
        width = abs(divisor)
        low, high = self.integral_bounds(numerator)
        if low < -2147483648 or high > 2147483647:
            fail("integer division/modulo numerator may exceed signed 32-bit range")
        def quotient(value):
            return int(value)//width if value >= 0 else -((-int(value))//width)
        first, last = quotient(low), quotient(high)
        if divisor < 0 and -first > 2147483647:
            fail("integer quotient may exceed signed 32-bit range")
        if last-first+1 > 256:
            fail("bounded integer division/modulo exceeds quotient-bin budget (256)")
        origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        def tree(start, end):
            if start == end:
                return Affine(float(start), ())
            middle = (start+end+1)//2
            boundary = middle*width if middle > 0 else (middle-1)*width+1
            return Select("lt", numerator, Affine(float(boundary), ()),
                          tree(start, middle-1), tree(middle, end), origin)
        self.expression_decision_origins.add(origin)
        value = tree(first, last)
        if divisor < 0:
            value = scale(value, -1.)
        if expr.op == "%":
            value = Binary("add", numerator, scale(value, -float(divisor)))
        check_ir(value, origin)
        return value

    def waveform(self, expr, resolve):
        resolve = self.typed_resolve(resolve)
        if expr.op == "laplace_np" and len(expr.args) != 3:
            raise CompileError(f"{self.model.source}:{expr.token.line}:{expr.token.column}: laplace_np epsilon is unsupported; omit the tolerance argument")
        input_nodes = self.node_ids
        def nested_fixed(nested):
            if nested.op != expr.op:
                raise CompileError(f"{expr.op} nesting is limited to fixed {expr.op} stages")
            return self.waveform(nested, resolve)
        value = lower(expr.args[0], resolve, input_nodes, self.model.source,
                  (lambda nested: self.waveform(nested, resolve)) if expr.op in ("sin", "cos", "exp", "ln", "sqrt", "idt", "laplace_nd", "laplace_np", "ddt") else nested_fixed if expr.op in ("absdelay", "slew") else None,
                      preserve_structure=True, decisions=self.expression_select,
                      validate_decision=self.validate_decision_expression, node_declarations=True)
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
            def setting(arg):
                def parameter(name):
                    try:
                        return self.parameter(name)
                    except CompileError as error:
                        if expr.op == "transition" and name in self.state_ids:
                            raise CompileError(str(error), code='unsupported_transition_timing_dependency',
                                               token=arg.token, instance=self.instance.name) from error
                        raise
                return lower(arg, parameter, {}, self.model.source)
            settings = [setting(arg) for arg in setting_args]
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
        elif expr.op in ("cos", "exp", "ln", "sqrt"):
            self.compilation.operators.append(MathFunction(expr.op, value, origin))
        elif expr.op == "absdelay":
            delay = settings[0].constant
            if delay < 0:
                raise CompileError("absdelay requires nonnegative delay; zero is an EVAS extension")
            self.compilation.operators.append(AbsDelay(value, delay, origin))
        elif expr.op == "transition":
            def continuous_value(item):
                if isinstance(item, Affine):
                    return bool(item.terms)
                if isinstance(item, Select):
                    # A predicate may select held values using a source node;
                    # the selected values themselves must remain held.
                    return continuous_value(item.then_value) or continuous_value(item.else_value)
                if isinstance(item, Binary):
                    return continuous_value(item.left) or continuous_value(item.right)
                return isinstance(item, Power) and continuous_value(item.base)
            if continuous_value(value):
                raise CompileError("transition target values must be held states or constants; continuous voltage targets are unsupported",
                                   token=expr.token, instance=self.instance.name)
            delay, rise = (v.constant for v in settings[:2])
            # LRM 2.4 §4.5.8: a positive explicit rise supplies omitted fall.
            fall = settings[2].constant if len(settings) == 3 else rise
            if delay < 0 or rise < 0 or fall < 0:
                raise CompileError("transition requires nonnegative delay and positive explicit edge times")
            if rise == 0 or fall == 0:
                raise CompileError("transition requires nonnegative delay and positive explicit edge times",
                                   code='unsupported_transition_zero_edges', token=expr.token,
                                   instance=self.instance.name)
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
        if leaf.kind == "initial_step":
            if self.model.children:
                raise CompileError("initial display events require a passive monitor without child instances", token=leaf.token)
            return InitialStepTrigger()
        if leaf.kind == "final_step":
            return FinalStepTrigger()
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
            value = self.lower_event(arg, self.event_parameter, {})
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
            result = CrossTrigger(self.lower_event(leaf.arguments[0], self.symbol, self.node_ids, lambda expr: self.waveform(expr, self.symbol), preserve_structure=True, node_declarations=True),
                                   int(direction), time_tol, expr_tol)
        else:
            # Lower optional source arguments into the existing explicit IR.
            # 1 ps is EVAS policy, not a prescribed LRM or Spectre default.
            arguments = leaf.arguments + (None,) * (4-len(leaf.arguments))
            start_arg, period_arg, tolerance_arg, enable_arg = arguments
            time_tol = 1e-12 if tolerance_arg is None else setting(tolerance_arg)
            if time_tol < 0:
                raise CompileError("timer requires nonnegative start and time_tol")
            values = [self.lower_event(arg, self.symbol, {}, preserve_structure=True) if arg is not None else Affine(0., ())
                      for arg in (start_arg, period_arg, enable_arg)]
            if enable_arg is None:
                values[2] = Affine(1., ())
            if all(isinstance(value, Affine) and not value.terms for value in values):
                start, period, enabled = (value.constant for value in values)
                if start < 0:
                    raise CompileError("timer requires nonnegative start and time_tol")
                result = TimerTrigger(start, period, time_tol, enabled != 0)
            else:
                if time_tol == 0:
                    raise CompileError("zero time_tol requires fixed timer parameters")
                result = HeldTimerTrigger(values[0], values[1], time_tol, values[2])
        return result

    def body(self, statements):
        result = []
        for statement in statements:
            origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
            if isinstance(statement, SyntaxDisplay):
                arguments = tuple(self.lower_event(arg, self.symbol, self.node_ids,
                    preserve_structure=True, decisions=self.expression_select,
                    validate_decision=self.validate_decision_expression, node_declarations=True)
                    for arg in statement.args)
                result.append(Display(statement.format, arguments, origin))
            elif isinstance(statement, SyntaxConditional):
                # The kernel evaluates predicates against the preceding
                # assignments, preserving procedural statement order.
                left = self.lower_event(statement.left, self.symbol, self.node_ids, preserve_structure=True, decisions=self.expression_select, node_declarations=True)
                right = self.lower_event(statement.right, self.symbol, self.node_ids, preserve_structure=True, decisions=self.expression_select, node_declarations=True)
                result.extend(self.event_conditional({"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation],
                                          left, right, self.body(statement.then_body), self.body(statement.else_body), origin))
            else:
                if statement.name not in self.state_ids:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: assignment target must be an instance state")
                # Reset feedback checks need voltage dependencies even
                # when a coefficient cancels or underflows to zero.
                value = self.lower_event(statement.rhs, self.symbol, self.node_ids, preserve_structure=True,
                                         decisions=self.expression_select, validate_decision=self.validate_decision_expression, node_declarations=True,
                                         integer_assignment_root=self.model.variables[statement.name] == "integer")
                if self.model.variables[statement.name] == "integer" and not self.integral(value):
                    raise CompileError("integer assignment requires integral state arithmetic")
                result.extend(self.event_assignment(self.state_ids[statement.name], value, origin))
        return tuple(result)

    @staticmethod
    def split_selection(expression):
        if isinstance(expression, Select):
            for field in ("left", "right"):
                child = InstanceCompiler.split_selection(getattr(expression, field))
                if child is not None:
                    decision, yes, no = child
                    return decision, replace(expression, **{field: yes}), replace(expression, **{field: no})
            return expression, expression.then_value, expression.else_value
        fields = ("left", "right") if isinstance(expression, Binary) else ("base",) if isinstance(expression, Power) else ()
        for field in fields:
            child = InstanceCompiler.split_selection(getattr(expression, field))
            if child is not None:
                decision, yes, no = child
                return decision, replace(expression, **{field: yes}), replace(expression, **{field: no})
        return None

    def event_conditional(self, relation, left, right, yes, no, origin):
        for field, expression in (("left", left), ("right", right)):
            choice = self.split_selection(expression)
            if choice is not None:
                decision, a, b = choice
                def continuation(value):
                    return self.event_conditional(relation, value if field == "left" else left,
                        value if field == "right" else right, yes, no, origin)
                return (Conditional(decision.relation, decision.left, decision.right,
                    continuation(a), continuation(b), decision.origin),)
        return (Conditional(relation, left, right, yes, no, origin),)

    def event_assignment(self, state, value, origin):
        # Select RHS decisions before installing the assignment. Distribute
        # enclosing arithmetic so the ordered event solver keeps affine leaves.
        count = 0
        def expand(expression):
            nonlocal count
            count += 1
            if count > 4096:
                raise CompileError("expanded event decision budget (4096) exceeded", code="resource_budget")
            choice = self.split_selection(expression)
            if choice is None:
                return (Assignment(state, expression),)
            decision, yes, no = choice
            return (Conditional(decision.relation, decision.left, decision.right,
                                expand(yes), expand(no), decision.origin),)
        return expand(value)

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
                raise CompileError(f"{self.model.source}: local variable {name!r} is not assigned before use")
            return self.symbol(name)
        return self.typed_resolve(resolve)

    def selected_value_supported(self, value):
        # Rational value arms use the kernel's certified polynomial/rational
        # evaluation. Their guards retain the narrower affine predicate scope.
        def children(item):
            if isinstance(item, Binary):
                return (item.left, item.right)
            if isinstance(item, Power):
                return (item.base,)
            if isinstance(item, Select):
                return (item.then_value, item.else_value)
            return ()
        def has_divide(item):
            return isinstance(item, Binary) and item.op == "divide" or any(has_divide(c) for c in children(item))
        def has_history(item):
            if isinstance(item, OperatorRef):
                return not isinstance(self.compilation.operators[item.operator], (Sin, MathFunction))
            return any(has_history(c) for c in children(item))
        def rational_tree(item):
            if isinstance(item, (Affine, StateRef)):
                return True
            if isinstance(item, Select):
                return (_predicate_degree(item.left) is not None and _predicate_degree(item.right) is not None
                        and rational_tree(item.then_value) and rational_tree(item.else_value))
            return isinstance(item, (Binary, Power)) and all(rational_tree(c) for c in children(item))
        def value_degree(item):
            if isinstance(item, OperatorRef):
                return 0
            if isinstance(item, Binary) and item.op in ("add", "multiply"):
                a, b = value_degree(item.left), value_degree(item.right)
                if a is None or b is None:
                    return None
                degree = max(a,b) if item.op == "add" else a+b
                return degree if degree <= 1 else None
            if isinstance(item, Select):
                if has_history(item.then_value) or has_history(item.else_value):
                    return None
                if _predicate_degree(item.left) is None or _predicate_degree(item.right) is None:
                    return None
                a, b = value_degree(item.then_value), value_degree(item.else_value)
                return max(a,b) if a is not None and b is not None else None
            return _predicate_degree(item)
        return value_degree(value) is not None or has_divide(value) and rational_tree(value)

    def validate_decision_expression(self, expr, value):
        origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        check_ir(value, origin)
        if not self.selected_value_supported(value):
            raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: selected value must remain piecewise-affine or a supported rational expression")

    def expression_select(self, expr, relation, left, right, then_value, else_value):
        origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        result = Select(relation, left, right, then_value, else_value, origin)
        check_ir(result, origin)
        if (_predicate_degree(left) is None or _predicate_degree(right) is None or
                not self.selected_value_supported(result)):
            raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: decision predicates and every arm must be affine or input-selected piecewise-affine")
        if not (self.expression_nodes(left) | self.expression_nodes(right)).issubset(self.allowed_condition_nodes):
            raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: decision predicates must depend only on input/inout ports")
        self.expression_decision_origins.add(origin)
        return result

    @staticmethod
    def contains_history_call(expr):
        pure_math = {"sin", "cos", "exp", "ln", "sqrt"}
        return (expr.op in OPERATOR_NAMES-pure_math or
                any(InstanceCompiler.contains_history_call(arg) for arg in expr.args))

    def lower_local(self, expr, env, *, preserve_structure=False, conditional=False):
        resolve = self.local_symbol(env)
        def outer_decision(item):
            if item.op in OPERATOR_NAMES:
                return False
            return item.op in DECISION_NAMES or any(outer_decision(arg) for arg in item.args)
        decision = outer_decision(expr)
        if decision and contains_operator(expr):
            raise CompileError(f"{self.model.source}:{expr.token.line}: decision expressions do not support waveform operators in any operand or arm")
        factory = self.expression_select
        def waveform(op):
            if conditional and self.contains_history_call(op):
                raise CompileError(f"{self.model.source}:{op.token.line}: history waveform call sites must be unconditional")
            return self.waveform(op, resolve)
        value = lower(expr, resolve, self.node_ids, self.model.source,
                      waveform, preserve_structure or decision, factory, self.validate_decision_expression, decision, node_declarations=True)
        # Validate the enclosing arithmetic too: an input-selected scalar must
        # not become a coefficient multiplying another input dependency.
        def has_expression_decision(item):
            pending, seen = [item], set()
            while pending:
                part = pending.pop()
                if id(part) in seen:
                    continue
                seen.add(id(part))
                if isinstance(part, Select):
                    if part.origin in self.expression_decision_origins:
                        return True
                    pending.extend((part.left, part.right, part.then_value, part.else_value))
                elif isinstance(part, Binary):
                    pending.extend((part.left, part.right))
                elif isinstance(part, Power):
                    pending.append(part.base)
            return False
        # Existing statement-if rejection remains at its original owning stage.
        # Apply the new source-arm check only to new expression decisions,
        # including ones read back through local aliases.
        if has_expression_decision(value):
            origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column, self.instance.name, expr.expansion)
            check_ir(value, origin)
            if not self.selected_value_supported(value):
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: selected value must remain piecewise-affine or a supported rational expression")
        return value

    def condition_domains(self, relation, left, right, domains):
        yes, no = dict(domains), dict(domains)
        if isinstance(left, Affine) and not left.terms and self.integral(right):
            left, right = right, left
            relation = {"lt":"gt", "le":"ge", "gt":"lt", "ge":"le"}[relation]
        if not (self.integral(left) and isinstance(right, Affine) and not right.terms
                and math.isfinite(right.constant)):
            return yes, no
        key = left.state if isinstance(left, StateRef) else ("local", id(left))
        low, high = domains.get(key, self.integral_bounds(left))
        threshold = right.constant
        if relation in ("lt", "ge"):
            boundary = math.ceil(threshold)
        else:
            boundary = math.floor(threshold)+1
        below, above = (low, min(high, boundary-1)), (max(low, boundary), high)
        yes[key], no[key] = (below, above) if relation in ("lt", "le") else (above, below)
        return yes, no

    def execute_analog(self, statements, env, conditional=False, active=Affine(1., ()), domains=None):
        result = dict(env)
        domains = dict(self.integer_state_ranges if domains is None else domains)
        emitted = []
        for statement in statements:
            if isinstance(statement, BoundStep):
                if contains_operator(statement.rhs):
                    raise CompileError(f'{self.model.source}:{statement.token.line}: $bound_step requires an expression without new waveform call sites')
                value = self.lower_local(statement.rhs, result, preserve_structure=True)
                if isinstance(value, Affine) and not value.terms and value.constant < 0:
                    raise CompileError('$bound_step requires a nonnegative value')
                origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column,
                                self.instance.name, statement.token.expansion)
                self.compilation.step_bounds.append(StepBound(value, active, origin))
            elif isinstance(statement, ContributionStatement):
                emitted.append((statement, self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure, conditional=conditional)))
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
                relation = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation]
                zero, one = Affine(0., ()), Affine(1., ())
                yes = Select('gt', active, zero, Select(relation, left, right, one, zero, origin), zero, origin)
                no = Select('gt', active, zero, Select(relation, left, right, zero, one, origin), zero, origin)
                yes_domains, no_domains = self.condition_domains(relation, left, right, domains)
                then_env, then_emitted = self.execute_analog(statement.then_body, result, conditional=True, active=yes, domains=yes_domains)
                else_env, else_emitted = self.execute_analog(statement.else_body, result, conditional=True, active=no, domains=no_domains)
                for selected, other, contributions in ((True, False, then_emitted), (False, True, else_emitted)):
                    for branch, value in contributions:
                        value = Select(relation, left, right,
                                       value if selected else Affine(0., ()),
                                       value if other else Affine(0., ()), origin)
                        check_ir(value, origin)
                        emitted.append((branch, value))
                for name in sorted(set(then_env) | set(else_env) | set(result)):
                    if name not in self.local_variables:
                        continue
                    yes_reachable = all(a <= b for a, b in yes_domains.values())
                    no_reachable = all(a <= b for a, b in no_domains.values())
                    if not yes_reachable or not no_reachable:
                        if yes_reachable and name in then_env:
                            result[name] = then_env[name]
                        elif no_reachable and name in else_env:
                            result[name] = else_env[name]
                        continue
                    if name not in then_env or name not in else_env:
                        raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if leaves local variable {name!r} unassigned")
                    if then_env[name] is else_env[name]:
                        result[name] = then_env[name]
                        continue
                    result[name] = Select({"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation], left, right, then_env[name], else_env[name], origin)
                    check_ir(result[name], origin)
            else:
                if statement.name not in self.local_variables:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog assignment target must be a local variable")
                if conditional and self.contains_history_call(statement.rhs):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: history waveform call sites must be unconditional")
                value = self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure, conditional=conditional)
                check_ir(value, Origin(self.model.source, statement.token.line, statement.token.column, self.instance.name))
                if self.model.variables[statement.name] == "integer":
                    self.validate_integer_value(value, statement.token)
                result[statement.name] = value
        return result, emitted

    def emit_contributions(self, analog_contributions):
        bound_branches = {}
        for branch_statement, expression in analog_contributions:
            branch = branch_statement.branch
            lower(branch, self.parameter, self.node_ids, self.model.source, node_declarations=True)  # validates both target nodes
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
