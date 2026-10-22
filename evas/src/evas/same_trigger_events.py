"""Join identically triggered event blocks of one module, in source order.

The analog block executes sequentially (LRM 2.4): when two ``@(...)``
statements with the same event expression fire at one time, the later body
runs after the earlier one and reads its writes. EVAS evaluates each block of
a batch from the pre-event state and refuses a block that reads another
block's same-batch write, so such programs were rejected. Appending the later
body to the earlier block reproduces the sequential order exactly.

Only blocks separated by other event statements qualify (no ordinary
statement, contribution or other analog code between them), so both observe
the same ordinary values. A body moved across intervening events must consist
of assignments, conditionals and loops only: no display output can change
order, and any same-time state interaction with an intervening block remains
refused by the kernel's batch reader/writer checks.
"""
from dataclasses import fields, is_dataclass, replace

from .syntax import Assignment, Conditional, Event, Loop, Token, While

_UNTIMED = ("initial_step", "final_step")


def _same(a, b):
    """Structural equality that ignores source positions."""
    if isinstance(a, Token) and isinstance(b, Token):
        return True
    if type(a) is not type(b):
        return False
    if isinstance(a, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if is_dataclass(a):
        return all(_same(getattr(a, f.name), getattr(b, f.name))
                   for f in fields(a) if f.name not in ("token", "expansion"))
    return a == b


def _movable(body):
    for item in body:
        if isinstance(item, Assignment):
            continue
        if isinstance(item, Conditional):
            if not (_movable(item.then_body) and _movable(item.else_body)):
                return False
        elif isinstance(item, (Loop, While)):
            if not _movable(item.body):
                return False
        else:
            return False
    return True


def _timed(event):
    return not any(trigger.kind in _UNTIMED for trigger in event.triggers)


def join_same_trigger_events(model):
    analog = list(model.analog)
    result = []
    run = []  # indices into result of the current run of adjacent events
    for item in analog:
        if not isinstance(item, Event):
            run = []
            result.append(item)
            continue
        target = None
        if _timed(item):
            for position, index in enumerate(run):
                earlier = result[index]
                if not _timed(earlier) or not _same(earlier.triggers, item.triggers):
                    continue
                adjacent = position == len(run) - 1
                scopes = model.local_alias_scopes
                arrays = model.local_array_alias_scopes
                if ((adjacent or _movable(item.body))
                        and scopes.get(earlier.token) == scopes.get(item.token)
                        and arrays.get(earlier.token) == arrays.get(item.token)):
                    target = index
                break
        if target is None:
            run.append(len(result))
            result.append(item)
        else:
            result[target] = replace(result[target], body=(*result[target].body, *item.body))
    if len(result) == len(analog):
        return model
    return replace(model, analog=result)
