"""Pure source elaboration before instance binding and semantic IR lowering."""
from dataclasses import replace

from .errors import CompileError
from .limits import MAX_EXPRESSION_DEPTH, MAX_IR_ITEMS, MAX_SOURCE_NESTING
from .syntax import Conditional, Event, Expr, Loop, Model, OPERATOR_NAMES


def inline_functions(model: Model) -> Model:
    """Substitute real input-only functions; never duplicate history call sites."""
    if not model.functions:
        return model
    def fail(message, token):
        raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}')

    def bounded(expr):
        # Preserve the original budget at function RHS/return boundaries.
        # checked carries compile-time obligations; only its value substitutes
        # into the computation. Ordinary caller expressions keep their existing
        # source and final IR limits, rather than gaining a new AST tree limit.
        memo, pending = {}, [(expr, False)]
        while pending:
            item, exiting = pending.pop()
            if id(item) in memo:
                continue
            if not exiting:
                pending.append((item, True))
                args = item.args[:1] if item.op == 'checked' else item.args
                pending.extend((a, False) for a in args)
                continue
            if item.op == 'checked':
                depth, size = memo[id(item.args[0])]
            else:
                depth = 1 + max((memo[id(a)][0] for a in item.args), default=0)
                size = 1 + sum(memo[id(a)][1] for a in item.args)
            if depth > MAX_EXPRESSION_DEPTH or size > MAX_IR_ITEMS:
                fail('function expansion exceeds expression depth/size budget', expr.token)
            memo[id(item)] = depth, size

    def unpack(expr, obligations):
        if expr.op == 'checked':
            obligations.extend(expr.args[1:])
            return expr.args[0]
        return expr

    def checked(value, obligations, origin):
        # Hoist obligations out of substituted values. Repeated uses of a
        # function argument must duplicate its computation, not its checks.
        unique = {id(item): item for item in obligations}
        if not unique:
            return value
        result = Expr('checked', None, (value, *unique.values()), origin.token,
                      expansion=origin.expansion)
        return result

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
        if stack and (expr.op in ('voltage', 'index') or expr.op in OPERATOR_NAMES):
            fail('pure analog functions cannot use voltage access or history operators', expr.token)
        expanded = tuple(expand(a, env, local_names, stack, depth+1) for a in expr.args)
        # Index evaluation and waveform arguments have their own closed
        # contexts. Their obligations must be checked at that entry point.
        if expr.op in ('node', 'index', 'array') or expr.op in OPERATOR_NAMES:
            return replace(expr, args=expanded)
        obligations = []
        args = tuple(unpack(a, obligations) for a in expanded)
        if expr.op != 'call':
            return checked(replace(expr, args=args), obligations, expr)
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
        obligations.extend(args)
        for statement in function.body:
            if statement.index is not None:
                fail('pure analog function assignments require scalar targets', statement.token)
            if statement.name not in names:
                fail('function assignments must target its local variables or return value', statement.token)
            local[statement.name] = unpack(expand(statement.rhs, local, names, (*stack, name), depth+1), obligations)
            bounded(local[statement.name])
            obligations.append(local[statement.name])
        if name not in local:
            fail('function must assign its return value', function.token)
        # Retain every argument and RHS through instance binding, including
        # discarded decisions and aliases. Only the real result is substituted
        # into the caller's computation; closed index/operator contexts stay local.
        bounded(local[name])
        return checked(local[name], obligations, expr)

    def body(statements):
        result = []
        for statement in statements:
            if isinstance(statement, Loop):
                result.append(replace(statement, start=expand(statement.start), limit=expand(statement.limit),
                                      update=expand(statement.update), body=body(statement.body)))
            elif isinstance(statement, Event):
                result.append(replace(statement, body=body(statement.body), triggers=tuple(
                    replace(leaf, arguments=tuple(expand(arg) if arg is not None else None
                                                for arg in leaf.arguments)) for leaf in statement.triggers)))
            elif isinstance(statement, Conditional):
                result.append(replace(statement, left=expand(statement.left), right=expand(statement.right),
                                      then_body=body(statement.then_body), else_body=body(statement.else_body)))
            else:
                updates = {'rhs': expand(statement.rhs)}
                if getattr(statement, 'index', None) is not None:
                    updates['index'] = expand(statement.index)
                result.append(replace(statement, **updates))
        return tuple(result)

    # Validate even unused declarations with symbolic real arguments, so bad
    # names, access/filter calls and recursive definitions cannot hide unused.
    for function in model.functions.values():
        dummy = Expr('call', function.name,
                     tuple(Expr('number', 0., (), function.token) for _ in function.inputs), function.token)
        expand(dummy)
    return replace(model,
                   parameters={n: expand(e) for n,e in model.parameters.items()},
                   parameter_ranges={n: tuple(replace(r,
                       lower=expand(r.lower) if isinstance(r.lower,Expr) else r.lower,
                       upper=expand(r.upper) if isinstance(r.upper,Expr) else r.upper) for r in ranges)
                                     for n,ranges in model.parameter_ranges.items()},
                   arrays={n: tuple(expand(e) for e in bounds) for n,bounds in model.arrays.items()},
                   node_ranges={n: tuple(expand(e) for e in bounds) if bounds else None for n,bounds in model.node_ranges.items()},
                   port_ranges={n: tuple(expand(e) for e in bounds) if bounds else None for n,bounds in model.port_ranges.items()},
                   children=tuple(replace(child, parameters=(tuple(expand(e) for e in child.parameters)
                                                           if isinstance(child.parameters,tuple)
                                                           else {n:expand(e) for n,e in child.parameters.items()}))
                                  for child in model.children),
                   analog=list(body(model.analog)), initial=list(body(model.initial)),
                   events=[replace(event, body=body(event.body), triggers=tuple(
                       replace(leaf, arguments=tuple(expand(arg) if arg is not None else None
                                                   for arg in leaf.arguments)) for leaf in event.triggers))
                           for event in model.events])


def unroll_loops(model: Model, parameter):
    """Instance-constant genvar loops, without adding a runtime execution path."""
    from .ir import Affine
    from .lowering import lower
    from .syntax import Assignment, ContributionStatement

    def has_loop(statements):
        return any(isinstance(statement, Loop) or isinstance(statement, Conditional)
                   and (has_loop(statement.then_body) or has_loop(statement.else_body))
                   for statement in statements)

    if not has_loop(model.analog):
        return tuple(model.analog)

    budget = 4096
    count = 0
    iterations = 0

    def fail(message, token):
        raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}')

    def substitute(expr, indices, memo=None):
        # One fixed loop-index environment per root substitution. Never share
        # replacements across iterations, statements or instance bindings.
        if memo is None:
            memo = {}
        key = id(expr)
        if key not in memo:
            memo[key] = (expr, substitute_value(expr, indices, memo))
        return memo[key][1]

    def substitute_value(expr, indices, memo):
        if expr.op == 'parameter' and expr.value in indices:
            return Expr('number', float(indices[expr.value]), (), expr.token)
        path = (*expr.expansion,*indices.items())
        if len(path) > MAX_SOURCE_NESTING:
            fail('expanded call-site identity depth budget exceeded',expr.token)
        return replace(expr, args=tuple(substitute(arg,indices,memo) for arg in expr.args), expansion=path)

    def origin(token, indices):
        path = (*token.expansion, *indices.items())
        if len(path) > MAX_SOURCE_NESTING:
            fail('expanded event identity depth budget exceeded', token)
        return replace(token, expansion=path)

    def constant(expr, indices):
        value = lower(substitute(expr,indices), parameter, {}, model.source)
        if not isinstance(value, Affine) or value.terms or not value.constant.is_integer() or not -2147483648 <= value.constant <= 2147483647:
            fail('genvar control requires a signed 32-bit instance-constant integer', expr.token)
        return int(value.constant)

    def body(statements, indices, depth=0):
        nonlocal count, iterations
        if depth > MAX_SOURCE_NESTING:
            fail('static loop nesting budget exceeded', statements[0].token)
        result = []
        for statement in statements:
            if isinstance(statement, Loop):
                if statement.name not in model.genvars or statement.name in indices:
                    fail('static for requires an unshadowed declared genvar', statement.token)
                value = constant(statement.start, indices)
                seen = set()
                while True:
                    scope = {**indices, statement.name:value}
                    end = constant(statement.limit,scope)
                    active = {'<': value<end, '<=':value<=end, '>':value>end, '>=':value>=end}[statement.relation]
                    if not active:
                        break
                    if value in seen or len(seen) == budget:
                        fail('nonterminating or over-budget static loop', statement.token)
                    iterations += 1
                    if iterations > budget:
                        fail('total static iteration budget (4096) exceeded', statement.token)
                    seen.add(value)
                    result.extend(body(statement.body, scope, depth+1))
                    value = constant(statement.update, scope)
            elif isinstance(statement, Conditional):
                result.append(replace(statement, left=substitute(statement.left,indices), right=substitute(statement.right,indices),
                                      then_body=body(statement.then_body,indices,depth+1),
                                      else_body=body(statement.else_body,indices,depth+1), token=origin(statement.token,indices)))
            else:
                if isinstance(statement, Assignment) and statement.name in model.genvars:
                    fail('genvar can only be assigned in its for control',statement.token)
                count += 1
                if count > budget:
                    fail('elaborated statement budget (4096) exceeded',statement.token)
                if isinstance(statement, Event):
                    result.append(replace(statement, token=origin(statement.token,indices),
                        body=body(statement.body,indices,depth+1), triggers=tuple(
                            replace(leaf, token=origin(leaf.token,indices), arguments=tuple(
                                substitute(arg,indices) if arg is not None else None for arg in leaf.arguments))
                            for leaf in statement.triggers)))
                    continue
                updates = {'rhs': substitute(statement.rhs, indices)}
                if isinstance(statement, Assignment) and statement.index is not None:
                    updates['index'] = substitute(statement.index, indices)
                if isinstance(statement, ContributionStatement):
                    updates['branch'] = substitute(statement.branch, indices)
                result.append(replace(statement, **updates))
        return tuple(result)

    return body(model.analog,{})
