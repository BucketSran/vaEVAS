"""Emit the retained analog process, with executable captures and event gates.

This layer does not evaluate source values or choose event occurrences. The
runtime executes each step against one candidate value/proof environment.
"""
from dataclasses import replace

from .errors import CompileError
from .native_audit import Charge
from .ir import (Affine, Assignment, AnalogProcedure, ContributionCapture, Event,
                 EventGate, InitialStepTrigger, Origin, ProcedureStep,
                 ProcedureConditional, RealBind, RealBinding, RealBoundary, RealLocal, StateRef, StepBoundCapture)
from .syntax import (Assignment as SourceAssignment, ContributionStatement, Display,
                     Event as SourceEvent, Conditional as SourceConditional, BoundStep,
                     Loop as SourceLoop)


class ProcedureBuilder:
    def __init__(self, compiler):
        self.compiler = compiler
        compilation = compiler.compilation
        compilation.native_audit.debit("procedure_builder_create", 12)
        self.procedure_id = len(compilation.procedure_builders)
        compilation.procedure_builders.append(self)
        self.bindings = {}
        self.values = {}
        self.binding_nodes = {}
        self.degree_facts = {}
        self.scope_facts = compiler.program_facts.reads
        self.state_scope_facts = {}
        self.scope_generation = 0
        self.actions = {}
        self.events = {}
        self.event_arguments = None
        self.contributions = {}
        self.conditions = {}
        self.step_bounds = {}
        self.elided_constants = set()
        self.source_ordinals = {}
        for ordinal, statement in enumerate(compiler.model.procedure):
            compilation.native_audit.debit("procedure_source_order_root", 4, statement)
            old = self.source_ordinals.get(statement.token, ordinal)
            self.source_ordinals[statement.token] = ordinal if old == ordinal else None

    def ordinal_for(self, token):
        if token in self.source_ordinals:
            return self.source_ordinals[token]
        # Only source-sensitive rewrites such as pulse-reset request an
        # expression's enclosing statement. Ordinary compilation does not pay
        # for an otherwise unused second traversal of every source expression.
        matches = set()
        child_fields = ("args", "rhs", "left", "right", "index", "body",
                        "then_body", "else_body", "start", "limit", "update",
                        "triggers", "arguments")
        audit = self.compiler.compilation.native_audit
        for ordinal, statement in enumerate(self.compiler.model.procedure):
            pending, seen = [statement], set()
            while pending:
                audit.debit("procedure_source_order_visit", 4)
                value = pending.pop()
                if id(value) in seen:
                    continue
                seen.add(id(value))
                if getattr(value, "token", None) == token:
                    matches.add(ordinal)
                    break
                if isinstance(value, (tuple, list)):
                    audit.debit("procedure_source_order_elements", len(value))
                    pending.extend(value)
                else:
                    audit.debit("procedure_source_order_child_fields", len(child_fields))
                    pending.extend(child for name in child_fields
                                   if (child := getattr(value, name, None)) is not None)
        result = next(iter(matches)) if len(matches) == 1 else None
        audit.debit("procedure_source_order_record", 2)
        self.source_ordinals[token] = result
        return result

    def before(self, first, second):
        self.compiler.compilation.native_audit.debit("procedure_source_order_lookup", 4)
        a, b = self.ordinal_for(first), self.ordinal_for(second)
        return a < b if a is not None and b is not None and a != b else None

    def origin(self, token):
        c = self.compiler
        return c.make_ir(Origin, token.source or c.model.source, token.line,
                         token.column, c.instance.name, token.expansion)

    def declare(self, names):
        c = self.compiler
        for name in c.model.variables:
            c.compilation.native_audit.debit("procedure_binding_declaration", 3)
            if name not in names or c.model.variables[name] != "real":
                continue
            binding = len(c.compilation.real_bindings)
            c.compilation.real_bindings.append(c.make_ir(
                RealBinding, self.procedure_id, name,
                self.origin(c.model.declaration_token), "occurrence"))
            self.bindings[name] = binding

    def audit_local_availability(self):
        """Occurrence locals cannot stand in for a previous accepted value."""
        if not self.bindings:
            return
        c = self.compiler

        def reads(expr, defined):
            if expr is None:
                return
            if c.model.functions:
                owner = c.compilation.native_audit
                owner.debit("procedure_local_scope_context", 3, expr)
                query = c.compilation.source_structure_contexts[c.instance.name]
                names = query.fact(expr)[1]
                owner.debit("procedure_local_scope_names", 1+len(names), expr)
                missing = False
                for name in names:
                    owner.debit("procedure_local_scope_name", 2+len(name), expr)
                    if name in self.bindings and name not in defined:
                        missing = True
                if not missing:
                    return
                # The immutable name summary is context-free. Availability is
                # checked against this exact source position, never cached.
                # Recover the original diagnostic token in the old DFS order.
                owner.debit("procedure_local_scope_pending", 2, expr)
                pending, seen = [expr], set()
                while pending:
                    owner.debit("procedure_local_scope_pop", 2, expr)
                    value = pending.pop()
                    owner.debit("procedure_local_scope_lookup", 2, value)
                    if id(value) in seen:
                        continue
                    owner.debit("procedure_local_scope_insert", 2, value)
                    seen.add(id(value))
                    if value.op == "parameter" and value.value in self.bindings and value.value not in defined:
                        raise CompileError("ordinary local is not assigned before use at its source position; a prior evaluation requires a persistent slot",
                                           code="unsupported_local_event", token=value.token,
                                           instance=c.instance.name)
                    owner.debit("procedure_local_scope_edges", 1+len(value.args), value)
                    pending.extend(value.args)
                return
            pending = [expr]
            while pending:
                value = pending.pop()
                c.compilation.native_audit.debit("procedure_local_scope_read", 1, value)
                if value.op == "parameter" and value.value in self.bindings and value.value not in defined:
                    raise CompileError("ordinary local is not assigned before use at its source position; a prior evaluation requires a persistent slot",
                                       code="unsupported_local_event", token=value.token,
                                       instance=c.instance.name)
                pending.extend(value.args)

        def body(sources, defined):
            defined = set(defined)
            for source in sources:
                c.compilation.native_audit.debit("procedure_local_scope_statement", 1, source)
                for field in ("rhs", "index", "left", "right", "start", "limit", "update"):
                    reads(getattr(source, field, None), defined)
                for expr in getattr(source, "args", ()):
                    reads(expr, defined)
                if isinstance(source, SourceConditional):
                    defined = body(source.then_body, defined) & body(source.else_body, defined)
                elif isinstance(source, SourceEvent):
                    for trigger in source.triggers:
                        for expr in trigger.arguments:
                            reads(expr, defined)
                    body(source.body, defined)
                elif hasattr(source, "body"):
                    body(source.body, defined)
                elif isinstance(source, SourceAssignment) and source.name in self.bindings:
                    defined.add(source.name)
            return defined

        body(c.model.procedure, set())

    def audit_original_source(self, model):
        """Charge/check original RHS scopes even when a loop expands to zero."""
        c = self.compiler
        owner = c.compilation.native_audit
        owner.activate(model.declaration_token)
        if model.functions:
            length = len(model.procedure) if model.procedure else len(model.analog)+len(model.initial)+len(model.events)
            owner.debit("procedure_original_pending", 2+length, model.declaration_token)
        pending = list(model.procedure) if model.procedure else [*model.analog, *model.initial, *model.events]
        seen = set()
        while pending:
            source = pending.pop()
            owner.debit("procedure_original_statement", 1, source)
            if model.functions and hasattr(source, "op"):
                owner.debit("procedure_original_expr_lookup", 2, source)
                if id(source) in seen:
                    continue
                owner.debit("procedure_original_expr_insert", 2, source)
                seen.add(id(source))
            if model.functions:
                owner.debit("procedure_original_fields", 7, source)
            for field in ("rhs", "index", "left", "right", "start", "limit", "update"):
                value = getattr(source, field, None)
                if value is not None:
                    if model.functions:
                        owner.debit("procedure_original_append", 1, source)
                    pending.append(value)
            args = getattr(source, "args", ())
            if model.functions:
                owner.debit("procedure_original_edges", 1+len(args), source)
            pending.extend(args)
            if isinstance(source, SourceEvent):
                for trigger in source.triggers:
                    if model.functions:
                        owner.debit("procedure_original_trigger_edges", 1+len(trigger.arguments), source)
                    pending.extend(expr for expr in trigger.arguments if expr is not None)
            for field in ("then_body", "else_body", "body"):
                children = getattr(source, field, ())
                if model.functions:
                    owner.debit("procedure_original_body_edges", 1+len(children), source)
                pending.extend(children)
            if hasattr(source, "op"):
                owner.debit("ordinary_scratch_visit", 1, source)
                if not model.functions:
                    if id(source) in seen:
                        continue
                    seen.add(id(source))
                if source.op == "parameter" and source.value not in model.variables and source.value not in model.parameters and source.value not in model.genvars:
                    raise CompileError("original procedural expression references an undeclared variable",
                                       code="unsupported_local_event", token=source.token,
                                       instance=c.instance.name)
                if source.op == "node" and source.value not in model.nodes and source.value != "0":
                    raise CompileError("original procedural expression references an undeclared node",
                                       code="undeclared_node", token=source.token,
                                       instance=c.instance.name)

    def capture(self, statement, value):
        c = self.compiler
        c.compilation.native_audit.debit("procedure_capture_record", 8, statement)
        origin = self.origin(statement.token)
        if statement.name in c.state_ids:
            if c.model.variables[statement.name] == "real":
                value = c.make_ir(RealBoundary, value, "store", origin)
            action = c.make_ir(Assignment, c.state_ids[statement.name], value)
            result = c.make_ir(StateRef, c.state_ids[statement.name])
            c.compilation.native_audit.debit("procedure_state_scope_record", 2)
            self.state_scope_facts.setdefault(result.state, []).append(value)
            self.scope_generation += 1
        else:
            binding = self.bindings[statement.name]
            value = c.make_ir(RealBoundary, value, "snapshot", origin)
            action = c.make_ir(RealBind, binding, value, origin)
            result = c.make_ir(RealLocal, binding)
            degree = c.predicate_degree(value)
            c.compilation.native_audit.debit("procedure_binding_degree_record", 2)
            self.degree_facts[id(result)] = (result, degree)
            c.program_facts.record_read(result, (value,))
            # Dependency admission is conservative over every source write;
            # it must not inline a mutable slot's latest RHS recursively.
            dependencies = c.expression_nodes(value)
            c.compilation.native_audit.debit("procedure_binding_dependencies", 2 + len(dependencies))
            self.binding_nodes.setdefault(binding, set()).update(dependencies)
            self.values[binding] = value
        self.actions.setdefault(statement.token, []).append(action)
        return result

    def event(self, source, index, arguments=()):
        self.compiler.compilation.native_audit.debit("procedure_event_record", 4, source)
        self.events.setdefault(source.token, []).append(index)
        if arguments:
            self.compiler.compilation.native_audit.debit('procedure_event_arguments_record', 3 + len(arguments), source)
            if self.event_arguments is None:
                self.event_arguments = {}
            self.event_arguments[index] = tuple(arguments)

    def argument(self, value, token):
        """Retain a proved closed numeric trigger argument at its source gate."""
        c = self.compiler
        c.compilation.native_audit.activate(token)
        c.compilation.native_audit.debit('procedure_argument_binding', 3, token)
        binding = len(c.compilation.real_bindings)
        origin = self.origin(token)
        c.compilation.real_bindings.append(c.make_ir(RealBinding, self.procedure_id,
            '$event_arg'+str(binding), origin, 'occurrence'))
        value = c.make_ir(RealBoundary, value, 'argument', origin)
        return c.make_ir(RealBind, binding, value, origin)

    def closed_integer(self, statement, value):
        """Retain a closed, exact signed32 source evaluation before aliasing it."""
        c = self.compiler
        c.compilation.native_audit.activate(statement)
        c.compilation.native_audit.debit('procedure_closed_integer_binding', 3, statement)
        binding = len(c.compilation.real_bindings)
        origin = self.origin(statement.token)
        c.compilation.real_bindings.append(c.make_ir(RealBinding, self.procedure_id,
            '$integer_alias'+str(binding), origin, 'occurrence'))
        value = c.make_ir(RealBoundary, value, 'snapshot', origin)
        action = c.make_ir(RealBind, binding, value, origin)
        self.actions.setdefault(statement.token, []).append(action)

    def contribution_key(self, source):
        # Static loop expansion retains the statement token, but the branch
        # carries the expanded source occurrence. Compatibility analog and
        # procedure views are separate objects with this same immutable key.
        expansion = source.branch.expansion
        self.compiler.compilation.native_audit.debit(
            "procedure_contribution_key", 3 + len(expansion), source)
        return source.token, expansion

    def contribution(self, source, index):
        self.compiler.compilation.native_audit.debit("procedure_contribution_record", 4, source)
        self.contributions.setdefault(self.contribution_key(source), []).append(index)

    def conditional(self, source, relation, left, right, origin):
        self.compiler.compilation.native_audit.debit("procedure_condition_record", 7, source)
        self.conditions.setdefault(source.token, []).append((relation, left, right, origin))

    def step_bound(self, source, index):
        self.compiler.compilation.native_audit.debit("procedure_step_bound_record", 4, source)
        self.step_bounds.setdefault(source.token, []).append(index)

    def emit(self):
        c = self.compiler
        ordinal = 0

        def reserve():
            nonlocal ordinal
            value = ordinal
            ordinal += 1
            return value

        def step(action, number=None):
            c.compilation.native_audit.debit("procedure_step_append", 3)
            number = reserve() if number is None else number
            if isinstance(action, EventGate):
                event = c.compilation.events[action.event]
                c.compilation.events[action.event] = replace(event,
                    procedure_id=self.procedure_id,
                    expanded_statement_ordinal=number)
            return c.make_ir(ProcedureStep, number, action)

        def body(sources):
            steps = []
            for source in sources:
                c.compilation.native_audit.debit("procedure_source_emit", 5, source)
                if isinstance(source, SourceConditional):
                    number = reserve()  # DFS preorder: node, then arm, else arm.
                    choices = self.conditions.get(source.token, [])
                    if not choices:
                        raise CompileError("ordinary conditional lacks its executable source operands",
                                           token=source.token, instance=c.instance.name)
                    relation, left, right, origin = choices.pop(0)
                    then_body, else_body = body(source.then_body), body(source.else_body)
                    action = c.make_ir(ProcedureConditional, relation, left, right,
                                       then_body, else_body, origin)
                    steps.append(step(action, number))
                elif isinstance(source, SourceEvent):
                    gate = event_gate(source)
                    if gate is None:
                        # Pure initial_step body was installed in State.initial.
                        continue
                    if self.event_arguments is not None:
                        c.compilation.native_audit.debit('procedure_argument_gate_lookup', 1, source)
                        for argument in self.event_arguments.get(gate.event, ()):
                            steps.append(step(argument))
                    steps.append(step(gate))
                elif isinstance(source, SourceAssignment):
                    actions = self.actions.get(source.token, [])
                    if actions:
                        steps.append(step(actions.pop(0)))
                    elif source.name in self.bindings or source.name in c.state_ids:
                        raise CompileError("ordinary real assignment lacks its source-position binding",
                                           token=source.token, instance=c.instance.name)
                    elif source.token not in self.elided_constants:
                        raise CompileError("ordinary integer alias requires an executable capture",
                                           code="unsupported_event_context", token=source.token,
                                           instance=c.instance.name)
                elif isinstance(source, ContributionStatement):
                    for index in self.contributions.get(self.contribution_key(source), ()):
                        steps.append(step(c.make_ir(ContributionCapture, index)))
                elif isinstance(source, BoundStep):
                    for index in self.step_bounds.get(source.token, ()):
                        steps.append(step(c.make_ir(StepBoundCapture, index)))
                else:
                    raise CompileError("ordinary procedure step requires executable capture support",
                                       code="unsupported_event_context", token=source.token,
                                       instance=c.instance.name)
            return tuple(steps)

        def has_display(statements):
            for statement in statements:
                if isinstance(statement, Display):
                    return True
                if isinstance(statement, SourceConditional) and (
                        has_display(statement.then_body) or has_display(statement.else_body)):
                    return True
                if isinstance(statement, SourceLoop) and has_display(statement.body):
                    return True
            return False

        def event_gate(source):
                choices = self.events.get(source.token, [])
                initial = any(leaf.kind == "initial_step" for leaf in source.triggers)
                if choices:
                    index = choices.pop(0)
                    # Mixed initial_step|cross: monitored leaves were compiled
                    # without initial_step. Initialization is State.initial
                    # (INITIAL_STATIC_LOOP_CONTRACT / 3553bb2a); do not re-attach
                    # an initial_step leaf that would emit a second t=0 record.
                elif initial:
                    # Parser-installed constant initialization is owned by
                    # model.initial / initialize_states. Emitting another
                    # initial_step event duplicates the body in IR and in the
                    # transient record. Display-only initial_step never enters
                    # model.initial and still needs a runtime gate.
                    if all(leaf.kind == "initial_step" for leaf in source.triggers) and not has_display(source.body):
                        return None
                    c.runtime_event_checks = False
                    c.active_event_aliases = c.aliases_at(source.token, body=True)
                    # Initial replay is aggregate work, but it is not a new
                    # held-target activation or an independently budgeted
                    # monitored event.
                    c.native_integer_charge = Charge(c.compilation.native_audit, None)
                    c.event_sampled_states = set()
                    previous_initial = getattr(c, '_actual_initial_power', False)
                    c._actual_initial_power = True
                    try:
                        body = c.body(source.body)
                    finally:
                        c._actual_initial_power = previous_initial
                    index = len(c.compilation.events)
                    c.compilation.events.append(c.make_ir(Event, c.make_ir(InitialStepTrigger), body,
                                                          self.origin(source.token)))
                else:
                    raise CompileError("source event has no unique procedure gate",
                                       token=source.token, instance=c.instance.name)
                return c.make_ir(EventGate, index)

        steps = body(c.model.procedure)
        if any(self.events.values()) or any(self.actions.values()) or any(self.conditions.values()):
            raise CompileError("compiled source steps are missing from the retained procedure",
                               instance=c.instance.name)
        for name, state in c.state_ids.items():
            # initialize_states owns parser-split initial_step bodies. Keep those
            # seeds for every slot (static loops, mixed cross share, ordinary
            # aliases). Declaration defaults remain only when no initial write ran.
            if name in c.initials:
                seed = c.initials[name]
                while isinstance(seed, RealBoundary):
                    seed = seed.value
                # SEED+i and other closed real trees must become scalars in
                # State.initial; the kernel voltage resolver rejects operator
                # initials that are not declaration constants or closed numbers.
                closed = c.program_real_constant(seed)
                if closed is not None:
                    seed = closed
            else:
                seed = c.declaration_initials.get(name, Affine(0., ()))
            if isinstance(seed, Affine) and not seed.terms:
                seed = seed.constant
            c.compilation.states[state] = replace(c.compilation.states[state], initial=seed)
        return c.make_ir(AnalogProcedure, self.procedure_id, c.instance.name, steps)
