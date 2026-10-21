"""Paid constant arithmetic composition over an already certified integer table.

No guard is transformed or removed. Ineligible tables retain the old producer.
The instance owner proves source typing, signed32 ranges and quotient bins first.
"""
import math

from .integer_arithmetic import truncating_division
from .ir import Affine, Select
from .limits import MAX_IR_ITEMS

MINIMUM, MAXIMUM = -2147483648, 2147483647

class _NoProbeRoom(Exception):
    pass

def _reserve(owner, source, kind, amount=1):
    # Stop an optional inactive probe BEFORE work or a debit that cannot fit.
    # Once active, an actual owner refusal propagates without fallback.
    if not owner.active and owner.used + amount > MAX_IR_ITEMS:
        raise _NoProbeRoom
    owner.debit(kind, amount, source)

def compose_integer_table(expression, operation, divisor, *, owner, source, make):
    if not isinstance(expression, Select) or operation not in ('/', '%'):
        return None

    try:
        # This is the mandatory IR walk's paid structural fact, not a semantic
        # range/role certificate. The strong reference prevents id reuse, and
        # transitive immutability excludes mutable descendants. Guards remain
        # identical objects for every original source and Rust consumer below.
        _reserve(owner, source, 'integer_compose_guard_fact_lookup', 4)
        fact = owner.ir_cache.get(id(expression))
        if fact is None or fact[0] is not expression or not fact[1][2]:
            return None
        _reserve(owner, source, 'integer_compose_containers', 2)
        pending, memo = [], {}
        _reserve(owner, source, 'integer_compose_pending', 2)
        pending.append((expression, False))
        while pending:
            _reserve(owner, source, 'integer_compose_pop')
            value, exiting = pending.pop()
            _reserve(owner, source, 'integer_compose_lookup')
            entry = memo.get(id(value))
            if entry is not None:
                assert entry[0] is value
                continue
            if not exiting:
                _reserve(owner, source, 'integer_compose_fields', 8)
                if isinstance(value, Select):
                    # Do not inspect/requalify left/right. They are copied by
                    # identity, never simplified, even if mapped arms coincide.
                    _reserve(owner, source, 'integer_compose_pending', 6)
                    pending.append((value, True))
                    pending.extend(((value.then_value, False), (value.else_value, False)))
                    continue
            # Retain the old analysis prepayment for every remaining node.
            # Only guard subtrees and their lookups/traversals were removed.
            _reserve(owner, source, 'integer_compose_analysis', 32)
            bounds, table = None, False
            if isinstance(value, Affine):
                if (not value.terms and math.isfinite(value.constant)
                        and value.constant.is_integer()
                        and MINIMUM <= value.constant <= MAXIMUM):
                    number = int(value.constant)
                    bounds, table = (number, number), True
            elif isinstance(value, Select):
                _reserve(owner, source, 'integer_compose_child_lookup', 2)
                yes, no = memo[id(value.then_value)], memo[id(value.else_value)]
                if yes[2] and no[2]:
                    bounds = min(yes[1][0], no[1][0]), max(yes[1][1], no[1][1])
                    table = True
            # Checked nodes, StateRef and every nonconstant VALUE leaf cannot
            # disappear. Their presence keeps the old arithmetic producer.
            _reserve(owner, source, 'integer_compose_memo_insert', 4)
            memo[id(value)] = value, bounds, table
        _reserve(owner, source, 'integer_compose_lookup')
        if not memo[id(expression)][2]:
            return None
    except _NoProbeRoom:
        return None

    # Every successful probe cost remains charged when aggregate enforcement
    # begins. No new allowance, memo owner, reset or refund is introduced.
    owner.activate(source)
    _reserve(owner, source, 'integer_compose_emit_containers', 4)
    pending, mapped = [(expression, False)], {}
    while pending:
        _reserve(owner, source, 'integer_compose_emit_pop')
        value, exiting = pending.pop()
        _reserve(owner, source, 'integer_compose_emit_lookup')
        if id(value) in mapped:
            continue
        if isinstance(value, Select) and not exiting:
            _reserve(owner, source, 'integer_compose_emit_pending', 6)
            pending.append((value, True))
            pending.extend(((value.then_value, False), (value.else_value, False)))
            continue
        _reserve(owner, source, 'integer_compose_emit_entry', 4)
        if isinstance(value, Select):
            _reserve(owner, source, 'integer_compose_emit_child_lookup', 2)
            result = make(Select, value.relation, value.left, value.right,
                          mapped[id(value.then_value)], mapped[id(value.else_value)], value.origin)
        else:
            _reserve(owner, source, 'integer_compose_leaf_arithmetic', 12)
            number = int(value.constant)
            quotient = truncating_division(number, divisor)
            result = make(Affine, float(quotient if operation == '/' else number-divisor*quotient), ())
        mapped[id(value)] = result
    _reserve(owner, source, 'integer_compose_emit_lookup')
    return mapped[id(expression)]
