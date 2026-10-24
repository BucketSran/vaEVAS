"""Initial-only closed real power, with native ln/exp boxes at execution.

The compatibility preview is symbolic and cannot allocate operators. The unique
retained initial event owns all native calls and source argument boundaries.
"""
from .errors import CompileError
from .ir import Affine, Binary, EventMath, MathFunction, OperatorRef, Origin, RealBoundary, Select


def lower_power(c, expr, base, exponent, *, preview):
    owner = c.compilation.native_audit
    owner.debit('initial_power_dispatch', 1, expr)
    # This shallow legacy check cannot erase any operand or its obligations.
    # In particular, a literal bounded exponent does not activate a new route.
    if isinstance(exponent, Affine) and not exponent.terms and (
            exponent.constant == .5 or exponent.constant.is_integer()
            and 1 <= exponent.constant <= 32):
        return None
    b = c.program_real_closed(exponent)
    if not b.closed or not b.finite:
        return None
    if b.value == .5 or b.value.is_integer() and 1 <= b.value <= 32:
        return None
    owner.activate(expr)
    owner.debit('initial_power_qualification', 4, expr)
    a = c.program_real_closed(base)
    if not a.closed or not a.finite:
        return None
    if a.value <= 0:
        raise CompileError('closed initial real power requires a strictly positive base',
                           code='unsupported_initial_event', token=expr.token,
                           instance=c.instance.name)
    def origin(item, stage=None):
        expansion = item.expansion
        owner.debit('initial_power_origin', 1+len(expansion), item)
        if stage:
            if len(expansion) >= 64:
                raise CompileError('closed initial math expansion exceeds64',
                                   code='resource_budget', token=item.token)
            expansion = (*expansion, (stage, 0))
        return c.make_ir(Origin, item.token.source or c.model.source,
                         item.token.line, item.token.column, c.instance.name, expansion)
    x = c.make_ir(RealBoundary, base, 'argument', origin(expr.args[0]))
    y = c.make_ir(RealBoundary, exponent, 'argument', origin(expr.args[1]))
    if b.value == 0:
        result = c.make_ir(Affine, 1., ())
        for argument in (y, x):
            result = c.make_ir(Select, 'lt', argument, c.make_ir(Affine, 0., ()),
                               result, result, origin(expr))
        return result
    if preview:
        logarithm = c.make_ir(EventMath, 'ln', (x,), origin(expr, '_evas_closed_pow_ln'))
        product = c.make_ir(Binary, 'multiply', y, logarithm)
        return c.make_ir(EventMath, 'exp', (product,), origin(expr, '_evas_closed_pow_exp'))
    logarithm = c.memoryless_operator(c.make_ir(MathFunction, 'ln', x,
                                               origin(expr, '_evas_closed_pow_ln')))
    product = c.make_ir(Binary, 'multiply', y, c.make_ir(OperatorRef, logarithm))
    result = c.memoryless_operator(c.make_ir(MathFunction, 'exp', product,
                                           origin(expr, '_evas_closed_pow_exp')))
    return c.make_ir(RealBoundary, c.make_ir(OperatorRef, result), 'sample', origin(expr))
