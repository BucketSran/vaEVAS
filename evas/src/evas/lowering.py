"""Bind arithmetic to polynomial IR, preserving the affine constant-folding path."""
import math

from .ir import Affine, Binary, Expression, Power, StateRef, Term
from .syntax import CompileError, Expr


def affine(constant, terms):
    return Affine(constant, tuple(Term(n, c) for n, c in sorted(terms.items()) if c != 0.0))


def scale(expression: Expression, factor: float) -> Expression:
    if isinstance(expression, Affine):
        return affine(expression.constant * factor, {t.node: t.coefficient * factor for t in expression.terms})
    return Binary("multiply", Affine(factor, ()), expression)


def lower(expr: Expr, parameters, nodes, source: str, operators=None, preserve_structure=False) -> Expression:
    def fail(message):
        raise CompileError(f"{source}:{expr.token.line}:{expr.token.column}: {message}")

    if expr.op in ("transition", "slew"):
        if operators is None:
            fail("waveform operators are only allowed in contributions; nesting is unsupported")
        return operators(expr)
    if expr.op == "number":
        return Affine(float(expr.value), ())
    if expr.op == "parameter":
        value = parameters(str(expr.value))
        return value if isinstance(value, StateRef) else Affine(value, ())
    if expr.op == "voltage":
        p, n = (str(arg.value) for arg in expr.args)
        if p not in nodes or n not in nodes:
            fail(f"undeclared electrical node in V({p},{n})")
        if preserve_structure and nodes[p] == nodes[n]:
            return Binary("add", Affine(0.0, (Term(nodes[p], 1.0),)),
                          Affine(0.0, (Term(nodes[n], -1.0),)))
        return affine(0.0, {} if nodes[p] == nodes[n] else {nodes[p]: 1.0, nodes[n]: -1.0})
    values = [lower(arg, parameters, nodes, source, operators, preserve_structure) for arg in expr.args]
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
