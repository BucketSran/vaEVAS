"""Bind arithmetic to polynomial IR, preserving the affine constant-folding path."""
import math
from dataclasses import fields
from typing import Callable, Mapping

from .ir import EventMath, Origin, Affine, Binary, Expression, OperatorRef, Power, Select, StateRef, Term
from .syntax import CompileError, Expr, OPERATOR_NAMES, DECISION_NAMES, contains_operator, contains_decision


class UnsupportedConstantPower(CompileError):
    """Private classification from the original pow rejection traversal."""


def _make(work, cls, *args):
    if work is not None:
        work('lower_emit_object',1)
        work('lower_emit_field',len(fields(cls)))
    return cls(*args)


def affine(constant, terms, *, work=None):
    if work is not None: work('lower_affine_scan',len(terms))
    return _make(work, Affine, constant, tuple(_make(work,Term,n,c) for n,c in sorted(terms.items()) if c!=0.0))


def scale(expression: Expression, factor: float, *, work=None) -> Expression:
    if factor == 1.0:
        return expression
    if isinstance(expression, Affine):
        return affine(expression.constant * factor, {t.node: t.coefficient * factor for t in expression.terms}, work=work)
    return _make(work,Binary,"multiply",_make(work,Affine,factor,()),expression)


def _has_bound_decision(expr: Expr, parameters) -> bool:
    """Inspect current bindings before a constant function result drops them."""
    work = getattr(parameters,"native_work",None)
    def has_select(value):
        pending, seen = [value], set()
        while pending:
            item = pending.pop()
            if work is not None: work("bound_decision_visit",1)
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
        if work is not None: work("bound_decision_source",1)
        if id(item) in seen:
            continue
        seen.add(id(item))
        if item.op == "parameter" and has_select(parameters(str(item.value))):
            return True
        pending.extend(item.args)
    return False


def lower_decision(op, values, select, *, work=None):
    """Build the common decision tree after callers validate source operands."""
    zero, one = _make(work,Affine,0.0,()), _make(work,Affine,1.0,())
    def choose(value, then_value, else_value):
        def boolean_tree(item):
            if work is not None: work("boolean_visit",1)
            if isinstance(item, Affine):
                return not item.terms and item.constant in (0., 1.)
            return isinstance(item, Select) and boolean_tree(item.then_value) and boolean_tree(item.else_value)
        if isinstance(value, Select) and boolean_tree(value):
            # Validate all source arms first, then substitute boolean
            # leaves. Testing the generated 0/1 tree twice duplicates
            # every predicate and produces exponential wire expansion.
            select("gt", value, zero, then_value, else_value)
            def substitute(item):
                if work is not None: work("boolean_substitute",1)
                if isinstance(item, Affine):
                    return then_value if item.constant else else_value
                return select(item.relation, item.left, item.right,
                              substitute(item.then_value), substitute(item.else_value))
            return substitute(value)
        return select("gt", value, zero, then_value,
                      select("lt", value, zero, then_value, else_value))
    if op == "abs":
        return select("ge", values[0], zero, values[0], scale(values[0], -1., work=work))
    if op in ("min", "max"):
        return select("le" if op == "min" else "ge", values[0], values[1], values[0], values[1])
    if op in ("<", "<=", ">", ">="):
        return select({"<":"lt", "<=":"le", ">":"gt", ">=":"ge"}[op], values[0], values[1], one, zero)
    if op in ("==", "!="):
        yes, no = (one, zero) if op == "==" else (zero, one)
        return select("le", values[0], values[1],
                      select("ge", values[0], values[1], yes, no), no)
    if op == "unary!":
        return choose(values[0], zero, one)
    if op == "ternary":
        return choose(values[0], values[1], values[2])
    truth = choose(values[1], one, zero)
    return choose(values[0], truth, zero) if op == "&&" else choose(values[0], one, truth)


class FiniteIntegerUnavailable(CompileError):
    """The original route ran out of representation, not semantic validity."""


def lower(expr: Expr, parameters: Callable[[str], float | Expression], nodes: Mapping[str, int],
          source: str, operators: Callable[[Expr], Expression] | None = None, preserve_structure: bool = False,
          decisions: Callable[..., Select] | None = None,
          validate_decision: Callable[[Expr, Expression], None] | None = None,
          decision_scope: bool = False, indices: Callable[[Expr], Expression] | None = None, *,
          memo: dict | None = None,
          node_declarations: bool = False) -> Expression:
    work = getattr(parameters,"native_work",None)
    if work is not None: work("lower_source_visit",1)
    validator = getattr(parameters, "validate_integer_operation", None)
    depth = getattr(parameters, "integer_operation_depth", 0)
    if validator is not None:
        parameters.integer_operation_depth = depth + 1
    try:
        try:
            value = _lower_checked(expr, parameters, nodes, source, operators, preserve_structure,
                                   decisions, validate_decision, decision_scope, indices,
                                   memo=memo, node_declarations=node_declarations)
        except FiniteIntegerUnavailable:
            native = getattr(parameters, "native_integer", None)
            value = native(expr) if native is not None else None
            if value is None:
                raise
        if validator is not None:
            try:
                checked = validator(expr, value, root=depth == 0 and getattr(parameters, "allow_integer_assignment_root", False))
            except FiniteIntegerUnavailable:
                native = getattr(parameters, "native_integer", None)
                checked = native(expr) if native is not None else None
                if checked is None:
                    raise
            if checked is not None:
                value = checked
        return value
    finally:
        if validator is not None:
            parameters.integer_operation_depth = depth


def _lower_checked(expr, parameters, nodes, source, operators, preserve_structure,
                   decisions, validate_decision, decision_scope, indices, *, memo, node_declarations):
    # Only a caller with the complete declared electrical environment may label
    # a missing voltage node invalid. Closed constant/state contexts stay unknown.
    # This flag changes failure metadata only, never voltage acceptance or IR.
    # Opt-in reuse for one fixed parameter/node binding without registration
    # callbacks. Callers own the lifetime and must not share across contexts.
    if memo is not None:
        if operators is not None or decisions is not None or validate_decision is not None or indices is not None:
            raise ValueError("lower memo cannot be used with semantic callbacks")
        key = (id(expr), preserve_structure, decision_scope, getattr(parameters, "source_floor_operand", False))
        if key not in memo:
            value = _lower(expr, parameters, nodes, source, operators, preserve_structure,
                           decisions, validate_decision, decision_scope, indices, memo, node_declarations)
            memo[key] = (expr, value)
        value = memo[key][1]
    else:
        value = _lower(expr, parameters, nodes, source, operators, preserve_structure,
                       decisions, validate_decision, decision_scope, indices, None, node_declarations)
    return value


def _lower(expr, parameters, nodes, source, operators, preserve_structure,
           decisions, validate_decision, decision_scope, indices, memo, node_declarations):
    work = getattr(parameters,"native_work",None)
    if work is not None: work("lower_child_attachment",len(expr.args))
    def fail(message, *, code="compile_error", error=CompileError):
        raise error(f"{expr.token.source or source}:{expr.token.line}:{expr.token.column}: {message}",
                           code=code, token=expr.token)

    event_math = getattr(parameters, "event_math", None)
    sampled_values = getattr(parameters, "sampled_values", False)
    finite_integer = getattr(parameters, "finite_integer_expression", None)
    if finite_integer is not None:
        result = finite_integer(expr, nodes,
            (operators, preserve_structure, decisions, validate_decision, decision_scope, indices),
            {"node_declarations": node_declarations})
        if result is not None:
            return result
    if expr.op == 'floor':
        if len(expr.args) != 1:
            fail('floor requires one real argument', code='unsupported_floor')
        argument = lower(expr.args[0], parameters, nodes, source, operators, True,
                         decisions, validate_decision, decision_scope, indices,
                         node_declarations=node_declarations)
        finite_floor = getattr(parameters, 'finite_floor', None)
        if finite_floor is None:
            fail('floor requires a source-proven finite range', code='unsupported_floor')
        try:
            return finite_floor(expr, argument)
        except CompileError as error:
            source_floor = getattr(parameters, 'source_floor', None)
            if source_floor is None or error.diagnostic['code'] != 'unsupported_floor':
                raise
            def lower_operand(bindings):
                def retained(name):
                    return bindings[name] if name in bindings else parameters(name)
                retained.__dict__.update(getattr(parameters, '__dict__', {}))
                retained.source_floor_operand = True
                return lower(expr.args[0], retained, nodes, source, operators, True,
                             decisions, validate_decision, decision_scope, indices,
                             node_declarations=node_declarations)
            return source_floor(expr, lower_operand)
    if event_math is not None and expr.op in ("sqrt", "abs", "min", "max"):
        args = tuple(lower(arg, parameters, nodes, source, None, True,
                           decisions, validate_decision, False, indices,
                           node_declarations=node_declarations) for arg in expr.args)
        if all(isinstance(arg, Affine) and not arg.terms for arg in args):
            values = [arg.constant for arg in args]
            try:
                value = {"sqrt": lambda: math.sqrt(values[0]),
                         "abs": lambda: abs(values[0]),
                         "min": lambda: min(values),
                         "max": lambda: max(values)}[expr.op]()
            except (ValueError, OverflowError):
                # Invalid pure mathematics remains a selected-arm runtime check.
                pass
            else:
                if math.isfinite(value):
                    return _make(work,Affine,value, ())
        return event_math(expr, args)

    if expr.op == "checked":
        scope = decision_scope or contains_decision(expr,visit=(lambda item:work("decision_scan",1)) if work is not None else None) or _has_bound_decision(expr, parameters)
        if scope and decisions is None:
            fail("decision expressions are only supported in stateless ordinary analog expressions")
        values = [lower(arg, parameters, nodes, source, operators,
                        preserve_structure or scope, decisions, validate_decision, scope, indices, memo=memo, node_declarations=node_declarations)
                  for arg in expr.args]
        if scope and validate_decision is not None:
            for arg, value in zip(expr.args, values):
                validate_decision(arg, value)
        # Obligations are compile-time structure checks, never runtime Selects.
        return values[0]

    if expr.op in DECISION_NAMES:
        if decisions is None:
            fail("decision expressions are only supported in stateless ordinary analog expressions")
        if contains_operator(expr,visit=(lambda item:work("operator_scan",1)) if work is not None else None) and event_math is None:
            fail("decision expressions do not support waveform operators in any operand or arm")
        values = [lower(arg, parameters, nodes, source, operators, True, decisions, validate_decision, True, indices, memo=memo, node_declarations=node_declarations) for arg in expr.args]
        zero, one = _make(work,Affine,0.0,()), _make(work,Affine,1.0,())
        def select(relation, left, right, then_value, else_value):
            return decisions(expr, relation, left, right, then_value, else_value)
        return lower_decision(expr.op, values, select, work=work)

    bound_exponent = None
    if expr.op == "power":
        bound_exponent = lower(expr.args[1], parameters, nodes, source,
                               preserve_structure=preserve_structure, indices=indices,
                               memo=memo, node_declarations=node_declarations)
        exponent = bound_exponent
        if isinstance(exponent, Affine) and not exponent.terms and exponent.constant == 0.5:
            if decision_scope:
                fail("decision expressions do not support waveform operators in any operand or arm")
            return lower(Expr("sqrt", None, (expr.args[0],), expr.token, expr.expansion),
                         parameters, nodes, source, operators, preserve_structure,
                         decisions, validate_decision, decision_scope, indices,
                         memo=memo, node_declarations=node_declarations)
    if expr.op in ("cos", "exp", "ln", "sqrt", "tanh") and operators is None:
        argument = lower(expr.args[0], parameters, nodes, source,
                         preserve_structure=preserve_structure, memo=memo,
                         node_declarations=node_declarations)
        if not isinstance(argument, Affine) or argument.terms:
            fail("nonconstant mathematical functions require a waveform contribution")
        try:
            value = {"cos": math.cos, "exp": math.exp, "ln": math.log,
                     "sqrt": math.sqrt, "tanh": math.tanh}[expr.op](argument.constant)
        except (ValueError, OverflowError):
            fail("mathematical constant is outside the finite function domain")
        if not math.isfinite(value):
            fail("nonfinite mathematical constant")
        return _make(work,Affine,value, ())
    if expr.op in OPERATOR_NAMES:
        if operators is None:
            fail("waveform operators are only allowed in contributions; nesting is unsupported")
        return operators(expr)
    if expr.op == "call":
        fail(f"unknown analog function {expr.value!r}")
    if expr.op == 'index':
        if indices is not None:
            return indices(expr)
        fail('array index requires scalarization before semantic lowering')
    if expr.op == "array":
        fail("standard array literals are only supported as laplace_nd coefficient lists")
    if expr.op == "time":
        if "$abstime" not in nodes:
            fail("absolute time is unavailable in a constant expression")
        return _make(work,Affine,0., (_make(work,Term,nodes["$abstime"], 1.),))
    if expr.op == "number":
        return _make(work,Affine,float(expr.value), ())
    if expr.op == "parameter":
        value = parameters(str(expr.value))
        return value if isinstance(value, (Affine, Binary, Power, Select, StateRef, OperatorRef, EventMath)) else _make(work,Affine,value, ())
    if expr.op == "voltage":
        p, n = (str(arg.value) for arg in expr.args)
        if p not in nodes or n not in nodes:
            fail(f"undeclared electrical node in V({p},{n})",
                 code="undeclared_node" if node_declarations else "compile_error")
        if preserve_structure and nodes[p] == nodes[n]:
            return _make(work,Binary,"add", _make(work,Affine,0.0, (_make(work,Term,nodes[p], 1.0),)),
                          _make(work,Affine,0.0, (_make(work,Term,nodes[n], -1.0),)))
        return affine(0.0, {} if nodes[p] == nodes[n] else {nodes[p]: 1.0, nodes[n]: -1.0}, work=work)
    values = [bound_exponent if expr.op == "power" and i == 1 else
              lower(arg, parameters, nodes, source, operators, preserve_structure,
                    decisions, validate_decision, decision_scope, indices, memo=memo,
                    node_declarations=node_declarations)
              for i, arg in enumerate(expr.args)]
    a = values[0]
    from .integer_bits import OPS
    if expr.op in OPS:
        bitwise = getattr(parameters, "integer_bitwise", None)
        if bitwise is None:
            fail("bitwise expression requires typed integer binding", code="unsupported_integer_bitwise")
        return bitwise(expr, values)
    if expr.op.startswith("unary"):
        result = scale(a, -1.0 if expr.op == "unary-" else 1.0, work=work)
    else:
        b = values[1]
        both_affine = (isinstance(a, Affine) and isinstance(b, Affine)
                       and not getattr(parameters, "source_floor_operand", False))
        if both_affine and preserve_structure and (a.terms or b.terms):
            both_affine = False
        if expr.op in ("+", "-"):
            sign = 1.0 if expr.op == "+" else -1.0
            if both_affine:
                terms = {t.node: t.coefficient for t in a.terms}
                for t in b.terms:
                    terms[t.node] = terms.get(t.node, 0.0) + sign * t.coefficient
                result = affine(a.constant + sign * b.constant, terms, work=work)
            else:
                result = _make(work,Binary,"add", a, scale(b, sign, work=work))
        elif expr.op == "*":
            if both_affine and not (a.terms and b.terms):
                factor = b.constant if a.terms else a.constant
                result = affine(a.constant * b.constant,
                                {t.node: t.coefficient * factor for t in (a.terms or b.terms)})
            else:
                result = _make(work,Binary,"multiply", a, b)
        elif expr.op in ("/", "%"):
            integer_arithmetic = getattr(parameters, "integer_arithmetic", None)
            integer_result = integer_arithmetic(expr, a, b) if integer_arithmetic is not None else None
            if integer_result is not None:
                return integer_result
            if expr.op == "%":
                fail("modulo requires integer typed operands and a supported constant divisor")
            if not isinstance(b, Affine) or b.terms:
                if operators is None and event_math is None and not sampled_values:
                    fail("variable division requires an ordinary analog expression")
                return _make(work,Binary,"divide", a, b)
            if b.constant == 0 and (event_math is not None or sampled_values):
                return _make(work,Binary,"divide", a, b)
            if b.constant == 0:
                fail("division requires a nonzero constant denominator")
            if getattr(parameters, "source_floor_operand", False):
                return Binary("divide", a, b)
            # Keep division, rather than multiplication by a reciprocal, on
            # the affine path so its existing rounding behavior is preserved.
            if isinstance(a, Affine) and not (preserve_structure and a.terms):
                result = affine(a.constant / b.constant, {t.node: t.coefficient / b.constant for t in a.terms})
            else:
                reciprocal = 1.0 / b.constant
                if not math.isfinite(reciprocal):
                    fail("nonfinite coefficient during constant folding")
                result = _make(work,Binary,"multiply", _make(work,Affine,reciprocal, ()), a) if preserve_structure else scale(a, reciprocal, work=work)
        elif expr.op == "power":
            finite_power = getattr(parameters, "finite_power", None)
            if finite_power is not None:
                finite_result = finite_power(expr, a, b)
                if finite_result is not None:
                    return finite_result
            if (not isinstance(b, Affine) or b.terms or not b.constant.is_integer()
                    or not 1 <= b.constant <= 32):
                fail("pow exponent must be an instance-constant integer in [1,32]",
                     error=UnsupportedConstantPower)
            exponent = int(b.constant)
            if isinstance(a, Affine) and not a.terms:
                try:
                    result = _make(work,Affine,a.constant ** exponent, ())
                except OverflowError:
                    fail("nonfinite coefficient during constant folding")
            elif exponent == 1:
                result = a
            else:
                result = _make(work,Power,a, exponent)
        else:
            fail(f"unsupported arithmetic {expr.op!r}")
    if isinstance(result, Affine) and not all(math.isfinite(x) for x in
            (result.constant, *(t.coefficient for t in result.terms))):
        fail("nonfinite coefficient during constant folding")
    return result
