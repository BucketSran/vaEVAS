"""Bind arithmetic to polynomial IR, preserving the affine constant-folding path."""
import math
from dataclasses import fields
from typing import Callable, Mapping

from .ir import (EventMath, Origin, Affine, Binary, Expression, OperatorRef, Power,
                 Select, StateRef, Term, RealBinary, RealBoundary, RealLocal, RealCall, UnsupportedSystemCall)
from .syntax import CompileError, Expr, OPERATOR_NAMES, DECISION_NAMES, contains_operator, contains_decision


class UnsupportedConstantPower(CompileError):
    """Private classification from the original pow rejection traversal."""


def _make(work, cls, *args):
    if work is not None:
        owner = getattr(work, '__self__', None)
        if owner is not None and hasattr(owner, 'emit_ir'):
            return owner.emit_ir(cls, args, {}, 'lower_emit')
        work('lower_emit_object',1)
        work('lower_emit_field',len(fields(cls)))
    return cls(*args)


def affine(constant, terms, *, work=None):
    if work is not None: work('lower_affine_scan',len(terms))
    return _make(work, Affine, constant, tuple(_make(work,Term,n,c) for n,c in sorted(terms.items()) if c!=0.0))


def _closed_scalar(value, parameters):
    if isinstance(value, Affine) and not value.terms:
        return value.constant
    query = getattr(parameters, 'program_real_closed', None)
    fact = query(value) if query is not None else None
    return fact.value if fact is not None and fact.closed and fact.finite else None


def _retain_closed_arguments(expr, arguments, result, parameters, source, work):
    """Execute proved closed arguments without replacing their rounded trees.

    Both leaves are the existing library result. The guard retains each source
    argument, in argument order, for execution and transport accounting.
    """
    for argument in reversed(arguments):
        if isinstance(argument, Affine) and not argument.terms:
            continue
        origin = _make(work, Origin, expr.token.source or source, expr.token.line,
                       expr.token.column, getattr(parameters, 'instance_name', '<expression>'), expr.expansion)
        result = _make(work, Select, 'lt', argument, _make(work, Affine, 0.0, ()), result, result, origin)
    return result


def scale(expression: Expression, factor: float, *, work=None) -> Expression:
    if factor == 1.0:
        return expression
    if isinstance(expression, Affine):
        return affine(expression.constant * factor, {t.node: t.coefficient * factor for t in expression.terms}, work=work)
    return _make(work,Binary,"multiply",_make(work,Affine,factor,()),expression)


def _has_bound_decision(expr: Expr, parameters, *, names=None) -> bool:
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
            if isinstance(item, (Binary, RealBinary)):
                pending.extend((item.left, item.right))
            elif isinstance(item, RealBoundary):
                pending.append(item.value)
            elif isinstance(item, Power):
                pending.append(item.base)
        return False

    if names is not None:
        # These are syntax reads in the original right-to-left DFS order, not
        # cached binding values. Resolve every name in this exact environment.
        if work is not None: work("bound_decision_names", 1+len(names))
        for read in names:
            if work is not None: work("bound_decision_name", 1+len(read.value))
            if has_select(parameters(read.value)):
                return True
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


def _conditional_lookup(parameters):
    """Lexical lazy arm: retain numeric operations; never bypass static types."""
    if getattr(parameters, 'defer_numeric_domain', False):
        return parameters
    work = getattr(parameters, 'native_work', None)
    if work is not None:
        work('conditional_lookup_copy', 1+len(getattr(parameters, '__dict__', {})))
    def lookup(name):
        return parameters(name)
    lookup.__dict__.update(getattr(parameters, '__dict__', {}))
    lookup.defer_numeric_domain = True
    return lookup


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


class _SourceAuditMemo(dict):
    """Private one-shape audit cache; callbacks must be read-only and fixed.

    Constructed by original event audits or read-only ordinary compatibility
    views after immutable/effect-free source qualification. Actual calls and
    public lower memo keep rejecting semantic callbacks.
    Integer operation validation still runs after every cache read in lower().
    """
    def __init__(self, work, callbacks):
        work('source_audit_lower_cache_create', 2)
        super().__init__()
        self.work, self.callbacks = work, callbacks
        self.binding_token = None

    def bind(self, resolve, nodes, flags):
        self.work('source_audit_lower_binding_guard', 6)
        receiver = getattr(resolve, '__self__', None)
        function = getattr(resolve, '__func__', resolve)
        if self.binding_token is None:
            self.work('source_audit_lower_binding_record', 5)
            self.binding_token = (receiver, function, nodes, flags)
        elif (self.binding_token[0] is not receiver or self.binding_token[1] is not function
              or self.binding_token[2] is not nodes or self.binding_token[3] != flags):
            raise ValueError('source audit memo requires its fixed binding and flags')


def _lower_checked(expr, parameters, nodes, source, operators, preserve_structure,
                   decisions, validate_decision, decision_scope, indices, *, memo, node_declarations):
    # Only a caller with the complete declared electrical environment may label
    # a missing voltage node invalid. Closed constant/state contexts stay unknown.
    # This flag changes failure metadata only, never voltage acceptance or IR.
    # Opt-in reuse for one fixed parameter/node binding without registration
    # callbacks. Callers own the lifetime and must not share across contexts.
    if memo is not None:
        audit = type(memo) is _SourceAuditMemo
        if audit:
            memo.work('source_audit_lower_callback_guard', 9)
            if (memo.binding_token is None
                    or getattr(parameters, '_source_audit_binding', None) is not memo.binding_token
                    or nodes is not memo.binding_token[2]
                    or (operators, decisions, validate_decision, indices) != memo.callbacks
                    or getattr(parameters, 'real_call', None) is not None):
                raise ValueError("source audit memo requires its fixed read-only callbacks")
        elif operators is not None or decisions is not None or validate_decision is not None or indices is not None or getattr(parameters, "real_call", None) is not None:
            raise ValueError("lower memo cannot be used with semantic callbacks")
        if audit:
            memo.work('source_audit_lower_cache_key', 8)
        key = (id(expr), preserve_structure, decision_scope, getattr(parameters, "source_floor_operand", False),
               getattr(parameters, "program_real", False), getattr(parameters, "defer_numeric_domain", False))
        if audit:
            # Assignment-root allowance may change intermediate validation.
            # Keep its lexical role separate even though the outer validator
            # is rerun after a hit. Lazy domains/program-real already enter key.
            key += (getattr(parameters, 'integer_operation_depth', 0) == 1
                    and getattr(parameters, 'allow_integer_assignment_root', False),
                    getattr(parameters, 'allow_integer_assignment_root', False))
            memo.work('source_audit_lower_cache_lookup', 1)
        entry = memo.get(key)
        if entry is None:
            value = _lower(expr, parameters, nodes, source, operators, preserve_structure,
                           decisions, validate_decision, decision_scope, indices, memo, node_declarations)
            if audit:
                memo.work('source_audit_lower_cache_insert', 2)
            entry = (expr, value)
            memo[key] = entry
        assert entry[0] is expr
        value = entry[1]
    else:
        value = _lower(expr, parameters, nodes, source, operators, preserve_structure,
                       decisions, validate_decision, decision_scope, indices, None, node_declarations)
    return value


def _checked_source_fact(memo, expr):
    """Read-only source shape within one fixed audit resolver/flags context."""
    from .source_queries import SourceQuery
    work = memo.work
    work('checked_source_context_lookup', 2)
    query = getattr(memo, 'checked_source_query', None)
    if query is None:
        def local(item):
            work('checked_source_shape', 3)
            if type(item.args) is not tuple or type(item.op) is not str:
                raise TypeError('checked source facts require immutable Expr children')
            if item.op in DECISION_NAMES:
                return (True, ()), False
            if item.op == 'parameter':
                if type(item.value) is not str:
                    raise TypeError('source parameter name must be a string')
                work('checked_source_parameter', 3+len(item.value))
                return (False, (item,)), True
            return (False, ()), True
        def merge(item, value, children):
            work('checked_source_merge', 3+len(children))
            if value[0] or any(child[0] for child in children):
                return True, ()
            names = value[1]
            # The original stack extends args then pops the last child first.
            for child in reversed(children):
                work('checked_source_name_child', 1)
                other = child[1]
                if not other or names is other:
                    continue
                if not names:
                    names = other
                    continue
                work('checked_source_names_container', 3+2*len(names))
                seen, ordered = {id(read) for read in names}, list(names)
                work('checked_source_names_scan', len(other))
                for read in other:
                    work('checked_source_name_lookup', 2)
                    if id(read) not in seen:
                        work('checked_source_name_insert', 2)
                        seen.add(id(read))
                        ordered.append(read)
                work('checked_source_names_freeze', 1+len(ordered))
                names = tuple(ordered)
            return False, names
        work('checked_source_context_retain', 1)
        query = SourceQuery(work.__self__, 'checked_source', local, merge)
        memo.checked_source_query = query
    return query(expr)


def _lower(expr, parameters, nodes, source, operators, preserve_structure,
           decisions, validate_decision, decision_scope, indices, memo, node_declarations):
    work = getattr(parameters,"native_work",None)
    if work is not None: work("lower_child_attachment",len(expr.args))
    def fail(message, *, code="compile_error", error=CompileError):
        raise error(f"{expr.token.source or source}:{expr.token.line}:{expr.token.column}: {message}",
                           code=code, token=expr.token)

    if expr.source_call is not None and getattr(parameters, "initial_preview", False):
        # This compatibility pass is not the source event execution. Retain the
        # exact substituted value tree; the actual call body below the retained
        # event owns every RHS effect. Never allocate call slots/operators here.
        if work is not None:
            work('real_call_preview_lookup_copy', 1+len(parameters.__dict__))
        def preview(name):
            return parameters(name)
        preview.__dict__.update(parameters.__dict__)
        preview.defer_numeric_domain = True
        def symbolic_math(item):
            arguments = tuple(lower(arg, preview, nodes, source, symbolic_math, True,
                decisions, validate_decision, decision_scope, indices,
                node_declarations=node_declarations) for arg in item.args)
            at = _make(work, Origin, item.token.source or source, item.token.line,
                       item.token.column, getattr(preview, "instance_name", "<expression>"), item.expansion)
            return _make(work, EventMath, item.op, arguments, at)
        return lower(expr.args[0], preview, nodes, source, symbolic_math, True,
            decisions, validate_decision, decision_scope, indices,
            node_declarations=node_declarations)

    call = getattr(parameters, "real_call", None)
    if expr.source_call is not None and call is not None:
        return call(expr, parameters, nodes, source, operators, preserve_structure,
                    decisions, validate_decision, decision_scope, indices,
                    node_declarations=node_declarations)

    if expr.op == 'unsupported_system_call':
        callback = getattr(parameters, 'unsupported_system_call', None)
        if callback is not None:
            return callback(expr, parameters, nodes, source, operators,
                preserve_structure, decisions, validate_decision, decision_scope,
                indices, node_declarations=node_declarations)
        fail(f"system function ${expr.value} is not supported", code='unsupported_system_function')

    event_math = getattr(parameters, "event_math", None)
    sampled_values = getattr(parameters, "sampled_values", False)
    finite_integer = getattr(parameters, "finite_integer_expression", None)
    if finite_integer is not None:
        result = finite_integer(expr, nodes,
            (operators, preserve_structure, decisions, validate_decision, decision_scope, indices),
            {"node_declarations": node_declarations})
        if result is not None:
            return result
    if expr.op == 'function_assign':
        # Closed constant binders do not audit every signed32 intermediate.
        # Keep new integer functions out of that route until it owns that proof.
        check = getattr(parameters, 'function_integer_assignment', None)
        if expr.value == 'integer' and check is None:
            fail('integer functions require a typed instance expression context',
                 code='unsupported_function_conversion')
        operand_parameters = parameters
        if hasattr(parameters, "instance_name"):
            def real_function_lookup(name):
                return parameters(name)
            real_function_lookup.__dict__.update(parameters.__dict__)
            real_function_lookup.program_real = True
            operand_parameters = real_function_lookup
        value = lower(expr.args[0], operand_parameters, nodes, source, operators, preserve_structure,
                      decisions, validate_decision, decision_scope, indices,
                      memo=memo, node_declarations=node_declarations)
        if expr.value == 'real':
            if getattr(operand_parameters, "program_real", False):
                origin = _make(work, Origin, expr.token.source or source,
                               expr.token.line, expr.token.column,
                               getattr(parameters, "instance_name", "<expression>"), expr.expansion)
                return _make(work, RealBoundary, value,
                             getattr(expr, "real_boundary_kind", None) or "store", origin)
            return value
        number = _closed_scalar(value, parameters)
        if number is not None:
            if not math.isfinite(number):
                fail('function integer assignment requires a finite signed 32-bit result', code='unsupported_function_conversion')
            fraction, whole = math.modf(number)
            rounded = whole + (math.copysign(1., fraction) if abs(fraction) >= .5 else 0.)
            if not -2147483648 <= rounded <= 2147483647:
                fail('function integer assignment exceeds signed 32-bit range', code='unsupported_function_conversion')
            return _retain_closed_arguments(expr, (value,), _make(work, Affine, rounded, ()), parameters, source, work)
        if check(expr, value):
            return value
        fail('function integer assignment requires a constant or proven signed 32-bit integer expression',
             code='unsupported_function_conversion')
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
        values = [_closed_scalar(arg, parameters) for arg in args]
        if all(value is not None for value in values):
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
                    return _retain_closed_arguments(expr, args, _make(work,Affine,value, ()), parameters, source, work)
        return event_math(expr, args)

    if expr.op == "checked":
        if not decision_scope and type(memo) is _SourceAuditMemo:
            source_decision, source_names = _checked_source_fact(memo, expr)
            scope = source_decision or _has_bound_decision(expr, parameters, names=source_names)
        else:
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
        permitted = None
        if getattr(parameters, "memoryless_decisions", False):
            from .elaboration import function_math
            permitted = lambda item:function_math(item, work)
        if contains_operator(expr, allowed=permitted,visit=(lambda item:work("operator_scan",1)) if work is not None else None) and event_math is None:
            fail("decision expressions do not support waveform operators in any operand or arm")
        values = []
        for position, arg in enumerate(expr.args):
            lazy = expr.op == 'ternary' and position > 0 or expr.op in ('&&', '||') and position == 1
            lookup = _conditional_lookup(parameters) if lazy else parameters
            values.append(lower(arg, lookup, nodes, source, operators, True,
                decisions, validate_decision, True, indices, memo=memo,
                node_declarations=node_declarations))
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
        if _closed_scalar(exponent, parameters) == 0.5:
            if decision_scope:
                fail("decision expressions do not support waveform operators in any operand or arm")
            result = lower(Expr("sqrt", None, (expr.args[0],), expr.token, expr.expansion),
                         parameters, nodes, source, operators, preserve_structure,
                         decisions, validate_decision, decision_scope, indices,
                         memo=memo, node_declarations=node_declarations)
            return _retain_closed_arguments(expr, (exponent,), result, parameters, source, work)
    prepared_math_argument = None
    call_math_checked = False
    sampled_math = getattr(parameters, "sampled_math", None)
    if (sampled_math is not None and event_math is None and operators is None
            and expr.op in ("sqrt", "ln") and len(expr.args) == 1):
        # Physical event assignment values keep sqrt/ln as runtime EventMath
        # when the owner accepts the argument as a sample (it returns None
        # otherwise). The kernel proves the domain over the complete argument
        # enclosure; a constant argument keeps the existing compile-time
        # folding and domain check.
        argument = lower(expr.args[0], parameters, nodes, source, None, True,
                         decisions, validate_decision, False, indices,
                         node_declarations=node_declarations)
        prepared_math_argument = argument
        call_math = getattr(parameters, 'function_math_value', None)
        if call_math is not None:
            call_math_checked = True
            native = call_math(expr, argument)
            if native is not None:
                return native
        if _closed_scalar(argument, parameters) is None:
            value = sampled_math(expr, (argument,))
            if value is not None:
                return value
    if expr.op in ("cos", "exp", "ln", "sqrt", "tanh") and operators is None:
        argument = (prepared_math_argument if prepared_math_argument is not None else
                    lower(expr.args[0], parameters, nodes, source, operators,
                          preserve_structure, decisions, validate_decision,
                          decision_scope, indices, memo=memo,
                          node_declarations=node_declarations))
        call_math = getattr(parameters, 'function_math_value', None)
        if call_math is not None and not call_math_checked:
            native = call_math(expr, argument)
            if native is not None:
                return native
        number = _closed_scalar(argument, parameters)
        if number is None:
            fail("nonconstant mathematical functions require a waveform contribution")
        try:
            value = {"cos": math.cos, "exp": math.exp, "ln": math.log,
                     "sqrt": math.sqrt, "tanh": math.tanh}[expr.op](number)
        except (ValueError, OverflowError):
            fail("mathematical constant is outside the finite function domain")
        if not math.isfinite(value):
            fail("nonfinite mathematical constant")
        return _retain_closed_arguments(expr, (argument,), _make(work,Affine,value, ()), parameters, source, work)
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
        value = _make(work,Affine,0., (_make(work,Term,nodes["$abstime"], 1.),))
        if getattr(parameters, "program_real", False):
            origin = _make(work, Origin, expr.token.source or source, expr.token.line,
                           expr.token.column, getattr(parameters, "instance_name", "<expression>"), expr.expansion)
            return _make(work, RealBoundary, value, "sample", origin)
        return value
    if expr.op == "number":
        return _make(work,Affine,float(expr.value), ())
    if expr.op == "parameter":
        value = parameters(str(expr.value))
        return value if isinstance(value, (Affine, Binary, RealBinary, RealBoundary, RealLocal, RealCall, UnsupportedSystemCall, Power, Select, StateRef, OperatorRef, EventMath)) else _make(work,Affine,value, ())
    if expr.op == "voltage":
        p, n = (str(arg.value) for arg in expr.args)
        if p not in nodes or n not in nodes:
            fail(f"undeclared electrical node in V({p},{n})",
                 code="undeclared_node" if node_declarations else "compile_error")
        if getattr(parameters, "program_real", False):
            value = affine(0.0, {} if nodes[p] == nodes[n] else {nodes[p]: 1.0, nodes[n]: -1.0}, work=work)
            origin = _make(work, Origin, expr.token.source or source, expr.token.line,
                           expr.token.column, getattr(parameters, "instance_name", "<expression>"), expr.expansion)
            return _make(work, RealBoundary, value, "sample", origin)
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
    if expr.op == "/":
        constant = getattr(parameters, "program_real_constant", None)
        if constant is not None and constant(values[1]) == 0.0 and not (getattr(parameters, "defer_numeric_domain", False) and getattr(parameters, "program_real", False) and getattr(parameters, "is_program_real_expression", lambda part:True)(expr)):
            fail("division by zero")
    # The source real route never enters affine coefficient folding or the
    # reciprocal rewrite below. Each node is a separate binary64 operation;
    # internal continuous equations retain their existing mathematical IR.
    real_operation = getattr(parameters, "program_real", False)
    real_type = getattr(parameters, "is_program_real_expression", lambda item: True)
    if real_operation and real_type(expr) and expr.op in ("+", "-", "*", "/", "unary+", "unary-"):
        if expr.op == "unary+":
            return a
        origin = _make(work, Origin, expr.token.source or source, expr.token.line,
                       expr.token.column, getattr(parameters, "instance_name", "<expression>"), expr.expansion)
        if expr.op == "unary-":
            return _make(work, RealBinary, "multiply", _make(work, Affine, -1., ()), a, origin)
        return _make(work, RealBinary, {"+":"add", "-":"subtract", "*":"multiply", "/":"divide"}[expr.op], a, values[1], origin)
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
            number = _closed_scalar(b, parameters)
            if (number is None or not number.is_integer() or not 1 <= number <= 32):
                fail("pow exponent must be an instance-constant integer in [1,32]",
                     error=UnsupportedConstantPower)
            exponent = int(number)
            if isinstance(a, Affine) and not a.terms:
                try:
                    result = _make(work,Affine,a.constant ** exponent, ())
                except OverflowError:
                    fail("nonfinite coefficient during constant folding")
            elif exponent == 1:
                result = a
            else:
                result = _make(work,Power,a, exponent)
            result = _retain_closed_arguments(expr, (b,), result, parameters, source, work)
        else:
            fail(f"unsupported arithmetic {expr.op!r}")
    if isinstance(result, Affine) and not all(math.isfinite(x) for x in
            (result.constant, *(t.coefficient for t in result.terms))):
        fail("nonfinite coefficient during constant folding")
    return result
