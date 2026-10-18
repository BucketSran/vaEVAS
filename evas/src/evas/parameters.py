"""One parameter binding algorithm for flat and hierarchical instances."""
import math
from .errors import CompileError
from .limits import MAX_PARAMETER_DEPTH
from .lowering import lower
from .syntax import contains_operator, contains_decision
from .integer_constants import check_integer_expression
from . import integer_bits, integer_arithmetic
from .ir import Affine


def attach_constant_integer_arithmetic(lookup, model, instance_name=''):
    """Attach typed constant division to a parameter lookup, retaining real /.

    The source checker audits every original integer intermediate separately;
    this callback supplies exact quotient semantics to existing real IR entry
    points. It never infers source integer type from an integral float value.
    """
    def divide(expr, numerator, denominator):
        if expr.op != '/' or not all(integer_bits.integer_type(
                arg, {}, model.parameter_types, model.genvars) for arg in expr.args):
            return None
        # Structural consumers can lower substituted genvar controls directly.
        # Audit the original subtree again before an already-folded numerator
        # can hide integer overflow in a later cancellation.
        pending, values = [expr], {}
        while pending:
            item = pending.pop()
            if item.op == 'parameter' and item.value not in values:
                values[item.value] = lookup(item.value)
            pending.extend(item.args)
        check_integer_expression(expr, model, values, check_literals=True, allow_division=True)
        def fail(message):
            raise CompileError(message, code='unsupported_integer_arithmetic',
                               token=expr.token, instance=instance_name or None)
        if not all(isinstance(value, Affine) and not value.terms
                   and value.constant.is_integer() for value in (numerator, denominator)):
            fail('integer parameter division requires constant integer operands')
        a, b = int(numerator.constant), int(denominator.constant)
        if not all(-2147483648 <= value <= 2147483647 for value in (a, b)):
            fail('integer parameter division operand exceeds signed 32-bit range')
        try:
            value = integer_arithmetic.truncating_division(a, b)
        except ValueError as error:
            fail(str(error))
        if not -2147483648 <= value <= 2147483647:
            fail('integer parameter quotient exceeds signed 32-bit range')
        return Affine(float(value), ())
    lookup.integer_arithmetic = divide
    return lookup


def bind_parameters(model, overrides, instance_name):
    def validate(expr):
        if contains_decision(expr):
            raise CompileError(f'{expr.token.source or model.source}:{expr.token.line}: decision expressions are not supported in parameter defaults or ranges')
        if (expr.op in ('voltage', 'array', 'index') or contains_operator(expr)
                or expr.op == 'parameter' and expr.value not in model.parameters):
            raise CompileError(f'{expr.token.source or model.source}:{expr.token.line}: invalid parameter default',
                               code='parameter_dependency', token=expr.token, instance=instance_name)
        for arg in expr.args:
            validate(arg)

    for expr in model.parameters.values():
        validate(expr)
    for ranges in model.parameter_ranges.values():
        for interval in ranges:
            for endpoint in (interval.lower, interval.upper):
                if endpoint is not None and not isinstance(endpoint, float):
                    validate(endpoint)
    if not set(overrides) <= model.parameters.keys():
        raise CompileError(f'{instance_name}: unknown parameter override',
                           code='parameter_override', instance=instance_name)
    dependencies, cache, active, depths = {}, {}, set(), {}
    def lookup(name):
        return cache[name]
    def bitwise(expr, values):
        if not all(integer_bits.integer_type(arg, {}, model.parameter_types, model.genvars)
                   and isinstance(value, Affine) and not value.terms and value.constant.is_integer()
                   for arg, value in zip(expr.args, values)):
            raise CompileError('bitwise operands require typed integer expressions',
                               code='unsupported_integer_bitwise', token=expr.token, instance=instance_name)
        try:
            value = integer_bits.evaluate(expr.op, *(int(value.constant) for value in values))
        except ValueError as error:
            raise CompileError(str(error), code='unsupported_integer_bitwise',
                               token=expr.token, instance=instance_name) from error
        return Affine(float(value), ())
    lookup.integer_bitwise = bitwise
    attach_constant_integer_arithmetic(lookup, model, instance_name)

    for name, expr in model.parameters.items():
        refs, pending = [], [] if name in overrides else [expr]
        while pending:
            item = pending.pop()
            if item.op == 'parameter' and item.value not in refs:
                refs.append(item.value)
            pending.extend(reversed(item.args))
        dependencies[name] = refs
    for root in model.parameters:
        pending = [(root, False)]
        while pending:
            name, exiting = pending.pop()
            if name in cache:
                continue
            if not exiting:
                if name in active:
                    raise CompileError(f'{model.source}: cyclic parameter defaults involving {name!r}',
                                       code='parameter_dependency', token=model.parameters[name].token, instance=instance_name)
                active.add(name)
                pending.append((name, True))
                pending.extend((ref, False) for ref in reversed(dependencies[name]))
                continue
            depth = 1 + max((depths[ref] for ref in dependencies[name]), default=0)
            if depth > MAX_PARAMETER_DEPTH:
                token = model.parameters[name].token
                raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: parameter dependency depth limit ({MAX_PARAMETER_DEPTH}) exceeded',
                                   code='resource_budget', token=token, instance=instance_name)
            if name in overrides:
                value = overrides[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise CompileError(f'{instance_name}: parameter {name!r} must be numeric',
                                       code='parameter_override', token=model.parameters[name].token, instance=instance_name)
                try:
                    value = float(value)
                except OverflowError as error:
                    raise CompileError(f'{instance_name}: nonfinite parameter {name!r}',
                                       code='parameter_override', token=model.parameters[name].token, instance=instance_name) from error
            else:
                check_integer_expression(model.parameters[name], model, cache,
                                         check_literals=model.parameter_types.get(name) == 'integer', allow_division=True)
                value = lower(model.parameters[name], lookup, {}, model.source).constant
            if not math.isfinite(value):
                raise CompileError(f'{instance_name}: nonfinite parameter {name!r}',
                                   code='parameter_override' if name in overrides else 'parameter_dependency',
                                   token=model.parameters[name].token, instance=instance_name)
            if model.parameter_types.get(name) == 'integer' and not (value.is_integer() and -2147483648 <= value <= 2147483647):
                raise CompileError(f'{instance_name}: integer parameter {name!r} requires an exact signed 32-bit value; implicit rounding is not supported',
                                   code='parameter_type', token=model.parameters[name].token, instance=instance_name)
            cache[name] = value
            depths[name] = depth
            active.remove(name)
    for name, ranges in model.parameter_ranges.items():
        included, excluded = [], []
        for interval in ranges:
            def evaluate(endpoint):
                if not isinstance(endpoint, float):
                    check_integer_expression(endpoint, model, cache, check_literals=True, allow_division=True)
                return endpoint if isinstance(endpoint, float) else lower(endpoint, lookup, {}, model.source).constant
            lo = evaluate(interval.lower)
            hi = lo if interval.upper is None else evaluate(interval.upper)
            if interval.upper is not None and not lo < hi:
                raise CompileError(f'{instance_name}: parameter {name!r} range requires lower < upper', code='parameter_range', token=interval.token, instance=instance_name)
            value = cache[name]
            inside = (value >= lo if interval.closed_left else value > lo) and (value <= hi if interval.closed_right else value < hi)
            (included if interval.kind == 'from' else excluded).append(inside)
        if included and not any(included) or any(excluded):
            raise CompileError(f'{instance_name}: effective parameter {name!r}={cache[name]} violates its from/exclude range',
                               code='parameter_range', token=model.parameters[name].token, instance=instance_name)
    return cache
