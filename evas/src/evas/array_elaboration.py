"""Scalarize instance-sized variable arrays before shared semantic lowering."""
from dataclasses import replace
from .errors import CompileError
from .ir import Affine
from .lowering import lower
from .syntax import Assignment, Conditional, Expr
from .elaboration import unroll_loops

ARRAY_BUDGET = 4096


def scalarize_arrays(model, parameter):
    def fail(message, token):
        raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}')

    def integer(expr):
        try:
            value = lower(expr, parameter, {}, model.source)
        except CompileError as error:
            fail(f'array bound/index requires an instance-constant integer: {error}', expr.token)
        if (not isinstance(value, Affine) or value.terms or not value.constant.is_integer()
                or not -2147483648 <= value.constant <= 2147483647):
            fail('array bound/index requires a signed 32-bit instance-constant integer', expr.token)
        return int(value.constant)

    ranges = {}
    variables = {}
    for name, kind in model.variables.items():
        if name not in model.arrays:
            variables[name] = kind
            continue
        left, right = model.arrays[name]
        first, last = integer(left), integer(right)
        count = abs(last-first)+1
        if count + sum(len(indices) for indices in ranges.values()) > ARRAY_BUDGET:
            fail('total array element budget (4096) exceeded', left.token)
        indices = range(first, last + (1 if last >= first else -1), 1 if last >= first else -1)
        ranges[name] = indices
        for index in indices:
            variables[f'{name}[{index}]'] = kind

    def element(name, index, token):
        if name not in ranges:
            fail(f'indexed identifier {name!r} is not a variable array', token)
        value = integer(index)
        if value not in ranges[name]:
            fail(f'array index {value} is outside {name!r} declaration', index.token)
        return f'{name}[{value}]'

    def expression(expr):
        if expr.op == 'index':
            return Expr('parameter', element(expr.value, expr.args[0], expr.token), (), expr.token)
        if expr.op == 'parameter' and expr.value in ranges:
            fail('array value requires an explicit element index', expr.token)
        return replace(expr, args=tuple(expression(a) for a in expr.args))

    def body(statements):
        result = []
        for statement in statements:
            if isinstance(statement, Conditional):
                result.append(replace(statement, left=expression(statement.left), right=expression(statement.right),
                                      then_body=body(statement.then_body), else_body=body(statement.else_body)))
            elif isinstance(statement, Assignment):
                name = statement.name
                if statement.index is not None:
                    name = element(name, statement.index, statement.token)
                elif name in ranges:
                    fail('array assignment requires an explicit element index', statement.token)
                result.append(replace(statement, name=name, rhs=expression(statement.rhs), index=None))
            else:
                result.append(replace(statement, rhs=expression(statement.rhs)))
        return tuple(result)

    return replace(model, variables=variables, arrays={}, analog=list(body(unroll_loops(model, parameter))),
                   initial=list(body(model.initial)), events=[replace(event, body=body(event.body), triggers=tuple(
                       replace(leaf, arguments=tuple(expression(a) if a is not None else None
                                                   for a in leaf.arguments)) for leaf in event.triggers))
                       for event in model.events])
