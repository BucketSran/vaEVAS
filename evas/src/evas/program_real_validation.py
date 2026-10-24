"""Validate IR33 structure and ownership before public materialization.

The caller first uses check_ir for size, cycles and depth. This pass walks every
branch using the caller's existing work callback; it creates no budget owner.
It establishes neither local-definition dominance nor call/occurrence lifetime
correctness. Those require producer/runtime proofs beyond these references.
"""
from dataclasses import is_dataclass
from typing import get_args

from .errors import CompileError
from .ir import (AnalogProcedure, ArrayWrite, Assignment, Conditional,
                 Contribution, ContributionCapture, Display, Event, EventGate,
                 Expression, IntegerState, Loop, Origin, ProcedureConditional,
                 ProcedureLoop, ProcedureStep, Program,
                 RealBind, RealBinding, RealBinary, RealBoundary, RealLocal, RealCall, UnsupportedSystemCall,
                 OperatorRef, StateRef, StepBound, StepBoundCapture)

_EXPRESSIONS = get_args(Expression)
_ACTIONS = (Assignment, Conditional, ArrayWrite, Loop, Display, RealBind,
            EventGate, ContributionCapture, StepBoundCapture,
            ProcedureConditional, ProcedureLoop)
_NEW_OPS = ('real_binary', 'real_boundary', 'real_local', 'real_call', 'unsupported_system_call')
_NEW_KINDS = ('real_bind', 'event_gate', 'contribution_capture', 'step_bound_capture',
              'procedure_if', 'procedure_loop')


def validate_program_ir(program, *, work=None, facts=None):
    """Reject malformed real/procedure nodes; do not infer execution proofs."""
    def charge(kind, amount=1):
        if work is not None:
            work(kind, amount)

    def fail(message):
        raise CompileError('IR33: ' + message, code='invalid_ir')

    def integer(value):
        return type(value) is int and value >= 0

    def text(value):
        return isinstance(value, str) and bool(value)

    def sequence(value):
        return isinstance(value, (tuple, list))

    def index(value, table, label):
        if not integer(value) or value >= len(table):
            fail(label + ' reference is out of range')

    charge('program_real_setup', 21)
    if not isinstance(program, Program) or type(program.schema_version) is not int or program.schema_version != 33:
        fail('expected schema version33 Program')
    for table in (program.procedures, program.real_bindings, program.events,
                  program.contributions, program.states, program.operators, program.step_bounds):
        charge('program_real_table')
        if not sequence(table):
            fail('program tables must be sequences')
    procedures = {}
    instance_owner = {}
    gates = {}
    captures = {}
    bound_captures = {}

    for procedure in program.procedures:
        charge('program_real_procedure', 5)
        if (not isinstance(procedure, AnalogProcedure) or not integer(procedure.procedure_id)
                or not text(procedure.instance) or not sequence(procedure.body)):
            fail('invalid procedure id, instance or body')
        pid = procedure.procedure_id
        if pid in procedures:
            fail('duplicate procedure id')
        procedures[pid] = procedure
        if procedure.instance in instance_owner:
            instance_owner[procedure.instance] = None
        else:
            instance_owner[procedure.instance] = pid

    def origin(value, owner):
        charge('program_real_origin_fields', 8)
        if (not isinstance(value, Origin) or not text(value.source)
                or not integer(value.line) or value.line == 0
                or not integer(value.column) or value.column == 0
                or not text(value.instance) or not sequence(value.expansion)):
            fail('invalid Origin')
        if owner is not None and value.instance != procedures[owner].instance:
            fail('Origin instance differs from its procedure')
        charge('program_real_origin_expansion', 1 + 3 * len(value.expansion))
        for expansion in value.expansion:
            if (not sequence(expansion) or len(expansion) != 2
                    or not text(expansion[0]) or type(expansion[1]) is not int):
                fail('invalid Origin expansion')

    has_call_bindings = False
    for binding in program.real_bindings:
        charge('program_real_binding', 5)
        if (not isinstance(binding, RealBinding) or not integer(binding.procedure_id)
                or binding.procedure_id not in procedures or not text(binding.name)
                or binding.lifetime not in ('occurrence', 'call')):
            fail('real binding requires a declared procedure and valid metadata')
        origin(binding.origin, binding.procedure_id)
        has_call_bindings = has_call_bindings or binding.lifetime == 'call'

    def binding_owner(reference, owner):
        index(reference, program.real_bindings, 'real binding')
        if owner is None:
            fail('real local/bind requires an unambiguous procedure owner')
        if program.real_bindings[reference].procedure_id != owner:
            fail('real local/bind crosses procedure ownership')

    def register_steps(body, pid, previous):
        charge('program_real_step_container')
        if not sequence(body):
            fail('procedure control bodies require ProcedureStep sequences')
        for step in body:
            charge('program_real_step', 5)
            if (not isinstance(step, ProcedureStep)
                    or not integer(step.expanded_statement_ordinal)
                    or step.expanded_statement_ordinal <= previous
                    or not isinstance(step.action, _ACTIONS)):
                fail('procedure ordinals must be unique and strictly increasing in DFS order; action must be typed')
            previous = step.expanded_statement_ordinal
            action = step.action
            if isinstance(action, EventGate):
                index(action.event, program.events, 'event gate')
                if action.event in gates:
                    fail('event has more than one procedure gate')
                charge('program_real_gate_record', 3)
                gates[action.event] = (pid, previous)
            elif isinstance(action, ContributionCapture):
                index(action.contribution, program.contributions, 'contribution capture')
                if action.contribution in captures:
                    fail('contribution has more than one capture')
                charge('program_real_capture_record', 2)
                captures[action.contribution] = pid
            elif isinstance(action, StepBoundCapture):
                index(action.step_bound, program.step_bounds, 'step bound capture')
                if action.step_bound in bound_captures:
                    fail('step bound has more than one capture')
                charge('program_real_capture_record', 2)
                bound_captures[action.step_bound] = pid
            elif isinstance(action, ProcedureConditional):
                charge('program_real_control_fields', 2)
                previous = register_steps(action.then_body, pid, previous)
                previous = register_steps(action.else_body, pid, previous)
            elif isinstance(action, ProcedureLoop):
                charge('program_real_control_fields', 3)
                previous = register_steps(action.initialize, pid, previous)
                previous = register_steps(action.body, pid, previous)
                previous = register_steps(action.update, pid, previous)
        return previous

    for procedure in program.procedures:
        register_steps(procedure.body, procedure.procedure_id, -1)

    for number, event in enumerate(program.events):
        charge('program_real_event_metadata', 5)
        if not isinstance(event, Event):
            fail('invalid Event table entry')
        if program.procedures:
            owner = gates.get(number)
            if (owner is None or type(event.procedure_id) is not int
                    or type(event.expanded_statement_ordinal) is not int
                    or (event.procedure_id, event.expanded_statement_ordinal) != owner):
                fail('Event metadata does not match its unique procedure gate')
            origin(event.origin, owner[0])
        elif event.procedure_id is not None or event.expanded_statement_ordinal is not None:
            fail('Event metadata names an undeclared procedure')

    for number, contribution in enumerate(program.contributions):
        charge('program_real_contribution_metadata', 4)
        if not isinstance(contribution, Contribution):
            fail('invalid Contribution table entry')
        if program.procedures:
            owner = captures.get(number)
            if owner is None:
                fail('contribution lacks its procedure capture')
            origin(contribution.origin, owner)
            if getattr(contribution.branch, 'instance', None) != procedures[owner].instance:
                fail('captured branch instance differs from its procedure')

    for number, bound in enumerate(program.step_bounds):
        charge('program_real_bound_metadata', 2)
        if not isinstance(bound, StepBound):
            fail('invalid StepBound table entry')
        if program.procedures:
            owner = bound_captures.get(number)
            if owner is None:
                fail('step bound lacks its procedure capture')
            origin(getattr(bound, 'origin', None), owner)

    call_owners = {}
    call_operators = {}
    if has_call_bindings and program.operators:
        charge('program_real_operator_use_container')
        operator_uses = []
    else:
        operator_uses = None

    def walk(root, owner, *, locals_allowed=True, direct_action=False, operator_scope=None):
        active_calls = [] if operator_scope is None else [operator_scope]
        call_argument = False
        charge('program_real_copyin_permission_scope', 1+(operator_scope is not None))
        copyin_permissions = [] if operator_scope is None else [False]
        # check_ir already bounded container depth at96. Recursive visits
        # therefore need no second heap stack or per-child copied records.
        # Step controls add at most one helper frame per container; total
        # validator recursion stays below2*96 plus a fixed helper overhead.
        charge('program_real_walk_entry')
        def visit_steps(body):
            charge('program_real_control_elements', 1 + len(body))
            for step in body:
                visit(step.action, True, True)

        def visit(value, direct=False, statement=False):
            nonlocal call_argument
            charge('program_real_visit')
            if type(value) in (str, int, float, bool, type(None)):
                return
            frontier = None
            if facts is not None and not active_calls and operator_uses is None:
                charge('program_real_fact_lookup')
                fact = facts.get(id(value))
                if fact is not None:
                    charge('program_real_fact_guard')
                    if len(fact) == 3:
                        retained, summary, children = fact
                        if (retained is value and len(summary) == 4
                                and summary[2] is True):
                            if summary[3] is False:
                                return
                            frontier = children
            if isinstance(value, Origin):
                # Old hand-authored mathematical IR can have placeholder
                # origins. New nodes check their own Origin above/below;
                # retained procedures additionally enforce instance ownership.
                if owner is not None:
                    origin(value, owner)
                return
            if isinstance(value, (RealBinary, RealBoundary, RealLocal, RealCall, UnsupportedSystemCall)) and statement:
                fail('real expression cannot occupy a statement slot')
            if isinstance(value, RealBinding):
                fail('real binding declarations belong in the binding table')
            if isinstance(value, OperatorRef) and active_calls:
                index(value.operator, program.operators, 'operator')
                charge('program_real_call_operator', 2+sum(len(scope) for scope in active_calls))
                prior = call_operators.get(value.operator)
                current = frozenset().union(*active_calls)
                if prior is not None and prior != current:
                    fail('call operator shared between call activations')
                call_operators[value.operator] = current
            if isinstance(value, OperatorRef) and operator_uses is not None:
                # Old mathematical wrappers can hide a call-owned OperatorRef
                # outside any Call. Retain actual use contexts before discovery
                # so a later inferred scope cannot grant that escaped use.
                index(value.operator, program.operators, 'operator')
                charge('program_real_operator_use_record', 2)
                operator_uses.append((value.operator, current if active_calls else None))
            if isinstance(value, UnsupportedSystemCall):
                if (value.op != 'unsupported_system_call' or value.function != 'rdist_normal'
                        or not sequence(value.args) or len(value.args) != 2
                        or not all(isinstance(argument, _EXPRESSIONS) for argument in value.args)):
                    fail('invalid deferred system function signature')
                index(value.seed, program.states, 'system call seed')
                state = program.states[value.seed]
                if owner is None or state.kind != 'integer' or state.instance != procedures[owner].instance or active_calls and not call_argument:
                    fail('system function seed requires same-instance integer state outside a function call')
                origin(value.origin, owner)
                charge('program_real_system_args', len(value.args))
                for argument in value.args:
                    visit(argument)
                return
            if isinstance(value, RealCall):
                if value.op != 'real_call' or owner is None or not sequence(value.bindings) or not sequence(value.body):
                    fail('invalid real_call structure or owner')
                origin(value.origin, owner)
                charge('program_real_call_bindings', 1+len(value.bindings))
                owned = set()
                for binding in value.bindings:
                    binding_owner(binding, owner)
                    if binding in owned or program.real_bindings[binding].lifetime != 'call':
                        fail('real_call requires distinct call lifetime bindings')
                    if binding in call_owners:
                        fail('real_call binding shared between calls')
                    call_owners[binding] = value
                    owned.add(binding)
                if not any(kind == 'function_call' for kind, _ in value.origin.expansion):
                    fail('real_call requires function occurrence Origin')
                result = value.result.value if isinstance(value.result, RealBoundary) else value.result
                if not isinstance(result, RealLocal) or result.binding not in owned:
                    fail('real_call result must be its owned return slot')
                previous = -1
                arguments_done = False
                def call_reads(expression, defined, argument):
                    pending = [expression]
                    while pending:
                        child = pending.pop()
                        charge('program_real_call_definition_read')
                        if isinstance(child, RealLocal):
                            if child.binding in owned and child.binding not in defined:
                                fail('call local read before assignment')
                            if child.binding not in owned and not argument:
                                fail('call body reads an external local')
                        elif isinstance(child, (StateRef, IntegerState)):
                            if not argument:
                                fail('call body reads an external state')
                        elif isinstance(child, RealCall):
                            # Only child copy-in can read the enclosing scope.
                            for entry in child.body:
                                action = entry.action
                                if not (isinstance(action, RealBind) and isinstance(action.value, RealBoundary) and action.value.kind == 'argument'):
                                    break
                                pending.append(action.value)
                        elif isinstance(child, OperatorRef):
                            index(child.operator, program.operators, 'operator')
                            spec = program.operators[child.operator]
                            if getattr(spec, 'kind', None) not in ('sin', 'math'):
                                fail('call body contains a non-memoryless operator')
                            pending.append(spec.input)
                        elif is_dataclass(child):
                            schema = type(child).__dataclass_fields__
                            charge('program_real_call_definition_fields', len(schema))
                            pending.extend(getattr(child, field.name) for field in schema.values() if field.name != 'origin')
                        elif isinstance(child, (tuple, list)):
                            charge('program_real_call_definition_children', len(child))
                            pending.extend(child)
                def call_steps(steps, defined, nested=False):
                    nonlocal previous, arguments_done
                    charge('program_real_call_steps', 1+len(steps))
                    for entry in steps:
                        if not isinstance(entry, ProcedureStep) or not integer(entry.expanded_statement_ordinal) or entry.expanded_statement_ordinal <= previous:
                            fail('real_call requires strictly ordered local ordinals')
                        previous = entry.expanded_statement_ordinal
                        action = entry.action
                        if isinstance(action, RealBind):
                            if action.binding not in owned:
                                fail('real_call bind is not owned')
                            argument = isinstance(action.value, RealBoundary) and action.value.kind == 'argument'
                            if argument and (nested or arguments_done):
                                fail('real_call arguments must form an entry prefix')
                            if not argument:
                                arguments_done = True
                            call_reads(action.value, defined, argument)
                            defined.add(action.binding)
                        elif isinstance(action, ProcedureConditional):
                            arguments_done = True
                            call_reads(action.left, defined, False)
                            call_reads(action.right, defined, False)
                            charge('program_real_call_definition_branch', 2+2*len(defined))
                            yes = call_steps(action.then_body, set(defined), True)
                            no = call_steps(action.else_body, set(defined), True)
                            defined = yes & no
                        else:
                            fail('real_call body only permits local bindings and conditionals')
                    return defined
                defined = call_steps(value.body, set())
                call_reads(value.result, defined, False)
                previous_argument = call_argument
                # An argument tag can carry module copy-in authority down a
                # chain, but cannot regain it after entering any function body.
                charge('program_real_copyin_permission_frame', 4)
                module_copyin = not active_calls or call_argument
                copyin_permissions.append(module_copyin)
                call_argument = False
                active_calls.append(owned)
                visit_steps(value.body)
                visit(value.result)
                active_calls.pop()
                copyin_permissions.pop()
                call_argument = previous_argument
                return
            if isinstance(value, RealBinary):
                if (value.op != 'real_binary' or value.operation not in ('add', 'subtract', 'multiply', 'divide')
                        or not isinstance(value.left, _EXPRESSIONS) or not isinstance(value.right, _EXPRESSIONS)):
                    fail('invalid real_binary operation or operand')
                origin(value.origin, owner)
            elif isinstance(value, RealBoundary):
                if (value.op != 'real_boundary' or value.kind not in ('store', 'sample', 'snapshot', 'argument', 'return')
                        or not isinstance(value.value, _EXPRESSIONS)):
                    fail('invalid real_boundary kind or operand')
                origin(value.origin, owner)
            elif isinstance(value, RealLocal):
                if value.op != 'real_local' or not (locals_allowed or active_calls):
                    fail('real local is invalid in this context')
                binding_owner(value.binding, owner)
                if program.real_bindings[value.binding].lifetime == 'call' and not any(value.binding in owned for owned in active_calls):
                    fail('call local escapes its activation')
            elif isinstance(value, RealBind):
                if not statement or value.kind != 'real_bind' or not isinstance(value.value, _EXPRESSIONS):
                    fail('invalid real_bind kind or operand')
                binding_owner(value.binding, owner)
                if program.real_bindings[value.binding].lifetime == 'call' and not any(value.binding in owned for owned in active_calls):
                    fail('call bind escapes its activation')
                origin(value.origin, owner)
                if active_calls:
                    previous_argument = call_argument
                    charge('program_real_copyin_permission_lookup')
                    call_argument = copyin_permissions[-1] and isinstance(value.value, RealBoundary) and value.value.kind == 'argument'
                    visit(value.value)
                    call_argument = previous_argument
                    return
            elif isinstance(value, (ProcedureConditional, ProcedureLoop)):
                expected = 'procedure_if' if isinstance(value, ProcedureConditional) else 'procedure_loop'
                if (value.kind != expected or owner is None or not direct
                        or value.relation not in ('lt', 'le', 'gt', 'ge')
                        or not isinstance(value.left, _EXPRESSIONS)
                        or not isinstance(value.right, _EXPRESSIONS)):
                    fail('invalid procedure control or missing owning ProcedureStep')
                # Do not let a legacy Conditional/Loop give nested gates an
                # implicit ordinal. Only these Step-bearing controls do so.
                charge('program_real_fields', len(type(value).__dataclass_fields__))
                origin(value.origin, owner)
                visit(value.left)
                visit(value.right)
                if isinstance(value, ProcedureConditional):
                    visit_steps(value.then_body)
                    visit_steps(value.else_body)
                else:
                    visit_steps(value.initialize)
                    visit_steps(value.body)
                    visit_steps(value.update)
                return
            elif isinstance(value, (EventGate, ContributionCapture, StepBoundCapture)):
                expected = ('event_gate' if isinstance(value, EventGate) else
                            'step_bound_capture' if isinstance(value, StepBoundCapture) else
                            'contribution_capture')
                if value.kind != expected or owner is None or not direct:
                    fail('gate/capture requires its own procedure statement ordinal')
            elif getattr(value, 'op', None) in _NEW_OPS or getattr(value, 'kind', None) in _NEW_KINDS:
                fail('new operation/kind has the wrong typed IR node')
            if isinstance(value, (Assignment, StateRef, IntegerState)) and owner is not None:
                index(value.state, program.states, 'state')
                if program.states[value.state].instance != procedures[owner].instance:
                    fail('state reference crosses procedure instance')
            if frontier is not None:
                # check_ir retained these edges during its original shape pass.
                # Only immutable same-object facts can omit irrelevant subtrees.
                charge('program_real_fact_children', len(frontier))
                for name, child in frontier:
                    statement_child = (isinstance(value, Event) and name == 'body'
                        or isinstance(value, Conditional) and name in ('then_body', 'else_body')
                        or isinstance(value, Loop) and name in ('initialize', 'body', 'update'))
                    visit(child, statement=statement_child or (name is None and statement))
            elif is_dataclass(value):
                # __dataclass_fields__ already exists; pay before iterating it
                # and reading its fields recursively. No fields() tuple is created.
                schema = type(value).__dataclass_fields__
                charge('program_real_fields', len(schema))
                for field in schema.values():
                    statement_child = (isinstance(value, Event) and field.name == 'body'
                        or isinstance(value, Conditional) and field.name in ('then_body', 'else_body')
                        or isinstance(value, Loop) and field.name in ('initialize', 'body', 'update'))
                    visit(getattr(value, field.name), statement=statement_child)
            elif isinstance(value, (tuple, list, dict)):
                charge('program_real_elements', len(value))
                if isinstance(value, dict):
                    if value.get('op') in _NEW_OPS or value.get('kind') in _NEW_KINDS:
                        fail('new operations require typed IR nodes')
                    children = value.values()
                else:
                    children = value
                for child in children:
                    visit(child, statement=statement)
            return

        visit(root, direct_action, direct_action)

    for procedure in program.procedures:
        for step in procedure.body:
            charge('program_real_action')
            walk(step.action, procedure.procedure_id, direct_action=True)
    for number, event in enumerate(program.events):
        charge('program_real_event_walk')
        gate = gates.get(number)
        walk(event, gate[0] if gate is not None else None)
    for number, contribution in enumerate(program.contributions):
        charge('program_real_contribution_walk')
        walk(contribution, captures.get(number))
    for state in program.states:
        charge('program_real_initial_walk')
        walk(state.initial, instance_owner.get(state.instance), locals_allowed=False)
    # Call activations can be owned by a later memoryless consumer's input.
    # Discover their operator scopes across the complete table before checking
    # any operator input's local reads. Table order is not activation order.
    if has_call_bindings and program.operators:
        charge('program_real_discovery_container', 1)
        discovered_edges = set()
    else:
        discovered_edges = None
    def discover(root, scope=None):
        # A procedure/event walk may already own the terminal memoryless
        # operator. Carry that actual activation through its operator inputs,
        # even when no enclosing Call node lives in any operator-table root.
        charge('program_real_discovery_frame', 3+(scope is not None))
        pending = [(root, () if scope is None else (scope,))]
        while pending:
            value, scopes = pending.pop()
            charge('program_real_discovery_visit')
            if isinstance(value, RealCall):
                if not sequence(value.bindings):
                    fail('invalid real_call bindings during discovery')
                charge('program_real_discovery_bindings', 3+len(value.bindings)+len(scopes))
                owned = set()
                for binding in value.bindings:
                    index(binding, program.real_bindings, 'real binding')
                    owned.add(binding)
                scopes = (*scopes, owned)
            if isinstance(value, OperatorRef) and scopes:
                index(value.operator, program.operators, 'operator')
                charge('program_real_discovery_scope', 2+sum(len(scope) for scope in scopes))
                current = frozenset().union(*scopes)
                prior = call_operators.get(value.operator)
                if prior is not None:
                    # An operator-table root can reveal a child call before its
                    # enclosing call is discovered through a later consumer. Only
                    # extend comparable provisional scopes here. The real walk
                    # below still requires exact equality at each actual use.
                    charge('program_real_discovery_compare', len(prior)+len(current))
                    if current <= prior:
                        current = prior
                    elif not prior <= current:
                        fail('call operator shared between call activations')
                call_operators[value.operator] = current
                charge('program_real_discovery_edge', 3+len(current))
                key = (value.operator, current)
                if key not in discovered_edges:
                    discovered_edges.add(key)
                    charge('program_real_discovery_frame', 3)
                    pending.append((program.operators[value.operator], (current,)))
                continue
            if isinstance(value, Origin):
                continue
            if is_dataclass(value):
                schema = type(value).__dataclass_fields__
                charge('program_real_discovery_fields', 3*len(schema))
                for field in schema.values():
                    if field.name != 'origin':
                        pending.append((getattr(value, field.name), scopes))
            elif isinstance(value, (tuple, list)):
                charge('program_real_discovery_elements', 2*len(value))
                for child in value:
                    pending.append((child, scopes))
    if has_call_bindings:
        charge('program_real_discovery_enumerate')
        for operator_number, item in enumerate(program.operators):
            charge('program_real_discovery_root', 2)
            discover(item, call_operators.get(operator_number))

    for operator_number, item in enumerate(program.operators):
        charge('program_real_consumer_walk')
        source = getattr(item, 'origin', None)
        owner = instance_owner.get(source.instance) if isinstance(source, Origin) else None
        walk(item, owner, operator_scope=call_operators.get(operator_number))
    for number, bound in enumerate(program.step_bounds):
        charge('program_real_consumer_walk')
        walk(bound, bound_captures.get(number))

    if operator_uses is not None:
        charge('program_real_operator_use_iteration')
        for operator_number, actual in operator_uses:
            charge('program_real_operator_use_check', 2)
            expected = call_operators.get(operator_number)
            charge('program_real_operator_use_compare', len(actual or ()) + len(expected or ()))
            if expected is not None and actual != expected:
                fail('call operator escapes its activation')

    for binding_number, binding in enumerate(program.real_bindings):
        charge('program_real_call_owner_complete')
        if binding.lifetime == 'call' and binding_number not in call_owners:
            fail('call binding has no syntactic owning real_call')
