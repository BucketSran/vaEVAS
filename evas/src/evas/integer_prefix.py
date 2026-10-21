"""Share an already-checked ordinary integer prefix across a branch merge.

The caller audits both original source branches before merging and checks the
expanded returned IR with the original budgets. This is not real arithmetic
reassociation or a new integer conversion rule.
"""
import math

from .ir import Affine, Binary, Select


def _pure_integer_values(*values, guards=()):
    memo = {}

    def pure(value, integer):
        key = (id(value), integer)
        if key in memo:
            return memo[key]
        if isinstance(value, Affine):
            result = (math.isfinite(value.constant)
                      and all(math.isfinite(term.coefficient) for term in value.terms)
                      and (not integer or not value.terms and value.constant.is_integer()))
        elif isinstance(value, Binary) and value.op in ('add', 'multiply'):
            result = pure(value.left, integer) and pure(value.right, integer)
        elif isinstance(value, Select):
            result = (pure(value.left, False) and pure(value.right, False)
                      and pure(value.then_value, integer) and pure(value.else_value, integer))
        else:
            # In particular, never move state, operators, event values,
            # checked arithmetic/index wrappers, or unknown IR variants.
            result = False
        memo[key] = result
        return result

    return (all(pure(value, True) for value in values)
            and all(pure(guard, False) for guard in guards))


def factor_integer_prefix(relation, left, right, then_value, else_value, origin,
                          *, integer_target, validate_integer):
    """Factor one identity-shared prefix; validate original arms before rewriting.

    ``integer_target`` must come from the declared ordinary local's type.
    ``validate_integer(value, origin)`` is the caller's existing integral and
    signed32 check, including all original branch assignment obligations.
    Structurally equal but distinct objects deliberately remain separate.
    """
    raw = Select(relation, left, right, then_value, else_value, origin)
    if not integer_target:
        return raw
    zero = Affine(0., ())
    if isinstance(then_value, Binary) and then_value.op == 'add' and then_value.left is else_value:
        prefix, yes, no = else_value, then_value.right, zero
    elif isinstance(else_value, Binary) and else_value.op == 'add' and else_value.left is then_value:
        prefix, yes, no = then_value, zero, else_value.right
    elif (isinstance(then_value, Binary) and isinstance(else_value, Binary)
          and then_value.op == else_value.op == 'add' and then_value.left is else_value.left):
        prefix, yes, no = then_value.left, then_value.right, else_value.right
    else:
        return raw
    if not _pure_integer_values(then_value, else_value, guards=(left, right)):
        return raw
    validate_integer(then_value, origin)
    validate_integer(else_value, origin)
    return Binary('add', prefix, Select(relation, left, right, yes, no, origin))
