"""Reject integer-parameter expressions whose semantics the real IR would lose.

This is a conservative boundary, not a second arithmetic evaluator: integer
division and overflow need a typed integer lowering path. Explicit real operands
use the existing real arithmetic. Legacy real-only expressions are unchanged.
"""
from dataclasses import fields, is_dataclass
from .errors import CompileError
from .syntax import Expr, Token


def check_integer_expression(expr, model, values, *, check_literals=False):
    """Include literal-only expressions at new typed/boundary entry points."""
    names = {n for n,t in model.parameter_types.items() if t == 'integer'}
    def uses_integer(e):
        return e.op == 'parameter' and e.value in names or any(uses_integer(a) for a in e.args)
    if not check_literals and (not names or not uses_integer(expr)):
        return

    def fail(e):
        raise CompileError(f'{model.source}:{e.token.line}: integer parameter arithmetic requires typed division/overflow semantics; use explicit real operands when real arithmetic is intended',
                           code='unsupported_integer_arithmetic', token=e.token)

    def visit(e):
        if e.op == 'number':
            # A substituted genvar retains its identifier token for provenance.
            return int(e.value) if e.token.text.isdigit() or e.token.kind == 'name' else None
        if e.op == 'parameter':
            return int(values[e.value]) if e.value in names and e.value in values else None
        args = [visit(a) for a in e.args]
        if e.op == 'checked':
            # Visit every obligation, but retain the actual return's type.
            return args[0]
        if not args or None in args:
            return None
        if e.op == '/':
            fail(e)
        # Preserve the signed minimum literal, whose positive magnitude is one
        # beyond the signed range. Computed negation/overflow still rejects.
        if e.op == 'unary-' and e.args[0].op == 'number' and args[0] == 2147483648:
            return -2147483648
        if e.op == '+': value = args[0]+args[1]
        elif e.op == '-': value = args[0]-args[1]
        elif e.op == '*': value = args[0]*args[1]
        elif e.op == 'unary-': value = -args[0]
        elif e.op == 'unary+': value = args[0]
        else: return None
        if any(not -2147483648 <= n <= 2147483647 for n in (*args,value)):
            fail(e)
        return value

    visit(expr)


def check_integer_model(model, values):
    """Check executable expressions/bounds; effective defaults are checked at bind."""
    if 'integer' not in model.parameter_types.values():
        return
    def visit(value):
        if isinstance(value,Expr):
            check_integer_expression(value,model,values)
        elif is_dataclass(value) and not isinstance(value,Token):
            for f in fields(value):
                visit(getattr(value,f.name))
        elif isinstance(value,dict):
            for child in value.values(): visit(child)
        elif isinstance(value,(list,tuple)):
            for child in value: visit(child)
    for f in fields(model):
        if f.name != 'parameters':
            visit(getattr(model,f.name))
