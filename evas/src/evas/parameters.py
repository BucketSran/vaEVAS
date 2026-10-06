"""One parameter binding algorithm for flat and hierarchical instances."""
import math
from .errors import CompileError
from .limits import MAX_PARAMETER_DEPTH
from .lowering import lower
from .syntax import contains_operator, contains_decision
from .integer_constants import check_integer_expression


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
                                         check_literals=model.parameter_types.get(name) == 'integer')
                value = lower(model.parameters[name], lambda n: cache[n], {}, model.source).constant
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
                    check_integer_expression(endpoint, model, cache, check_literals=True)
                return endpoint if isinstance(endpoint, float) else lower(endpoint, cache.__getitem__, {}, model.source).constant
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
