"""Normalize a narrow rational guard under an explicit positive path bound.

This module does not broaden the value evaluator or infer numerical bounds from
samples. Facts belong to the source branch where they were derived. The caller
must retain ordinary source audits and the existing IR/resource checks.
"""
from dataclasses import dataclass
import math

from .ir import Affine, Binary, Power, Select
from .errors import CompileError
from .limits import check_ir


@dataclass(frozen=True)
class PositiveFact:
    expression: Affine
    lower: float

    def __post_init__(self):
        if not _finite_affine(self.expression) or not math.isfinite(self.lower) or self.lower <= 0:
            raise ValueError("a positive fact requires a finite affine expression and positive finite lower bound")


def _finite_affine(value):
    return (isinstance(value, Affine) and math.isfinite(value.constant)
            and all(math.isfinite(term.coefficient) for term in value.terms))


def _affine_degree(value, memo=None):
    # Match the existing structural affine scope without folding dependencies.
    memo = {} if memo is None else memo
    key = id(value)
    if key in memo:
        return memo[key]
    degree = None
    if _finite_affine(value):
        degree = int(bool(value.terms))
    elif isinstance(value, Binary) and value.op in ("add", "multiply"):
        left, right = _affine_degree(value.left, memo), _affine_degree(value.right, memo)
        if left is not None and right is not None:
            candidate = max(left, right) if value.op == "add" else left + right
            degree = candidate if candidate <= 1 else None
    elif isinstance(value, Power) and value.exponent == 1:
        degree = _affine_degree(value.base, memo)
    elif isinstance(value, Select):
        degrees = [_affine_degree(item, memo) for item in
                   (value.left, value.right, value.then_value, value.else_value)]
        if all(item is not None for item in degrees):
            degree = max(degrees)
    memo[key] = degree
    return degree


def _constant(value):
    return _finite_affine(value) and not value.terms


def condition_positive_facts(relation, left, right, facts=()):
    """Return true/false path facts from one already-bound affine comparison.

    A strictly positive finite threshold is required even for a strict guard.
    Thus d > 0 alone stays outside this first supported scope. Facts use the
    bound voltage expression, so overwriting a source alias cannot reuse a fact
    about a different expression. No cancellation or alias-name matching occurs.
    """
    yes, no = tuple(facts), tuple(facts)
    if _constant(left) and _finite_affine(right) and right.terms:
        left, right = right, left
        relation = {"lt": "gt", "le": "ge", "gt": "lt", "ge": "le"}.get(relation)
    if not (_finite_affine(left) and left.terms and _constant(right)
            and right.constant > 0):
        return yes, no
    fact = PositiveFact(left, right.constant)
    if relation in ("gt", "ge"):
        yes += (fact,)
    elif relation in ("lt", "le"):
        no += (fact,)
    return yes, no


def positive_lower_bound(value, facts=()):
    """Prove positivity for every arm of an already-audited affine Select tree.

    Each arm receives only its own guard facts. The result is a bound on the
    selected value; arm facts never become facts about other voltage expressions.
    """
    degree_memo, bound_memo = {}, {}

    def bound(item, path_facts):
        key = (id(item), path_facts)
        if key in bound_memo:
            return bound_memo[key]
        result = None
        if _constant(item):
            result = item.constant if item.constant > 0 else None
        elif _finite_affine(item):
            matches = [fact.lower for fact in path_facts if fact.expression == item]
            result = max(matches) if matches else None
        elif isinstance(item, Select) and _affine_degree(item, degree_memo) is not None:
            yes, no = condition_positive_facts(item.relation, item.left, item.right, path_facts)
            left, right = bound(item.then_value, yes), bound(item.else_value, no)
            if left is not None and right is not None:
                result = min(left, right)
        bound_memo[key] = result
        return result

    return bound(value, tuple(facts))


def _normalize_direct_quotient_comparison(relation, left, right, facts=()):
    """Return an affine-equivalent guard or None when this scope cannot prove it.

    Only a piecewise-affine numerator over a piecewise-affine denominator, compared with a finite
    node-free constant, is supported. Path facts or the denominator's own Select
    arms must establish its positive lower bound. Multiplication remains explicit in IR;
    the caller's existing certified arithmetic handles its rounding, overflow
    and uncertainty. The quotient value arm is never replaced or evaluated here.
    """
    if relation not in ("lt", "le", "gt", "ge"):
        return None
    if _constant(left) and isinstance(right, Binary) and right.op == "divide":
        left, right = right, left
        relation = {"lt": "gt", "le": "ge", "gt": "lt", "ge": "le"}[relation]
    if not (isinstance(left, Binary) and left.op == "divide" and _constant(right)
            and _affine_degree(left.left) is not None and _affine_degree(left.right) is not None):
        return None
    if positive_lower_bound(left.right, facts) is None:
        return None
    return relation, left.left, Binary("multiply", right, left.right)


def normalize_positive_quotient_comparison(relation, left, right, facts=()):
    """Normalize a direct quotient or distribute a constant comparison over Select.

    Distribution follows only value arms, preserving every original guard. Each
    leaf must already be affine or satisfy the direct positive-divisor rule.
    General rational arithmetic is outside this scope. Counts describe the
    expanded tree, including repeated occurrences of shared Python objects.
    """
    direct = _normalize_direct_quotient_comparison(relation, left, right, facts)
    if direct is not None:
        return direct
    if relation not in ("lt", "le", "gt", "ge"):
        return None
    if _constant(left) and isinstance(right, Select):
        left, right = right, left
        relation = {"lt": "gt", "le": "ge", "gt": "lt", "ge": "le"}[relation]
    if not (isinstance(left, Select) and _constant(right)):
        return None
    if _affine_degree(left) is not None:
        # Preserve the existing representation and budgets of supported guards.
        return None
    # Audit the original expanded operands before a comparison can replace them.
    check_ir((left, right), left.origin)
    leaf_count = 0
    zero, one = Affine(0.0, ()), Affine(1.0, ())

    def compare(value, path_facts):
        nonlocal leaf_count
        if isinstance(value, Select):
            if _affine_degree(value.left) is None or _affine_degree(value.right) is None:
                return None
            yes, no = condition_positive_facts(value.relation, value.left, value.right, path_facts)
            then_value = compare(value.then_value, yes)
            else_value = compare(value.else_value, no)
            if then_value is None or else_value is None:
                return None
            result = Select(value.relation, value.left, value.right, then_value, else_value, value.origin)
        else:
            leaf_count += 1
            if leaf_count > 4096:
                raise CompileError("expanded selected comparison budget (4096 leaves) exceeded", code="resource_budget")
            guard = _normalize_direct_quotient_comparison(relation, value, right, path_facts)
            if guard is None:
                if _affine_degree(value) is None:
                    return None
                guard = relation, value, right
            result = Select(*guard, one, zero, left.origin)
        check_ir(result, left.origin)
        return result

    result = compare(left, tuple(facts))
    return ("gt", result, Affine(0.5, ())) if result is not None else None
