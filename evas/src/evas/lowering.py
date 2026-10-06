"""Bind arithmetic to polynomial IR, preserving the affine constant-folding path."""
import math
from typing import Callable, Mapping

from .ir import Affine, Binary, Expression, OperatorRef, Power, Select, StateRef, Term
from .syntax import CompileError, Expr, OPERATOR_NAMES, DECISION_NAMES, contains_operator, contains_decision


def affine(constant, terms):
    return Affine(constant, tuple(Term(n, c) for n, c in sorted(terms.items()) if c != 0.0))


def scale(expression: Expression, factor: float) -> Expression:
    if factor == 1.0:
        return expression
    if isinstance(expression, Affine):
        return affine(expression.constant * factor, {t.node: t.coefficient * factor for t in expression.terms})
    return Binary("multiply", Affine(factor, ()), expression)


def _has_bound_decision(expr: Expr, parameters) -> bool:
    """Inspect current bindings before a constant function result drops them."""
    def has_select(value):
        pending, seen = [value], set()
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, Select):
                return True
            if isinstance(item, Binary):
                pending.extend((item.left, item.right))
            elif isinstance(item, Power):
                pending.append(item.base)
        return False

    pending, seen = [expr], set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if item.op == "parameter" and has_select(parameters(str(item.value))):
            return True
        pending.extend(item.args)
    return False


def lower(expr: Expr, parameters: Callable[[str], float | Expression], nodes: Mapping[str, int],
          source: str, operators: Callable[[Expr], Expression] | None = None, preserve_structure: bool = False,
          decisions: Callable[..., Select] | None = None,
          validate_decision: Callable[[Expr, Expression], None] | None = None,
          decision_scope: bool = False, *, memo: dict | None = None) -> Expression:
    # Opt-in reuse for one fixed parameter/node binding without registration
    # callbacks. Callers own the lifetime and must not share across contexts.
    if memo is not None:
        if operators is not None or decisions is not None or validate_decision is not None:
            raise ValueError("lower memo cannot be used with semantic callbacks")
        key = (id(expr), preserve_structure, decision_scope)
        if key not in memo:
            value = _lower(expr, parameters, nodes, source, operators, preserve_structure,
                           decisions, validate_decision, decision_scope, memo)
            memo[key] = (expr, value)
        return memo[key][1]
    return _lower(expr, parameters, nodes, source, operators, preserve_structure,
                  decisions, validate_decision, decision_scope, None)


def _lower(expr, parameters, nodes, source, operators, preserve_structure,
           decisions, validate_decision, decision_scope, memo):
    def fail(message, *, code="compile_error"):
        raise CompileError(f"{expr.token.source or source}:{expr.token.line}:{expr.token.column}: {message}",
                           code=code, token=expr.token)

    if expr.op == "checked":
        scope = decision_scope or contains_decision(expr) or _has_bound_decision(expr, parameters)
        if scope and decisions is None:
            fail("decision expressions are only supported in stateless ordinary analog expressions")
        values = [lower(arg, parameters, nodes, source, operators,
                        preserve_structure or scope, decisions, validate_decision, scope, memo=memo)
                  for arg in expr.args]
        if scope and validate_decision is not None:
            for arg, value in zip(expr.args, values):
                validate_decision(arg, value)
        # Obligations are compile-time structure checks, never runtime Selects.
        return values[0]

    if expr.op in DECISION_NAMES:
        if decisions is None:
            fail("decision expressions are only supported in stateless ordinary analog expressions")
        if contains_operator(expr):
            fail("decision expressions do not support waveform operators in any operand or arm")
        values = [lower(arg, parameters, nodes, source, operators, True, decisions, validate_decision, True, memo=memo) for arg in expr.args]
        zero, one = Affine(0.0, ()), Affine(1.0, ())
        def select(relation, left, right, then_value, else_value):
            return decisions(expr, relation, left, right, then_value, else_value)
        def choose(value, then_value, else_value):
            return select("gt", value, zero, then_value,
                          select("lt", value, zero, then_value, else_value))
        if expr.op in ("<", "<=", ">", ">="):
            return select({"<":"lt", "<=":"le", ">":"gt", ">=":"ge"}[expr.op], values[0], values[1], one, zero)
        if expr.op == "unary!":
            return choose(values[0], zero, one)
        if expr.op == "ternary":
            return choose(values[0], values[1], values[2])
        truth = choose(values[1], one, zero)
        return choose(values[0], truth, zero) if expr.op == "&&" else choose(values[0], one, truth)

    if expr.op in OPERATOR_NAMES:
        if operators is None:
            fail("waveform operators are only allowed in contributions; nesting is unsupported")
        return operators(expr)
    if expr.op == "call":
        fail(f"unknown analog function {expr.value!r}")
    if expr.op == 'index':
        fail('array index requires scalarization before semantic lowering')
    if expr.op == "array":
        fail("standard array literals are only supported as laplace_nd coefficient lists")
    if expr.op == "number":
        return Affine(float(expr.value), ())
    if expr.op == "parameter":
        value = parameters(str(expr.value))
        return value if isinstance(value, (Affine, Binary, Power, Select, StateRef, OperatorRef)) else Affine(value, ())
    if expr.op == "voltage":
        p, n = (str(arg.value) for arg in expr.args)
        if p not in nodes or n not in nodes:
            fail(f"undeclared electrical node in V({p},{n})", code="undeclared_node")
        if preserve_structure and nodes[p] == nodes[n]:
            return Binary("add", Affine(0.0, (Term(nodes[p], 1.0),)),
                          Affine(0.0, (Term(nodes[n], -1.0),)))
        return affine(0.0, {} if nodes[p] == nodes[n] else {nodes[p]: 1.0, nodes[n]: -1.0})
    values = [lower(arg, parameters, nodes, source, operators, preserve_structure, decisions, validate_decision, decision_scope, memo=memo) for arg in expr.args]
    a = values[0]
    if expr.op.startswith("unary"):
        result = scale(a, -1.0 if expr.op == "unary-" else 1.0)
    else:
        b = values[1]
        both_affine = isinstance(a, Affine) and isinstance(b, Affine)
        if both_affine and preserve_structure and (a.terms or b.terms):
            both_affine = False
        if expr.op in ("+", "-"):
            sign = 1.0 if expr.op == "+" else -1.0
            if both_affine:
                terms = {t.node: t.coefficient for t in a.terms}
                for t in b.terms:
                    terms[t.node] = terms.get(t.node, 0.0) + sign * t.coefficient
                result = affine(a.constant + sign * b.constant, terms)
            else:
                result = Binary("add", a, scale(b, sign))
        elif expr.op == "*":
            if both_affine and not (a.terms and b.terms):
                factor = b.constant if a.terms else a.constant
                result = affine(a.constant * b.constant,
                                {t.node: t.coefficient * factor for t in (a.terms or b.terms)})
            else:
                result = Binary("multiply", a, b)
        elif expr.op == "/":
            if not isinstance(b, Affine) or b.terms or b.constant == 0:
                fail("division requires a nonzero constant denominator")
            # Keep division, rather than multiplication by a reciprocal, on
            # the affine path so its existing rounding behavior is preserved.
            if isinstance(a, Affine) and not (preserve_structure and a.terms):
                result = affine(a.constant / b.constant, {t.node: t.coefficient / b.constant for t in a.terms})
            else:
                reciprocal = 1.0 / b.constant
                if not math.isfinite(reciprocal):
                    fail("nonfinite coefficient during constant folding")
                result = Binary("multiply", Affine(reciprocal, ()), a) if preserve_structure else scale(a, reciprocal)
        elif expr.op == "power":
            if (not isinstance(b, Affine) or b.terms or not b.constant.is_integer()
                    or not 1 <= b.constant <= 32):
                fail("pow exponent must be an instance-constant integer in [1,32]")
            exponent = int(b.constant)
            if isinstance(a, Affine) and not a.terms:
                try:
                    result = Affine(a.constant ** exponent, ())
                except OverflowError:
                    fail("nonfinite coefficient during constant folding")
            elif exponent == 1:
                result = a
            else:
                result = Power(a, exponent)
        else:
            fail(f"unsupported arithmetic {expr.op!r}")
    if isinstance(result, Affine) and not all(math.isfinite(x) for x in
            (result.constant, *(t.coefficient for t in result.terms))):
        fail("nonfinite coefficient during constant folding")
    return result
