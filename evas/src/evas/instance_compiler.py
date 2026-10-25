"""Compile one bound instance while sharing explicit program output tables.

Parameter/local/state environments belong to this instance. Global node indices,
operator/state IDs and output order belong to Compilation; no loop-captured state.
"""
from dataclasses import dataclass, field, fields, is_dataclass, replace
import math
from fractions import Fraction
from typing import TYPE_CHECKING

from .ir import (Affine, Term, Assignment, Conditional, Binary, RealBinary, RealBoundary, RealLocal, RealCall, UnsupportedSystemCall, BranchIdentity, Contribution, CrossTrigger, Event, TimerTrigger, HeldTimerTrigger, OrTrigger,
                 IntegerPrimitive, IntegerLiteral, IntegerState, ArrayRead, ArrayWrite, IntegerRound, CheckedInteger, CheckedIndex, Loop as RuntimeLoop, EventMath, Origin, Program, Power, Select, Forcing, State, StateRef, OperatorRef, Transition, AbsDelay, Slew, Idt, LaplaceNd, IdtMod, Sin, MathFunction, Ddt, StepBound, Display, FinalStepTrigger, InitialStepTrigger)
from .lowering import lower, scale, UnsupportedConstantPower, FiniteIntegerUnavailable, _SourceAuditMemo
from .limits import check_ir, MAX_IR_ITEMS
from .integer_table_composition import compose_integer_table
from . import held_power2
from .integer_invariants import SourceProofRequest
from .forcing_components import source_forcing_tree, audit_original_reads, residual_checks, split_source_quadratic
from .input_rational_scope import input_rational_tree
from . import readout_scope
from .compact_source_select import compact_source_assignment
from .integer_prefix import factor_integer_prefix
from .parameters import bind_parameters
from .elaboration import unroll_loops
from .array_elaboration import scalarize_arrays, ARRAY_BUDGET
from . import event_index_domains, integer_bits, finite_math
from .native_audit import NativeAudit
from .rational_predicates import condition_positive_facts, normalize_positive_quotient_comparison
from .initialization_aliases import bind_initial_voltage_aliases, bind_runtime_voltage_aliases, bind_event_body_aliases
from .syntax import (CompileError, Model, contains_operator, contains_decision,
                     Assignment as SyntaxAssignment, Conditional as SyntaxConditional, Display as SyntaxDisplay, Event as SyntaxEvent,
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
    native_audit: NativeAudit = field(default_factory=NativeAudit)
    integer_proof_owner: object = field(default_factory=SourceProofRequest)
    indices: dict[str, int] = field(init=False)
    source_rational_origins: list[Origin] = field(default_factory=list)
    source_rational_nodes: set[int] = field(default_factory=lambda: {0})
    # Deferred (origin, diagnostic) pairs; see readout_scope.check.
    readout_pending: list = field(default_factory=list)
    # Physical sampled sqrt/ln sites: (origin, voltage nodes of the argument).
    sampled_math_reads: list = field(default_factory=list)
    memoryless_registry: object = field(default=None, repr=False)
    settled_integer_reads: bool = False
    history_consumer_candidate: bool = False
    # References only: bind_hierarchy/parse_sources already own these objects.
    # No original-tree proof is visited or charged without a forcing marker.
    forcing_original_bindings: list[tuple[Model, dict[str, int], str]] = field(default_factory=list)
    pending_contributions: list = field(init=False, repr=False)
    contribution_emission_index: int = field(default=0, init=False, repr=False)
    contribution_emission_error: Exception | None = field(default=None, init=False, repr=False)
    procedure_builders: list = field(default_factory=list)
    real_bindings: list = field(default_factory=list)
    procedures: tuple = field(default=(), init=False)

    def __post_init__(self):
        self.indices = {name: i for i, name in enumerate(self.nodes)}
        self.native_audit.debit("contribution_queue_create")
        self.pending_contributions = []

    def emit_pending_contributions(self):
        if self.contribution_emission_error is not None:
            raise self.contribution_emission_error
        if not self.pending_contributions:
            return
        try:
            while self.contribution_emission_index < len(self.pending_contributions):
                # Pay the record/field reads and possible failure reference.
                self.native_audit.debit("contribution_queue_visit", 4)
                compiler, contributions = self.pending_contributions[self.contribution_emission_index]
                try:
                    compiler.emit_contributions(contributions)
                except CompileError as error:
                    error.diagnostic.setdefault("instance", compiler.instance.name)
                    raise
                self.contribution_emission_index += 1
            self.native_audit.debit("contribution_queue_release", 3 * len(self.pending_contributions))
            self.pending_contributions.clear()
            self.contribution_emission_index = 0
        except Exception as error:
            # A partially emitted compilation cannot resume or publish. Keep
            # its first failure and partial state, without replaying emitters.
            self.contribution_emission_error = error
            raise

    def program(self) -> Program:
        # Frontend has now compiled every instance's real states/operators.
        # Repeated Program reads never emit or bill these contributions again.
        self.emit_pending_contributions()
        if self.procedure_builders and not self.procedures:
            self.procedures = tuple(builder.emit() for builder in self.procedure_builders)
        self.native_audit.debit("program_copy",5+len(self.contributions)+len(self.states)+len(self.events)+len(self.operators)+len(self.step_bounds))
        self.native_audit.debit("emit_field",len(fields(Program)))
        result = Program(self.nodes, tuple(self.contributions), tuple(self.states), tuple(self.events), tuple(self.operators),
                         step_bounds=tuple(self.step_bounds), procedures=self.procedures,
                         real_bindings=tuple(self.real_bindings))
        check_ir(result, work=self.native_audit.ir_work, cache=self.native_audit.ir_cache)
        if any(isinstance(c.rhs, Forcing) for c in result.contributions):
            # Preserve R6's original, pre-scalarization component role audit.
            # It owns its existing source-proof phase; no reduced Program is
            # substituted for the original bound instance/node references.
            self.initial_math_work -= 3 * len(result.contributions)
            if self.initial_math_work < 0:
                raise CompileError('forcing output dependency budget exceeded', code='resource_budget')
            outputs = {n for c in result.contributions if isinstance(c.rhs, Forcing)
                       for n in (c.positive, c.negative)} - {0}
            numeric_reads = set()
            for model, node_ids, owner in self.forcing_original_bindings:
                try:
                    numeric_reads.update(audit_original_reads(self, model, node_ids, outputs))
                except CompileError as error:
                    error.diagnostic.setdefault('instance', owner)
                    raise
            self.initial_math_work -= len(numeric_reads)**2 + 8*len(numeric_reads)
            if self.initial_math_work < 0:
                raise CompileError('forcing numeric role budget exceeded', code='resource_budget')

            def emit_forcing_ir(cls, *args, **kwargs):
                # These added IR objects use the existing request audit too.
                self.native_audit.debit("emit_object")
                self.native_audit.debit("emit_field", len(fields(cls)))
                return cls(*args, **kwargs)

            footprint = emit_forcing_ir(Affine, 0., tuple(
                emit_forcing_ir(Term, n, 0.) for n in sorted(numeric_reads)))
            self.native_audit.debit("copy_container")
            self.native_audit.debit("copy_element", len(result.contributions))
            contributions = list(result.contributions)
            for index, contribution in enumerate(contributions):
                if isinstance(contribution.rhs, Forcing):
                    original = contribution.rhs
                    self.native_audit.debit("copy_container")
                    self.native_audit.debit("copy_element", len(original.checked) + 1)
                    checked = (*original.checked, footprint)
                    value = emit_forcing_ir(Forcing, original.value, original.origin, checked)
                    contributions[index] = emit_forcing_ir(
                        Contribution, contribution.branch, contribution.positive,
                        contribution.negative, value, contribution.origin)
                    break
            self.native_audit.debit("program_copy", 5 + len(contributions))
            result = emit_forcing_ir(Program, result.nodes, tuple(contributions),
                                    result.states, result.events, result.operators,
                                    step_bounds=result.step_bounds, procedures=result.procedures,
                                    real_bindings=result.real_bindings)
            check_ir(result, work=self.native_audit.ir_work, cache=self.native_audit.ir_cache)
        if self.history_consumer_candidate:
            from .history_consumer_scope import original_reads
            if not result.operators or any(not isinstance(op, Transition) for op in result.operators):
                raise CompileError("decision predicates must depend only on input/inout ports unless the complete ordinary history consumer program has only Transition histories")
            self.native_audit.debit("history_source_copy",len(result.contributions))
            contributions=list(result.contributions)
            for model,node_ids,owner in self.forcing_original_bindings:
                reads=original_reads(model,node_ids,self.native_audit)
                self.native_audit.debit("history_source_visit")
                reads.discard(0)
                if not reads:
                    continue
                index=None
                for i,c in enumerate(contributions):
                    self.native_audit.debit("history_source_visit")
                    if c.origin.instance==owner and c.positive not in reads and c.negative not in reads:
                        index=i
                        break
                if index is None:
                    raise CompileError("original history reads require an owning contribution")
                # Keep discarded source reads in the original Program. The
                # kernel follows these zero terms before simplifying values.
                def emit(cls,*args):
                    self.native_audit.debit("emit_object")
                    self.native_audit.debit("emit_field",len(fields(cls)))
                    return cls(*args)
                terms=[]
                self.native_audit.debit("history_source_copy")
                for n in range(len(result.nodes)):
                    self.native_audit.debit("history_source_visit")
                    if n in reads:
                        self.native_audit.debit("history_source_copy")
                        terms.append(emit(Term,n,0.))
                self.native_audit.debit("history_source_copy",len(terms))
                footprint=emit(Affine,0.,tuple(terms))
                contribution=contributions[index]
                rhs=emit(Binary,"add",contribution.rhs,footprint)
                self.native_audit.debit("emit_field",len(fields(Contribution)))
                contributions[index]=replace(contribution,rhs=rhs)
            self.native_audit.debit("program_copy",5+len(contributions))
            result=replace(result,contributions=tuple(contributions))
            check_ir(result,work=self.native_audit.ir_work,cache=self.native_audit.ir_cache)
        # A replacement Program must keep the SAME owner for expanded transport.
        object.__setattr__(result, "_native_audit", self.native_audit)
        # A physical sampled sqrt/ln argument must read actual driven inputs.
        # A node any contribution drives is an electrical unknown (or a
        # conflicting source), outside the sampled contract: keep the refusal.
        if self.sampled_math_reads:
            targets = {node for c in result.contributions for node in (c.positive, c.negative)} - {0}
            for origin, nodes in self.sampled_math_reads:
                if nodes & targets:
                    raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: nonconstant mathematical functions require a waveform contribution")
        pending = list(self.readout_pending)
        if self.source_rational_origins:
            trees = [input_rational_tree(c.rhs, self.source_rational_nodes) for c in result.contributions]
            if (result.states or result.events or result.operators or result.step_bounds
                    or any(tree is None for tree in trees)):
                # A stateful program may still own these decisions as unread
                # readout outputs; otherwise the original diagnostic stands.
                pending.extend((origin, "non-affine guards require a complete stateless input-only algebraic program")
                               for origin in self.source_rational_origins)
        if pending:
            readout_scope.check(result, pending, self.native_audit)
        return result


def state_reads(expression):
    """State indices read anywhere in an IR expression, every arm included."""
    found, seen, pending = set(), set(), [expression]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, StateRef):
            found.add(item.state)
        elif isinstance(item, ArrayRead):
            found.update(item.states)
        if isinstance(item, (tuple, list)):
            pending.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, f.name) for f in fields(item))
    return found


def _predicate_degree(expression, memo=None, local_facts=None, work=None):
    """Structural scope: node-free constant (0), affine/select (1), or unsupported.

    No cancellation removes a dependency. Input-selected constants count as
    input-dependent, so only a node-free scalar can multiply a predicate.
    """
    if memo is None:
        memo = {}
    key = id(expression)
    if work is not None:
        work("predicate_scope_visit", 1)
    if key in memo:
        return memo[key][1]
    if isinstance(expression, StateRef):
        result = 1
    elif isinstance(expression, (RealLocal, RealCall)):
        fact = local_facts.get(key) if local_facts is not None else None
        result = fact[1] if fact is not None and fact[0] is expression else 1
    elif isinstance(expression, RealBoundary):
        result = _predicate_degree(expression.value, memo, local_facts, work)
    elif isinstance(expression, RealBinary):
        # Source admission only. The runtime must evaluate these as rounded
        # program values, never differentiate this tree as an affine equation.
        left, right = _predicate_degree(expression.left, memo, local_facts, work), _predicate_degree(expression.right, memo, local_facts, work)
        if left is None or right is None:
            result = None
        elif expression.operation in ("add", "subtract"):
            result = max(left, right)
        elif expression.operation == "divide":
            result = left if right == 0 else None
        else:
            result = left + right if left + right <= 1 else None
    elif isinstance(expression, UnsupportedSystemCall):
        # The selected leaf has no return value: runtime must fail atomically.
        # No numerical degree/proof is inferred from a nominal random value.
        result = 0
    elif isinstance(expression, EventMath):
        result = 0 if all(_predicate_degree(arg, memo, local_facts, work) == 0 for arg in expression.args) else None
    elif isinstance(expression, Affine):
        result = int(bool(expression.terms))
    elif isinstance(expression, Binary):
        if expression.op == "divide":
            result = None
        else:
            left, right = _predicate_degree(expression.left, memo, local_facts, work), _predicate_degree(expression.right, memo, local_facts, work)
            if left is None or right is None:
                result = None
            else:
                degree = max(left, right) if expression.op == "add" else left + right
                result = degree if degree <= 1 else None
    elif isinstance(expression, Power):
        degree = _predicate_degree(expression.base, memo, local_facts, work)
        result = degree if degree == 0 or expression.exponent == 1 else None
    elif isinstance(expression, Select):
        degrees = [_predicate_degree(value, memo, local_facts, work) for value in
                   (expression.left, expression.right, expression.then_value, expression.else_value)]
        result = None if None in degrees else max(degrees)
    else:
        result = None
    memo[key] = (expression, result)
    return result


class InstanceCompiler:
    def program_real_closed(self, expression):
        return self.program_facts.query(expression)

    def program_real_constant(self, expression):
        # Declaration/initial seeds are often already bare floats (integer n=0)
        # or closed Affines. Querying a non-Affine scalar used to activate the
        # held-target aggregate audit and then refuse large legal timer decks.
        if isinstance(expression, (int, float)):
            return float(expression) if math.isfinite(expression) else None
        if isinstance(expression, Affine) and not expression.terms:
            return expression.constant if math.isfinite(expression.constant) else None
        fact = self.program_real_closed(expression)
        return fact.value if fact.finite else None

    def predicate_degree(self, expression):
        builder = getattr(self, "procedure_builder", None)
        facts = builder.degree_facts if builder is not None else None
        return _predicate_degree(expression, local_facts=facts,
                                 work=self.compilation.native_audit.ir_work)

    def scale_ir(self, expression, factor):
        return scale(expression, factor, work=self.compilation.native_audit.ir_work)

    def make_ir(self, cls, *args, **kwargs):
        # Debit before constructing the dataclass; native/event/target emission
        # all use the same explicit Compilation owner, including failed tries.
        owner = self.compilation.native_audit
        return owner.emit_ir(cls, args, kwargs, "emit")

    def __init__(self, instance: "Instance", model: Model, nets: dict[str, str], compilation: Compilation, *,
                 source_model: Model | None = None):
        self.instance = instance
        self.model = model
        self.event_body_source_model = source_model
        self.procedure_source_model = source_model or model
        self.compilation = compilation
        from .program_real_facts import ProgramRealFacts
        self.program_facts = ProgramRealFacts(compilation.native_audit.ir_work)
        self.cache: dict[str, float] = {}
        self.node_ids = {name: compilation.indices[net] for name, net in nets.items()}
        if "$abstime" in compilation.indices:
            self.node_ids["$abstime"] = compilation.indices["$abstime"]
        self.initials = {}
        self.expression_decision_origins = set()
        self.forcing_seen = False
        self.forcing_checks = {}
        self.forcing_ordinary_active = False
        self.allowed_condition_nodes = {0} | ({self.node_ids["$abstime"]} if "$abstime" in self.node_ids else set()) | {self.node_ids[port] for port, direction in model.directions.items()
                                             if direction in ("input", "inout")}
        self.compilation.source_rational_nodes.update(self.allowed_condition_nodes)
        self.compilation.forcing_original_bindings.append(
            (source_model or model, self.node_ids, instance.name))

    def compile(self):
        self.cache = bind_parameters(self.model, self.instance.parameters, self.instance.name)
        from .ordinary_held_state import plan as ordinary_held_state
        from .deferred_system_calls import seed_storage
        self.deferred_seed_names = seed_storage(self.model, self.compilation.native_audit)
        held_model = ordinary_held_state(self)
        if held_model is not None:
            # Keep original source identity for admit/scratch/prefix; execute
            # the rewritten held model. Clearing the source made those proofs
            # fall through onto rewritten roles.
            if self.event_body_source_model is None:
                self.event_body_source_model = self.model
            self.model = held_model
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
        if self.model.functions:
            self.model = scalarize_arrays(self.model, self.parameter,
                native_audit=self.compilation.native_audit)
        else:
            self.model = scalarize_arrays(self.model, self.parameter)
        from .procedural import ProcedureBuilder
        # Trigger lowering is the only place a process binding is not enough.
        self.event_trigger_expression = False
        self.procedure_builder = ProcedureBuilder(self) if self.model.procedure else None
        self.array_elements = self._declared_elements()
        self.array_dispatch_leaves = 0
        self.array_flow = {}
        self._array_flow_holder = []
        # A declaration does not become held state just because another variable
        # has an event writer. Walk writes (including conditional/loop bodies),
        # so event targets retain the VA declaration default of zero.
        floor_prefix_candidates = None
        def writes(statements, *, ordinary=False):
            nonlocal floor_prefix_candidates
            for statement in statements:
                if isinstance(statement, SyntaxAssignment):
                    # Reuse this existing mandatory writer traversal as a
                    # syntax-only dispatch hint. No hint container exists for
                    # old programs without a top-level integer Floor writer.
                    if (ordinary and statement.index is None and statement.rhs.op == "floor"
                            and self.model.variables.get(statement.name) == "integer"):
                        self.compilation.native_audit.debit("integer_prefix_candidate_hint", 4, statement)
                        if floor_prefix_candidates is None:
                            floor_prefix_candidates = []
                        floor_prefix_candidates.append(statement.name)
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
        self.compilation.native_audit.debit('deferred_seed_state_roles', 1+len(self.deferred_seed_names))
        persistent.update(self.deferred_seed_names)
        event_writers = set(self.deferred_seed_names)
        for event in self.model.events:
            persistent.update(writes(event.body))
            if any(trigger.kind in ("cross", "timer") for trigger in event.triggers):
                event_writers.update(writes(event.body))
        analog_writers = set(writes(self.model.analog, ordinary=True))
        all_writers = persistent | analog_writers
        immutable_names = set(self.model.variable_initializers) - all_writers - declaration_writers - set(self.model.arrays)
        self.local_variables = analog_writers - persistent
        if self.procedure_builder is not None:
            self.procedure_builder.declare(self.local_variables)
            self.binding_values = self.procedure_builder.values
        self.integer_event_prefix = None
        if floor_prefix_candidates is not None:
            from .ordinary_integer_event_prefix import qualify as integer_event_prefix
            plan = integer_event_prefix(self)
            if plan.names:
                self.integer_event_prefix = plan
                # Every internal slot read is dominated by its same-callback
                # original prefix. The hint above grants no qualification.
                self.local_variables.difference_update(plan.names)
        self.preserve_analog_structure = self.compilation.preserve_structure or bool(self.local_variables)
        read_query = None
        if self.model.functions:
            from .source_queries import SourceStructure
            owner = self.compilation.native_audit
            owner.debit('source_structure_instance_context', 3)
            contexts = getattr(self.compilation, 'source_structure_contexts', None)
            if contexts is None:
                owner.debit('source_structure_contexts_container')
                contexts = {}
                owner.debit('source_structure_contexts_retain')
                self.compilation.source_structure_contexts = contexts
            read_query = contexts.get(self.instance.name)
            if read_query is None:
                # A prior instance with time can short-circuit global time
                # discovery; this instance still owns an independent context.
                read_query = SourceStructure(owner)
                owner.debit('source_structure_context_record', 3)
                contexts[self.instance.name] = read_query
        def expression_reads(expr):
            if expr is None:
                return set()
            if read_query is not None:
                return read_query.reads(expr, self.array_elements)
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
        # A real event scratch may also be assigned in the ordinary body.
        # Its old ordinary value is irrelevant only when every event read is
        # dominated by a same-callback write. Retain the event state slot and
        # give ordinary evaluation a separate source-ordered alias environment.
        owner = self.compilation.native_audit
        owner.debit("copy_container")
        ordinary_scratch = set()
        source_model = self.event_body_source_model or self.initial_math_source_model
        for name in analog_writers:
            owner.debit("ordinary_scratch_candidate")
            if self.procedure_builder is not None and name in getattr(self, "ordinary_held_process_slots", ()):
                # The held-state proof retains this original scalar slot;
                # it is not the legacy same-evaluation integer alias route.
                ordinary_scratch.add(name)
                continue
            if (self.procedure_builder is not None and self.integer_event_prefix is not None
                    and name in self.integer_event_prefix.names):
                owner.debit("integer_prefix_native_ordinary_scope", 2)
                # The original prefix certificate owns this integer storage;
                # execution now writes it at the retained source statement.
                ordinary_scratch.add(name)
                continue
            if self.procedure_builder is not None and self.model.variables[name] == "real":
                ordinary_scratch.add(name)
                continue
            if name in persistent and self.model.variables[name] == "real" and name not in event_writers:
                from .initial_ordinary_alias import admit
                if admit(self, name, persistent, analog_writers, source_model):
                    owner.debit("copy_element")
                    ordinary_scratch.add(name)
                continue
            if name in persistent and self.model.variables[name] == "integer":
                from .ordinary_integer_current_alias import admit as admit_current_integer
                if admit_current_integer(self, name, source_model):
                    owner.debit("copy_element")
                    ordinary_scratch.add(name)
                continue
            if name not in persistent or self.model.variables[name] != "real" or name not in event_writers:
                continue
            owner.activate(self.model.initial[0].token if self.model.initial else None)
            owner.debit("ordinary_scratch_scalar_identity")
            if source_model.arrays or source_model.variables.get(name) != "real":
                raise CompileError("ordinary/event scratch requires an original scalar identity without arrays",
                                   code="unsupported_local_event", instance=self.instance.name)
            def scratch_reads(expr):
                if expr is None:
                    return False
                self.compilation.native_audit.extra(expr, "ordinary_scratch_visit")
                return ((expr.op == "parameter" and expr.value == name)
                        or any(scratch_reads(arg) for arg in expr.args))
            def scratch_loop_touches(body):
                for item in body:
                    owner.extra(item, "ordinary_scratch_loop_statement")
                    if isinstance(item, SyntaxAssignment) and item.name == name:
                        return True
                    for field in ("rhs", "left", "right", "index", "start", "limit", "update"):
                        if scratch_reads(getattr(item, field, None)):
                            return True
                    if isinstance(item, SyntaxDisplay):
                        for arg in item.args:
                            if scratch_reads(arg):
                                return True
                    for field in ("then_body", "else_body", "body"):
                        if scratch_loop_touches(getattr(item, field, ())):
                            return True
                return False
            def scratch_body(body, assigned=False, *, ordinary=False):
                for item in body:
                    self.compilation.native_audit.extra(item, "ordinary_scratch_statement")
                    for field in ("rhs", "left", "right", "index", "start", "limit", "update"):
                        if scratch_reads(getattr(item, field, None)) and not assigned:
                            raise CompileError("ordinary/event scratch is not assigned before use" if ordinary else "ordinary/event scratch requires a same-callback write before every read",
                                               code="unsupported_local_event", instance=self.instance.name)
                    if isinstance(item, SyntaxDisplay):
                        for arg in item.args:
                            if scratch_reads(arg) and not assigned:
                                raise CompileError("ordinary/event scratch display reads a prior evaluation",
                                                   code="unsupported_local_event", instance=self.instance.name)
                    if isinstance(item, SyntaxConditional):
                        yes_assigned = scratch_body(item.then_body, assigned, ordinary=ordinary)
                        no_assigned = scratch_body(item.else_body, assigned, ordinary=ordinary)
                        assigned = yes_assigned and no_assigned
                    elif isinstance(item, Loop):
                        # No loop-carried alias proof is introduced here.
                        if scratch_loop_touches(item.body):
                            raise CompileError("ordinary/event scratch loop requires a separate carry proof",
                                               code="unsupported_local_event", instance=self.instance.name)
                    elif isinstance(item, SyntaxAssignment) and item.name == name:
                        assigned = True
                return assigned
            owner.debit("copy_container")
            owner.debit("copy_element", len(source_model.events))
            source_events = list(source_model.events)
            owner.debit("copy_container")
            owner.debit("copy_element", len(source_model.analog))
            original_pending = list(source_model.analog)
            owner.debit("copy_container")
            ordinary_writers = []
            while original_pending:
                item = original_pending.pop()
                self.compilation.native_audit.extra(item, "ordinary_scratch_source_order")
                if isinstance(item, SyntaxEvent):
                    owner.debit("copy_element")
                    source_events.append(item)
                elif isinstance(item, SyntaxAssignment) and item.name == name:
                    owner.debit("copy_element")
                    ordinary_writers.append(item)
                else:
                    for field in ("then_body", "else_body", "body"):
                        children = getattr(item, field, ())
                        owner.debit("copy_element", len(children))
                        original_pending.extend(children)
            for item in ordinary_writers:
                for event in source_events:
                    self.compilation.native_audit.extra(item, "ordinary_scratch_source_compare")
                    a, b = item.token, event.token
                    if a.source != b.source or (a.line, a.column) <= (b.line, b.column):
                        raise CompileError("ordinary/event scratch must follow callback declarations",
                                           code="unsupported_local_event", instance=self.instance.name)
            scratch_body(source_model.initial)
            scratch_body(source_model.analog, ordinary=True)
            for event in source_events:
                for trigger in event.triggers:
                    if any(scratch_reads(arg) for arg in trigger.arguments):
                        raise CompileError("ordinary/event scratch cannot drive an event trigger",
                                           code="unsupported_local_event", instance=self.instance.name)
                scratch_body(event.body)
            owner.debit("copy_element")
            ordinary_scratch.add(name)
        if ordinary_scratch:
            owner.debit("copy_container")
            owner.debit("copy_element", len(self.local_variables) + len(ordinary_scratch))
            self.ordinary_alias_variables = self.local_variables | ordinary_scratch
        else:
            self.ordinary_alias_variables = self.local_variables
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
        if self.procedure_builder is not None:
            self.procedure_builder.audit_local_availability()
            if (self.procedure_builder.bindings or any(
                    self.model.variables[name] == "real" for name in analog_writers & persistent)):
                self.procedure_builder.audit_original_source(self.procedure_source_model)
        self.constant_local_aliases = self.bind_constant_local_aliases(writes)
        self.initial_voltage_aliases = bind_initial_voltage_aliases(self, writes)
        self.runtime_voltage_aliases = bind_runtime_voltage_aliases(self, writes)
        self.event_body_aliases = bind_event_body_aliases(self, writes)
        self.ordinary_event_prefixes = None
        if self.event_body_prefix_demand:
            from .ordinary_event_prefix import bind as bind_ordinary_event_prefixes
            self.ordinary_event_prefixes = bind_ordinary_event_prefixes(self, writes)
        self.active_event_aliases = {}
        seeds = self.bind_declaration_initializers(event_writers, immutable_names)
        # No-writer declaration values belong to the variable namespace. They
        # never enter model.parameters/cache or manufacture held event state.
        self.immutable_declarations = {name: value for name, value in seeds.items() if name in immutable_names}
        self.declaration_initials = {name: value for name, value in seeds.items() if name not in immutable_names}
        self.initialize_states()
        from .event_real_ranges import floor_use_sites
        self.event_floor_range_facts = floor_use_sites(
            [(event.body if self.integer_event_prefix is None else self.integer_event_prefix.body(event, self.compilation.native_audit)) for event in self.model.events],
            [name for name in self.state_names if self.model.variables[name] == 'real'],
            self.parameter, integer_type=self.integer_type)
        self.infer_integer_state_ranges()
        self.analyze_event_index_domains()
        from .event_specialization import audit_event_body, specialize_event_body
        self.array_audit_dispatch_leaves = 0
        native_allowances = {}
        for event_index, event in enumerate(self.model.events):
            self.active_event_aliases = self.aliases_at(event.token, body=True)
            self.runtime_event_checks = self.checked_event_context(event)
            view = self.compilation.native_audit.event_view((self.instance.name, event_index))
            native_allowances[id(event)] = audit_event_body(self, (event.body if self.integer_event_prefix is None else self.integer_event_prefix.body(event, self.compilation.native_audit)), view)
        for event in self.model.events:
            self.active_event_aliases = self.aliases_at(event.token)
            self.runtime_event_checks = self.checked_event_context(event)
            self.native_integer_charge = native_allowances[id(event)]
            self.trigger_argument_captures = None
            self.event_trigger_expression = True
            try:
                triggers = tuple(self.trigger(leaf) for leaf in event.triggers)
            finally:
                self.event_trigger_expression = False
            event_trigger = triggers[0] if len(triggers) == 1 else self.make_ir(OrTrigger, triggers)
            origin = self.make_ir(Origin, event.token.source or self.model.source, event.token.line, event.token.column, self.instance.name, event.token.expansion)
            def retained(body):
                if self.event_reachable_statements is None:
                    return body
                return tuple(replace(item, then_body=retained(item.then_body), else_body=retained(item.else_body))
                             if isinstance(item, SyntaxConditional) else item
                             for item in body if id(item) in self.event_reachable_statements)
            if self.integer_event_prefix is None or self.procedure_builder is not None:
                # Native procedures execute the qualified prefix once at its
                # actual ordinary source position. The Plan still supplies
                # all-source/storage qualification; do not copy it into gates.
                execution = specialize_event_body(retained(event.body), self.cache,
                                                  work=native_allowances[id(event)])
            else:
                prefix = self.integer_event_prefix.event_prefixes.get(event.token, ())
                self.compilation.native_audit.debit("integer_prefix_execution_copy", 1 + len(prefix) + len(event.body), event)
                execution = specialize_event_body((*prefix, *retained(event.body)), self.cache,
                                                  work=native_allowances[id(event)])
            self.active_event_aliases = self.aliases_at(event.token, body=True)
            self.event_sampled_states = set()
            event_index = len(self.compilation.events)
            self.compilation.events.append(self.make_ir(Event, event_trigger, self.body(execution), origin))
            if self.procedure_builder is not None:
                self.procedure_builder.event(event, event_index, self.trigger_argument_captures)
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
        self.held_power2_alias_candidates = held_power2.target_aliases(self, statements)
        if (held_power2.reserve(self.compilation.native_audit, "held_power2_alias_ready_setup", 2)
                and self.held_power2_alias_candidates
                and held_power2.reserve(self.compilation.native_audit, "held_power2_alias_ready_container", 2)):
            self.held_power2_ready = {}
        else:
            self.held_power2_ready = None
        try:
            self.forcing_ordinary_active = True
            _, contributions = self.execute_analog(statements, {})
        finally:
            self.forcing_ordinary_active = False
            self.ordinary_integer_bounds = None
        # Retain references, not AST/IR copies, until the complete operator
        # table can select the contribution consumer independently of order.
        self.compilation.native_audit.debit("contribution_queue_retain", 3)
        self.compilation.pending_contributions.append((self, contributions))

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
                value = lower(statement.rhs, self.typed_resolve(resolve,
                    program_real=self.model.variables[statement.name] == 'real'), {}, self.model.source)
                if not isinstance(value, Affine) or value.terms:
                    fact = self.program_real_closed(value)
                    if not fact.closed or not fact.finite:
                        continue
                elif not math.isfinite(value.constant):
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
        result = {name: value for name, value in aliases.items()
                  if name in self.model.local_alias_scopes.get(token, ())}
        prefixes = getattr(self, 'ordinary_event_prefixes', None)
        if body and prefixes:
            result.update(prefixes.get(token, {}))
        return result

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
                real = self.model.variables[name] == "real"
                value = lower(expr, self.typed_resolve(self.parameter, program_real=real), {}, self.model.source)
                fact = self.program_real_closed(value)
                if not fact.closed or not fact.finite:
                    raise CompileError("declaration initialization requires a finite scalar constant")
                if self.model.variables[name] == "integer":
                    self.validate_integer_value(value, expr.token, initial=True)
                elif real:
                    origin = self.make_ir(Origin, expr.token.source or self.model.source,
                                          expr.token.line, expr.token.column, self.instance.name,
                                          expr.token.expansion)
                    value = self.make_ir(RealBoundary, value, "store", origin)
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
        env = {name: self.make_ir(Affine, 0., ()) for name in self.state_names}
        # All explicit seeds have been validated before initial_step can
        # overwrite them. This environment belongs to only this instance.
        env.update(self.declaration_initials)
        def resolve(values, aliases):
            lookup = self.typed_resolve(lambda name: values[name] if name in values else
                                      self.local_read(name, aliases.get(name)) if self.procedure_builder is not None and name in self.procedure_builder.bindings else
                                      aliases[name] if name in aliases else self.parameter(name),
                                      program_real=True)
            lookup.initial_preview = self.procedure_builder is not None
            if lookup.initial_preview:
                from .initial_power import lower_power
                def preview_power(expr, base, exponent):
                    result = lower_power(self, expr, base, exponent, preview=True)
                    return self.finite_power(expr, base, exponent) if result is None else result
                lookup.finite_power = preview_power
            return lookup
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
            elif isinstance(value, RealBoundary):
                number = constant_snapshot(value.value)
            elif isinstance(value, (Binary, RealBinary)):
                a, b = constant_snapshot(value.left), constant_snapshot(value.right)
                operation = value.operation if isinstance(value, RealBinary) else value.op
                number = {'add': lambda: a+b, 'subtract': lambda: a-b,
                          'multiply': lambda: a*b, 'divide': lambda: a/b}[operation]()
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
                    if self.procedure_builder is None and (has_output(statement.then_body) or has_output(statement.else_body)):
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
                    if self.procedure_builder is not None:
                        continue  # The unique runtime initial gate owns this output.
                    arguments = []
                    for argument in statement.args:
                        value = lower(argument, resolve(values, aliases), self.node_ids, self.model.source,
                                      preserve_structure=True, decisions=self.initial_select,
                                      validate_decision=self.validate_initial_operand, node_declarations=True)
                        arguments.append(self.make_ir(Affine, constant_snapshot(value), ()))
                    origin = self.make_ir(Origin, statement.token.source or self.model.source, statement.token.line,
                                    statement.token.column, self.instance.name, statement.token.expansion)
                    if active:
                        snapshots.append(self.make_ir(Display, statement.format, tuple(arguments), origin))
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
                        if self.procedure_builder is None:
                            self.state_names = ()
                            self.state_ids = {}
                            for name in closed:
                                values.pop(name, None)
                        else:
                            origin = self.make_ir(Origin, statement.token.source or self.model.source,
                                statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
                            values[statement.name] = self.make_ir(RealBoundary, closed[statement.name], 'store', origin)
                        continue
                    self.validate_initial_operand(statement.rhs, value)
                    def constant_arms(item):
                        if isinstance(item, Affine):
                            return not item.terms
                        if isinstance(item, RealBoundary):
                            return constant_arms(item.value)
                        if isinstance(item, (RealBinary, RealLocal)):
                            return self.program_facts.query(item, 'leaf_values') is not None
                        if isinstance(item, Select):
                            return constant_arms(item.then_value) and constant_arms(item.else_value)
                        if isinstance(item, Binary):
                            return item.op in ("add", "multiply") and constant_arms(item.left) and constant_arms(item.right)
                        return isinstance(item, Power) and constant_arms(item.base)
                    if self.model.variables[statement.name] == "integer":
                        if not constant_arms(value):
                            raise CompileError("integer initial_step values require constant-valued arms selected by input predicates")
                        self.validate_integer_value(value, statement.token, initial=True)
                    if self.model.variables[statement.name] == "real":
                        origin = self.make_ir(Origin, statement.token.source or self.model.source,
                            statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
                        value = self.make_ir(RealBoundary, value, "store", origin)
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
        if snapshots and self.procedure_builder is None:
            self.compilation.events.append(self.make_ir(Event, self.make_ir(InitialStepTrigger, ), tuple(snapshots), snapshots[0].origin))
        for name, value in env.items():
            if isinstance(value, Affine) and not value.terms:
                value = value.constant
                if self.model.variables[name] == "integer" and not -2147483648 <= value <= 2147483647:
                    raise CompileError("integer initialization must be an exact signed 32-bit integer")
            self.initials[name] = value
        self.compilation.states.extend(self.make_ir(State, self.instance.name, name, self.model.variables[name], self.initials[name]) for name in self.state_names)

    def validate_initial_operand(self, expr, value):
        # Check all lowered function obligations, including dead branches.
        if self.predicate_degree(value) is None:
            # A finite union of source-selected constant leaves is an initial
            # input observation, not a general nonlinear voltage function.
            # Preserve the guard and rounded tree; this certificate does not
            # turn the whole expression into a closed scalar.
            if self.program_facts.query(value, 'selected_interval') is None:
                raise CompileError("initial comparison operands must be structurally affine or finite input-selected constants")
        if not self.expression_nodes(value).issubset(self.allowed_condition_nodes):
            raise CompileError("initial comparison depends on a non-input voltage")

    def initial_select(self, expr, relation, left, right, then_value, else_value):
        self.validate_initial_operand(expr, left)
        self.validate_initial_operand(expr, right)
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        result = self.make_ir(Select, relation, left, right, then_value, else_value, origin)
        self.checked_ir(result, origin)
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

    def local_read(self, name, source=None):
        read = self.make_ir(RealLocal, self.procedure_builder.bindings[name])
        # The caller supplies an existing source-position alias/prefix proof,
        # never a binding's later writer or a persistent state's seed. Closed
        # qualification still inspects every source dependency of that proof.
        if source is not None:
            self.program_facts.record_read(read, (source,))
        return read

    def symbol(self, name):
        builder = getattr(self, "procedure_builder", None)
        if builder is not None and name in builder.bindings:
            # A later event body reads this source-position binding. A cross
            # or timer argument does not: without an alias or prefix already
            # proved for this token, the original integrator-local guard stays
            # rejected instead of becoming an unbound real_local.
            source = self.active_event_aliases.get(name)
            if source is None and self.event_trigger_expression:
                raise CompileError(f"{self.model.source}: event expressions cannot read ordinary analog local variable {name!r}; use direct input or persistent state expressions",
                                   code='unsupported_local_event', instance=self.instance.name)
            return self.local_read(name, source)
        if name in self.active_event_aliases:
            return self.active_event_aliases[name]
        if name in self.local_variables:
            raise CompileError(f"{self.model.source}: event expressions cannot read ordinary analog local variable {name!r}; use direct input or persistent state expressions",
                               code='unsupported_local_event', instance=self.instance.name)
        return self.make_ir(StateRef, self.state_ids[name]) if name in self.state_ids else self.parameter(name)

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
        program_real = kwargs.pop("program_real", False)
        execute_calls = kwargs.pop("execute_calls", False)
        typed = self.typed_resolve(resolve, allow_integer_assignment_root=assignment_root,
                                  program_real=program_real, execute_calls=execute_calls)
        typed.sampled_values = sampled_values
        audit_memo = kwargs.get('memo')
        if type(audit_memo) is _SourceAuditMemo:
            # An original-tree audit cache is owned by one source use-site;
            # binding, numeric roles and node declarations are fixed explicitly.
            self.compilation.native_audit.debit('source_audit_lower_binding_flags', 7, expr)
            audit_memo.bind(resolve, nodes, (assignment_root, event_values, sampled_values,
                static_integer_audit, program_real, kwargs.get('node_declarations', False)))
            self.compilation.native_audit.debit('source_audit_lower_binding_attach', 1, expr)
            typed._source_audit_binding = audit_memo.binding_token
        if (event_values or sampled_values) and hasattr(self, 'native_integer_charge'):
            native_charge = self.native_integer_charge
            typed.native_integer = lambda item: self.native_event_integer(item, resolve, native_charge)
        if event_values or sampled_values:
            typed.finite_floor = lambda item, argument: self.finite_floor(item, argument, native=True)
            typed.source_floor = lambda item, lower_operand: self.source_floor(item, lower_operand, resolve)
        if event_values:
            if getattr(self, "runtime_event_checks", False) and not static_integer_audit:
                typed.validate_integer_operation = self.checked_event_integer
            def math_value(item, args):
                origin = self.make_ir(Origin, item.token.source or self.model.source, item.token.line,
                    item.token.column, self.instance.name, item.expansion)
                return self.make_ir(EventMath, item.op, args, origin)
            typed.event_math = math_value
            kwargs["decisions"] = self.event_select
            kwargs.pop("validate_decision", None)
        elif sampled_values and getattr(self, "sampled_math_slot", False):
            # Physical sampled sqrt/ln, only in an event assignment value; the
            # kernel certifies each domain over the complete actual argument
            # enclosure at the event. The argument must apply to a sample: a
            # voltage read now, or a state this event already assigned from
            # one. Anything else returns None and keeps the original refusal.
            def sampled_math(item, args):
                nodes = frozenset(self.expression_nodes(args[0]) - {0})
                if not nodes and not (state_reads(args[0]) & self.event_sampled_states):
                    return None
                origin = self.make_ir(Origin, item.token.source or self.model.source, item.token.line,
                    item.token.column, self.instance.name, item.expansion)
                self.compilation.sampled_math_reads.append((origin, nodes))
                return self.make_ir(EventMath, item.op, args, origin)
            typed.sampled_math = sampled_math
        try:
            table = self.integer_expression_table(expr, resolve, nodes, args, kwargs)
            if table is not None:
                return table
            value = lower(expr, typed, nodes, self.model.source, *args, **kwargs)
            if assignment_root and not self.integral(value) and expr.op == "voltage":
                if not isinstance(value, Affine) or not self.expression_nodes(value).issubset(self.allowed_condition_nodes):
                    raise CompileError("integer conversion requires a direct physical input probe", token=expr.token, instance=self.instance.name)
                from .integer_invariants import ProofBudgetExceeded
                work = self.compilation.integer_proof_owner
                try:
                    work.activate()
                    work.charge()
                except ProofBudgetExceeded as error:
                    raise CompileError(str(error), code="resource_budget", token=expr.token, instance=self.instance.name) from error
                origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column, self.instance.name, expr.expansion)
                return self.make_ir(IntegerRound, value, origin)
            return value
        except CompileError as error:
            if (error.diagnostic['code'] in ('unsupported_local_event', 'unsupported_event_state_dependency')
                    and 'location' not in error.diagnostic):
                raise CompileError(str(error), code=error.diagnostic['code'], token=expr.token,
                                   instance=self.instance.name) from error
            raise

    def event_select(self, expr, relation, left, right, yes, no):
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        result = self.make_ir(Select, relation, left, right, yes, no, origin)
        self.checked_ir(result, origin)
        return result

    def integral(self, expression):
        self.compilation.native_audit.extra(expression, "integral_visit")
        # Do not introduce an implicit real-to-integer rounding rule.
        if isinstance(expression, Affine):
            return not expression.terms and expression.constant.is_integer()
        if isinstance(expression, (RealBinary, RealBoundary, RealLocal)):
            return self.program_facts.query(expression, 'integer_range') is not None
        if isinstance(expression, (IntegerRound, CheckedIndex, CheckedInteger, IntegerPrimitive)):
            return True
        if isinstance(expression, ArrayRead):
            return all(self.compilation.states[state].kind == "integer" for state in expression.states)
        if isinstance(expression, StateRef):
            return self.compilation.states[expression.state].kind == "integer"
        if isinstance(expression, EventMath):
            return expression.function == "floor" or expression.function in ("abs", "min", "max") and all(self.integral(arg) for arg in expression.args)
        if isinstance(expression, Select):
            return self.integral(expression.then_value) and self.integral(expression.else_value)
        if isinstance(expression, Power):
            return self.integral(expression.base) and expression.exponent >= 0
        return isinstance(expression, Binary) and expression.op in ("add", "multiply") and self.integral(expression.left) and self.integral(expression.right)

    def integral_bounds(self, expression):
        self.compilation.native_audit.extra(expression, "bound_visit")
        if isinstance(expression, IntegerRound):
            return -2147483648, 2147483647
        if isinstance(expression, IntegerPrimitive):
            if expression.function == 'remainder':
                divisor = expression.args[1]
                # Only successful checked values participate in this enclosure.
                # A dynamic signed32 divisor can have magnitude at most 2**31.
                width = abs(divisor.value) if isinstance(divisor, IntegerLiteral) else 2147483648
                return -width + 1, width - 1
            return -2147483648, 2147483647
        if isinstance(expression, ArrayRead):
            bounds = [self.integral_bounds(self.make_ir(StateRef, state)) for state in expression.states]
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
        if isinstance(expression, (RealBinary, RealBoundary, RealLocal)):
            bounds = self.program_facts.query(expression, 'integer_range')
            if bounds is not None:
                return bounds
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
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        return self.make_ir(CheckedInteger, value, origin)

    def typed_resolve(self, resolve, *, allow_integer_assignment_root=False, program_real=False, execute_calls=False):
        def lookup(name):
            return resolve(name)
        lookup.native_work = self.compilation.native_audit.ir_work
        lookup.program_real = program_real
        from .deferred_system_calls import lower_unsupported
        lookup.unsupported_system_call = lambda *args, **kwargs: lower_unsupported(self, *args, **kwargs)
        lookup.defer_numeric_domain = getattr(resolve, "defer_numeric_domain", False)
        lookup.initial_preview = getattr(resolve, "initial_preview", False)
        if (execute_calls or getattr(resolve, "real_call", None) is not None) and self.procedure_builder is not None:
            from .real_calls import lower_call
            lookup.real_call = lambda *args, **kwargs: lower_call(self, *args, **kwargs)
        lookup.instance_name = self.instance.name
        lookup.is_program_real_expression = lambda expr: not self.integer_type(expr)
        lookup.program_real_constant = self.program_real_constant
        lookup.program_real_closed = self.program_real_closed
        if hasattr(lookup, 'real_call') and not lookup.initial_preview:
            lookup.function_math_value = self.function_math_value
        def function_integer_assignment(expr, value):
            if not self.integer_type(expr.args[0]) or not self.integral(value):
                return False
            low, high = self.integral_bounds(value)
            return -2147483648 <= low <= high <= 2147483647
        lookup.function_integer_assignment = function_integer_assignment
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
        if getattr(self, '_actual_initial_power', False):
            from .initial_power import lower_power
            result = lower_power(self, expr, base, exponent, preview=False)
            if result is not None:
                return result
        if not self.integer_type(expr.args[1]) or not self.integral(exponent):
            return None
        bounds = self.integral_bounds(exponent)
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        try:
            result = finite_math.power(base, exponent, bounds, origin)
        except ValueError as error:
            raise CompileError(str(error), token=expr.token,
                               instance=self.instance.name) from error
        if result is not None:
            self.expression_decision_origins.add(origin)
        return result

    def source_floor(self, expr, lower_operand, resolve):
        from .source_floor_event import source_floor
        return source_floor(self, expr, lower_operand, resolve)

    def finite_floor(self, expr, argument, *, native=False):
        from .finite_floor import floor_table
        if (self.predicate_degree(argument) is None
                or not self.expression_nodes(argument).issubset(self.allowed_condition_nodes)):
            raise CompileError('floor requires a source-clamped piecewise-affine input expression',
                               code='unsupported_floor', token=expr.token, instance=self.instance.name)
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        fact = getattr(self, 'event_floor_range_facts', {}).get(id(expr))
        state_bounds = ({self.state_ids[name]: bounds for name, bounds in fact[1].items()}
                        if fact is not None and fact[0] is expr else None)
        try:
            result = floor_table(argument, origin, state_bounds=state_bounds,
                                 constant_value=self.program_real_constant(argument), factory=self.make_ir,
                                 local_facts=self.program_facts.reads, work=self.compilation.native_audit.ir_work)
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
            result = self.make_ir(EventMath, 'floor', (argument,), origin)
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
        # Source Expr is immutable and the scalarized instance's type tables
        # do not change during lowering. Reuse an actual earlier proof instead
        # of recursively retyping the same arithmetic for every consumer.
        audit = self.compilation.native_audit
        cache = getattr(self, "_integer_type_cache", None)
        if cache is None:
            audit.debit("typing_cache_create")
            self._integer_type_cache = cache = {}
        audit.debit("typing_cache_lookup")
        cached = cache.get(id(expr))
        if cached is not None:
            assert cached[0] is expr
            return cached[1]
        value = integer_bits.integer_type(expr, self.model.variables,
                                         self.model.parameter_types, self.model.genvars,
                                         visit=lambda item: audit.extra(item, "typing_visit"))
        audit.debit("typing_cache_insert", 2)
        cache[id(expr)] = (expr, value)
        return value

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
        writers = [writer for event in self.model.events for writer in writes((event.body if self.integer_event_prefix is None else self.integer_event_prefix.body(event, self.compilation.native_audit)))]
        for name in self.state_names:
            if self.model.variables[name] != "integer":
                continue
            state = self.state_ids[name]
            initial = self.initials[name]
            initial = self.make_ir(Affine, initial, ()) if isinstance(initial, (int, float)) else initial
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
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line,
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
                    if error.diagnostic.get('code') == 'resource_budget':
                        raise
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
                        return self.make_ir(Affine, float(low), ())
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
                return self.make_ir(Select, "lt", state, self.make_ir(Affine, float(middle), ()),
                              split(first, middle - 1), split(middle, last), origin)
            if low == high:
                value = leaf(low)
                return self.make_ir(Select, "lt", state, self.make_ir(Affine, low + 0.5, ()), value, value, origin)
            return split(low, high)
        value = table(0, {})
        self.checked_ir(value, origin)
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
            if expr.op in (">>", "&"):
                raise FiniteIntegerUnavailable("bounded integer bitwise operation exceeds finite-domain budget (256)",
                    code="unsupported_integer_bitwise", token=expr.token, instance=self.instance.name)
            fail("bounded integer bitwise operation exceeds finite-domain budget (256)")
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line,
                        expr.token.column, self.instance.name, expr.expansion)
        if len(values) == 2:
            from .finite_floor import map_integer_leaves
            mapped = map_integer_leaves(values[0], expr.op, values[1])
            if mapped is not None:
                self.checked_ir(mapped, origin)
                self.expression_decision_origins.add(origin)
                return mapped
        def tree(operand, args):
            if operand == len(values):
                return self.make_ir(Affine, float(integer_bits.evaluate(expr.op, *args)), ())
            low, high = bounds[operand]
            if low == high:
                value = tree(operand + 1, args + [low])
                if isinstance(values[operand], Affine) and not values[operand].terms:
                    return value
                # Range proof does not erase an original source read, even
                # when every successful value is the same integer. The kernel
                # retains predicate reads for equivalent Select arms.
                return self.make_ir(Select, "lt", values[operand], self.make_ir(Affine, low + 0.5, ()), value, value, origin)
            def split(first, last):
                if first == last:
                    return tree(operand + 1, args + [first])
                middle = (first + last + 1) // 2
                return self.make_ir(Select, "lt", values[operand], self.make_ir(Affine, float(middle), ()),
                              split(first, middle - 1), split(middle, last), origin)
            return split(low, high)
        value = tree(0, [])
        self.checked_ir(value, origin)
        if any(low != high for low, high in bounds):
            self.expression_decision_origins.add(origin)
        return value

    def checked_ir(self, value, origin=None):
        return check_ir(value, origin, work=self.compilation.native_audit.ir_work, cache=self.compilation.native_audit.ir_cache)

    def native_event_integer(self, expr, resolve, charge):
        # This is called only after the original route classified a finite
        # representation failure. One bottom-up visit types each source node;
        # no domain enumeration, child retyping, or folded arithmetic inputs.
        def build(item):
            charge(item)
            if item.op == 'number':
                if not integer_bits.integer_type(item, self.model.variables, self.model.parameter_types, self.model.genvars, visit=lambda leaf: charge.extra(leaf, "typing_visit")):
                    return None
                number = item.value
            elif item.op == 'parameter':
                if not integer_bits.integer_type(item, self.model.variables, self.model.parameter_types, self.model.genvars, visit=lambda leaf: charge.extra(leaf, "typing_visit")):
                    return None
                value = resolve(item.value)
                if isinstance(value, StateRef):
                    return self.make_ir(IntegerState, value.state)
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
            elif item.op in ('+', '-', '%', '>>', '&'):
                charge.extra(item, "emit_tuple", 1 + len(item.args))
                values = tuple(build(arg) for arg in item.args)
                if any(value is None for value in values):
                    return None
                if item.op == '%' and isinstance(values[1], IntegerLiteral) and values[1].value == 0:
                    raise CompileError('integer division/modulo requires a nonzero divisor', token=item.token)
                if item.op == '>>' and not isinstance(values[1], IntegerLiteral):
                    return None
                origin = self.make_ir(Origin, item.token.source or self.model.source, item.token.line,
                                item.token.column, self.instance.name, item.expansion)
                if all(isinstance(value, IntegerLiteral) for value in values):
                    a, b = (value.value for value in values)
                    charge(item)
                    if item.op == '+':
                        number = a+b
                    elif item.op == '-':
                        number = a-b
                    elif item.op in ('>>', '&'):
                        number = integer_bits.evaluate(item.op, a, b)
                    else:
                        if a == -2147483648 and b == -1:
                            raise CompileError('integer quotient may exceed signed 32-bit range', token=item.token)
                        magnitude = abs(a)//abs(b)
                        number = a - (-magnitude if (a<0)!=(b<0) else magnitude)*b
                else:
                    return self.make_ir(IntegerPrimitive, {'+': 'add', '-': 'subtract', '%': 'remainder', '>>': 'shift_right', '&': 'bit_and'}[item.op], values, origin)
            else:
                return None
            if not math.isfinite(number) or int(number) != number or not -2147483648 <= number <= 2147483647:
                raise CompileError('integer intermediate may exceed signed 32-bit range', token=item.token)
            return self.make_ir(IntegerLiteral, int(number))
        value = build(expr)
        if isinstance(value, IntegerPrimitive):
            self.checked_ir(value, getattr(value, "origin", None))
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
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        if isinstance(numerator, Select):
            owner = self.compilation.native_audit
            # Prepay dispatch and callback bindings before creating them. An inactive old route may skip an
            # optional probe before insufficient headroom incurs any new work.
            if owner.active or owner.used + 8 <= MAX_IR_ITEMS:
                owner.debit('integer_compose_dispatch', 8, expr)
                mapped = compose_integer_table(numerator, expr.op, divisor,
                    owner=owner, source=expr, make=self.make_ir)
                if mapped is not None:
                    self.checked_ir(mapped, origin)
                    self.expression_decision_origins.add(origin)
                    return mapped
        def tree(start, end):
            if start == end:
                return self.make_ir(Affine, float(start), ())
            middle = (start+end+1)//2
            boundary = middle*width if middle > 0 else (middle-1)*width+1
            return self.make_ir(Select, "lt", numerator, self.make_ir(Affine, float(boundary), ()),
                          tree(start, middle-1), tree(middle, end), origin)
        self.expression_decision_origins.add(origin)
        value = tree(first, last)
        if divisor < 0:
            value = self.scale_ir(value, -1.)
        if expr.op == "%":
            value = self.make_ir(Binary, "add", numerator, self.scale_ir(value, -float(divisor)))
        self.checked_ir(value, origin)
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
        bodies = [(event.body if self.integer_event_prefix is None else self.integer_event_prefix.body(event, self.compilation.native_audit)) for event in self.model.events]
        def parameters(name):
            return self.parameter(name)
        from .integer_invariants import proof_parameters
        from .event_real_ranges import integer_floor_bounds
        parameters.real_floor_bounds = lambda expr: integer_floor_bounds(self.event_floor_range_facts, expr)
        proof_work = self.compilation.integer_proof_owner.instance()
        baseline_parameters = proof_parameters(parameters, proof_work)
        def location_of(token):
            return f"{token.source or self.model.source}:{token.line}:{token.column}"
        from .integer_invariants import ProofBudgetExceeded, OptionalProofUnavailable

        try:
            event_index_domains._charge(baseline_parameters, 6)
            def collect(entry, lookup, partitioned=None):
                # Every source use and every intermediate state is visited in the
                # same complete flow. Nothing is published until it has finished.
                event_index_domains._charge(lookup, 1 + len(entry))
                lifetime = dict(entry)
                event_index_domains._charge(lookup, 4)
                def retain_intermediates(env):
                    event_index_domains._charge(lookup, 3 * len(env))
                    for name, value in env.items():
                        lifetime[name] = event_index_domains.hull(lifetime[name], value)
                event_index_domains._charge(lookup)
                reached = set() if partitioned is not None else None
                found, keepalive = event_index_domains.use_site_facts(
                    bodies, entry, arrays=self.array_elements, parameters=lookup,
                    location_of=location_of, partitioned=partitioned,
                    reachable=reached, on_state=retain_intermediates)
                return found, keepalive, lifetime, reached

            # The mandatory baseline never assumes a seed is a runtime range.
            # Its conservative facts may be upgraded before final admission.
            event_index_domains._charge(baseline_parameters, 1 + len(states))
            domains = {name: event_index_domains.TOP for name in states}
            facts, holder, lifetime_domains, reachable = collect(domains, baseline_parameters)
            try:
                optional_work = proof_work.optional_view()
                optional_work.charge()  # additional lookup closure
                inference_parameters = proof_parameters(parameters, optional_work)
                candidate, _widened = event_index_domains.entry_domains(
                    bodies, initial, arrays=self.array_elements,
                    parameters=inference_parameters, states=states)
                partitions = event_index_domains.boolean_partitions(
                    bodies, initial, arrays=self.array_elements,
                    parameters=inference_parameters, states=states)
                upgraded = collect(candidate, inference_parameters, partitions)
            except OptionalProofUnavailable:
                # No unit was started after the cap. Partial use/reachability
                # facts are discarded; spent work and the baseline remain.
                pass
            else:
                domains = candidate
                facts, holder, lifetime_domains, reachable = upgraded
        except ValueError as error:
            raise CompileError(f'{self.model.source}: {error}', code='resource_budget',
                               instance=self.instance.name)
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
            origin = self.make_ir(Origin, token.source or self.model.source, token.line, token.column,
                            self.instance.name, token.expansion)
            return self.make_ir(CheckedIndex, value, low, high, origin)
        return value

    def _array_read_tree(self, array, elements, index_value, token, *, register=True):
        """Complete balanced Select over every declared slot (no fallback arm)."""
        origin = self.make_ir(Origin, token.source or self.model.source, token.line, token.column,
                        self.instance.name, token.expansion)
        if self.compact_event_candidate():
            return self.make_ir(ArrayRead, tuple(self.state_ids[f'{array}[{k}]'] for k in elements),
                             index_value, elements[0], elements[-1], origin)
        def tree(items):
            if len(items) == 1:
                return self.make_ir(StateRef, self.state_ids[f'{array}[{items[0]}]'])
            middle = len(items) // 2
            boundary = items[middle - 1] + 0.5
            return self.make_ir(Select, "lt", index_value, self.make_ir(Affine, boundary, ()),
                          tree(items[:middle]), tree(items[middle:]), origin)
        result = tree(elements)
        if len(elements) == 1 and isinstance(index_value, CheckedIndex):
            result = self.make_ir(Select, "lt", index_value, self.make_ir(Affine, elements[0]+0.5, ()), result, result, origin)
        self.checked_ir(result, origin)
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
        if kind == "real":
            value = self.make_ir(RealBoundary, value, "store", origin)
        if self.compact_event_candidate():
            self.array_dispatch_leaves += len(elements)
            if self.array_dispatch_leaves > ARRAY_BUDGET:
                raise CompileError('dynamic array dispatch budget (4096 leaves) exceeded',
                                   code='resource_budget', token=statement.token,
                                   instance=self.instance.name)
            return (self.make_ir(ArrayWrite, tuple(self.state_ids[f'{array}[{k}]'] for k in elements),
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
            return (self.make_ir(Conditional, "lt", index_value, self.make_ir(Affine, boundary, ()),
                                tuple(dispatch(items[:middle])), tuple(dispatch(items[middle:])), origin),)
        result = dispatch(elements)
        if len(elements) == 1 and isinstance(index_value, CheckedIndex):
            result = (self.make_ir(Conditional, "lt", index_value, self.make_ir(Affine, elements[0]+0.5, ()), result, result, origin),)
        return result

    def held_integer_source_charge(self, root, resolve):
        # This is entered only from a known finite-representation failure in
        # a Transition input. One real aggregate owner covers source audit,
        # delegated typing, emission, fallback and subsequent wire copies.
        from .native_audit import Charge
        charge = Charge(self.compilation.native_audit, None)
        pending, found = [root], False
        allowed = {"number", "parameter", "+", "-", "*", ">>", "&", "unary+", "unary-",
                   "<", "<=", ">", ">=", "==", "!=", "&&", "||", "unary!", "ternary"}
        while pending:
            item = pending.pop()
            charge.extra(item, "target_ast")
            if item.op in (">>", "&") and not found:
                self.compilation.native_audit.activate(item)
                found = True
            if item.op not in allowed:
                raise CompileError("typed held Transition target must be a pure integer-state projection/Select",
                                   code="unsupported_held_integer_target", token=item.token)
            if item.op == "parameter":
                name = str(item.value)
                value = resolve(name)
                # Parameter binding already checked the original dependency tree,
                # overrides and finiteness. Match lower()'s numeric-constant IR
                # representation without admitting numeric state/local aliases.
                if (name in self.model.parameters and type(value) in (int, float)
                        and math.isfinite(value)):
                    value = self.make_ir(Affine, float(value), ())
                if isinstance(value, StateRef):
                    state = self.compilation.states[value.state]
                    if state.kind != "integer" or state.instance != self.instance.name:
                        raise CompileError("typed held Transition target requires same-owner integer state",
                                           code="unsupported_held_integer_target", token=item.token)
                elif not isinstance(value, Affine) or value.terms or not math.isfinite(value.constant):
                    raise CompileError("typed held Transition target aliases must be finite constants",
                                       code="unsupported_held_integer_target", token=item.token)
            pending.extend(item.args)
        return charge if found else None

    def memoryless_operator(self, spec):
        from .memoryless_operators import Registry
        owner = self.compilation.native_audit
        owner.debit("memoryless_registry_dispatch", item=spec)
        owner.debit("memoryless_occurrence_metadata", 1+len(spec.origin.expansion), spec)
        if any(kind == "function_call" for kind, _ in spec.origin.expansion):
            owner.activate(spec)
        if self.compilation.memoryless_registry is None:
            owner.debit("memoryless_registry_create", 4, spec)
            self.compilation.memoryless_registry = Registry(owner)
        return self.compilation.memoryless_registry.register(spec, self.compilation.operators)

    def function_math_value(self, expr, value):
        """Consume an already lowered executable call without rebuilding it."""
        from dataclasses import is_dataclass
        owner = self.compilation.native_audit
        owner.debit('function_math_call_scan_container', 1, expr)
        pending = [value]
        while pending:
            item = pending.pop()
            owner.debit('function_math_call_scan', 1, expr)
            if isinstance(item, RealCall):
                origin = self.make_ir(Origin, expr.token.source or self.model.source,
                    expr.token.line, expr.token.column, self.instance.name, expr.expansion)
                index = self.memoryless_operator(self.make_ir(MathFunction, expr.op, value, origin))
                return self.make_ir(RealBoundary, self.make_ir(OperatorRef, index), 'sample', origin)
            if isinstance(item, tuple):
                owner.debit('function_math_call_scan_tuple', len(item), expr)
                pending.extend(item)
            elif is_dataclass(item) and not isinstance(item, Origin):
                descriptor = type(item).__dataclass_fields__
                owner.debit('function_math_call_scan_fields', 2*len(descriptor), expr)
                pending.extend(getattr(item, field.name) for field in descriptor.values())
        return None

    def waveform(self, expr, resolve):
        from .elaboration import MEMORYLESS_MATH
        owner = self.compilation.native_audit
        owner.debit("function_math_input_metadata", 1+len(expr.expansion), expr)
        helper_math = (expr.op in MEMORYLESS_MATH and
                       any(kind == "function_call" for kind, _ in expr.expansion))
        # The callback closes over the caller's lookup; a real function body
        # still owns rounded source arithmetic at every mathematical operand.
        resolve = self.typed_resolve(resolve, program_real=
            getattr(resolve, "program_real", False) or helper_math)
        resolve.memoryless_decisions = self.procedure_builder is not None
        target_charge = None
        target_checked = False
        target_source = expr.args[0]
        if expr.op == "transition" and self.forcing_ordinary_active:
            owner = self.compilation.native_audit
            if held_power2.reserve(owner, "held_power2_target_dispatch", 8, expr):
                alias = (self.held_power2_ready.get(str(target_source.value))
                         if target_source.op == "parameter" and self.held_power2_ready is not None else None)
                if alias is not None:
                    target_source = alias
                plan = held_power2.source_plan(self, target_source)
                if alias is not None and plan is None:
                    raise CompileError("held target alias source binding changed", token=target_source.token)
                if plan is not None and held_power2.compatible_program(self, target_source):
                    owner.activate(target_source)
                    owner.debit("held_power2_target_binding", 8, target_source)
                    from .native_audit import Charge
                    target_charge = Charge(owner, None)
                    target_checked = True
                    resolve.integer_arithmetic = lambda item, a, b: held_power2.arithmetic(self, plan, item, a, b)
        if expr.op == "transition":
            def native_target(item):
                nonlocal target_charge, target_checked
                if not target_checked:
                    target_charge = self.held_integer_source_charge(expr.args[0], resolve)
                    target_checked = True
                return (self.native_event_integer(item, resolve, target_charge)
                        if target_charge is not None else None)
            resolve.native_integer = native_target
        if expr.op == "laplace_np" and len(expr.args) != 3:
            raise CompileError(f"{self.model.source}:{expr.token.line}:{expr.token.column}: laplace_np epsilon is unsupported; omit the tolerance argument")
        input_nodes = self.node_ids
        def nested_fixed(nested):
            if nested.op != expr.op:
                raise CompileError(f"{expr.op} nesting is limited to fixed {expr.op} stages")
            return self.waveform(nested, resolve)
        def target_select(item, relation, left, right, yes, no):
            if target_charge is None:
                return self.expression_select(item, relation, left, right, yes, no)
            origin = self.make_ir(Origin, item.token.source or self.model.source,
                item.token.line, item.token.column, self.instance.name, item.expansion)
            value = self.make_ir(Select, relation, left, right, yes, no, origin)
            self.checked_ir(value, origin)
            return value
        def target_decision(item, value):
            if target_charge is None:
                self.validate_decision_expression(item, value)
            else:
                self.checked_ir(value, getattr(value, "origin", None))
        value = lower(target_source, resolve, input_nodes, self.model.source,
                  (lambda nested: self.waveform(nested, resolve)) if expr.op in ("sin", "cos", "exp", "ln", "sqrt", "tanh", "idt", "laplace_nd", "laplace_np", "ddt") else nested_fixed if expr.op in ("absdelay", "slew") else None,
                      preserve_structure=True, decisions=target_select,
                      validate_decision=target_decision, node_declarations=True)
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
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column, self.instance.name, expr.expansion)
        index = len(self.compilation.operators)
        if expr.op == "idt":
            if len(expr.args) == 3:
                # An assert set only at event instants needs its own lowering (#230).
                from . import idt_pulse_reset
                pulse = idt_pulse_reset.plan(self, expr, resolve)
                if pulse is not None:
                    return idt_pulse_reset.emit(self, pulse, expr, value, settings[0].constant, origin)
            reset = lower(expr.args[2], resolve, {}, self.model.source, preserve_structure=True) if len(expr.args) == 3 else None
            self.compilation.operators.append(self.make_ir(Idt, value, settings[0].constant, origin, reset))
        elif expr.op == "ddt":
            self.compilation.operators.append(self.make_ir(Ddt, value, origin))
        elif expr.op in ("laplace_nd", "laplace_np"):
            self.compilation.operators.append(self.make_ir(LaplaceNd, value, numerator, denominator, origin))
        elif expr.op == "idtmod":
            ic, modulus = (v.constant for v in settings[:2])
            offset = settings[2].constant if len(settings) == 3 else 0.0
            if modulus <= 0:
                raise CompileError("idtmod requires positive explicit modulus")
            self.compilation.operators.append(self.make_ir(IdtMod, value, ic, modulus, offset, origin))
        elif expr.op == "sin":
            index = self.memoryless_operator(self.make_ir(Sin, value, origin))
        elif expr.op in ("cos", "exp", "ln", "sqrt", "tanh"):
            index = self.memoryless_operator(self.make_ir(MathFunction, expr.op, value, origin))
        elif expr.op == "absdelay":
            delay = settings[0].constant
            if delay < 0:
                raise CompileError("absdelay requires nonnegative delay; zero is an EVAS extension")
            self.compilation.operators.append(self.make_ir(AbsDelay, value, delay, origin))
        elif expr.op == "transition":
            builder = self.procedure_builder
            state_sources = builder.state_scope_facts if builder is not None else None
            generation = builder.scope_generation if builder is not None else 0
            def continuous_value(item):
                return self.program_facts.query(item, "continuous", state_sources=state_sources,
                                                generation=generation)
            def dc_target_candidate(item):
                self.compilation.native_audit.debit("transition_scope_nodes", 1 + len(self.model.directions))
                allowed_nodes = frozenset({0} | {self.node_ids[port] for port, direction in self.model.directions.items()
                                                 if direction in ("input", "inout")})
                return self.program_facts.query(item, "dc", state_sources=state_sources,
                                                generation=generation, allowed_nodes=allowed_nodes)
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
            self.compilation.operators.append(self.make_ir(Transition, value, delay, rise, fall, origin))
        elif expr.op == "slew":
            rise = settings[0].constant
            fall = settings[1].constant if len(settings) == 2 else -rise
            if rise <= 0 or fall >= 0:
                raise CompileError("slew requires explicit rise > 0 and fall < 0")
            self.compilation.operators.append(self.make_ir(Slew, value, rise, fall, origin))
        else:
            raise CompileError(f"unsupported waveform operator {expr.op!r}")
        return self.make_ir(OperatorRef, index)

    def trigger(self, leaf):
        if leaf.kind == "initial_step":
            if self.model.children:
                raise CompileError("initial display events require a passive monitor without child instances", token=leaf.token)
            return self.make_ir(InitialStepTrigger, )
        if leaf.kind == "final_step":
            return self.make_ir(FinalStepTrigger, )
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
        def constant_value(value):
            if isinstance(value, Affine) and not value.terms:
                return value.constant
            fact = self.program_real_closed(value)
            return fact.value if fact.closed and fact.finite else None

        def setting(arg):
            value = self.lower_event(arg, self.event_parameter, {}, program_real=True)
            number = constant_value(value)
            if number is None:
                raise CompileError(f"{leaf.kind} settings must be instance constants")
            return value, number

        def retain(arguments):
            for arg, value in arguments:
                if isinstance(value, Affine) and not value.terms:
                    continue
                if self.procedure_builder is None:
                    raise CompileError('nonliteral fixed trigger arguments require a procedure capture', token=arg.token)
                if self.trigger_argument_captures is None:
                    self.compilation.native_audit.debit('trigger_argument_capture_create', 3, arg)
                    self.trigger_argument_captures = []
                self.compilation.native_audit.debit('trigger_argument_capture_append', 1, arg)
                self.trigger_argument_captures.append(self.procedure_builder.argument(value, arg.token))

        if leaf.kind == "cross":
            settings = [0.0, 1e-12, 1e-9]
            retained = []
            for index, arg in enumerate(leaf.arguments[1:]):
                value, settings[index] = setting(arg)
                retained.append((arg, value))
            direction, time_tol, expr_tol = settings
            if direction not in (-1, 0, 1) or time_tol <= 0 or expr_tol <= 0:
                raise CompileError("cross requires direction -1/0/1 and positive tolerances")
            result = self.make_ir(CrossTrigger, self.lower_event(leaf.arguments[0], self.symbol, self.node_ids, lambda expr: self.waveform(expr, self.symbol), preserve_structure=True, node_declarations=True),
                                   int(direction), time_tol, expr_tol)
            retain(retained)
        else:
            # Lower optional source arguments into the existing explicit IR.
            # 1 ps is EVAS policy, not a prescribed LRM or Spectre default.
            arguments = leaf.arguments + (None,) * (4-len(leaf.arguments))
            start_arg, period_arg, tolerance_arg, enable_arg = arguments
            tolerance_value, time_tol = (None, 1e-12) if tolerance_arg is None else setting(tolerance_arg)
            if time_tol < 0:
                raise CompileError("timer requires nonnegative start and time_tol")
            values = [self.lower_event(arg, self.symbol, {}, preserve_structure=True, program_real=True) if arg is not None else self.make_ir(Affine, 0., ())
                      for arg in (start_arg, period_arg, enable_arg)]
            if enable_arg is None:
                values[2] = self.make_ir(Affine, 1., ())
            constants = [constant_value(value) for value in values]
            if all(value is not None for value in constants):
                start, period, enabled = constants
                if start < 0:
                    raise CompileError("timer requires nonnegative start and time_tol")
                result = self.make_ir(TimerTrigger, start, period, time_tol, enabled != 0)
                retain([(arg, value) for arg, value in
                        ((start_arg, values[0]), (period_arg, values[1]),
                         (tolerance_arg, tolerance_value), (enable_arg, values[2])) if arg is not None])
            else:
                if time_tol == 0:
                    raise CompileError("zero time_tol requires fixed timer parameters")
                result = self.make_ir(HeldTimerTrigger, values[0], values[1], time_tol, values[2])
                if tolerance_arg is not None:
                    retain(((tolerance_arg, tolerance_value),))
        return result

    def numeric_observer_candidate(self, *, visit=None):
        # This source check preserves existing physical-expression lowering.
        # The kernel proves isolation against the complete original bound IR.
        def physical(statements):
            for statement in statements:
                if visit is not None:
                    visit(statement)
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
                                event_values=observer, sampled_values=not observer,
                                program_real=True, execute_calls=True, **kwargs)

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
            origin = self.make_ir(Origin, statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
            if isinstance(statement, Loop):
                self.validate_runtime_loop(statement)
                initialize = SyntaxAssignment(statement.name, statement.start, statement.token)
                update = SyntaxAssignment(statement.name, statement.update, statement.token)
                result.append(self.make_ir(RuntimeLoop, self.body((initialize,)),
                    {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation],
                    self.make_ir(StateRef, self.state_ids[statement.name]),
                    self.lower_event_value(statement.limit, self.symbol, self.node_ids, preserve_structure=True),
                    self.body(statement.body), self.body((update,)), origin))
            elif isinstance(statement, SyntaxDisplay):
                arguments = tuple(self.lower_event_value(arg, self.symbol, self.node_ids,
                    preserve_structure=True, decisions=self.expression_select,
                    validate_decision=self.validate_decision_expression, node_declarations=True,
                    indices=self.event_index_read)
                    for arg in statement.args)
                result.append(self.make_ir(Display, statement.format, arguments, origin))
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
                self.sampled_math_slot = True
                try:
                    value = self.closed_initial_math.get(statement.name)
                    if value is None:
                        value = self.lower_event_value(statement.rhs, self.symbol, self.node_ids, preserve_structure=True,
                                             decisions=self.expression_select, validate_decision=self.validate_decision_expression, node_declarations=True,
                                             indices=self.event_index_read,
                                             integer_assignment_root=self.model.variables[statement.name] == "integer")
                finally:
                    self.sampled_math_slot = False
                if self.expression_nodes(value) - {0} or state_reads(value) & self.event_sampled_states:
                    self.event_sampled_states.add(self.state_ids[statement.name])
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
        # IR33's retained procedure executor resolves Select predicates lazily
        # in both ordinary If and Event.body If. Do not expand its source arms
        # again after Parser kept each one once. The legacy route is unchanged.
        if self.procedure_builder is not None or self.compact_event_candidate():
            return (self.make_ir(Conditional, relation, left, right, yes, no, origin),)
        for field, expression in (("left", left), ("right", right)):
            choice = self.split_selection(expression)
            if choice is not None:
                decision, a, b = choice
                def continuation(value):
                    return self.event_conditional(relation, value if field == "left" else left,
                        value if field == "right" else right, yes, no, origin)
                return (self.make_ir(Conditional, decision.relation, decision.left, decision.right,
                    continuation(a), continuation(b), decision.origin),)
        return (self.make_ir(Conditional, relation, left, right, yes, no, origin),)

    def event_assignment(self, state, value, origin, *, compact_source=False):
        if self.compilation.states[state].kind == "real":
            value = self.make_ir(RealBoundary, value, "store", origin)
        if self.procedure_builder is not None or self.compact_event_candidate() or compact_source:
            # IR33 evaluates nested Select lazily at the assignment's source
            # position and applies the original integer conversion/range
            # check. Keep source predicates once instead of duplicating the
            # body for every combination of input-selected constants.
            return (self.make_ir(Assignment, state, value),)
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
                return (self.make_ir(Assignment, state, expression),)
            decision, yes, no = choice
            return (self.make_ir(Conditional, decision.relation, decision.left, decision.right,
                                expand(yes), expand(no), decision.origin),)
        return expand(value)

    def expression_nodes(self, expression):
        if isinstance(expression, UnsupportedSystemCall):
            return set().union(*(self.expression_nodes(argument) for argument in expression.args))
        if isinstance(expression, RealCall):
            return set(getattr(self, "real_call_nodes", {}).get(id(expression), ()))
        if isinstance(expression, EventMath):
            return set().union(*(self.expression_nodes(arg) for arg in expression.args))
        if isinstance(expression, Affine):
            return {term.node for term in expression.terms}
        if isinstance(expression, (Binary, RealBinary)):
            return self.expression_nodes(expression.left) | self.expression_nodes(expression.right)
        if isinstance(expression, RealBoundary):
            return self.expression_nodes(expression.value)
        if isinstance(expression, RealLocal):
            builder = self.procedure_builder
            return set(builder.binding_nodes.get(expression.binding, ())) if builder is not None else set()
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
            if self.procedure_builder is not None and name in self.state_ids:
                return self.make_ir(StateRef, self.state_ids[name])
            if name in self.ordinary_alias_variables:
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
        builder = self.procedure_builder
        return input_rational_tree(value, self.allowed_condition_nodes,
                                   local_facts=builder.scope_facts if builder is not None else None,
                                   work=self.compilation.native_audit.ir_work) is not None

    def request_input_rational(self, origin):
        self.compilation.source_rational_origins.append(origin)

    def selected_value_supported(self, value):
        if isinstance(value, (RealBinary, RealBoundary, RealLocal, RealCall, UnsupportedSystemCall)):
            # Rounded program expressions own a different numerical consumer.
            # Keep every source operand and defer proof/refusal to that owner.
            return True
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
                return (self.predicate_degree(item.left) is not None and self.predicate_degree(item.right) is not None
                        and rational_tree(item.then_value) and rational_tree(item.else_value))
            return isinstance(item, (Binary, Power)) and all(rational_tree(c) for c in children(item))
        def value_degree(item):
            if isinstance(item, (RealBinary, RealLocal)):
                # As for these nodes at the outer value boundary above, this
                # is source admission, not an affine proof for the real consumer.
                return 0
            if isinstance(item, RealBoundary):
                return value_degree(item.value)
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
                if self.predicate_degree(item.left) is None or self.predicate_degree(item.right) is None:
                    return None
                a, b = value_degree(item.then_value), value_degree(item.else_value)
                return max(a,b) if a is not None and b is not None else None
            return self.predicate_degree(item)
        return value_degree(value) is not None or has_divide(value) and rational_tree(value)

    def source_forcing_candidate(self, value):
        if self.forcing_ordinary_active and source_forcing_tree(value, self.allowed_condition_nodes, self):
            self.compilation.initial_math_work -= 1
            if self.compilation.initial_math_work < 0:
                raise CompileError('forcing checked expression budget exceeded', code='resource_budget')
            self.forcing_checks[id(value)] = value
            self.forcing_seen = True
            return True
        return False

    def validate_decision_expression(self, expr, value):
        origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column,
                        self.instance.name, expr.expansion)
        self.checked_ir(value, origin)
        if not self.selected_value_supported(value):
            if self.input_rational_candidate(value):
                self.request_input_rational(origin)
            elif self.source_forcing_candidate(value):
                pass
            elif not self.readout_candidate(value, origin, "selected value must remain piecewise-affine or a supported rational expression"):
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: selected value must remain piecewise-affine or a supported rational expression")

    def readout_candidate(self, value, origin, message):
        # Defer only a structural candidate; Compilation.program() requires the
        # complete Program to keep this decision in unread grounded outputs.
        if not readout_scope.readout_tree(value):
            return False
        self.compilation.readout_pending.append((origin, message))
        return True

    def expression_select(self, expr, relation, left, right, then_value, else_value, *, register=True, raw=None):
        owner = self.compilation.native_audit
        owner.debit("decision_reuse_dispatch")
        if raw is None:
            origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column,
                            self.instance.name, expr.expansion)
            result = self.make_ir(Select, relation, left, right, then_value, else_value, origin)
        else:
            # Prepay the exact-role/identity metadata checks before reading the
            # proposed object. This is not a cached semantic or range verdict.
            owner.debit("decision_reuse_metadata", 16, expr)
            if (not isinstance(raw, Select) or raw.relation != relation or
                    raw.left is not left or raw.right is not right or
                    raw.then_value is not then_value or raw.else_value is not else_value or
                    not isinstance(raw.origin, Origin) or
                    raw.origin.source != (expr.token.source or self.model.source) or
                    raw.origin.line != expr.token.line or raw.origin.column != expr.token.column or
                    raw.origin.instance != self.instance.name or raw.origin.expansion is not expr.expansion):
                raise CompileError("decision reuse requires the original decision and source role", token=expr.token)
            origin, result = raw.origin, raw
        # Always call the original checker. Only its same-owner, strongly held
        # transitive-immutable identity cache can avoid a second structural walk.
        self.checked_ir(result, origin)
        predicate_affine = self.predicate_degree(left) is not None and self.predicate_degree(right) is not None
        if (not predicate_affine or not self.selected_value_supported(result)):
            if self.input_rational_candidate(result):
                self.request_input_rational(origin)
            elif self.source_forcing_candidate(result):
                pass
            elif not self.readout_candidate(result, origin, "decision predicates and every arm must be affine or input-selected piecewise-affine"):
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: decision predicates and every arm must be affine or input-selected piecewise-affine")
        predicate_nodes = self.expression_nodes(left) | self.expression_nodes(right)
        if not predicate_nodes.issubset(self.allowed_condition_nodes):
            if not self.history_condition_candidate(predicate_affine,origin,predicate_nodes):
                raise CompileError(f"{origin.source}:{origin.line}:{origin.column}: decision predicates must depend only on input/inout ports")
        if register:
            self.expression_decision_origins.add(origin)
        return result

    def history_condition_candidate(self,predicate_affine,origin,predicate_nodes):
        # This is source dispatch only. It grants no execution permission:
        # original-source and whole-Program audits remain mandatory.
        self.compilation.native_audit.activate(origin)
        self.compilation.native_audit.debit("history_candidate_visit",2+len(predicate_nodes),origin)
        if (not predicate_affine or
                not getattr(self.compilation, "has_waveform_operators", False) or
                any(node < 0 or node >= len(self.compilation.nodes) for node in predicate_nodes)):
            return False
        self.compilation.history_consumer_candidate=True
        return True

    @staticmethod
    def contains_history_call(expr):
        pure_math = {"sin", "cos", "exp", "ln", "sqrt", "tanh"}
        return (expr.op in OPERATOR_NAMES-pure_math or
                any(InstanceCompiler.contains_history_call(arg) for arg in expr.args))

    def lower_local(self, expr, env, *, preserve_structure=False, conditional=False, positive_facts=(), program_real=False, execute_calls=False, source_floor_prefix=False):
        resolve = self.local_symbol(env)
        resolve.program_real = program_real
        if source_floor_prefix:
            resolve.source_floor = lambda item, operand: self.source_floor(item, operand, resolve)
        if program_real and self.procedure_builder is not None:
            from .real_calls import lower_call
            resolve.real_call = lambda *args, **kwargs: lower_call(self, *args, **kwargs)
        resolve.memoryless_decisions = self.procedure_builder is not None
        def outer_decision(item):
            if item.op in OPERATOR_NAMES:
                return False
            return item.op in DECISION_NAMES or any(outer_decision(arg) for arg in item.args)
        if self.model.functions:
            query = getattr(self, '_outer_decision_query', None)
            if query is None:
                from .source_queries import SourceQuery
                query = self._outer_decision_query = SourceQuery(
                    self.compilation.native_audit, 'source_outer_decision',
                    lambda item: ((False, False) if item.op in OPERATOR_NAMES else
                                  (True, False) if item.op in DECISION_NAMES else (False, True)),
                    lambda item, local, children: any(children))
            decision = query(expr)
        else:
            decision = outer_decision(expr)
        permitted = None
        if resolve.memoryless_decisions:
            from .elaboration import function_math
            permitted = lambda item:function_math(item, self.compilation.native_audit.ir_work)
        if decision and contains_operator(expr, allowed=permitted,
                visit=lambda item:self.compilation.native_audit.debit("function_decision_scan", item=item)):
            raise CompileError(f"{self.model.source}:{expr.token.line}: decision expressions do not support waveform operators in any operand or arm")
        def factory(item, relation, left, right, then_value, else_value):
            raw = self.make_ir(Select, relation, left, right, then_value, else_value,
                         self.make_ir(Origin, item.token.source or self.model.source, item.token.line, item.token.column,
                                self.instance.name, item.expansion))
            self.checked_ir(raw, raw.origin)
            # Keep the existing denominator proof before the stateless input
            # fallback: another instance may add a waveform operator later.
            normalized = normalize_positive_quotient_comparison(relation, left, right, positive_facts)
            if normalized is not None:
                relation, left, right = normalized
                return self.expression_select(item, relation, left, right, then_value, else_value)
            # The original raw tree has already been checked above. Retain it
            # unchanged; all expression semantics below are still checked fresh.
            self.compilation.native_audit.debit("decision_reuse_call", 2, item)
            return self.expression_select(item, relation, left, right, then_value, else_value, raw=raw)
        def waveform(op):
            if conditional and self.contains_history_call(op):
                raise CompileError(f"{self.model.source}:{op.token.line}: history waveform call sites must be unconditional")
            return self.waveform(op, resolve)
        audit_memo = None
        if self.model.functions and not program_real:
            # One read-only compatibility view. Actual source calls are emitted
            # separately by the retained procedure and never use this cache.
            from .source_queries import SourceQuery
            owner = self.compilation.native_audit
            owner.debit('compat_lower_allowed_ops', 16, expr)
            allowed = frozenset(('number', 'parameter', 'node', 'voltage', '+', '-', '*', '/',
                                 'unary+', 'unary-', 'checked', 'function_assign'))
            def local(item):
                qualified = item.op in allowed and not (item.op == 'function_assign' and item.value != 'real')
                return (qualified, item.source_call is not None), qualified
            def merge(item, value, children):
                owner.debit('compat_lower_merge', 3+2*len(children), item)
                return value[0] and all(child[0] for child in children), value[1] or any(child[1] for child in children)
            qualified, has_call = SourceQuery(owner, 'compat_lower_qualification', local, merge)(expr)
            if qualified and has_call and execute_calls:
                from .real_calls import lower_call
                resolve.real_call = lambda *args, **kwargs: lower_call(self, *args, **kwargs)
            elif qualified and has_call:
                audit_memo = _SourceAuditMemo(owner.ir_work,
                    (waveform, factory, self.validate_decision_expression, None))
                audit_memo.bind(resolve, self.node_ids,
                    (preserve_structure or decision, decision, conditional, program_real))
                resolve._source_audit_binding = audit_memo.binding_token
        value = lower(expr, resolve, self.node_ids, self.model.source,
                      waveform, preserve_structure or decision, factory, self.validate_decision_expression,
                      decision, memo=audit_memo, node_declarations=True)
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
            origin = self.make_ir(Origin, expr.token.source or self.model.source, expr.token.line, expr.token.column, self.instance.name, expr.expansion)
            self.checked_ir(value, origin)
            if not self.selected_value_supported(value):
                if self.input_rational_candidate(value):
                    self.request_input_rational(origin)
                elif self.source_forcing_candidate(value):
                    pass
                elif not self.readout_candidate(value, origin, "selected value must remain piecewise-affine or a supported rational expression"):
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
            if (self.integer_event_prefix is not None and self.procedure_builder is None
                    and not conditional and statement.token in self.integer_event_prefix.moved_tokens):
                # The complete original statement is audited and executed in
                # each qualified callback; no continuous consumer exists.
                self.compilation.native_audit.debit("integer_prefix_ordinary_transfer", 1, statement)
                continue
            if isinstance(statement, BoundStep):
                if contains_operator(statement.rhs):
                    raise CompileError(f'{self.model.source}:{statement.token.line}: $bound_step requires an expression without new waveform call sites')
                value = self.lower_local(statement.rhs, result, preserve_structure=True, positive_facts=positive_facts, program_real=True)
                if isinstance(value, Affine) and not value.terms and value.constant < 0:
                    raise CompileError('$bound_step requires a nonnegative value')
                origin = self.make_ir(Origin, statement.token.source or self.model.source, statement.token.line, statement.token.column,
                                self.instance.name, statement.token.expansion)
                value = self.make_ir(RealBoundary, value, "argument", origin)
                index = len(self.compilation.step_bounds)
                selected = self.make_ir(Affine, 1., ()) if self.procedure_builder is not None else active
                self.compilation.step_bounds.append(self.make_ir(StepBound, value, selected, origin))
                if self.procedure_builder is not None:
                    self.procedure_builder.step_bound(statement, index)
            elif isinstance(statement, ContributionStatement):
                emitted.append((statement, self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure, conditional=conditional, positive_facts=positive_facts, execute_calls=True)))
            elif isinstance(statement, SyntaxConditional):
                if contains_operator(statement.left) or contains_operator(statement.right):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates do not support waveform operators")
                origin = self.make_ir(Origin, statement.token.source or self.model.source, statement.token.line, statement.token.column, self.instance.name, statement.token.expansion)
                left = self.lower_local(statement.left, result, preserve_structure=True, positive_facts=positive_facts, program_real=True)
                right = self.lower_local(statement.right, result, preserve_structure=True, positive_facts=positive_facts, program_real=True)
                self.checked_ir(left, origin)
                self.checked_ir(right, origin)
                predicate_affine = self.predicate_degree(left) is not None and self.predicate_degree(right) is not None
                predicate_nodes = self.expression_nodes(left) | self.expression_nodes(right)
                if not predicate_nodes.issubset(self.allowed_condition_nodes):
                    if not self.history_condition_candidate(predicate_affine,origin,predicate_nodes):
                        raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates must depend only on input/inout ports")
                if not predicate_affine:
                    if self.input_rational_candidate(left) and self.input_rational_candidate(right):
                        self.request_input_rational(origin)
                    else:
                        candidate = self.make_ir(Binary, "add", left, self.scale_ir(right, -1.0))
                        if (not self.source_forcing_candidate(candidate)
                                and not self.readout_candidate(candidate, origin, "ordinary analog if predicates must be affine or input-selected piecewise-affine; nonlinear products and powers are unsupported")):
                            raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog if predicates must be affine or input-selected piecewise-affine; nonlinear products and powers are unsupported")
                relation = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[statement.relation]
                if self.procedure_builder is not None:
                    self.procedure_builder.conditional(statement, relation, left, right, origin)
                zero, one = self.make_ir(Affine, 0., ()), self.make_ir(Affine, 1., ())
                yes = self.make_ir(Select, 'gt', active, zero, self.make_ir(Select, relation, left, right, one, zero, origin), zero, origin)
                no = self.make_ir(Select, 'gt', active, zero, self.make_ir(Select, relation, left, right, zero, one, origin), zero, origin)
                yes_domains, no_domains = self.condition_domains(relation, left, right, domains)
                yes_facts, no_facts = condition_positive_facts(relation, left, right, positive_facts)
                then_env, then_emitted = self.execute_analog(statement.then_body, result, conditional=True, active=yes, domains=yes_domains, positive_facts=yes_facts)
                else_env, else_emitted = self.execute_analog(statement.else_body, result, conditional=True, active=no, domains=no_domains, positive_facts=no_facts)
                for selected, other, contributions in ((True, False, then_emitted), (False, True, else_emitted)):
                    for branch, value in contributions:
                        if self.procedure_builder is None:
                            value = self.make_ir(Select, relation, left, right,
                                           value if selected else self.make_ir(Affine, 0., ()),
                                           value if other else self.make_ir(Affine, 0., ()), origin)
                        self.checked_ir(value, origin)
                        emitted.append((branch, value))
                for name in sorted(set(then_env) | set(else_env) | set(result)):
                    if name not in self.ordinary_alias_variables:
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
                    if self.procedure_builder is not None and (name in self.procedure_builder.bindings or name in self.state_ids):
                        # Both arms write the same executable slot. Its value
                        # is chosen when the branch runs, not by evaluating a
                        # predicate again after an arm may have changed it.
                        result[name] = (self.make_ir(StateRef, self.state_ids[name])
                                        if name in self.state_ids else
                                        self.make_ir(RealLocal, self.procedure_builder.bindings[name]))
                        if isinstance(result[name], RealLocal):
                            degrees = [self.predicate_degree(item) for item in
                                       (left, right, then_env[name], else_env[name])]
                            degree = None if None in degrees else max(degrees)
                            self.compilation.native_audit.debit("procedure_binding_degree_merge", 2)
                            self.procedure_builder.degree_facts[id(result[name])] = (result[name], degree)
                            self.program_facts.record_read(result[name],
                                (left, right, then_env[name], else_env[name]), relation=relation)
                        continue
                    if then_env[name] is else_env[name]:
                        result[name] = then_env[name]
                        continue
                    if self.procedure_builder is not None and self.model.variables[name] == "integer":
                        a, b = then_env[name], else_env[name]
                        if isinstance(a, Affine) and isinstance(b, Affine) and not a.terms and not b.terms and a.constant == b.constant:
                            result[name] = a
                            continue
                        # A proved floor table is already a Select. A later constant
                        # clamp merges with that table; two plain constants still
                        # need an executable integer slot.
                        if not isinstance(a, Select) and not isinstance(b, Select):
                            raise CompileError("conditional integer alias requires an executable typed binding",
                                               code="unsupported_event_context", token=statement.token,
                                               instance=self.instance.name)
                    result[name] = factor_integer_prefix(
                        relation, left, right, then_env[name], else_env[name], origin,
                        integer_target=self.model.variables.get(name) == "integer",
                        validate_integer=self.validate_integer_value)
                    self.checked_ir(result[name], origin)
            else:
                if statement.name not in self.ordinary_alias_variables:
                    raise CompileError(f"{self.model.source}:{statement.token.line}: ordinary analog assignment target must be a local variable")
                if conditional and self.contains_history_call(statement.rhs):
                    raise CompileError(f"{self.model.source}:{statement.token.line}: history waveform call sites must be unconditional")
                candidate = None
                if held_power2.reserve(self.compilation.native_audit, "held_power2_alias_dispatch", 4, statement):
                    candidate = (self.held_power2_alias_candidates.get(statement.name)
                                 if self.held_power2_alias_candidates is not None and self.held_power2_ready is not None else None)
                if not conditional and candidate is statement:
                    plan = held_power2.source_plan(self, statement.rhs)
                    if plan is not None and held_power2.compatible_program(self, statement.rhs):
                        self.compilation.native_audit.activate(statement)
                        self.compilation.native_audit.debit("held_power2_alias_ready", 4, statement)
                        self.held_power2_ready[statement.name] = statement.rhs
                        continue
                prefix_source = (self.procedure_builder is not None and self.integer_event_prefix is not None
                                 and statement.name in self.integer_event_prefix.names
                                 and statement.token in self.integer_event_prefix.moved_tokens)
                value = self.lower_local(statement.rhs, result, preserve_structure=self.preserve_analog_structure, conditional=conditional, positive_facts=positive_facts,
                                         program_real=True, source_floor_prefix=prefix_source)
                self.checked_ir(value, self.make_ir(Origin, self.model.source, statement.token.line, statement.token.column, self.instance.name))
                if self.model.variables[statement.name] == "integer":
                    if prefix_source and isinstance(value, EventMath) and value.function == 'floor':
                        # This qualified original prefix owns an actual Integer
                        # state assignment. Floor proves integrality; the native
                        # typed store must check its range before a later clamp.
                        # Do not add a second real-to-integer conversion or grant
                        # unbounded ordinary temporaries this checked-store role.
                        self.compilation.native_audit.debit("integer_prefix_native_checked_store", 5, statement)
                        state = self.state_ids.get(statement.name)
                        if (state is None or self.compilation.states[state].kind != 'integer'
                                or not self.integral(value)):
                            raise CompileError("native source floor requires its checked integer state store",
                                               token=statement.token, instance=self.instance.name)
                    else:
                        self.validate_integer_value(value, statement.token)
                if self.procedure_builder is not None and (self.model.variables[statement.name] == "real" or statement.name in self.state_ids):
                    result[statement.name] = self.procedure_builder.capture(statement, value)
                else:
                    result[statement.name] = value
                    if self.procedure_builder is not None:
                        if isinstance(value, Affine) and not value.terms:
                            self.procedure_builder.elided_constants.add(statement.token)
                        else:
                            fact = self.program_real_closed(value)
                            if fact.closed and fact.finite and fact.value.is_integer() and -2147483648 <= fact.value <= 2147483647:
                                self.procedure_builder.closed_integer(statement, value)
                                result[statement.name] = self.make_ir(Affine, fact.value, ())
                            elif isinstance(value, Select):
                                # validate_integer_value already accepted this tree.
                                # Keep the finite-floor Select inline for later
                                # contributions; do not invent an integer slot.
                                self.procedure_builder.elided_constants.add(statement.token)
                            else:
                                raise CompileError("ordinary integer alias requires an executable capture",
                                                   code="unsupported_event_context", token=statement.token,
                                                   instance=self.instance.name)
        return result, emitted

    def emit_contributions(self, analog_contributions):
        mixed = {}
        for index, (_, expression) in enumerate(analog_contributions):
            parts = split_source_quadratic(expression, self.allowed_condition_nodes, self)
            if parts is not None:
                mixed[index] = parts
                self.forcing_seen = True
        checked = ()
        if self.forcing_seen:
            forbidden, roots = set(), []
            for index, (statement, expression) in enumerate(analog_contributions):
                if index in mixed or source_forcing_tree(expression, self.allowed_condition_nodes, self):
                    forbidden.update(self.node_ids[str(arg.value)] for arg in statement.branch.args)
                    roots.append(mixed[index][0] if index in mixed else expression)
            forbidden.discard(0)
            if not forbidden:
                raise CompileError('new forcing expression requires an independent output consumer',
                                   code='unsupported_forcing_scope')
            self.compilation.initial_math_work -= len(self.forcing_checks)
            if self.compilation.initial_math_work < 0:
                raise CompileError('forcing checked expression copy budget exceeded', code='resource_budget')
            checked = residual_checks(self, roots, self.forcing_checks)
        bound_branches = {}
        for index, (branch_statement, expression) in enumerate(analog_contributions):
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
            origin = self.make_ir(Origin, branch.token.source or self.model.source, branch.token.line, branch.token.column, self.instance.name, branch.expansion)
            identity = self.make_ir(BranchIdentity, self.instance.name, *pair)
            if index in mixed:
                source, residual = mixed[index]
                value = self.make_ir(Forcing, self.scale_ir(source, sign), origin, checked)
                checked = ()
                self.compilation.contributions.append(self.make_ir(Contribution, identity, p, n, value, origin))
                if self.procedure_builder is not None:
                    self.procedure_builder.contribution(branch_statement, len(self.compilation.contributions)-1)
                expression = residual
            value = self.scale_ir(expression, sign)
            if index not in mixed and self.forcing_seen and source_forcing_tree(value, self.allowed_condition_nodes, self):
                value = self.make_ir(Forcing, value, origin, checked)
                checked = ()
            self.compilation.contributions.append(self.make_ir(Contribution, identity, p, n, value, origin))
            if self.procedure_builder is not None:
                self.procedure_builder.contribution(branch_statement, len(self.compilation.contributions)-1)
