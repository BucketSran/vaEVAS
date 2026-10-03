"""One parameter binding algorithm for flat and hierarchical instances."""
import math
from .errors import CompileError
from .limits import MAX_PARAMETER_DEPTH
from .lowering import lower
from .syntax import contains_operator


def bind_parameters(model, overrides, instance_name):
    def validate(expr):
        if (expr.op in ('voltage', 'array', 'index') or contains_operator(expr)
                or expr.op == 'parameter' and expr.value not in model.parameters):
            raise CompileError(f'{model.source}:{expr.token.line}: invalid parameter default')
        for arg in expr.args:
            validate(arg)

    for expr in model.parameters.values():
        validate(expr)
    if not set(overrides) <= model.parameters.keys():
        raise CompileError(f'{instance_name}: unknown parameter override')
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
                    raise CompileError(f'{model.source}: cyclic parameter defaults involving {name!r}')
                active.add(name)
                pending.append((name, True))
                pending.extend((ref, False) for ref in reversed(dependencies[name]))
                continue
            depth = 1 + max((depths[ref] for ref in dependencies[name]), default=0)
            if depth > MAX_PARAMETER_DEPTH:
                token = model.parameters[name].token
                raise CompileError(f'{model.source}:{token.line}:{token.column}: parameter dependency depth limit ({MAX_PARAMETER_DEPTH}) exceeded')
            if name in overrides:
                value = overrides[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise CompileError(f'{instance_name}: parameter {name!r} must be numeric')
                try:
                    value = float(value)
                except OverflowError as error:
                    raise CompileError(f'{instance_name}: nonfinite parameter {name!r}') from error
            else:
                value = lower(model.parameters[name], lambda n: cache[n], {}, model.source).constant
            if not math.isfinite(value):
                raise CompileError(f'{instance_name}: nonfinite parameter {name!r}')
            cache[name] = value
            depths[name] = depth
            active.remove(name)
    return cache
