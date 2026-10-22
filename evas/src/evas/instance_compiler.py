"""Compile one bound instance while sharing explicit program output tables.

Parameter/local/state environments belong to this instance. Global node indices,
operator/state IDs and output order belong to Compilation; no loop-captured state.
"""
from dataclasses import dataclass, field, replace
import math
from fractions import Fraction
from typing import TYPE_CHECKING

from .ir import (Affine, Assignment, Conditional, Binary, BranchIdentity, Contribution, CrossTrigger, Event, TimerTrigger, HeldTimerTrigger, OrTrigger,
                 IntegerPrimitive, IntegerLiteral, IntegerState, ArrayRead, ArrayWrite, CheckedInteger, CheckedIndex, Loop as RuntimeLoop, EventMath, Origin, Program, Power, Select, State, StateRef, OperatorRef, Transition, AbsDelay, Slew, Idt, LaplaceNd, IdtMod, Sin, MathFunction, Ddt, StepBound, Display, FinalStepTrigger, InitialStepTrigger)
from .lowering import lower, scale, UnsupportedConstantPower, FiniteIntegerUnavailable
from .limits import check_ir
from .input_rational_scope import input_rational_tree
from .compact_source_select import compact_source_assignment
from .integer_prefix import factor_integer_prefix
from .parameters import bind_parameters
from .elaboration import unroll_loops
from .array_elaboration import scalarize_arrays, ARRAY_BUDGET
from . import event_index_domains, integer_bits, finite_math
from .rational_predicates import condition_positive_facts, normalize_positive_quotient_comparison
from .initialization_aliases import bind_initial_voltage_aliases, bind_runtime_voltage_aliases, bind_event_body_aliases
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
    initial_math_work: int = 100_000
    indices: dict[str, int] = field(init=False)
    source_rational_origins: list[Origin] = field(default_factory=list)
    source_rational_nodes: set[int] = field(default_factory=lambda: {0})
    settled_integer_reads: bool = False

    def __post_init__(self):
        self.indices = {name: i for i, name in enumerate(self.nodes)}

    def program(self) -> Program:
        result = Program(self.nodes, tuple(self.contributions), tuple(self.states), tuple(self.events), tuple(self.operators),
                         step_bounds=tuple(self.step_bounds))
        check_ir(result)
        if self.source_rational_origins:
            trees = [input_rational_tree(c.rhs, self.source_rational_nodes) for c in result.contributions]
            if (result.states or result.events or result.operators or result.step_bounds
                    or any(tree is None for tree in trees)):
                origin = self.source_rational_origins[0]
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: non-affine guards require a complete stateless input-only algebraic program")
        return result


def _predicate_degree(expression, memo=None):
    """Structural scope: node-free constant (0), affine/select (1), or unsupported.

    No cancellation removes a dependency. Input-selected constants count as
    input-dependent, so only a node-free scalar can multiply a predicate.
    """
    if memo is None:
        memo = {}
    key = id(expression)
    if key in memo:
        return memo[key][1]
    if isinstance(expression, StateRef):
        result = 1
    elif isinstance(expression, Affine):
        result = int(bool(expression.terms))
    elif isinstance(expression, Binary):
        if expression.op == "divide":
            result = None
        else:
            left, right = _predicate_degree(expression.left, memo), _predicate_degree(expression.right, memo)
            if left is None or right is None:
                result = None
            else:
                degree = max(left, right) if expression.op == "add" else left + right
                result = degree if degree <= 1 else None
    elif isinstance(expression, Power):
        degree = _predicate_degree(expression.base, memo)
        result = degree if degree == 0 or expression.exponent == 1 else None
    elif isinstance(expression, Select):
        degrees = [_predicate_degree(value, memo) for value in
                   (expression.left, expression.right, expression.then_value, expression.else_value)]
        result = None if None in degrees else max(degrees)
    else:
        result = None
    memo[key] = (expression, result)
    return result


class InstanceCompiler:
    def __init__(self, instance: "Instance", model: Model, nets: dict[str, str], compilation: Compilation, *,
                 source_model: Model | None = None):
        self.instance = instance
        self.model = model
        self.event_body_source_model = source_model
        self.compilation = compilation
        self.cache: dict[str, float] = {}
        self.node_ids = {name: compilation.indices[net] for name, net in nets.items()}
        if "$abstime" in compilation.indices:
            self.node_ids["$abstime"] = compilation.indices["$abstime"]
        self.initials = {}
        self.expression_decision_origins = set()
        self.allowed_condition_nodes = {0} | ({self.node_ids["$abstime"]} if "$abstime" in self.node_ids else set()) | {self.node_ids[port] for port, direction in model.directions.items()
                                             if direction in ("input", "inout")}
        self.compilation.source_rational_nodes.update(self.allowed_condition_nodes)

    def compile(self):
        self.cache = bind_parameters(self.model, self.instance.parameters, self.instance.name)
        self.closed_initial_math = {}
        self.initial_math_source_model = self.model
        # Inspect source writers before scalarization unrolls even zero-trip
        # loops. A future/dead write must not create an immutable binding.
        declaration_writers, pending = set(), list(self.model.initial) + list(self.model.analog)
        for event in self.model.events:
            pending.extend(event.body)
        while pending:
            item = pending.pop()
            if isinstance(item, (SyntaxAssignment, Loop)):
                declaration_writers.add(item.name)
            for branch in ("then_body", "else_body", "body"):
                pending.extend(getattr(item, branch, ()))
        self.model = scalarize_arrays(self.model, self.parameter)
        self.array_elements = self._declared_elements()
        self.array_dispatch_leaves = 0
        self.array_flow = {}
        self._array_flow_holder = []
        # A declaration does not become held state just because another variable
        # has an event writer. Walk writes (including conditional/loop bodies),
        # so event targets retain the VA declaration default of zero.
        def writes(statements):
            for statement in statements:
                if isinstance(statement, SyntaxAssignment):
                    if statement.index is not None and statement.name in self.array_elements:
                        # A dynamic write can select any declared slot.
                        yield from (f'{statement.name}[{k}]'
                                    for k in self.array_elements[statement.name])
                    else:
                        yield statement.name
                elif isinstance(statement, SyntaxConditional):
                    yield from writes(statement.then_body)
                    yield from writes(statement.else_body)
                elif isinstance(statement, Loop):
                    yield statement.name
                    yield from writes(statement.body)

        persistent = set(writes(self.model.initial))
        event_writers = set()
        for event in self.model.events:
            persistent.update(writes(event.body))
            if any(trigger.kind in ("cross", "timer") for trigger in event.triggers):
                event_writers.update(writes(event.body))
        all_writers = persistent | set(writes(self.model.analog))
        immutable_names = set(self.model.variable_initializers) - all_writers - declaration_writers - set(self.model.arrays)
        self.local_variables = set(writes(self.model.analog)) - persistent
        self.preserve_analog_structure = self.compilation.preserve_structure or bool(self.local_variables)
        def expression_reads(expr):
            if expr is None:
                return set()
            if expr.op == "index" and str(expr.value) in self.array_elements:
                # A dynamic read can observe any declared slot.
                names = {f'{expr.value}[{k}]' for k in self.array_elements[str(expr.value)]}
            else:
                names = {expr.value} if expr.op == "parameter" else set()
            for arg in expr.args:
                names.update(expression_reads(arg))
            return names
        def reads(statements):
            names = set()
            for statement in statements:
                for field in ("rhs", "index", "left", "right", "start", "limit", "update"):
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
                                 if name not in self.local_variables and name not in immutable_names and name not in self.closed_initial_math
                                 and (name in persistent or name in referenced))
        self.state_ids = {name: len(self.compilation.states) + index for index, name in enumerate(self.state_names)}
        self.constant_local_aliases = self.bind_constant_local_aliases(writes)
        self.initial_voltage_aliases = bind_initial_voltage_aliases(self, writes)
        self.runtime_voltage_aliases = bind_runtime_voltage_aliases(self, writes)
        self.event_body_aliases = bind_event_body_aliases(self, writes)
        self.active_event_aliases = {}
        seeds = self.bind_declaration_initializers(event_writers, immutable_names)
        # No-writer declaration values belong to the variable namespace. They
        # never enter model.parameters/cache or manufacture held event state.
        self.immutable_declarations = {name: value for name, value in seeds.items() if name in immutable_names}
        self.declaration_initials = {name: value for name, value in seeds.items() if name not in immutable_names}
        self.initialize_states()
        from .event_real_ranges import floor_use_sites
        self.event_floor_range_facts = floor_use_sites(
            [event.body for event in self.model.events],
            [name for name in self.state_names if self.model.variables[name] == 'real'],
            self.parameter, integer_type=self.integer_type)
        self.infer_integer_state_ranges()
        self.analyze_event_index_domains()
        from .event_specialization import audit_event_body, specialize_event_body
        self.array_audit_dispatch_leaves = 0
        native_allowances = {}
        for event in self.model.events:
            self.active_event_aliases = self.aliases_at(event.token, body=True)
            self.runtime_event_checks = self.checked_event_context(event)
            native_allowances[id(event)] = audit_event_body(self, event.body)
        for event in self.model.events:
            self.active_event_aliases = self.aliases_at(event.token)
            self.runtime_event_checks = self.checked_event_context(event)
            self.native_integer_charge = native_allowances[id(event)]
            triggers = tuple(self.trigger(leaf) for leaf in event.triggers)
            event_trigger = triggers[0] if len(triggers) == 1 else OrTrigger(triggers)
            origin = Origin(event.token.source or self.model.source, event.token.line, event.token.column, self.instance.name, event.token.expansion)
            def retained(body):
                if self.event_reachable_statements is None:
                    return body
                return tuple(replace(item, then_body=retained(item.then_body), else_body=retained(item.else_body))
                             if isinstance(item, SyntaxConditional) else item
                             for item in body if id(item) in self.event_reachable_statements)
            execution = specialize_event_body(retained(event.body), self.cache)
            self.active_event_aliases = self.aliases_at(event.token, body=True)
            self.compilation.events.append(Event(event_trigger, self.body(execution), origin))
        self.active_event_aliases = {}
        statements = unroll_loops(self.model, self.parameter)
        self.validate_branch_presence(statements)
        # Only a whole-program no-feedback certificate permits these bounds.
        # Initialization and all event/final-step lowering above retain the
        # lifetime domains and every original checked integer intermediate.
        self.ordinary_integer_bounds = None
        if self.compilation.settled_integer_reads:
            self.ordinary_integer_bounds = dict(self.integer_state_ranges)
            for name, (low, high) in self.event_entry_domains.items():
                state = self.state_ids[name]
                old_low, old_high = self.integer_state_ranges.get(state, (-2147483648, 2147483647))
                # Both facts are sound; a coarser entry transfer must not
                # replace a stronger existing state-independent writer proof.
                self.ordinary_integer_bounds[state] = (max(low, old_low), min(high, old_high))
        try:
            _, contributions = self.execute_analog(statements, {})
        finally:
            self.ordinary_integer_bounds = None
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

    def bind_constant_local_aliases(self, writes):
        # Only a unique unconditional writer can denote the same instance
        # constant throughout an analysis. Evaluate candidates in source order,
        # never from a dependency graph that could move a future write earlier.
        counts = {}
        for name in writes(self.model.analog):
            counts[name] = counts.get(name, 0) + 1
        aliases = {}
        for statement in self.model.analog:
            if (not isinstance(statement, SyntaxAssignment) or statement.index is not None
                    or statement.name not in self.local_variables or counts[statement.name] != 1):
                continue
            pending = [statement.rhs]
            pure = True
            while pending:
                expr = pending.pop()
                if (expr.op in ("voltage", "time", "array", "index", "call")
                        or expr.op in OPERATOR_NAMES
                        or expr.op == "parameter" and expr.value not in self.model.parameters
                        and expr.value not in aliases):
                    pure = False
                    break
                pending.extend(expr.args)
            if not pure:
                continue
            try:
                def resolve(name):
                    return aliases[name] if name in aliases else self.parameter(name)
                value = lower(statement.rhs, self.typed_resolve(resolve), {}, self.model.source)
                if not isinstance(value, Affine) or value.terms or not math.isfinite(value.constant):
                    continue
                if self.model.variables[statement.name] == "integer":
                    self.validate_integer_value(value, statement.token, initial=True)
                aliases[statement.name] = value
            except CompileError as error:
                if error.diagnostic['code'] == 'resource_budget':
                    raise
                # Ordinary execution still diagnoses an invalid assignment.
        return aliases

    def aliases_at(self, token, *, body=False):
        # Retain expressions here. Event lowering evaluates their input nodes
        # at the current physical root, independently of initial sampling.
        aliases = self.constant_local_aliases | self.runtime_voltage_aliases
        if body:
            aliases |= self.event_body_aliases
        return {name: value for name, value in aliases.items()
                if name in self.model.local_alias_scopes.get(token, ())}

    def bind_declaration_initializers(self, event_writers, immutable_names):
        # Declarations either seed existing event state or bind a no-writer
        # scalar. Neither reads another variable's default/initial value.
        seeds = {}
        for name, expr in self.model.variable_initializers.items():
            try:
                if name not in event_writers | immutable_names or name in self.model.arrays:
                    raise CompileError("declaration initialization requires a scalar event target or a variable without procedural writers")
                pending = [expr]
                while pending:
                    item = pending.pop()
                    if (item.op in ("voltage", "time", "array", "index")
                            or item.op == "parameter" and item.value not in self.model.parameters
                            or item.op in OPERATOR_NAMES or item.op in DECISION_NAMES):
                        raise CompileError("declaration initializers require instance-constant parameter expressions")
                    pending.extend(item.args)
                value = lower(expr, self.typed_resolve(self.parameter), {}, self.model.source)
                if not isinstance(value, Affine) or value.terms or not math.isfinite(value.constant):
                    raise CompileError("declaration initialization requires a finite scalar constant")
                if self.model.variables[name] == "integer":
                    self.validate_integer_value(value, expr.token, initial=True)
                seeds[name] = value
            except CompileError as exc:
                if exc.diagnostic['code'] == 'resource_budget':
                    raise
                raise CompileError(f'unsupported declaration initializer: {exc}',
                                   code='unsupported_initial_event', token=expr.token,
                                   instance=self.instance.name) from exc
        return seeds

    def initialize_states(self):
        # Initial procedural execution uses a symbolic environment. Each write
        # replaces the previous value, and branch merges preserve source order.
        env = {name: Affine(0., ()) for name in self.state_names}
        # All explicit seeds have been validated before initial_step can
        # overwrite them. This environment belongs to only this instance.
        env.update(self.declaration_initials)
        def resolve(values, aliases):
            return self.typed_resolve(lambda name: values[name] if name in values else
                                      aliases[name] if name in aliases else self.parameter(name))
        snapshots = []
        def constant_snapshot(value):
            try:
                return constant_snapshot_value(value)
            except ArithmeticError as error:
                raise CompileError('active initial output requires finite snapshots') from error
        def constant_snapshot_value(value):
            # Resolve only closed initializer values. Even a dead arm must not
            # smuggle voltage/history observation into the new output contract.
            if isinstance(value, Affine) and not value.terms:
                number = value.constant
            elif isinstance(value, Binary):
                a, b = constant_snapshot(value.left), constant_snapshot(value.right)
                number = {'add': lambda: a+b, 'multiply': lambda: a*b,
                          'divide': lambda: a/b}[value.op]()
            elif isinstance(value, Power):
                number = constant_snapshot(value.base) ** value.exponent
            elif isinstance(value, Select):
                a, b = constant_snapshot(value.left), constant_snapshot(value.right)
                yes, no = constant_snapshot(value.then_value), constant_snapshot(value.else_value)
                number = yes if {'lt': a<b, 'le': a<=b, 'gt': a>b, 'ge': a>=b}[value.relation] else no
            else:
                raise CompileError('active initial output requires constant initialization snapshots')
            if not math.isfinite(number):
                raise CompileError('active initial output requires finite snapshots')
            return number
        def has_output(statements):
            return any(isinstance(item, SyntaxDisplay) or isinstance(item, SyntaxConditional)
                       and (has_output(item.then_body) or has_output(item.else_body)) for item in statements)
        def execute(statements, values, aliases=None, active=True):
            values = dict(values)
            for statement in statements:
                if (isinstance(statement, SyntaxAssignment)
                        and statement.name in self.closed_initial_math):
                    continue  # Complete observer-free initial AST was audited by its owner.
                if statement.token in self.model.local_alias_scopes:
                    aliases = {name: value for name, value in
                               (self.constant_local_aliases | self.initial_voltage_aliases).items()
                               if name in self.model.local_alias_scopes[statement.token]}
                aliases = aliases or {}
                if isinstance(statement, SyntaxConditional):
                    left = lower(statement.left, resolve(values, aliases), self.node_ids, self.model.source,
                                 preserve_structure=True, decisions=self.initial_select, node_declarations=True)
                    right = lower(statement.right, resolve(values, aliases), self.node_ids, self.model.source,
                                  preserve_structure=True, decisions=self.initial_select, node_declarations=True)
                    self.validate_initial_operand(statement.left, left)
                    self.validate_initial_operand(statement.right, right)
                    if has_output(statement.then_body) or has_output(statement.else_body):
                        a, b = constant_snapshot(left), constant_snapshot(right)
                        selected = {'<': a<b, '<=': a<=b, '>': a>b, '>=': a>=b}[statement.relation]
                    else:
                        selected = True
                    yes = execute(statement.then_body, values, aliases, active and selected)
                    no = execute(statement.else_body, values, aliases, active and not selected)
                    for name in values:
                        if yes[name] is not no[name]:
                            values[name] = self.initial_select(statement.left,
                                {"<":"lt", "<=":"le", ">":"gt", ">=":"ge"}[statement.relation],
                                left, right, yes[name], no[name])
                elif isinstance(statement, SyntaxDisplay):
                    arguments = []
                    for argument in statement.args:
                        value = lower(argument, resolve(values, aliases), self.node_ids, self.model.source,
                                      preserve_structure=True, decisions=self.initial_select,
                                      validate_decision=self.validate_initial_operand, node_declarations=True)
                        arguments.append(Affine(constant_snapshot(value), ()))
                    origin = Origin(statement.token.source or self.model.source, statement.token.line,
                                    statement.token.column, self.instance.name, statement.token.expansion)
                    if active:
                        snapshots.append(Display(statement.format, tuple(arguments), origin))
                else:
                    if not isinstance(statement, SyntaxAssignment) or statement.name not in self.state_ids:
                        raise CompileError("initial_step requires declared state assignments")
                    try:
                        value = lower(statement.rhs, resolve(values, aliases), self.node_ids, self.model.source,
                                      preserve_structure=True, decisions=self.initial_select,
                                      validate_decision=self.validate_initial_operand, node_declarations=True)
                    except UnsupportedConstantPower:
                        # The original traversal owns classification. Old accepted
                        # initializers never enter or pay for the optional proof.
                        from .initial_constant_math import binding
                        closed = binding(self, self.initial_math_source_model)
                        if statement.name not in closed:
                            raise
                        self.closed_initial_math = closed
                        self.state_names = ()
                        self.state_ids = {}
                        for name in closed:
                            values.pop(name, None)
                        continue
                    self.validate_initial_operand(statement.rhs, value)
                    def constant_arms(item):
                        if isinstance(item, Affine):
                            return not item.terms
                        if isinstance(item, Select):
                            return constant_arms(item.then_value) and constant_arms(item.else_value)
                        if isinstance(item, Binary):
                            return item.op in ("add", "multiply") and constant_arms(item.left) and constant_arms(item.right)
                        return isinstance(item, Power) and constant_arms(item.base)
                    if self.model.variables[statement.name] == "integer":
                        if not constant_arms(value):
                            raise CompileError("integer initial_step values require constant-valued arms selected by input predicates")
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
        if snapshots:
            self.compilation.events.append(Event(InitialStepTrigger(), tuple(snapshots), snapshots[0].origin))
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
        # Internal constant lookup does not grant parameter override authority:
        # bind_parameters validated external keys before these bindings exist.
        if name in getattr(self, "closed_initial_math", {}):
            return self.closed_initial_math[name]
        if name in getattr(self, "immutable_declarations", {}):
            return self.immutable_declarations[name]
        if name not in self.model.parameters:
            raise CompileError(f"{self.model.source}: unknown parameter {name!r}")
        return self.cache[name]

    def symbol(self, name):
        if name in self.active_event_aliases:
            return self.active_event_aliases[name]
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
        event_values = kwargs.pop("event_values", False)
        sampled_values = kwargs.pop("sampled_values", False)
        static_integer_audit = kwargs.pop("static_integer_audit", False)
        typed = self.typed_resolve(resolve, allow_integer_assignment_root=assignment_root)
        typed.sampled_values = sampled_values
        if (event_values or sampled_values) and hasattr(self, 'native_integer_charge'):
            typed.native_integer = lambda item: self.native_event_integer(item, resolve)
        if event_values or sampled_values:
            typed.finite_floor = lambda item, argument: self.finite_floor(item, argument, native=True)
        if event_values:
            if getattr(self, "runtime_event_checks", False) and not static_integer_audit:
                typed.validate_integer_operation = self.checked_event_integer
            def math_value(item, args):
                origin = Origin(item.token.source or self.model.source, item.token.line,
                    item.token.column, self.instance.name, item.expansion)
                return EventMath(item.op, args, origin)
            typed.event_math = math_value
            kwargs["decisions"] = self.event_select
            kwargs.pop("validate_decision", None)
        try:
            table = self.integer_expression_table(expr, resolve, nodes, args, kwargs)
            if table is not None:
                return table
            return lower(expr, typed, nodes, self.model.source, *args, **kwargs)
        except CompileError as error:
            if (error.diagnostic['code'] in ('unsupported_local_event', 'unsupported_event_state_dependency')
                    and 'location' not in error.diagnostic):
                raise CompileError(str(error), code=error.diagnostic['code'], token=expr.token,
                                   instance=self.instance.name) from error
            raise

    def event_select(self, expr, relation, left, right, yes, no):
        origin = Origin(expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        result = Select(relation, left, right, yes, no, origin)
        check_ir(result, origin)
        return result

    def integral(self, expression):
        # Do not introduce an implicit real-to-integer rounding rule.
        if isinstance(expression, Affine):
            return not expression.terms and expression.constant.is_integer()
        if isinstance(expression, (CheckedIndex, CheckedInteger, IntegerPrimitive)):
            return True
        if isinstance(expression, ArrayRead):
            return all(self.compilation.states[state].kind == "integer" for state in expression.states)
        if isinstance(expression, StateRef):
            return self.compilation.states[expression.state].kind == "integer"
        if isinstance(expression, EventMath):
            return expression.function == "floor" or expression.function != "sqrt" and all(self.integral(arg) for arg in expression.args)
        if isinstance(expression, Select):
            return self.integral(expression.then_value) and self.integral(expression.else_value)
        if isinstance(expression, Power):
            return self.integral(expression.base) and expression.exponent >= 0
        return isinstance(expression, Binary) and expression.op in ("add", "multiply") and self.integral(expression.left) and self.integral(expression.right)

    def integral_bounds(self, expression):
        if isinstance(expression, IntegerPrimitive):
            if expression.function == 'remainder':
                divisor = expression.args[1]
                # Only successful checked values participate in this enclosure.
                # A dynamic signed32 divisor can have magnitude at most 2**31.
                width = abs(divisor.value) if isinstance(divisor, IntegerLiteral) else 2147483648
                return -width + 1, width - 1
            return -2147483648, 2147483647
        if isinstance(expression, ArrayRead):
            bounds = [self.integral_bounds(StateRef(state)) for state in expression.states]
            return min(a for a,b in bounds), max(b for a,b in bounds)
        if isinstance(expression, CheckedInteger):
            low, high = self.integral_bounds(expression.value)
            # A successful checked node is both in its source-proven range
            # and in signed32. The runtime check remains in the expression.
            low, high = max(low, -2147483648), min(high, 2147483647)
            if low > high:
                raise CompileError("checked integer arithmetic has no signed 32-bit result",
                                   code="unsupported_integer_arithmetic", token=expression.origin,
                                   instance=self.instance.name)
            return low, high
        if isinstance(expression, CheckedIndex):
            return expression.first, expression.last
        if isinstance(expression, Affine) and not expression.terms:
            return expression.constant, expression.constant
        if isinstance(expression, StateRef):
            bounds = getattr(self, "ordinary_integer_bounds", None)
            if bounds is None:
                bounds = getattr(self, "integer_state_ranges", {})
            return bounds.get(expression.state, (-2147483648, 2147483647))
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

    def checked_event_integer(self, expr, value, *, root=False):
        if (expr.op not in ("+", "-", "*", "/", "%", "unary-", "unary+") or
                not self.integer_type(expr) or not self.integral(value)):
            return None
        # Keep all existing static errors for constant expressions. A runtime
        # observer preserves each arithmetic node, so overflow cannot disappear
        # in a later cancellation or an unused Select arm.
        pending = [expr]
        state_dependent = False
        while pending:
            item = pending.pop()
            state_dependent |= item.op in ("parameter", "index") and item.value in self.model.variables
            pending.extend(item.args)
        if not state_dependent:
            self.validate_integer_operation(expr, value, root=root)
            return None
        origin = Origin(expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        return CheckedInteger(value, origin)

    def typed_resolve(self, resolve, *, allow_integer_assignment_root=False):
        def lookup(name):
            return resolve(name)
        lookup.integer_arithmetic = self.integer_arithmetic
        lookup.integer_bitwise = self.integer_bitwise
        lookup.finite_power = self.finite_power
        lookup.finite_floor = self.finite_floor
        lookup.validate_integer_operation = self.validate_integer_operation
        lookup.allow_integer_assignment_root = allow_integer_assignment_root
        if getattr(self, "ordinary_integer_bounds", None) is not None:
            def finite_integer(expr, nodes, args, options):
                # The existing complete table audits each original arithmetic
                # node before folding a row. Per-bit nested tables would copy
                # a shift tree again for every possible AND operand value.
                if expr.op not in integer_bits.OPS | {"+", "-", "*", "/", "%", "unary+", "unary-"}:
                    return None
                return self.integer_expression_table(expr, lookup, nodes, args, options)
            lookup.finite_integer_expression = finite_integer
        return lookup

    def finite_power(self, expr, base, exponent):
        if not self.integer_type(expr.args[1]) or not self.integral(exponent):
            return None
        bounds = self.integral_bounds(exponent)
        origin = Origin(expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        try:
            result = finite_math.power(base, exponent, bounds, origin)
        except ValueError as error:
            raise CompileError(str(error), token=expr.token,
                               instance=self.instance.name) from error
        if result is not None:
            self.expression_decision_origins.add(origin)
        return result

    def finite_floor(self, expr, argument, *, native=False):
        from .finite_floor import floor_table
        if (_predicate_degree(argument) is None
                or not self.expression_nodes(argument).issubset(self.allowed_condition_nodes)):
            raise CompileError('floor requires a source-clamped piecewise-affine input expression',
                               code='unsupported_floor', token=expr.token, instance=self.instance.name)
        origin = Origin(expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        fact = getattr(self, 'event_floor_range_facts', {}).get(id(expr))
        state_bounds = ({self.state_ids[name]: bounds for name, bounds in fact[1].items()}
                        if fact is not None and fact[0] is expr else None)
        try:
            result = floor_table(argument, origin, state_bounds=state_bounds)
        except CompileError as error:
            if not native or error.diagnostic['code'] != 'unsupported_floor':
                raise
            # Audit the original operand before cancelled voltage/state reads
            # can disappear from a folded affine. This gate does not grant a
            # lifetime range or turn floor's real source type into integer.
            def source_input(item):
                if item.op == 'voltage':
                    return all(self.node_ids.get(str(node.value)) in self.allowed_condition_nodes
                               and str(node.value) != '$abstime' for node in item.args)
                if item.op == 'parameter':
                    return item.value in self.model.parameters
                return item.op in ('number', '+', '-', '*', '/', 'unary+', 'unary-') and all(
                    source_input(child) for child in item.args)
            def binary_scale(number):
                return number == 0 or math.isfinite(number) and math.frexp(abs(number))[0] == 0.5
            def affine_input(value):
                if isinstance(value, Affine):
                    return all(t.node in self.allowed_condition_nodes and
                               t.node != self.node_ids.get('$abstime') and binary_scale(t.coefficient)
                               for t in value.terms)
                if isinstance(value, Binary) and value.op in ('add', 'multiply'):
                    if value.op == 'multiply' and any(isinstance(part, Affine) and not part.terms
                            and not binary_scale(part.constant) for part in (value.left,value.right)):
                        return False
                    return affine_input(value.left) and affine_input(value.right)
                return isinstance(value, Power) and value.exponent == 1 and affine_input(value.base)
            if not source_input(expr.args[0]) or not affine_input(argument):
                raise error
            result = EventMath('floor', (argument,), origin)
        if isinstance(result, Select):
            self.expression_decision_origins.add(origin)
        return result

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
            if isinstance(item, IntegerPrimitive):
                return True  # Each typed child retains its runtime signed32 check.
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
            raise FiniteIntegerUnavailable("integer intermediate signed 32-bit range is unproven",
                               token=expr.token, instance=self.instance.name)
        raise CompileError("integer intermediate may exceed signed 32-bit range",
                           token=expr.token, instance=self.instance.name)

    def integer_type(self, expr):
        return integer_bits.integer_type(expr, self.model.variables,
                                         self.model.parameter_types, self.model.genvars)

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
            # Dynamic indexed writes conservatively target every declared slot.
            for statement in statements:
                if isinstance(statement, SyntaxAssignment):
                    if statement.index is not None and statement.name in self.array_elements:
                        targets = tuple(f'{statement.name}[{k}]'
                                        for k in self.array_elements[statement.name])
                    else:
                        targets = (statement.name,)
                    yield targets, statement.rhs
                elif isinstance(statement, Loop):
                    # The control is assigned repeatedly at runtime. Its
                    # initializer alone is not a lifetime range proof.
                    yield (statement.name,), statement.update
                    yield from writes(statement.body)
                elif isinstance(statement, SyntaxConditional):
                    yield from writes(statement.then_body)
                    yield from writes(statement.else_body)
        writers = [writer for event in self.model.events for writer in writes(event.body)]
        for name in self.state_names:
            if self.model.variables[name] != "integer":
                continue
            state = self.state_ids[name]
            initial = self.initials[name]
            initial = Affine(initial, ()) if isinstance(initial, (int, float)) else initial
            bounds = [self.integral_bounds(initial)]
            for targets, rhs in writers:
                if name not in targets:
                    continue
                try:
                    value = self.lower_event(rhs, self.symbol, self.node_ids,
                        preserve_structure=True, decisions=self.expression_select,
                        node_declarations=True, indices=self.conservative_array_read)
                    if contains_state(value) or not self.integral(value):
                        raise CompileError("state-dependent integer bound")
                    bounds.append(self.integral_bounds(value))
                except CompileError:
                    bounds = [(-2147483648, 2147483647)]
                    break
            ranges[state] = min(a for a, _ in bounds), max(b for _, b in bounds)
        self.integer_state_ranges = ranges

    def integer_expression_table(self, expr, resolve, nodes, args, options):
        """One bounded pure-integer table, preserving all original state reads."""
        if not self.integer_type(expr):
            return None
        allowed = integer_bits.OPS | {"number", "parameter", "+", "-", "*", "/", "%", "unary+", "unary-"}
        pending, references, has_bits, runtime_divisor = [expr], {}, False, False
        while pending:
            item = pending.pop()
            if item.op not in allowed:
                return None
            has_bits |= item.op in integer_bits.OPS
            if item.op in ("<<", ">>", "/", "%"):
                # Runtime shifts retain their instance-constant contract.
                # Division/modulo instead retain every divisor read in this
                # complete bounded table and audit every original grid row.
                count = [item.args[1]]
                while count:
                    part = count.pop()
                    if part.op == "parameter" and part.value in self.model.variables:
                        if item.op in ("<<", ">>"):
                            return None
                        runtime_divisor = True
                    count.extend(part.args)
            if item.op == "parameter" and item.value in self.model.variables:
                value = resolve(item.value)
                if isinstance(value, StateRef):
                    references[item.value] = value
                elif not isinstance(value, Affine) or value.terms:
                    return None
            pending.extend(item.args)
        if not (has_bits or runtime_divisor) or not references:
            return None
        states = tuple(dict.fromkeys(references.values()))
        bounds = [tuple(map(int, self.integral_bounds(state))) for state in states]
        if not integer_bits.small_domain(bounds):
            return None
        code = "unsupported_integer_bitwise" if has_bits else "unsupported_integer_arithmetic"
        context = "bitwise" if has_bits else "integer arithmetic"
        origin = Origin(expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        options = dict(options)
        options.pop("memo", None)  # A binding owns its memo; never reuse across rows.
        def table(operand, bindings):
            if operand == len(states):
                def lookup(name):
                    return bindings[references[name]] if name in references else resolve(name)
                typed = self.typed_resolve(lookup)
                # Every grid row uses the existing strict arithmetic observer,
                # not the successful-range clipping of runtime checked nodes.
                try:
                    value = lower(expr, typed, nodes, self.model.source, *args, **options)
                except CompileError as error:
                    raise CompileError(context + " expression cannot prove every integer intermediate: " + str(error),
                        code=code, token=expr.token,
                        instance=self.instance.name) from error
                # Modulo deliberately retains arithmetic IR even for constant
                # arguments. Prove that the strict lowering left only constant
                # arithmetic, rather than adding another expression evaluator.
                pending, constant = [value], True
                while pending:
                    item = pending.pop()
                    if isinstance(item, Affine):
                        constant &= not item.terms
                    elif isinstance(item, Binary) and item.op in ("add", "multiply"):
                        pending.extend((item.left, item.right))
                    elif isinstance(item, Select):
                        pending.extend((item.left, item.right, item.then_value, item.else_value))
                    else:
                        # Includes StateRef, ArrayRead, OperatorRef, and checked
                        # nodes: none may disappear behind a point bound.
                        constant = False
                if constant and self.integral(value):
                    low, high = self.integral_bounds(value)
                    if low == high and -2147483648 <= low <= 2147483647:
                        return Affine(float(low), ())
                raise CompileError("finite integer binding did not produce proven constant integer IR",
                    code=code, token=expr.token,
                    instance=self.instance.name)
            state = states[operand]
            low, high = bounds[operand]
            def leaf(number):
                return table(operand + 1, bindings | {state: float(number)})
            def split(first, last):
                if first == last:
                    return leaf(first)
                middle = (first + last + 1) // 2
                return Select("lt", state, Affine(float(middle), ()),
                              split(first, middle - 1), split(middle, last), origin)
            if low == high:
                value = leaf(low)
                return Select("lt", state, Affine(low + 0.5, ()), value, value, origin)
            return split(low, high)
        value = table(0, {})
        check_ir(value, origin)
        self.expression_decision_origins.add(origin)
        return value

    def integer_bitwise(self, expr, values):
        def fail(message):
            raise CompileError(message, token=expr.token, instance=self.instance.name,
                               code="unsupported_integer_bitwise")
        if not all(self.integer_type(arg) and self.integral(value)
                   for arg, value in zip(expr.args, values)):
            fail("bitwise operands require typed integer expressions")
        # A checked node's successful interval is clipped to signed32. A
        # finite table may fold that interval to a constant and discard the
        # node, so require the original arithmetic to be safe independently.
        pending = list(values)
        while pending:
            item = pending.pop()
            if isinstance(item, CheckedInteger):
                low, high = self.integral_bounds(item.value)
                if low < -2147483648 or high > 2147483647:
                    fail("bitwise operand has an unproven checked integer intermediate")
                pending.append(item.value)
            elif isinstance(item, CheckedIndex):
                low, high = self.integral_bounds(item.index)
                if low < item.first or high > item.last:
                    fail("bitwise operand has an unproven checked array index")
                pending.append(item.index)
            elif isinstance(item, Binary):
                pending.extend((item.left, item.right))
            elif isinstance(item, Select):
                pending.extend((item.left, item.right, item.then_value, item.else_value))
            elif isinstance(item, Power):
                pending.append(item.base)
            elif isinstance(item, EventMath):
                pending.extend(item.args)
            elif isinstance(item, ArrayRead):
                pending.append(item.index)
        bounds = [tuple(map(int, self.integral_bounds(value))) for value in values]
        if expr.op in ("<<", ">>") and bounds[1][0] != bounds[1][1]:
            fail("bitwise shift count requires an instance-constant integer")
        if expr.op in ("<<", ">>") and not isinstance(values[1], Affine):
            fail("bitwise shift count requires an instance-constant integer")
        if not integer_bits.small_domain(bounds):
            fail("bounded integer bitwise operation exceeds finite-domain budget (256)")
        origin = Origin(expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        if len(values) == 2:
            from .finite_floor import map_integer_leaves
            mapped = map_integer_leaves(values[0], expr.op, values[1])
            if mapped is not None:
                check_ir(mapped, origin)
                self.expression_decision_origins.add(origin)
                return mapped
        def tree(operand, args):
            if operand == len(values):
                return Affine(float(integer_bits.evaluate(expr.op, *args)), ())
            low, high = bounds[operand]
            if low == high:
                value = tree(operand + 1, args + [low])
                if isinstance(values[operand], Affine) and not values[operand].terms:
                    return value
                # Range proof does not erase an original source read, even
                # when every successful value is the same integer. The kernel
                # retains predicate reads for equivalent Select arms.
                return Select("lt", values[operand], Affine(low + 0.5, ()), value, value, origin)
            def split(first, last):
                if first == last:
                    return tree(operand + 1, args + [first])
                middle = (first + last + 1) // 2
                return Select("lt", values[operand], Affine(float(middle), ()),
                              split(first, middle - 1), split(middle, last), origin)
            return split(low, high)
        value = tree(0, [])
        check_ir(value, origin)
        if any(low != high for low, high in bounds):
            self.expression_decision_origins.add(origin)
        return value

    def native_event_integer(self, expr, resolve):
        # This is called only after the original route classified a finite
        # representation failure. One bottom-up visit types each source node;
        # no domain enumeration, child retyping, or folded arithmetic inputs.
        def build(item):
            self.native_integer_charge(item)
            if item.op == 'number':
                if not integer_bits.integer_type(item, self.model.variables, self.model.parameter_types, self.model.genvars):
                    return None
                number = item.value
            elif item.op == 'parameter':
                if not integer_bits.integer_type(item, self.model.variables, self.model.parameter_types, self.model.genvars):
                    return None
                value = resolve(item.value)
                if isinstance(value, StateRef):
                    return IntegerState(value.state)
                if isinstance(value, Affine) and not value.terms:
                    number = value.constant
                elif isinstance(value, (int, float)):
                    number = value
                else:
                    return None
            elif item.op in ('unary+', 'unary-'):
                value = build(item.args[0])
                if not isinstance(value, IntegerLiteral):
                    return None
                number = value.value if item.op == 'unary+' else -value.value
            elif item.op in ('+', '-', '%'):
                values = tuple(build(arg) for arg in item.args)
                if any(value is None for value in values):
                    return None
                if item.op == '%' and isinstance(values[1], IntegerLiteral) and values[1].value == 0:
                    raise CompileError('integer division/modulo requires a nonzero divisor', token=item.token)
                origin = Origin(item.token.source or self.model.source, item.token.line,
                                item.token.column, self.instance.name, item.expansion)
                if all(isinstance(value, IntegerLiteral) for value in values):
                    a, b = (value.value for value in values)
                    self.native_integer_charge(item)
                    if item.op == '+':
                        number = a+b
                    elif item.op == '-':
                        number = a-b
                    else:
                        if a == -2147483648 and b == -1:
                            raise CompileError('integer quotient may exceed signed 32-bit range', token=item.token)
                        magnitude = abs(a)//abs(b)
                        number = a - (-magnitude if (a<0)!=(b<0) else magnitude)*b
                else:
                    return IntegerPrimitive({'+': 'add', '-': 'subtract', '%': 'remainder'}[item.op], values, origin)
            else:
                return None
            if not math.isfinite(number) or int(number) != number or not -2147483648 <= number <= 2147483647:
                raise CompileError('integer intermediate may exceed signed 32-bit range', token=item.token)
            return IntegerLiteral(int(number))
        value = build(expr)
        if isinstance(value, IntegerPrimitive):
            check_ir(value, value.origin)
            return value
        return None

    def integer_arithmetic(self, expr, numerator, denominator):
        if not all(self.integer_type(arg) for arg in expr.args):
            return None
        def fail(message):
            raise CompileError(message, token=expr.token, instance=self.instance.name,
                               code="unsupported_integer_arithmetic")
        if expr.op == '%' and (not isinstance(denominator, Affine) or denominator.terms):
            # The operands are source-integer typed above. Only event callers
            # have a native fallback; other consumers retain this rejection.
            raise FiniteIntegerUnavailable('integer remainder requires runtime divisor checking',
                code='unsupported_integer_arithmetic', token=expr.token, instance=self.instance.name)
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
            if not isinstance(numerator, Affine) or numerator.terms:
                raise FiniteIntegerUnavailable("integer quotient requires runtime signed32 checking",
                    code="unsupported_integer_arithmetic", token=expr.token, instance=self.instance.name)
            fail("integer quotient may exceed signed 32-bit range")
        if last-first+1 > 256:
            raise FiniteIntegerUnavailable("bounded integer division/modulo exceeds quotient-bin budget (256)",
                code="unsupported_integer_arithmetic", token=expr.token, instance=self.instance.name)
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

    def _declared_elements(self):
        """Ascending slot integers per retained array declaration."""
        def integer(expr):
            value = lower(expr, self.parameter, {}, self.model.source)
            if (not isinstance(value, Affine) or value.terms or not value.constant.is_integer()
                    or not -2147483648 <= value.constant <= 2147483647):
                raise CompileError(f'{self.model.source}:{expr.token.line}:{expr.token.column}: '
                                   f'array declaration bound requires a signed 32-bit instance-constant integer',
                                   token=expr.token, instance=self.instance.name)
            return int(value.constant)
        return {name: tuple(range(min(integer(left), integer(right)), max(integer(left), integer(right)) + 1))
                for name, (left, right) in self.model.arrays.items()}

    def analyze_event_index_domains(self):
        """Global entry invariant plus per-use FlowFacts for dynamic indices."""
        states = [name for name in self.state_names if self.model.variables[name] == "integer"]
        initial = {}
        for name in states:
            value = self.initials[name]
            if isinstance(value, (int, float)):
                bounds = (int(value), int(value))
            else:
                low, high = self.integral_bounds(value)
                bounds = (int(low), int(high))
            initial[name] = event_index_domains.clamp(bounds)
        bodies = [event.body for event in self.model.events]
        def parameters(name):
            return self.parameter(name)
        from .event_real_ranges import integer_floor_bounds
        parameters.real_floor_bounds = lambda expr: integer_floor_bounds(self.event_floor_range_facts, expr)
        def location_of(token):
            return f"{token.source or self.model.source}:{token.line}:{token.column}"
        from .integer_invariants import ProofBudgetExceeded
        try:
            try:
                domains, _widened = event_index_domains.entry_domains(
                    bodies, initial, arrays=self.array_elements,
                    parameters=parameters, states=states)
            except ProofBudgetExceeded:
                # Range inference is optional. Exhaustion proves no finite
                # invariant and must not reject an otherwise valid old model
                # or restart the candidate search with a fresh allowance.
                domains = {name: event_index_domains.TOP for name in states}
                partitions = None
            else:
                partitions = event_index_domains.boolean_partitions(
                    bodies, initial, arrays=self.array_elements,
                    parameters=parameters, states=states)
            reachable = set() if partitions is not None else None
            facts, holder = event_index_domains.use_site_facts(
                bodies, domains, arrays=self.array_elements,
                parameters=parameters, location_of=location_of, partitioned=partitions, reachable=reachable)
        except ValueError as error:
            raise CompileError(f'{self.model.source}: {error}', code='resource_budget',
                               instance=self.instance.name)
        # A closed event invariant also bounds persistent integers read by
        # continuous expressions, e.g. a selector divided into bus bits. Keep
        # unbounded endpoints under the existing checked-assignment policy.
        lifetime_domains = dict(domains)
        def retain_intermediates(env):
            for name, value in env.items():
                lifetime_domains[name] = event_index_domains.hull(lifetime_domains[name], value)
        for body in bodies:
            event_index_domains.flow(body, domains, arrays=self.array_elements,
                                     parameters=parameters, on_state=retain_intermediates)
        for name, (low, high) in lifetime_domains.items():
            if -2147483648 < low <= high < 2147483647:
                self.integer_state_ranges[self.state_ids[name]] = (low, high)
        self.event_reachable_statements = reachable
        self.event_entry_domains = domains
        self.array_flow = facts
        self._array_flow_holder = holder

    def _dynamic_index(self, expr, token, access, array):
        """Lower one residual dynamic index with typed checks and admission."""
        location = f"{token.source or self.model.source}:{token.line}:{token.column}"
        entry = self.array_flow.get(id(expr))
        if entry is None:
            raise CompileError(f'{location}: dynamic {access} index of {array!r} lacks flow facts',
                               code='array_index_range', token=token, instance=self.instance.name)
        _, facts = entry
        elements = self.array_elements.get(array, ())
        if not elements:
            raise CompileError(f'{location}: {array!r} is not a declared variable array',
                               token=token, instance=self.instance.name)
        if not self.integer_type(expr):
            raise CompileError(f'{location}: dynamic array index of {array!r} requires a typed integer expression',
                               code='array_index_type', token=token, instance=self.instance.name)
        value = self.lower_event_value(expr, self.symbol, self.node_ids, preserve_structure=True)
        if not self.integral(value):
            raise CompileError(f'{location}: dynamic array index of {array!r} requires integral arithmetic',
                               code='array_index_type', token=token, instance=self.instance.name)
        low, high = elements[0], elements[-1]
        if facts.index != event_index_domains.BOTTOM and not event_index_domains.within(facts.index, low, high):
            if not self.compact_event_candidate():
                raise CompileError(f'{location}: dynamic {access} index of {array!r} is not provably within '
                                   f'[{low}:{high}]; interval [{facts.index[0]},{facts.index[1]}]',
                                   code='array_index_range', token=token, instance=self.instance.name)
            origin = Origin(token.source or self.model.source, token.line, token.column,
                            self.instance.name, token.expansion)
            return CheckedIndex(value, low, high, origin)
        return value

    def _array_read_tree(self, array, elements, index_value, token, *, register=True):
        """Complete balanced Select over every declared slot (no fallback arm)."""
        origin = Origin(token.source or self.model.source, token.line, token.column,
                        self.instance.name, token.expansion)
        if self.compact_event_candidate():
            return ArrayRead(tuple(self.state_ids[f'{array}[{k}]'] for k in elements),
                             index_value, elements[0], elements[-1], origin)
        def tree(items):
            if len(items) == 1:
                return StateRef(self.state_ids[f'{array}[{items[0]}]'])
            middle = len(items) // 2
            boundary = items[middle - 1] + 0.5
            return Select("lt", index_value, Affine(boundary, ()),
                          tree(items[:middle]), tree(items[middle:]), origin)
        result = tree(elements)
        if len(elements) == 1 and isinstance(index_value, CheckedIndex):
            result = Select("lt", index_value, Affine(elements[0]+0.5, ()), result, result, origin)
        check_ir(result, origin)
        if register:
            self.expression_decision_origins.add(origin)
        return result

    def event_index_read(self, expr):
        """`indices` hook: residual dynamic read in an event expression."""
        array = str(expr.value)
        elements = self.array_elements.get(array, ())
        index_value = self._dynamic_index(expr.args[0], expr.token, 'read', array)
        interval = self.array_flow[id(expr.args[0])][1].index
        if (interval != event_index_domains.BOTTOM and
                event_index_domains.within(interval, elements[0], elements[-1])):
            elements = tuple(k for k in elements if interval[0] <= k <= interval[1])
        return self._array_read_tree(array, elements, index_value, expr.token)

    def conservative_array_read(self, expr):
        """Range-inference view of a dynamic read: a Select over every slot."""
        array = str(expr.value)
        elements = self.array_elements.get(array, ())
        index_value = self.lower_event(expr.args[0], self.symbol, self.node_ids, preserve_structure=True)
        return self._array_read_tree(array, elements, index_value, expr.token)

    def event_array_write(self, statement, origin):
        """Single-path balanced If dispatch; only the selected slot is assigned."""
        array = statement.name
        elements = self.array_elements.get(array, ())
        index_value = self._dynamic_index(statement.index, statement.token, 'write', array)
        kind = self.model.variables[f'{array}[{elements[0]}]']
        value = self.lower_event_value(statement.rhs, self.symbol, self.node_ids, preserve_structure=True,
                                 decisions=self.expression_select, validate_decision=self.validate_decision_expression,
                                 node_declarations=True, indices=self.event_index_read,
                                 integer_assignment_root=(kind == "integer"))
        if kind == "integer" and not self.integral(value):
            raise CompileError("integer assignment requires integral state arithmetic",
                               token=statement.token, instance=self.instance.name)
        if self.compact_event_candidate():
            self.array_dispatch_leaves += len(elements)
            if self.array_dispatch_leaves > ARRAY_BUDGET:
                raise CompileError('dynamic array dispatch budget (4096 leaves) exceeded',
                                   code='resource_budget', token=statement.token,
                                   instance=self.instance.name)
            return (ArrayWrite(tuple(self.state_ids[f'{array}[{k}]'] for k in elements),
                               index_value, value, elements[0], elements[-1], origin),)
        def dispatch(items):
            if len(items) == 1:
                self.array_dispatch_leaves += 1
                if self.array_dispatch_leaves > ARRAY_BUDGET:
                    raise CompileError('dynamic array dispatch budget (4096 leaves) exceeded',
                                       code='resource_budget', token=statement.token,
                                       instance=self.instance.name)
                return self.event_assignment(self.state_ids[f'{array}[{items[0]}]'], value, origin)
            middle = len(items) // 2
            boundary = items[middle - 1] + 0.5
            return (Conditional("lt", index_value, Affine(boundary, ()),
                                tuple(dispatch(items[:middle])), tuple(dispatch(items[middle:])), origin),)
        result = dispatch(elements)
        if len(elements) == 1 and isinstance(index_value, CheckedIndex):
            result = (Conditional("lt", index_value, Affine(elements[0]+0.5, ()), result, result, origin),)
        return result

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
                  (lambda nested: self.waveform(nested, resolve)) if expr.op in ("sin", "cos", "exp", "ln", "sqrt", "tanh", "idt", "laplace_nd", "laplace_np", "ddt") else nested_fixed if expr.op in ("absdelay", "slew") else None,
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
            ic, modulus = (v.constant for v in settings[:2])
            offset = settings[2].constant if len(settings) == 3 else 0.0
            if modulus <= 0:
                raise CompileError("idtmod requires positive explicit modulus")
            self.compilation.operators.append(IdtMod(value, ic, modulus, offset, origin))
        elif expr.op == "sin":
            self.compilation.operators.append(Sin(value, origin))
        elif expr.op in ("cos", "exp", "ln", "sqrt", "tanh"):
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
            def dc_target_candidate(item):
                # Admission only: the kernel must prove each original physical
                # source constant on the entire run, including unselected arms.
                if isinstance(item, Affine):
                    nodes = {0} | {self.node_ids[port] for port, direction in self.model.directions.items()
                                   if direction in ("input", "inout")}
                    return all(term.node in nodes for term in item.terms)
                if isinstance(item, StateRef):
                    return True
                if isinstance(item, Select):
                    return dc_target_candidate(item.then_value) and dc_target_candidate(item.else_value)
                if isinstance(item, Binary) and item.op in ("add", "multiply"):
                    return dc_target_candidate(item.left) and dc_target_candidate(item.right)
                return False
            if continuous_value(value) and not dc_target_candidate(value):
                raise CompileError("transition target values must be held states or constants; unsupported whole-domain DC candidate",
                                   token=expr.token, instance=self.instance.name)
            delay, rise = (v.constant for v in settings[:2])
            # LRM 2.4 §4.5.8: a positive explicit rise supplies omitted fall.
            fall = settings[2].constant if len(settings) == 3 else rise
            if expr.token.default_transition is not None:
                rise = expr.token.default_transition if rise == 0 else rise
                fall = expr.token.default_transition if fall == 0 else fall
            if delay < 0 or rise < 0 or fall < 0:
                raise CompileError("transition requires nonnegative delay and positive explicit edge times")
            if rise == 0 or fall == 0:
                raise CompileError("transition requires nonnegative delay and positive explicit edge times",
                                   code='unsupported_transition_zero_edges', token=expr.token,
                                   instance=self.instance.name)
            self.compilation.operators.append(Transition(value, delay, rise, fall, origin))
        elif expr.op == "slew":
            rise = settings[0].constant
            fall = settings[1].constant if len(settings) == 2 else -rise
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
                if (expr.op == 'voltage' or contains_operator(expr)
                        or expr.op == 'parameter' and expr.value in self.active_event_aliases
                        and self.expression_nodes(self.active_event_aliases[expr.value])):
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

    def numeric_observer_candidate(self):
        # This source check preserves existing physical-expression lowering.
        # The kernel proves isolation against the complete original bound IR.
        def physical(statements):
            for statement in statements:
                if isinstance(statement, (ContributionStatement, BoundStep)):
                    return True
                if isinstance(statement, SyntaxConditional) and (physical(statement.then_body) or physical(statement.else_body)):
                    return True
            return False
        return not physical(self.model.analog)

    def checked_event_context(self, event):
        for trigger in event.triggers:
            if trigger.kind == "initial_step":
                return False
            if trigger.kind == "timer":
                try:
                    start = lower(trigger.arguments[0], self.parameter, {}, self.model.source)
                except CompileError:
                    continue
                if isinstance(start, Affine) and not start.terms and start.constant == 0:
                    return False
        return True

    def compact_event_candidate(self):
        return getattr(self, "runtime_event_checks", False) and self.numeric_observer_candidate()

    def lower_event_value(self, expr, resolve, nodes, *args, **kwargs):
        observer = self.numeric_observer_candidate()
        if not observer and kwargs.get("decisions") is not None:
            # Execution uses causal dependency/domain certification. The
            # original-tree audit keeps its own decision callbacks instead.
            kwargs["decisions"] = self.event_select
            kwargs.pop("validate_decision", None)
        return self.lower_event(expr, resolve, nodes, *args,
                                event_values=observer, sampled_values=not observer, **kwargs)

    def validate_runtime_loop(self, statement):
        def fail(message):
            raise CompileError(message, token=statement.token, instance=self.instance.name,
                               code="unsupported_event_loop")
        if not self.numeric_observer_candidate():
            fail("runtime loops require an isolated numeric observer")
        if self.model.variables.get(statement.name) != "integer" or statement.name in self.array_elements:
            fail("runtime loop control must be a declared scalar integer")
        if not self.integer_type(statement.start) or not self.integer_type(statement.limit):
            fail("runtime loop bounds require typed integer values")
        expr = statement.update
        if (expr.op not in ("+", "-") or expr.args[0].op != "parameter" or
                expr.args[0].value != statement.name):
            fail("runtime loop update requires its control plus a constant signed step")
        step = lower(expr.args[1], self.parameter, {}, self.model.source)
        if not isinstance(step, Affine) or step.terms or not step.constant.is_integer():
            fail("runtime loop step must be an instance-constant integer")
        step = step.constant * (1 if expr.op == "+" else -1)
        if step == 0 or (step > 0) != (statement.relation in ("<", "<=")):
            fail("runtime loop step direction does not match its relation")
        def audit(items):
            for item in items:
                if isinstance(item, SyntaxAssignment) and item.name == statement.name:
                    fail("runtime loop body cannot write its control")
                if isinstance(item, Loop):
                    if item.name == statement.name:
                        fail("runtime loops cannot share an active control")
                    audit(item.body)
                elif isinstance(item, SyntaxConditional):
                    audit(item.then_body)
                    audit(item.else_body)
                elif not isinstance(item, (SyntaxAssignment, SyntaxDisplay)):
                    fail("runtime loop body requires event assignments, displays or conditionals")
        audit(statement.body)

    def body(self, statements):
        result = []
        for statement in statements:
            origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
            if isinstance(statement, Loop):
                self.validate_runtime_loop(statement)
                initialize = SyntaxAssignment(statement.name, statement.start, statement.token)
                update = SyntaxAssignment(statement.name, statement.update, statement.token)
                result.append(RuntimeLoop(self.body((initialize,)),
                    {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation],
                    StateRef(self.state_ids[statement.name]),
                    self.lower_event_value(statement.limit, self.symbol, self.node_ids, preserve_structure=True),
                    self.body(statement.body), self.body((update,)), origin))
            elif isinstance(statement, SyntaxDisplay):
                arguments = tuple(self.lower_event_value(arg, self.symbol, self.node_ids,
                    preserve_structure=True, decisions=self.expression_select,
                    validate_decision=self.validate_decision_expression, node_declarations=True,
                    indices=self.event_index_read)
                    for arg in statement.args)
                result.append(Display(statement.format, arguments, origin))
            elif isinstance(statement, SyntaxConditional):
                # The kernel evaluates predicates against the preceding
                # assignments, preserving procedural statement order.
                left = self.lower_event_value(statement.left, self.symbol, self.node_ids, preserve_structure=True, decisions=self.expression_select, node_declarations=True, indices=self.event_index_read)
                right = self.lower_event_value(statement.right, self.symbol, self.node_ids, preserve_structure=True, decisions=self.expression_select, node_declarations=True, indices=self.event_index_read)
                result.extend(self.event_conditional({"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation],
                                          left, right, self.body(statement.then_body), self.body(statement.else_body), origin))
            elif isinstance(statement, SyntaxAssignment) and statement.index is not None:
                # Dynamic array write: index and RHS at their sequential site,
                # single-path dispatch with exactly one selected-slot leaf.
                result.extend(self.event_array_write(statement, origin))
            else:
                if statement.name not in self.state_ids:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: assignment target must be an instance state")
                # Reset feedback checks need voltage dependencies even
                # when a coefficient cancels or underflows to zero.
                value = self.lower_event_value(statement.rhs, self.symbol, self.node_ids, preserve_structure=True,
                                         decisions=self.expression_select, validate_decision=self.validate_decision_expression, node_declarations=True,
                                         indices=self.event_index_read,
                                         integer_assignment_root=self.model.variables[statement.name] == "integer")
                if self.model.variables[statement.name] == "integer" and not self.integral(value):
                    raise CompileError("integer assignment requires integral state arithmetic")
                result.extend(self.event_assignment(self.state_ids[statement.name], value, origin,
                    compact_source=compact_source_assignment(self, statement, value, origin)))
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
        if isinstance(expression, EventMath):
            for index, arg in enumerate(expression.args):
                child = InstanceCompiler.split_selection(arg)
                if child is not None:
                    decision, yes, no = child
                    def arm(value):
                        args = list(expression.args)
                        args[index] = value
                        return replace(expression, args=tuple(args))
                    return decision, arm(yes), arm(no)
            return None
        fields = ("left", "right") if isinstance(expression, Binary) else ("base",) if isinstance(expression, Power) else ()
        for field in fields:
            child = InstanceCompiler.split_selection(getattr(expression, field))
            if child is not None:
                decision, yes, no = child
                return decision, replace(expression, **{field: yes}), replace(expression, **{field: no})
        return None

    def event_conditional(self, relation, left, right, yes, no, origin):
        if self.compact_event_candidate():
            return (Conditional(relation, left, right, yes, no, origin),)
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

    def event_assignment(self, state, value, origin, *, compact_source=False):
        if self.compact_event_candidate() or compact_source:
            return (Assignment(state, value),)
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
        if isinstance(expression, EventMath):
            return set().union(*(self.expression_nodes(arg) for arg in expression.args))
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

    def input_rational_candidate(self, value):
        # Binding declarations identify only a frontend candidate. The kernel
        # must still audit the whole original Program against actual driven nodes.
        if self.state_names or self.model.initial or self.model.events:
            return False
        pending = list(self.model.analog)
        while pending:
            statement = pending.pop()
            if isinstance(statement, BoundStep):
                return False
            for field in ('rhs', 'left', 'right', 'start', 'limit', 'update'):
                expression = getattr(statement, field, None)
                if expression is not None and contains_operator(expression):
                    return False
            for field in ('body', 'then_body', 'else_body'):
                pending.extend(getattr(statement, field, ()))
        return input_rational_tree(value, self.allowed_condition_nodes) is not None

    def request_input_rational(self, origin):
        self.compilation.source_rational_origins.append(origin)

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
            if self.input_rational_candidate(value):
                self.request_input_rational(origin)
            else:
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: selected value must remain piecewise-affine or a supported rational expression")

    def expression_select(self, expr, relation, left, right, then_value, else_value, *, register=True):
        origin = Origin(expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        result = Select(relation, left, right, then_value, else_value, origin)
        check_ir(result, origin)
        if (_predicate_degree(left) is None or _predicate_degree(right) is None or
                not self.selected_value_supported(result)):
            if self.input_rational_candidate(result):
                self.request_input_rational(origin)
            else:
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: decision predicates and every arm must be affine or input-selected piecewise-affine")
        if not (self.expression_nodes(left) | self.expression_nodes(right)).issubset(self.allowed_condition_nodes):
            raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: decision predicates must depend only on input/inout ports")
        if register:
            self.expression_decision_origins.add(origin)
        return result

    @staticmethod
    def contains_history_call(expr):
        pure_math = {"sin", "cos", "exp", "ln", "sqrt", "tanh"}
        return (expr.op in OPERATOR_NAMES-pure_math or
                any(InstanceCompiler.contains_history_call(arg) for arg in expr.args))

    def lower_local(self, expr, env, *, preserve_structure=False, conditional=False, positive_facts=()):
        resolve = self.local_symbol(env)
        def outer_decision(item):
            if item.op in OPERATOR_NAMES:
                return False
            return item.op in DECISION_NAMES or any(outer_decision(arg) for arg in item.args)
        decision = outer_decision(expr)
        if decision and contains_operator(expr):
            raise CompileError(f"{self.model.source}:{expr.token.line}: decision expressions do not support waveform operators in any operand or arm")
        def factory(item, relation, left, right, then_value, else_value):
            raw = Select(relation, left, right, then_value, else_value,
                         Origin(item.token.source or self.model.source, item.token.line, item.token.column,
                                self.instance.name, item.expansion))
            check_ir(raw, raw.origin)
            # Keep the existing denominator proof before the stateless input
            # fallback: another instance may add a waveform operator later.
            normalized = normalize_positive_quotient_comparison(relation, left, right, positive_facts)
            if normalized is not None:
                relation, left, right = normalized
            return self.expression_select(item, relation, left, right, then_value, else_value)
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
                if self.input_rational_candidate(value):
                    self.request_input_rational(origin)
                else:
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

    def execute_analog(self, statements, env, conditional=False, active=Affine(1., ()), domains=None, positive_facts=()):
        result = dict(env)
        domains = dict(self.integer_state_ranges if domains is None else domains)
        emitted = []
        for statement in statements:
            if isinstance(statement, BoundStep):
                if contains_operator(statement.rhs):
                    raise CompileError(f'{self.model.source}:{statement.token.line}: $bound_step requires an expression without new waveform call sites')
                value = self.lower_local(statement.rhs, result, preserve_structure=True, positive_facts=positive_facts)
                if isinstance(value, Affine) and not value.terms and value.constant < 0:
                    raise CompileError('$bound_step requires a nonnegative value')
                origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column,
                                self.instance.name, statement.token.expansion)
                self.compilation.step_bounds.append(StepBound(value, active, origin))
            elif isinstance(statement, ContributionStatement):
                emitted.append((statement, self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure, conditional=conditional, positive_facts=positive_facts)))
            elif isinstance(statement, SyntaxConditional):
                if contains_operator(statement.left) or contains_operator(statement.right):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates do not support waveform operators")
                origin = Origin(statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
                left = self.lower_local(statement.left, result, preserve_structure=True, positive_facts=positive_facts)
                right = self.lower_local(statement.right, result, preserve_structure=True, positive_facts=positive_facts)
                check_ir(left, origin)
                check_ir(right, origin)
                if not self.expression_nodes(left).issubset(self.allowed_condition_nodes) or not self.expression_nodes(right).issubset(self.allowed_condition_nodes):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates must depend only on input/inout ports")
                if _predicate_degree(left) is None or _predicate_degree(right) is None:
                    if self.input_rational_candidate(left) and self.input_rational_candidate(right):
                        self.request_input_rational(origin)
                    else:
                        raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates must be affine or input-selected piecewise-affine; nonlinear products and powers are unsupported")
                relation = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation]
                zero, one = Affine(0., ()), Affine(1., ())
                yes = Select('gt', active, zero, Select(relation, left, right, one, zero, origin), zero, origin)
                no = Select('gt', active, zero, Select(relation, left, right, zero, one, origin), zero, origin)
                yes_domains, no_domains = self.condition_domains(relation, left, right, domains)
                yes_facts, no_facts = condition_positive_facts(relation, left, right, positive_facts)
                then_env, then_emitted = self.execute_analog(statement.then_body, result, conditional=True, active=yes, domains=yes_domains, positive_facts=yes_facts)
                else_env, else_emitted = self.execute_analog(statement.else_body, result, conditional=True, active=no, domains=no_domains, positive_facts=no_facts)
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
                        # A branch-only temporary need not escape the merge.
                        # Any later read still fails in local_symbol unless a
                        # following assignment defines a value on every path.
                        result.pop(name, None)
                        continue
                    if then_env[name] is else_env[name]:
                        result[name] = then_env[name]
                        continue
                    result[name] = factor_integer_prefix(
                        relation, left, right, then_env[name], else_env[name], origin,
                        integer_target=self.model.variables.get(name) == "integer",
                        validate_integer=self.validate_integer_value)
                    check_ir(result[name], origin)
            else:
                if statement.name not in self.local_variables:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog assignment target must be a local variable")
                if conditional and self.contains_history_call(statement.rhs):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: history waveform call sites must be unconditional")
                value = self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure, conditional=conditional, positive_facts=positive_facts)
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
