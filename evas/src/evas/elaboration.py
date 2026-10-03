"""Pure source elaboration before instance binding and semantic IR lowering."""
from dataclasses import replace

from .errors import CompileError
from .limits import MAX_EXPRESSION_DEPTH, MAX_IR_ITEMS, MAX_SOURCE_NESTING
from .syntax import Conditional, Expr, Model, OPERATOR_NAMES


def inline_functions(model: Model) -> Model:
    """Substitute real input-only functions; never duplicate history call sites."""
    if not model.functions:
        return model
    def fail(message, token):
        raise CompileError(f'{model.source}:{token.line}:{token.column}: {message}')

    def bounded(expr):
        # Shared AST arguments still expand at every use on the JSON wire.
        memo, pending = {}, [(expr, False)]
        while pending:
            item, exiting = pending.pop()
            if id(item) in memo:
                continue
            if not exiting:
                pending.append((item, True))
                pending.extend((a, False) for a in item.args)
                continue
            depth = 1 + max((memo[id(a)][0] for a in item.args), default=0)
            size = 1 + sum(memo[id(a)][1] for a in item.args)
            if depth > MAX_EXPRESSION_DEPTH or size > MAX_IR_ITEMS:
                fail('function expansion exceeds expression depth/size budget', expr.token)
            memo[id(item)] = depth, size

    def expand(expr, env=None, local_names=frozenset(), stack=(), depth=0):
        if depth > MAX_EXPRESSION_DEPTH:
            fail('function expansion exceeds expression depth budget', expr.token)
        env = env or {}
        if expr.op == 'parameter':
            if expr.value in env:
                return env[expr.value]
            if expr.value in local_names:
                fail(f'function local {expr.value!r} is not assigned before use', expr.token)
            if stack and expr.value not in model.parameters:
                fail('function may only read its locals, arguments and module parameters', expr.token)
            return expr
        if stack and (expr.op == 'voltage' or expr.op in OPERATOR_NAMES):
            fail('pure analog functions cannot use voltage access or history operators', expr.token)
        args = tuple(expand(a, env, local_names, stack, depth+1) for a in expr.args)
        if expr.op != 'call':
            result = replace(expr, args=args)
            return result
        name = str(expr.value)
        if name not in model.functions:
            fail(f'unknown analog function {name!r}', expr.token)
        if name in stack or len(stack) >= MAX_SOURCE_NESTING:
            fail('recursive or excessively nested analog function calls are unsupported', expr.token)
        function = model.functions[name]
        if len(args) != len(function.inputs):
            fail(f'function {name!r} requires {len(function.inputs)} inputs', expr.token)
        pending = list(args)
        while pending:
            item = pending.pop()
            if item.op in OPERATOR_NAMES:
                fail('function arguments cannot contain history call sites', item.token)
            pending.extend(item.args)
        local = dict(zip(function.inputs, args))
        names = function.variables | {name}
        for statement in function.body:
            if statement.name not in names:
                fail('function assignments must target its local variables or return value', statement.token)
            local[statement.name] = expand(statement.rhs, local, names, (*stack, name), depth+1)
            bounded(local[statement.name])
        if name not in local:
            fail('function must assign its return value', function.token)
        bounded(local[name])
        return local[name]

    def body(statements):
        result = []
        for statement in statements:
            if isinstance(statement, Conditional):
                result.append(replace(statement, left=expand(statement.left), right=expand(statement.right),
                                      then_body=body(statement.then_body), else_body=body(statement.else_body)))
            else:
                result.append(replace(statement, rhs=expand(statement.rhs)))
        return tuple(result)

    # Validate even unused declarations with symbolic real arguments, so bad
    # names, access/filter calls and recursive definitions cannot hide unused.
    for function in model.functions.values():
        dummy = Expr('call', function.name,
                     tuple(Expr('number', 0., (), function.token) for _ in function.inputs), function.token)
        expand(dummy)
    return replace(model,
                   parameters={n: expand(e) for n,e in model.parameters.items()},
                   analog=list(body(model.analog)), initial=list(body(model.initial)),
                   events=[replace(event, body=body(event.body), triggers=tuple(
                       replace(leaf, arguments=tuple(expand(arg) if arg is not None else None
                                                   for arg in leaf.arguments)) for leaf in event.triggers))
                           for event in model.events])
