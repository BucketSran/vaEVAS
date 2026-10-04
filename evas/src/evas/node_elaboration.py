"""Instance-constant electrical vectors become ordinary, independent nodes.

This owns electrical bit order; variable arrays retain their separate state
identities. Both use the same existing expression/loop IR after expansion.
"""
from dataclasses import replace
from .errors import CompileError
from .ir import Affine
from .lowering import lower
from .elaboration import unroll_loops
from .syntax import Assignment, Conditional, ContributionStatement
from .integer_constants import check_integer_model, check_integer_expression


def scalarize_nodes(model, parameters):
    check_integer_model(model, parameters)
    def fail(message, token=None, code='unsupported_vector'):
        raise CompileError(f'{model.source}: {message}', code=code, token=token)

    def parameter(name):
        if name not in parameters:
            fail(f'unknown parameter {name!r} in electrical bound/index')
        return parameters[name]

    model = replace(model, analog=list(unroll_loops(model, parameter)))
    # Genvar substitution can expose integer-only arithmetic in both values and
    # node/array indices. Recheck the complete expanded tree before real lowering.
    check_integer_model(model, parameters)

    def integer(expr):
        check_integer_expression(expr, model, parameters, check_literals=True)
        try:
            value = lower(expr, parameter, {}, model.source)
        except CompileError as exc:
            fail(f'electrical bound/index must be instance-constant: {exc}', expr.token)
        if not isinstance(value, Affine) or value.terms or not value.constant.is_integer() or not -2147483648 <= value.constant <= 2147483647:
            fail('electrical bound/index must be a signed 32-bit instance-constant integer', expr.token)
        return int(value.constant)

    def indices(bounds):
        if bounds is None:
            return None
        first, last = (integer(e) for e in bounds)
        if abs(last-first)+1 > 4096:
            fail('electrical vector element budget (4096) exceeded', bounds[0].token)
        step = 1 if last >= first else -1
        return tuple(range(first,last+step,step))

    ranges = {name: indices(model.node_ranges.get(name)) for name in model.nodes}
    for name in model.ports:
        if indices(model.port_ranges.get(name)) != ranges[name]:
            fail(f'port/electrical vector declaration mismatch for {name!r}', code='vector_declaration')
    groups = {name: (name,) if bits is None else tuple(f'{name}[{i}]' for i in bits)
              for name,bits in ranges.items()}
    if any(bits is not None for bits in ranges.values()) and sum(map(len,groups.values())) > 4096:
        fail('total electrical node budget (4096) exceeded')
    groups['0'] = ('0',)

    def expression(expr):
        if expr.op == 'node':
            bits = ranges.get(expr.value)
            if expr.args:
                if bits is None:
                    fail(f'indexed electrical node {expr.value!r} is not a vector', expr.token)
                index = integer(expr.args[0])
                if index not in bits:
                    fail(f'electrical index {index} outside {expr.value!r}', expr.token)
                return replace(expr, value=f'{expr.value}[{index}]', args=())
            if bits is not None:
                fail(f'electrical vector {expr.value!r} requires an explicit bit index', expr.token)
        return replace(expr, args=tuple(expression(a) for a in expr.args))

    def body(statements):
        result = []
        for s in statements:
            if isinstance(s,Conditional):
                result.append(replace(s,left=expression(s.left),right=expression(s.right),
                                      then_body=body(s.then_body),else_body=body(s.else_body)))
            else:
                updates = dict(rhs=expression(s.rhs))
                if isinstance(s,ContributionStatement):
                    updates['branch'] = expression(s.branch)
                if isinstance(s,Assignment) and s.index is not None:
                    updates['index'] = expression(s.index)
                result.append(replace(s,**updates))
        return tuple(result)

    return replace(model, ports=tuple(bit for p in model.ports for bit in groups[p]),
                   nodes={bit for n in model.nodes for bit in groups[n]},
                   directions={bit: direction for n,direction in model.directions.items() for bit in groups[n]},
                   node_ranges={},port_ranges={},analog=list(body(model.analog)),
                   initial=list(body(model.initial)),events=[replace(e,body=body(e.body),triggers=tuple(
                       replace(leaf,arguments=tuple(expression(a) if a is not None else None for a in leaf.arguments))
                       for leaf in e.triggers)) for e in model.events]), groups
