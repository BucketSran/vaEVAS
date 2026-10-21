"""A closed initial-only scalar binding, retaining its original math AST.

This narrow producer has no runtime writers or initialization observers. Ordinary
relations consume the native math boxes, never a precomputed pow representative.
"""
from fractions import Fraction as Q
import math
from .errors import CompileError
from .ir import Affine, Binary, MathFunction, OperatorRef, Origin
from .limits import check_ir
from .integer_bits import integer_type
from .syntax import Assignment, ContributionStatement


def binding(compiler, model):
    # Preserve every old route unless this complete, observer-free source shape
    # contains a pow which the original integer/half-power paths cannot lower.
    if (len(model.initial) != 1 or model.events or model.variable_initializers
            or model.arrays or not model.analog):
        return {}
    statement = model.initial[0]
    if (not isinstance(statement, Assignment) or statement.index is not None
            or model.variables.get(statement.name) != 'real'
            or compiler.state_names != (statement.name,)):
        return {}

    def charge(n=1):
        remaining = compiler.compilation.initial_math_work
        if n > remaining:
            compiler.compilation.initial_math_work = 0
            raise CompileError('closed initial math exceeds source proof budget (100000)',
                               code='resource_budget', token=statement.token,
                               instance=compiler.instance.name)
        compiler.compilation.initial_math_work = remaining - n

    for ordinary in model.analog:
        charge()
        if not isinstance(ordinary, ContributionStatement):
            return {}

    def fail(message):
        raise CompileError(message, code='unsupported_initial_event',
                           token=statement.token, instance=compiler.instance.name)

    # This scan retains dependencies before any arithmetic/identity can erase
    # them, including all checked function arguments and zero-weight operands.
    pending, powers = [statement.rhs], []
    while pending:
        charge()
        expr = pending.pop()
        if expr.op == 'power':
            powers.append(expr)
        elif expr.op not in ('number','parameter','+','-','*','/','unary+','unary-','checked'):
            return {}
        if expr.op == 'parameter' and expr.value not in model.parameters:
            return {}
        pending.extend(expr.args)
    if len(powers) != 1:
        return {}

    types = {}

    def rational(expr):
        charge()
        if expr.op == 'number':
            result = Q(expr.value)
        elif expr.op == 'parameter':
            result = Q(compiler.parameter(expr.value))
        else:
            args = [rational(arg) for arg in expr.args]
            if expr.op == 'checked':
                result = args[0]
            elif expr.op in ('unary+','unary-'):
                result = args[0] if expr.op == 'unary+' else -args[0]
            elif expr.op in ('+','-','*','/'):
                charge()
                a,b = args
                if expr.op == '/' and types[id(expr.args[0])] and types[id(expr.args[1])]:
                    fail('closed initial math does not replace source integer division')
                if expr.op == '/' and b == 0:
                    fail('closed initial math requires a nonzero denominator')
                result = {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[expr.op]()
            else:
                fail('pow operands require closed rational instance constants')
        charge()
        typed = integer_type(expr, model.variables, model.parameter_types, model.genvars,
                             child_types=tuple(types[id(arg)] for arg in expr.args))
        types[id(expr)] = typed
        if (typed and expr.op in ('+', '-', '*', '/', 'unary+', 'unary-')
                and not -2147483648 <= result <= 2147483647):
            fail('integer intermediate may exceed signed 32-bit range')
        if max(result.numerator.bit_length(),result.denominator.bit_length()) > 4096:
            fail('closed initial rational exceeds 4096 bits')
        try:
            representative = float(result)
        except OverflowError:
            fail('closed initial math is not finite')
        if not math.isfinite(representative) or result and representative == 0:
            fail('closed initial math is not finitely representable')
        return result

    power = powers[0]
    base, exponent = (rational(arg) for arg in power.args)
    if exponent == Q(1,2) or exponent.denominator == 1 and exponent != 0:
        return {}
    if base <= 0:
        fail('closed initial real power requires a strictly positive base')
    def audit_parts(expr):
        charge()
        if expr.op == 'power':
            return True
        contains = [audit_parts(a) for a in expr.args]
        if any(contains):
            for arg, has_power in zip(expr.args, contains):
                if not has_power:
                    rational(arg)
        return any(contains)

    audit_parts(statement.rhs)

    # Audit all contribution statements in the same scan owner. The ordinary
    # compiler still validates their entire source and electrical relations.

    def origin(expr, stage=None):
        t = expr.token
        if stage and len(t.expansion) >= 64:
            raise CompileError('closed initial math expansion exceeds64',code='resource_budget',token=t)
        return Origin(t.source or model.source,t.line,t.column,
                      compiler.instance.name,t.expansion + ((stage,0),) if stage else t.expansion)

    def build(expr):
        charge()
        if expr.op == 'number':
            return Affine(expr.value,())
        if expr.op == 'parameter':
            return Affine(compiler.parameter(expr.value),())
        args = [build(a) for a in expr.args] if expr.op != 'power' else None
        if expr.op == 'checked':
            return args[0]
        if expr.op in ('unary+','unary-'):
            return args[0] if expr.op == 'unary+' else Binary('multiply',Affine(-1.,()),args[0])
        if expr.op in ('+','-','*','/'):
            a,b = args
            if expr.op == '-':
                return Binary('add',a,Binary('multiply',Affine(-1.,()),b))
            return Binary({'+':'add','*':'multiply','/':'divide'}[expr.op],a,b)
        if expr.op == 'power':
            # Both complete operands were audited above. This exact identity
            # only applies to this positive, dependency-free base.
            if exponent == 0:
                return Affine(1.,())
            x,y = (build(a) for a in expr.args)
            charge(2)
            index = len(compiler.compilation.operators)
            compiler.compilation.operators.append(MathFunction('ln',x,origin(expr,'_evas_closed_pow_ln')))
            compiler.compilation.operators.append(MathFunction('exp',Binary('multiply',y,OperatorRef(index)),origin(expr,'_evas_closed_pow_exp')))
            return OperatorRef(index+1)
        fail('unsupported closed initial arithmetic')

    # Audit arithmetic outside pow as well. Its denominator may be the proved
    # positive native power, so runtime outward arithmetic owns the final check.
    value = build(statement.rhs)
    check_ir(value,origin(statement.rhs))
    return {statement.name:value}
