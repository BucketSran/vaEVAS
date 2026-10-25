"""Ordinary analog variables that keep their value between evaluations.

Verilog-A analog variables persist (LRM 2.4 4.2, 5.3): an ordinary read that
is not dominated by a write of the same evaluation observes the previously
accepted value. ``if (V(s) > vth) q = 1; V(y) <+ q;`` is a level-sensitive
latch. This module rewrites such a program into the existing certified event
state machinery; it adds no IR and no kernel consumer.

Let U be the ordinary statements that write held variables H. The admitted
slice requires (checked on the original tree, unselected arms included):

* U contains only scalar assignments and conditionals;
* every read of an H variable inside U is dominated by a write in U on that
  path, assignment right sides read no voltage/time/local, and predicates are
  either instance-constant affine voltage atoms or voltage-free expressions;
* for each atom, all of its relations agree at the exact zero with one side.

Then U(U(s, p), p) = U(s, p) for fixed predicate truths p, and the dense-time
state is piecewise constant between atom crossings and callbacks. With a held
slot ``h`` and the ordinary current value ``U(slot, p(t))``:

* ``initial_step`` commits ``U`` after its body at t=0;
* each atom crossing commits ``U(U(slot, pre), root)``: the triggering atom is
  forced to its pre-crossing side, then U is re-evaluated at the certified root
  (where the kernel's same-zero proof gives the exact-zero truths);
* each callback that reads/writes H or a U input first reconstructs the pre
  value ``U(slot, root)`` and runs U at the source position of the ordinary
  statements (before or after the callback);
* every rewritten body ends with ``h = h`` so any two of them in the same
  candidate batch are rejected by the existing same-time writer check.

Ordinary reads use a renamed local initialized from the slot and updated by U
at the beginning of the ordinary evaluation. Unsupported shapes return None and
keep the previous compiler path and diagnostics.
"""
from dataclasses import replace
from fractions import Fraction
import math

from .errors import CompileError
from .ir import Affine
from .lowering import lower
from .syntax import (Assignment, Conditional, ContributionStatement, Display,
                     BoundStep, Loop, Event, Trigger, Expr)

PURE = frozenset(('number', 'parameter', 'unary+', 'unary-', '+', '-', '*', '/', '%',
                  '&', '|', '^', 'unary~', '<<', '>>', '<', '<=', '>', '>=', '==', '!=',
                  '&&', '||', 'unary!', 'ternary', 'abs', 'min', 'max'))
VOLTAGE = frozenset(('voltage', 'node'))
PHYSICAL = VOLTAGE | frozenset(('time',))
SUFFIX = '$held'


class _Unsupported(Exception):
    pass


def _reads(expr, out=None):
    out = set() if out is None else out
    if expr is not None:
        if expr.op == 'parameter':
            out.add(expr.value)
        for arg in expr.args:
            _reads(arg, out)
    return out


def _ops(expr, out=None):
    out = set() if out is None else out
    out.add(expr.op)
    for arg in expr.args:
        if expr.op != 'voltage':
            _ops(arg, out)
    return out


def _statement_exprs(item):
    for field in ('rhs', 'index', 'left', 'right', 'start', 'limit', 'update'):
        expr = getattr(item, field, None)
        if expr is not None:
            yield expr
    if isinstance(item, Display):
        yield from item.args


def _writes(body, out=None):
    out = set() if out is None else out
    for item in body:
        if isinstance(item, (Assignment, Loop)):
            out.add(item.name)
        for field in ('then_body', 'else_body', 'body'):
            _writes(getattr(item, field, ()), out)
    return out


def _all_reads(body, out=None, *, reads=_reads, owner=None):
    out = set() if out is None else out
    for item in body:
        for expr in _statement_exprs(item):
            if reads is _reads:
                _reads(expr, out)
            else:
                names = reads(expr)
                owner.debit('held_source_read_aggregate', 1+2*len(names), expr)
                out.update(names)
        if isinstance(item, Event):
            for trigger in item.triggers:
                for arg in trigger.arguments:
                    if reads is _reads:
                        _reads(arg, out)
                    else:
                        names = reads(arg)
                        owner.debit('held_source_read_aggregate', 1+2*len(names), arg)
                        out.update(names)
        for field in ('then_body', 'else_body', 'body'):
            _all_reads(getattr(item, field, ()), out, reads=reads, owner=owner)
    return out


class _HeldQueries:
    """Immutable syntax facts for this bound instance, never held values."""
    def __init__(self, compiler):
        from .source_queries import SourceStructure
        owner = compiler.compilation.native_audit
        owner.debit('held_source_context_lookup', 3)
        contexts = getattr(compiler.compilation, 'source_structure_contexts', None)
        if contexts is None:
            owner.debit('source_structure_contexts_container')
            contexts = {}
            owner.debit('source_structure_contexts_retain')
            compiler.compilation.source_structure_contexts = contexts
        query = contexts.get(compiler.instance.name)
        if query is None:
            query = SourceStructure(owner)
            owner.debit('source_structure_context_record', 3)
            contexts[compiler.instance.name] = query
        owner.debit('held_source_query_container', 3)
        self.structure, self.owner, self.operations = query, owner, None

    def reads(self, expr):
        if expr is None:
            return frozenset()
        return self.structure.fact(expr)[1]

    def ops(self, expr):
        if self.operations is None:
            from .source_queries import SourceQuery
            def local(item):
                self.owner.debit('held_source_op_shape', 3, item)
                if type(item.args) is not tuple or type(item.op) is not str:
                    raise TypeError('held syntax query requires immutable Expr children')
                self.owner.debit('held_source_op_name', 2+len(item.op), item)
                return frozenset((item.op,)), item.op != 'voltage'
            def merge(item, value, children):
                for child in children:
                    self.owner.debit('held_source_op_union', 1+len(value)+len(child), item)
                    value = value | child
                return value
            self.owner.debit('held_source_ops_retain')
            self.operations = SourceQuery(self.owner, 'held_source_ops', local, merge)
        return self.operations(expr)


def _position(item):
    return item.token.source, item.token.line, item.token.column


def _rename(expr, mapping):
    if expr is None:
        return None
    args = tuple(_rename(arg, mapping) for arg in expr.args)
    if expr.op == 'parameter' and expr.value in mapping:
        return replace(expr, value=mapping[expr.value], args=args)
    if args != expr.args:
        return replace(expr, args=args)
    return expr


def _rename_statement(item, mapping, *, targets=False):
    changes = {}
    for field in ('rhs', 'index', 'left', 'right', 'start', 'limit', 'update'):
        if getattr(item, field, None) is not None:
            changes[field] = _rename(getattr(item, field), mapping)
    if isinstance(item, Display):
        changes['args'] = tuple(_rename(arg, mapping) for arg in item.args)
    if targets and isinstance(item, Assignment) and item.name in mapping:
        changes['name'] = mapping[item.name]
    for field in ('then_body', 'else_body', 'body'):
        if hasattr(item, field):
            changes[field] = tuple(_rename_statement(child, mapping, targets=targets)
                                   for child in getattr(item, field))
    return replace(item, **changes)


def _zero_truth(relation):
    # Exact-zero truth of (left-right) relation 0; the kernel's same-zero proof.
    return relation in ('<=', '>=')


def _side_truth(relation, sign):
    return (sign > 0) if relation in ('>', '>=') else (sign < 0)


def _unconstrained_probe(compiler, node, charge):
    """Keep the probe out of circuit equations that could determine its value.

    Port direction alone is insufficient: another instance can drive an input.
    Exclude both LHS providers and numerical RHS/alias reads. Otherwise exact
    physical projection could invert an equation whose output is driven.
    Predicate reads are safe here: conditional contributions disable that
    projection, and state/select source values are opaque to it. A non-driven
    probe then has neither a causal provider nor a nonzero projection column;
    its retained condition fails the finite event-frame check before commit.
    Inspect the complete bound program, including unselected arms. Binding
    has already removed zero-iteration loops, which contribute no equation.
    Unexpanded functions and complex endpoints keep the previous route.
    """
    bindings = compiler.compilation.held_power2_bindings
    target = compiler.compilation.nodes[node]
    charge('held_probe_bindings', len(bindings) + 2)
    for _, model, nets in bindings:
        charge('held_probe_functions', 1)
        if model.functions:
            return False
        charge('held_probe_roots', len(model.analog) + len(model.initial) + len(model.events) + 4)
        pending = [*model.analog, *model.initial, *model.events]
        while pending:
            charge('held_probe_statement', 4)
            item = pending.pop()
            if isinstance(item, ContributionStatement):
                charge('held_probe_endpoints', len(item.branch.args) + 2)
                for endpoint in item.branch.args:
                    if endpoint.op != 'node':
                        return False
                    name = str(endpoint.value)
                    charge('held_probe_net', len(name) + len(target) + 2)
                    mapped = '0' if name == '0' else nets.get(name)
                    if mapped is None or mapped == target:
                        return False
            if not isinstance(item, Conditional):
                charge('held_probe_expression_roots', 8 + (len(item.args) if isinstance(item, Display) else 0))
                expressions = list(_statement_exprs(item))
                if isinstance(item, Event):
                    charge('held_probe_triggers', len(item.triggers) + 1)
                    for trigger in item.triggers:
                        charge('held_probe_arguments', len(trigger.arguments) + 1)
                        expressions.extend(arg for arg in trigger.arguments if arg is not None)
                while expressions:
                    charge('held_probe_expression', 4)
                    expr = expressions.pop()
                    if expr.op == 'node':
                        name = str(expr.value)
                        charge('held_probe_read_net', len(name) + len(target) + 2)
                        mapped = '0' if name == '0' else nets.get(name)
                        if mapped is None or mapped == target:
                            return False
                    charge('held_probe_expression_children', len(expr.args) + 1)
                    expressions.extend(expr.args)
            for field in ('then_body', 'else_body', 'body'):
                children = getattr(item, field, ())
                charge('held_probe_children', len(children) + 1)
                pending.extend(children)
    return True


def plan(compiler):
    """Return a rewritten executable model, or None when the slice does not apply."""
    model = compiler.model
    owner = compiler.compilation.native_audit

    # Programs without a held read keep their exact prior audit totals: the
    # role scan is metered locally and debited only once a held read exists.
    pending = {'held_state_dispatch': 2 + len(model.analog)}

    def charge(kind, amount=1):
        if pending is None:
            owner.debit('held_state_' + kind, amount)
        else:
            pending['held_state_' + kind] = pending.get('held_state_' + kind, 0) + amount

    def settle():
        nonlocal pending
        if pending is not None:
            work, pending = pending, None
            for kind, amount in work.items():
                owner.debit(kind, amount)

    charge.settle = settle
    if model.arrays or model.genvars:
        return None
    ordinary = list(model.analog)
    if any(isinstance(item, Event) for item in ordinary):
        return None
    writers = _writes(ordinary)
    if not writers:
        return None
    queries = _HeldQueries(compiler) if model.functions else None
    try:
        return _plan(compiler, model, ordinary, writers, charge, queries)
    except _Unsupported:
        if model.procedure and getattr(compiler, 'ordinary_held_proof_required', False):
            # Retaining the process is not itself a dense-time certificate.
            # A failed held proof must not admit tracking/running-max or a
            # timer input with an uncertified exact-zero side merely because
            # real assignments now have executable source-position captures.
            pending_statements = list(ordinary)
            while pending_statements:
                item = pending_statements.pop()
                charge('unproved_process_statement')
                for expr in _statement_exprs(item):
                    if queries is not None:
                        if queries.ops(expr) & PHYSICAL:
                            raise CompileError('ordinary held physical update lacks its dense-time certificate',
                                               code='unsupported_local_event', token=item.token,
                                               instance=compiler.instance.name)
                        continue
                    pending_exprs = [expr]
                    while pending_exprs:
                        current = pending_exprs.pop()
                        charge('unproved_process_expression')
                        if current.op in VOLTAGE or current.op == 'time':
                            raise CompileError('ordinary held physical update lacks its dense-time certificate',
                                               code='unsupported_local_event', token=item.token,
                                               instance=compiler.instance.name)
                        pending_exprs.extend(current.args)
                for field in ('then_body', 'else_body', 'body'):
                    pending_statements.extend(getattr(item, field, ()))
        return None


def _plan(compiler, model, ordinary, writers, charge, queries=None):
    read_names = queries.reads if queries is not None else _reads
    op_names = queries.ops if queries is not None else _ops
    def body_reads(body):
        return _all_reads(body, reads=read_names, owner=queries.owner if queries is not None else None)

    events = list(model.events)
    runtime, initial_events = [], []
    for event in events:
        kinds = {trigger.kind for trigger in event.triggers}
        if kinds == {'initial_step'}:
            initial_events.append(event)
        else:
            runtime.append(event)
    sources = {_position(item)[0] for item in (*ordinary, *events, *model.initial)}
    if len(sources) != 1:
        raise _Unsupported

    # Must-write analysis in source order, with callbacks at their positions.
    held = set()

    def flow(body, must):
        must = set(must)
        for item in body:
            charge('visit')
            if isinstance(item, Event):
                for trigger in item.triggers:
                    for arg in trigger.arguments:
                        held.update((read_names(arg) & writers) - must)
                flow(item.body, must)
                continue
            for expr in _statement_exprs(item):
                held.update((read_names(expr) & writers) - must)
            if queries is None and isinstance(item, (ContributionStatement, BoundStep)):
                held.update((read_names(item.rhs) & writers) - must)
            if isinstance(item, Conditional):
                must = flow(item.then_body, must) & flow(item.else_body, must)
            elif isinstance(item, Loop):
                held.update((body_reads(item.body) & writers) - must)
            elif isinstance(item, Assignment) and item.index is None:
                must.add(item.name)
        return must

    sequence = sorted([*ordinary, *runtime], key=_position)
    flow(sequence, set())
    if not held:
        return None
    charge.settle()
    compiler.ordinary_held_proof_required = True

    # U: every top-level ordinary statement writing a held variable. Its other
    # targets join H; a renamed current value replaces them in ordinary code.
    while True:
        indices = [i for i, item in enumerate(ordinary) if _writes((item,)) & held]
        targets = set().union(*(_writes((ordinary[i],)) for i in indices))
        if targets <= held:
            break
        held |= targets
    if any(model.variables.get(name) not in ('real', 'integer') for name in held):
        raise _Unsupported
    if any(name in model.variable_initializers for name in held):
        raise _Unsupported
    update = [ordinary[i] for i in indices]
    first, last = indices[0], indices[-1]
    for item in ordinary[first:last + 1]:
        if item not in update and (body_reads((item,)) & held):
            raise _Unsupported
    begin, end = _position(ordinary[first]), _position(ordinary[last])
    for item in (*model.initial, *(s for e in initial_events for s in e.body)):
        if _position(item) > begin:
            raise _Unsupported

    # Admission of U and atom classes.
    parameters = set(model.parameters)
    lookup = compiler.typed_resolve(compiler.parameter)
    atoms = []          # (conditional, class index, sign)
    classes = []        # (vector, guard Expr, token)

    def vector(value):
        if not isinstance(value, Affine) or not value.terms or not math.isfinite(value.constant):
            raise _Unsupported
        result = {'1': Fraction(value.constant)}
        for term in value.terms:
            if not math.isfinite(term.coefficient):
                raise _Unsupported
            result[term.node] = result.get(term.node, Fraction(0)) + Fraction(term.coefficient)
        return {key: number for key, number in result.items() if number}

    def proportional(a, b):
        if set(a) != set(b):
            return None
        pivot = next(key for key in sorted(a, key=str) if key != '1')
        ratio = b[pivot] / a[pivot]
        if all(a[key] * ratio == b[key] for key in a):
            return 1 if ratio > 0 else -1
        return None

    def classify(item):
        guard = Expr('-', None, (item.left, item.right), item.token)
        try:
            value = lower(guard, lookup, compiler.node_ids, model.source)
        except CompileError as error:
            if error.diagnostic.get('code') == 'resource_budget':
                raise
            raise _Unsupported from error
        current = vector(value)
        for index, (other, _, _) in enumerate(classes):
            sign = proportional(other, current)
            if sign is not None:
                return index, sign
        classes.append((current, guard, item.token))
        return len(classes) - 1, 1

    def admit(body, must):
        must = set(must)
        for item in body:
            charge('admit')
            if isinstance(item, Assignment):
                if item.index is not None or not op_names(item.rhs) <= PURE:
                    raise _Unsupported
                admit_reads(read_names(item.rhs), must)
                must.add(item.name)
            elif isinstance(item, Conditional):
                names = read_names(item.left) | read_names(item.right)
                ops = op_names(item.left) | op_names(item.right)
                if ops & VOLTAGE:
                    if not ops <= PURE | VOLTAGE or not names <= parameters:
                        raise _Unsupported
                    atoms.append((item, *classify(item)))
                elif ops <= PURE:
                    admit_reads(names, must)
                else:
                    raise _Unsupported
                must = admit(item.then_body, must) & admit(item.else_body, must)
            else:
                raise _Unsupported
        return must

    def admit_reads(names, must):
        for name in names:
            if name in parameters and name not in model.variables:
                continue
            if name in held:
                if name not in must:
                    raise _Unsupported
            elif name not in model.variables or name in writers:
                raise _Unsupported

    admit(update, set())
    if not classes:
        raise _Unsupported
    for index in range(len(classes)):
        relations = [(item.relation, sign) for item, cls, sign in atoms if cls == index]
        # The exact-zero pattern must equal one side's pattern.
        zero = [_zero_truth(r) for r, _ in relations]
        if zero != [_side_truth(r, s) for r, s in relations] and \
                zero != [_side_truth(r, -s) for r, s in relations]:
            raise _Unsupported
    atom_of = {id(item): (cls, sign) for item, cls, sign in atoms}

    def forced(body, cls, side):
        result = []
        for item in body:
            if isinstance(item, Conditional):
                entry = atom_of.get(id(item))
                then_body, else_body = forced(item.then_body, cls, side), forced(item.else_body, cls, side)
                if entry is not None and entry[0] == cls:
                    result.extend(then_body if _side_truth(item.relation, entry[1] * side) else else_body)
                else:
                    result.append(replace(item, then_body=tuple(then_body), else_body=tuple(else_body)))
            else:
                result.append(item)
        return result

    update_inputs = set().union(*(body_reads((item,)) for item in update)) - held
    token = update[0].token
    closing = [Assignment(name, Expr('parameter', name, (), token), token) for name in sorted(held)]

    # Trigger reads must observe the committed slot. That is current only when
    # leaving each atom's exact-zero pattern side writes no trigger-read name.
    trigger_reads = set()
    for event in runtime:
        for trigger in event.triggers:
            for arg in trigger.arguments:
                trigger_reads |= read_names(arg) & held
    if trigger_reads:
        for index, (_, cls_guard, _) in enumerate(classes):
            relations = [(item.relation, sign) for item, cls, sign in atoms if cls == index]
            zero = [_zero_truth(r) for r, _ in relations]
            for side in (1, -1):
                if zero != [_side_truth(r, s * side) for r, s in relations] and \
                        _writes(forced(update, index, side)) & trigger_reads:
                    raise _Unsupported

    # Source callbacks with a cross guard sharing an atom zero set own that
    # direction's commit; any other coincidence is rejected by `closing`.
    merged = {}
    new_events = []
    for event in events:
        if event in initial_events:
            new_events.append(event)
            continue
        kinds = {trigger.kind for trigger in event.triggers}
        if not kinds <= {'cross', 'timer'}:
            if _writes(event.body) & (held | update_inputs) or body_reads((event,)) & held:
                raise _Unsupported
            new_events.append(event)
            continue
        touches = (_writes(event.body) & (held | update_inputs)) or (body_reads((event,)) & held)
        shared = None
        for trigger in event.triggers:
            if trigger.kind != 'cross':
                continue
            if read_names(trigger.arguments[0]) - parameters:
                continue
            try:
                current = vector(lower(trigger.arguments[0], lookup, compiler.node_ids, model.source))
            except (CompileError, _Unsupported):
                continue
            for index, (other, _, _) in enumerate(classes):
                sign = proportional(other, current)
                if sign is not None:
                    if len(event.triggers) != 1 or len(trigger.arguments) < 2:
                        raise _Unsupported
                    try:
                        direction = lower(trigger.arguments[1], lookup, {}, model.source)
                    except CompileError as error:
                        raise _Unsupported from error
                    if not isinstance(direction, Affine) or direction.terms or direction.constant not in (1., -1.):
                        raise _Unsupported
                    shared = (index, int(direction.constant) * sign)
        if not touches and shared is None:
            new_events.append(event)
            continue
        position = _position(event)
        if begin < position < end:
            raise _Unsupported
        before = position < begin
        if shared is not None:
            if shared in merged:
                raise _Unsupported
            merged[shared] = event
            prefix = forced(update, shared[0], -shared[1])
        else:
            prefix = list(update)
        # A trailing U is the next evaluation after the callback; it keeps the
        # committed slot equal to the current value for trigger readers.
        body = [*prefix, *event.body, *update] if before else [*prefix, *update, *event.body, *update]
        charge('callback', len(body))
        new_events.append(replace(event, body=tuple(body) + tuple(closing)))

    # A mathematical affine zero need not be a program-RN boundary. For
    # example V(u)+2**53 can round to 2**53 on both sides of V(u)==0.
    # Earlier reads and shared-root callbacks need a separate frame proof.
    preparations = None
    if model.procedure:
        charge('procedure_preparation_scope', 5 + len(atoms) + len(runtime))
        direct_atoms = all(
            item.left.op == 'voltage' and len(item.left.args) == 2
            and item.left.args[0].op == item.left.args[1].op == 'node'
            and compiler.node_ids.get(str(item.left.args[1].value)) == 0
            and compiler.node_ids.get(str(item.left.args[0].value)) in compiler.allowed_condition_nodes
            and compiler.node_ids.get(str(item.left.args[0].value)) != 0
            and item.right.op == 'number'
            for item, _, _ in atoms)
        if len(classes) == 1 and first == 0 and not merged and direct_atoms \
                and all(_position(event) > end for event in runtime) \
                and _unconstrained_probe(compiler,
                    compiler.node_ids[str(atoms[0][0].left.args[0].value)], charge):
            preparations = []

    for index, (_, guard, origin) in enumerate(classes):
        for direction in (1, -1):
            if (index, direction) in merged:
                continue
            number = Expr('number', 1., (), origin)
            setting = number if direction > 0 else Expr('unary-', None, (number,), origin)
            previous = tuple(forced(update, index, -direction))
            body = (*previous, *update, *closing)
            charge('atom_event', len(body))
            new_events.append(Event((Trigger('cross', (guard, setting), origin),), body, origin))
            if preparations is not None:
                charge('atom_preparation', 8 + len(previous) + len(closing))
                preparations.append(replace(new_events[-1], body=(*previous, *closing)))

    initial = list(model.initial)
    if initial_events:
        # Keep a separate initial_step event body: append U to the last one.
        last_event = initial_events[-1]
        new_events = [replace(e, body=tuple(e.body) + tuple(update)) if e is last_event else e
                      for e in new_events]
    else:
        initial.extend(update)

    if model.procedure:
        # In the admitted direct-probe slice, a crossing reconstructs the left-side
        # value U(slot, pre). The source procedure then evaluates U(root) at
        # its original position. Queries execute neither of these gates and
        # must not commit their temporary ordinary values.
        wakeups = (tuple(preparations) if preparations is not None else
                   tuple(replace(event, body=tuple(closing))
                         for event in new_events[len(events):]))
        compiler.ordinary_held_process_slots = frozenset(held)
        charge('procedure_wakeups', len(wakeups) + sum(len(e.body) for e in wakeups))
        procedure = ((*wakeups, *model.procedure) if preparations is not None else
                     (*model.procedure, *wakeups))
        return replace(model, events=[*events, *wakeups], procedure=procedure)

    mapping = {name: name + SUFFIX for name in held}
    if any(alias in model.variables or alias in model.parameters for alias in mapping.values()):
        raise _Unsupported
    current = [Assignment(mapping[name], Expr('parameter', name, (), token), token) for name in sorted(held)]
    current.extend(_rename_statement(item, mapping, targets=True) for item in update)
    rest = [_rename_statement(item, mapping) for item in ordinary if item not in update]
    variables = dict(model.variables)
    variables.update({mapping[name]: model.variables[name] for name in held})
    charge('rewrite', len(current) + len(rest) + len(new_events))
    return replace(model, analog=[*current, *rest], initial=initial, events=new_events,
                   variables=variables)
