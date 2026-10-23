"""idt assert pulses written by monitored events (LRM 2.4 section 4.5.4, #230).

``reset = 0; @(timer(...)) reset = 1; V(y) <+ idt(x, c, reset);`` is the LRM
ramp_generator. Every evaluation clears the assert; the event sets it, and the
idt call that follows in source order reads 1 only in the evaluation at the
event instant. LRM: "Once assert becomes zero, idt() returns the integral of
the argument starting from the last instant where assert was nonzero", so the
integral restarts from c at every such instant.

Ordinary evaluation reads the ordinary current alias (0) and the event value
lives only in the event state slot, so the plain lowering loses the instants.
A level reset cannot express a zero-length assert. The admitted slice is lowered
with existing certified IR only:

* a hidden integer parity ``p`` (initial 0) is toggled at the end of each
  pulsing event body when the assert value at the call site is nonzero; the
  body first restores the ordinary value, which the source executes before it;
* ``idt(x, c, assert) = A + (B - c)`` with ``A = idt(x, c, p)`` and
  ``B = idt(x, c, 1 - p)``.

At every instant exactly one of A and B is held at exactly c by its level
reset; the other was released at the last toggle (or integrates from t=0), so
A + (B - c) = c + integral from the last pulse. Two pulsing blocks in the same
instant both write ``p`` and remain the existing same-time writer conflict.

Admitted: a bare integer assert with exactly one unconditional top-level
ordinary writer whose value is an instance constant, set in cross/timer
callbacks that lie between that writer and the call. A constant nonzero
ordinary value holds c throughout and keeps the plain lowering. Other forms
whose event-instant value can differ from the ordinary value (copies through
locals, expressions, final_step, several or conditional ordinary writers,
macro or cross-file source order) are refused. Pure event states (no ordinary
writer) keep the existing level-reset path.
"""
from dataclasses import dataclass, replace

from .errors import CompileError
from .ir import Affine, Assignment, Binary, Conditional, Idt, OperatorRef, Origin, State, StateRef
from .lowering import lower
from .syntax import Assignment as SyntaxAssignment, Conditional as SyntaxConditional, Loop


@dataclass(frozen=True)
class Plan:
    slot: int
    events: tuple[int, ...]
    ordinary: float


def _fail(compiler, expr, message):
    raise CompileError(f"{compiler.model.source}:{expr.token.line}:{expr.token.column}: idt assert {message}",
                       code='unsupported_idt_pulse_reset', token=expr.token, instance=compiler.instance.name)


def _before(first, second):
    """Strict source order, or None when the tokens are not comparable."""
    if first.source != second.source or first.expansion or second.expansion:
        return None
    return (first.line, first.column) < (second.line, second.column)


def _reads(expr, names):
    if expr is None:
        return
    if expr.op == 'parameter':
        names.add(expr.value)
    for arg in expr.args:
        _reads(arg, names)


def _writers(statements, name, guards=(), top=True):
    """Yield (statement, enclosing guard expressions, top-level) for writes of name."""
    for item in statements:
        if isinstance(item, (SyntaxAssignment, Loop)) and item.name == name:
            yield item, guards, top
        if isinstance(item, SyntaxConditional):
            inner = (*guards, item.left, item.right)
            yield from _writers(item.then_body, name, inner, False)
            yield from _writers(item.else_body, name, inner, False)
        elif isinstance(item, Loop):
            yield from _writers(item.body, name, (*guards, item.start, item.limit, item.update), False)


def _writes(statements, name):
    return next(_writers(statements, name), None) is not None


def plan(compiler, expr, resolve):
    """Return a Plan, None for the existing lowering, or raise a refusal."""
    model, call, argument = compiler.model, expr.token, expr.args[2]
    events = list(enumerate(model.events))

    def event_writers(name):
        return [(index, event) for index, event in events if _writes(event.body, name)]

    def ordinary_writers(name):
        return list(_writers(model.analog, name))

    def maybe_before_call(event):
        order = _before(event.token, call)
        return order is None or order

    # Every variable whose value can reach the assert through ordinary writes.
    direct = argument.value if argument.op == 'parameter' and argument.value in model.variables else None
    pending, seen = set(), set()
    _reads(argument, pending)
    while pending:
        name = pending.pop()
        if name in seen or name not in model.variables:
            continue
        seen.add(name)
        for statement, guards, _ in ordinary_writers(name):
            for item in (*guards, getattr(statement, 'rhs', None), getattr(statement, 'start', None),
                         getattr(statement, 'limit', None), getattr(statement, 'update', None)):
                _reads(item, pending)
    for name in seen - {direct}:
        if ordinary_writers(name) and any(maybe_before_call(event) for _, event in event_writers(name)):
            _fail(compiler, expr, f"reads {name!r}, which an event sets before this call and an ordinary "
                  "statement also writes; only a bare integer assert can be lowered at event instants")
    if direct is None:
        return None
    writers = ordinary_writers(direct)
    if not writers:
        return None  # Pure event state: the existing level reset owns it.
    single = writers[0][0] if len(writers) == 1 and writers[0][2] else None
    pulsing = []
    for index, event in event_writers(direct):
        if single is None or single.index is not None:
            if maybe_before_call(event):
                pulsing.append((index, event))
            continue
        written_first = _before(single.token, event.token)
        before_call = _before(event.token, call)
        written_after = _before(call, single.token)
        if None in (written_first, before_call, written_after):
            pulsing.append((index, event))
        elif before_call and (written_first or written_after):
            pulsing.append((index, event))
    if not pulsing:
        return None
    if single is None or single.index is not None:
        _fail(compiler, expr, f"{direct!r} is set by an event and needs exactly one unconditional top-level "
              "ordinary assignment to be lowered at event instants")
    if (model.variables[direct] != 'integer' or direct not in compiler.state_ids
            or direct not in compiler.ordinary_alias_variables):
        _fail(compiler, expr, f"{direct!r} set by an event must be an integer cleared by an ordinary assignment")
    if not _before(single.token, call):
        _fail(compiler, expr, f"{direct!r} must be assigned before the idt call")
    for _, event in pulsing:
        if not _before(single.token, event.token) or not _before(event.token, call):
            _fail(compiler, expr, f"{direct!r} event and ordinary assignment order is not provable")
        if any(trigger.kind not in ('cross', 'timer') for trigger in event.triggers):
            _fail(compiler, expr, f"{direct!r} set at final_step or another unsupported event instant")
    ordinary = lower(argument, resolve, {}, model.source, preserve_structure=True)
    if not isinstance(ordinary, Affine) or ordinary.terms:
        _fail(compiler, expr, f"{direct!r} ordinary value must be an instance constant when an event sets it")
    if ordinary.constant != 0:
        return None  # Nonzero at every other instant: the output is IC throughout.
    return Plan(compiler.state_ids[direct], tuple(index for index, _ in pulsing), ordinary.constant)


def emit(compiler, plan, expr, value, ic, origin):
    """Append the parity state, two level-reset idts and the event toggles.

    Operator identity is the call site. A keeps the idt token; B, the
    complementary history, is identified by the assert argument token, which no
    other operator call can occupy.
    """
    compilation, make = compiler.compilation, compiler.make_ir
    argument = expr.args[2].token
    complement = make(Origin, argument.source or compiler.model.source, argument.line, argument.column,
                      compiler.instance.name, expr.args[2].expansion or origin.expansion)
    first = len(compilation.events) - len(compiler.model.events)
    for index in plan.events:
        token = compiler.model.events[index].token
        event = compilation.events[first + index]
        if (event.origin.line, event.origin.column, event.origin.instance) != (token.line, token.column, compiler.instance.name):
            raise CompileError("idt assert pulse lost its event identity", code='unsupported_idt_pulse_reset',
                               token=token, instance=compiler.instance.name)
    slot = compilation.states[plan.slot]
    parity = len(compilation.states)
    compilation.states.append(make(State, compiler.instance.name,
                                   f"{slot.name}@idt_pulse{len(compilation.operators)}", 'integer', 0.0))
    zero, one, minus = make(Affine, 0.0, ()), make(Affine, 1.0, ()), make(Affine, -1.0, ())
    flipped = make(Binary, 'add', one, make(Binary, 'multiply', minus, make(StateRef, parity)))
    flip = (make(Assignment, parity, flipped),)
    assert_value = make(StateRef, plan.slot)
    # Integer assert != 0, written with the IR's ordered relations.
    toggle = make(Conditional, 'ge', assert_value, zero,
                  (make(Conditional, 'le', assert_value, zero, (), flip, origin),), flip, origin)
    restored = getattr(compiler, 'idt_pulse_restored', set())
    compiler.idt_pulse_restored = restored
    for index in plan.events:
        event = compilation.events[first + index]
        body = (*event.body, toggle)
        if (first + index, plan.slot) not in restored:
            restored.add((first + index, plan.slot))
            body = (make(Assignment, plan.slot, make(Affine, plan.ordinary, ())), *body)
        compilation.events[first + index] = replace(event, body=body)
    held = len(compilation.operators)
    compilation.operators.append(make(Idt, value, ic, origin, make(StateRef, parity)))
    compilation.operators.append(make(Idt, value, ic, complement, flipped))
    complement_ref = make(OperatorRef, held + 1)
    # A + (B - c): B - c is exactly 0 while B is held, and no intermediate
    # adds two copies of a large IC.
    offset = complement_ref if ic == 0 else make(Binary, 'add', complement_ref, make(Affine, -ic, ()))
    return make(Binary, 'add', make(OperatorRef, held), offset)
