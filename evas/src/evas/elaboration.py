"""Pure source elaboration before instance binding and semantic IR lowering."""
from dataclasses import replace

from .errors import CompileError
from .limits import MAX_EXPRESSION_DEPTH, MAX_IR_ITEMS, MAX_SOURCE_NESTING
from .syntax import Assignment, Conditional, Event, Expr, Loop, Model, OPERATOR_NAMES


def inline_functions(model: Model) -> Model:
    """Substitute typed input-only functions; never duplicate history call sites."""
    if not model.functions:
        return model
    def fail(message, token, *, code="compile_error"):
        raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}', code=code, token=token)

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
            if item.op == 'checked' or item.op == 'function_assign' and item.value == 'real':
                # A real copy preserves the computational tree. Keep its
                # typed AST node and ordinary lowering/audit visits, without
                # counting that metadata as another expanded arithmetic node.
                # Integer assignments still count their conversion operation.
                depth, size = memo[id(item.args[0])]
            else:
                depth = 1 + max((memo[id(a)][0] for a in item.args), default=0)
                size = 1 + sum(memo[id(a)][1] for a in item.args)
            if depth > MAX_EXPRESSION_DEPTH or size > MAX_IR_ITEMS:
                fail('function expansion exceeds expression depth/size budget', expr.token, code="resource_budget")
            memo[id(item)] = depth, size

    def unpack(expr, obligations):
        if expr.op == 'checked':
            obligations.extend(expr.args[1:])
            value = expr.args[0]
            return replace(value, result_type=expr.result_type) if expr.result_type else value
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
            fail('function expansion exceeds expression depth budget', expr.token, code="resource_budget")
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
            fail('recursive or excessively nested analog function calls are unsupported', expr.token,
                 code='compile_error' if name in stack else 'resource_budget')
        function = model.functions[name]
        if len(args) != len(function.inputs):
            fail(f'function {name!r} requires {len(function.inputs)} inputs', expr.token)
        pending = list(args)
        while pending:
            item = pending.pop()
            if item.op in OPERATOR_NAMES:
                fail('function arguments cannot contain history call sites', item.token)
            pending.extend(item.args)
        def assignment(value, kind, token):
            return Expr('function_assign', kind, (value,), token, result_type=kind)
        local = {n:assignment(value, function.variable_types[n], expr.token)
                 for n,value in zip(function.inputs,args)}
        if function.return_type == 'integer':
            local[name] = Expr('number', 0., (), function.token, result_type='integer')
        names = function.variables | {name}
        obligations.extend(local[n] for n in function.inputs)
        def statements(body, bindings, expansion_depth):
            for statement in body:
                # Branch descent and calls share a budget: separately bounded
                # source nesting and call chains can multiply Python stack use.
                if expansion_depth > MAX_EXPRESSION_DEPTH:
                    fail('function expansion exceeds combined branch/call depth budget',
                         statement.token, code="resource_budget")
                if isinstance(statement, Conditional):
                    # Capture the predicate before either branch changes locals.
                    # The immutable expression keeps VA's sequential semantics.
                    predicate = Expr(statement.relation, None,
                        (statement.left, statement.right), statement.token)
                    predicate = unpack(expand(predicate, bindings, names, (*stack, name), expansion_depth+1), obligations)
                    bounded(predicate)
                    obligations.append(predicate)
                    then_values = statements(statement.then_body, dict(bindings), expansion_depth+1)
                    else_values = statements(statement.else_body, dict(bindings), expansion_depth+1)
                    merged = {}
                    for target in then_values:
                        if target not in else_values:
                            continue
                        yes, no = then_values[target], else_values[target]
                        value = yes if yes is no else Expr('ternary', None,
                            (predicate, yes, no), statement.token)
                        bounded(value)
                        merged[target] = value
                    bindings = merged
                    continue
                if not isinstance(statement, Assignment):
                    fail('pure analog functions require scalar assignments and finite if/else branches', statement.token)
                if statement.index is not None:
                    fail('pure analog function assignments require scalar targets', statement.token)
                if statement.name not in names:
                    fail('function assignments must target its local variables or return value', statement.token)
                value = unpack(expand(statement.rhs, bindings, names, (*stack, name), expansion_depth+1), obligations)
                kind = function.return_type if statement.name == name else function.variable_types[statement.name]
                bindings[statement.name] = assignment(value, kind, statement.token)
                bounded(bindings[statement.name])
                obligations.append(bindings[statement.name])
            return bindings
        local = statements(function.body, local, depth)
        if name not in local:
            fail('function must assign its return value', function.token)
        # Retain every argument and RHS through instance binding, including
        # discarded decisions and aliases. Only the typed result is substituted
        # into the caller's computation; closed index/operator contexts stay local.
        bounded(local[name])
        return replace(checked(local[name], obligations, expr), result_type=function.return_type)

    def body(statements):
        from .syntax import Display
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
            elif isinstance(statement, Display):
                result.append(replace(statement, args=tuple(expand(arg) for arg in statement.args)))
            else:
                updates = {'rhs': expand(statement.rhs)}
                if getattr(statement, 'index', None) is not None:
                    updates['index'] = expand(statement.index)
                result.append(replace(statement, **updates))
        return tuple(result)

    # Validate even unused declarations structurally, so bad
    # names, access/filter calls and recursive definitions cannot hide unused.
    for function in model.functions.values():
        dummy = Expr('call', function.name,
                     tuple(Expr('number', 0., (), function.token) for _ in function.inputs), function.token)
        expand(dummy)
    return replace(model,
                   parameters={n: expand(e) for n,e in model.parameters.items()},
                   variable_initializers={n: expand(e) for n,e in model.variable_initializers.items()},
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


def _validate_loop_node_declarations(model: Model):
    """Check voltage names before a loop can erase them, without creating IR.

    Declarations are fixed for this model, so expression identity is sufficient
    for this name-only walk. It checks every checked/conditional arm but neither
    evaluates indices nor proves types, ranges or event activation. Keep strong
    references in the cache; never share it across models or compilations.
    """
    from .syntax import ContributionStatement, Display

    pending = [*model.initial, *model.analog, *model.events]
    seen = {}
    while pending:
        item = pending.pop()
        key = id(item)
        if key in seen:
            continue
        if isinstance(item, Expr):
            if item.op == 'node' and item.value != '0' and item.value not in model.nodes:
                token = item.token
                raise CompileError(
                    f'{token.source or model.source}:{token.line}:{token.column}: '
                    f'undeclared electrical node {item.value!r}',
                    code='undeclared_node', token=token)
            pending.extend(item.args)
        elif isinstance(item, Loop):
            pending.extend((item.start, item.limit, item.update, *item.body))
        elif isinstance(item, Conditional):
            pending.extend((item.left, item.right, *item.then_body, *item.else_body))
        elif isinstance(item, Event):
            pending.extend(item.body)
            pending.extend(arg for leaf in item.triggers for arg in leaf.arguments if arg is not None)
        elif isinstance(item, Assignment):
            pending.append(item.rhs)
            if item.index is not None:
                pending.append(item.index)
        elif isinstance(item, ContributionStatement):
            pending.extend((item.branch, item.rhs))
        elif isinstance(item, Display):
            pending.extend(item.args)
        else:
            raise CompileError('unsupported statement in loop declaration check', token=item.token)
        seen[key] = item


def elaborate_loops(model: Model, parameter):
    """Expand initial and analog trees with one budget; no runtime loop path."""
    from .ir import Affine
    from .lowering import lower
    from .syntax import Assignment, ContributionStatement, Display

    def has_loop(statements):
        return any(isinstance(statement, Loop) or isinstance(statement, Conditional)
                   and (has_loop(statement.then_body) or has_loop(statement.else_body))
                   or isinstance(statement, Event) and has_loop(statement.body)
                   for statement in statements)

    if not has_loop(model.analog) and not has_loop(model.initial):
        if any(has_loop(event.body) for event in model.events):
            _validate_loop_node_declarations(model)
        return model

    budget = 4096
    count = 0
    iterations = 0

    def fail(message, token, *, code="compile_error"):
        raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}', code=code, token=token)

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
            # The static control is validated signed32 before it enters indices.
            return Expr('number', float(indices[expr.value]), (), expr.token, result_type='integer')
        path = (*expr.expansion,*indices.items())
        if len(path) > MAX_SOURCE_NESTING:
            fail('expanded call-site identity depth budget exceeded', expr.token, code="resource_budget")
        return replace(expr, args=tuple(substitute(arg,indices,memo) for arg in expr.args), expansion=path)

    def origin(token, indices):
        path = (*token.expansion, *indices.items())
        if len(path) > MAX_SOURCE_NESTING:
            fail('expanded event identity depth budget exceeded', token, code="resource_budget")
        return replace(token, expansion=path)

    def constant(expr, indices):
        try:
            value = lower(substitute(expr,indices), parameter, {}, model.source)
        except CompileError as exc:
            if exc.diagnostic['code'] == 'resource_budget':
                raise
            fail(f'static for control requires a signed 32-bit instance-constant integer: {exc}', expr.token)
        if not isinstance(value, Affine) or value.terms or not value.constant.is_integer() or not -2147483648 <= value.constant <= 2147483647:
            fail('static for control requires a signed 32-bit instance-constant integer', expr.token)
        return int(value.constant)

    def node_name(expr, indices):
        return (f'{expr.value}[{constant(expr.args[0], indices)}]'
                if expr.args else str(expr.value))

    def dependencies(expr, indices, memo=None):
        if memo is None:
            memo = {}
        key = id(expr)
        if key in memo:
            return memo[key][1]
        result = dependency_value(expr, indices, memo)
        memo[key] = (expr, result)
        return result

    def dependency_value(expr, indices, memo):
        nodes, held = set(), False
        if expr.op == 'voltage':
            return {node_name(arg, indices) for arg in expr.args}, False
        if expr.op in OPERATOR_NAMES or expr.op in ('parameter', 'index') and expr.value in model.variables:
            held = True
        for arg in expr.args:
            child_nodes, child_held = dependencies(arg, indices, memo)
            nodes |= child_nodes
            held |= child_held
        return nodes, held

    def validate_loop(statement, active):
        integer_local = model.variables.get(statement.name) == 'integer' and statement.name not in model.arrays
        if (statement.name not in model.genvars and not integer_local) or statement.name in active:
            fail('static for requires an unshadowed declared genvar or scalar integer', statement.token)
        if integer_local:
            def writes(body):
                for item in body:
                    if isinstance(item, Assignment) and item.name == statement.name:
                        return True
                    if isinstance(item, Conditional) and (writes(item.then_body) or writes(item.else_body)):
                        return True
                    if isinstance(item, (Loop, Event)) and (getattr(item, 'name', None) == statement.name or writes(item.body)):
                        return True
                return False
            if writes(statement.body):
                fail('static integer for body cannot modify its loop control variable', statement.token)
        return integer_local

    def validate_event_body(statements, active, affected, erased=False):
        # Empty static loops must not erase unsupported event-body structure.
        def integral_type(expr):
            if expr.result_type == 'real':
                return False
            if expr.result_type == 'integer':
                return True
            if expr.op == 'number':
                return expr.token.text.isdecimal() or expr.token.kind == 'name'
            if expr.op == 'parameter':
                return (model.variables.get(expr.value) == 'integer' or
                        model.parameter_types.get(expr.value) == 'integer' or
                        expr.value in model.genvars)
            if expr.op in ('<', '<=', '>', '>=', '==', '!=', '&&', '||', 'unary!'):
                return True
            if expr.op == 'index':
                return model.variables.get(expr.value) == 'integer'
            if expr.op == 'checked':
                return integral_type(expr.args[0])
            if expr.op == 'ternary':
                return all(integral_type(arg) for arg in expr.args[1:])
            return expr.op in ('+', '-', '*', '/', '%', 'unary+', 'unary-') and all(integral_type(arg) for arg in expr.args)

        def integer_range(expr):
            # An erased body has no runtime signed32 check. Use the declaration
            # domain for states, the bound value for parameters/genvars, and
            # validate each typed intermediate before an outer fold erases it.
            if expr.op == 'number':
                return int(expr.value), int(expr.value)
            if expr.op == 'parameter':
                if expr.value in active:
                    return active[expr.value], active[expr.value]
                if expr.value in model.parameters:
                    value = parameter(expr.value)
                    return int(value), int(value)
                return -2147483648, 2147483647
            if expr.op == 'index':
                return -2147483648, 2147483647
            if expr.op in ('<', '<=', '>', '>=', '==', '!=', '&&', '||', 'unary!'):
                return 0, 1
            if expr.op == 'checked':
                return integer_range(expr.args[0])
            if expr.op == 'ternary':
                a, b = (integer_range(arg) for arg in expr.args[1:])
                return min(a[0], b[0]), max(a[1], b[1])
            a = integer_range(expr.args[0])
            if expr.op == 'unary+':
                return a
            if expr.op == 'unary-':
                return -a[1], -a[0]
            b = integer_range(expr.args[1])
            if expr.op == '+':
                return a[0]+b[0], a[1]+b[1]
            if expr.op == '-':
                return a[0]-b[1], a[1]-b[0]
            if expr.op == '*':
                products = [x*y for x in a for y in b]
                return min(products), max(products)
            if b[0] != b[1] or b[0] == 0:
                fail('erased integer division/modulo requires a nonzero constant divisor', expr.token)
            divisor = b[0]
            if expr.op == '%':
                width = abs(divisor)-1
                return max(a[0], -width) if a[0] < 0 else 0, min(a[1], width) if a[1] > 0 else 0
            def quotient(value):
                return (abs(value)//abs(divisor)) * (-1 if (value < 0) != (divisor < 0) else 1)
            values = [quotient(value) for value in a]
            return min(values), max(values)

        def expression(expr, predicate=False, seen=None, *, assignment_root=False):
            if seen is None:
                seen = set()
            if id(expr) in seen:
                return
            seen.add(id(expr))
            if expr.op in OPERATOR_NAMES and expr.op not in ("sin", "cos", "exp", "ln", "sqrt"):
                fail('event bodies do not support history/operator calls', expr.token)
            if expr.op == 'parameter' and expr.value in model.arrays:
                fail('array identifier requires an index', expr.token)
            if expr.op == 'parameter' and expr.value not in model.variables and expr.value not in model.parameters and expr.value not in model.genvars and expr.value not in active:
                fail(f'unknown parameter or variable {expr.value!r}', expr.token)
            if expr.op == 'index':
                if expr.value not in model.arrays:
                    fail('indexed identifier is not a declared variable array', expr.token)
                from .array_elaboration import gate_dynamic_index
                gate_dynamic_index(substitute(expr.args[0], active), model)
                try:
                    index = constant(expr.args[0], active)
                except CompileError as error:
                    if error.diagnostic['code'] == 'resource_budget':
                        raise
                    if erased:
                        fail('erased loop dynamic array index lacks a retained use-site proof', expr.token,
                             code='array_index_range')
                else:
                    first, last = (constant(bound, active) for bound in model.arrays[expr.value])
                    if not min(first, last) <= index <= max(first, last):
                        fail('array index is outside its declaration', expr.token, code='array_index_range')
            if predicate and expr.op in ('parameter', 'index') and expr.value in model.variables:
                fail('event conditions and loop controls cannot depend on state', expr.token)
            for arg in expr.args:
                expression(arg, predicate, seen)
            if erased and expr.op in ('+', '-', '*', '/', '%', 'unary+', 'unary-') and integral_type(expr):
                low, high = integer_range(expr)
                if low < -2147483648 or high > 2147483647:
                    def unknown_state(item):
                        return (item.op == 'index' or item.op == 'parameter' and
                                item.value in model.variables and item.value not in active or
                                any(unknown_state(arg) for arg in item.args))
                    # Match the retained assignment's final signed32 check.
                    # Only its full value may retain an unknown state domain;
                    # every inner operation still needs its own range proof.
                    if not (assignment_root and unknown_state(expr) and
                            low <= 2147483647 and high >= -2147483648):
                        fail('erased loop integer intermediate may exceed signed 32-bit range', expr.token)

        for statement in statements:
            if isinstance(statement, Loop):
                validate_loop(statement, active)
                # Retained runtime loops receive full original-tree admission
                # after scalarization; never substitute an invented control.
                pending = [statement.start, statement.limit]
                dynamic = False
                while pending:
                    item = pending.pop()
                    dynamic |= item.op == 'parameter' and item.value in model.variables
                    pending.extend(item.args)
                if dynamic:
                    continue
                start = constant(statement.start, active)
                scope = {**active, statement.name: start}
                expression(substitute(statement.start, active), True)
                for expr in (statement.limit, statement.update):
                    expression(substitute(expr, scope), True)
                constant(statement.limit, scope)
                constant(statement.update, scope)
                limit = constant(statement.limit, scope)
                reachable = {'<': start < limit, '<=': start <= limit,
                             '>': start > limit, '>=': start >= limit}[statement.relation]
                validate_event_body(statement.body, scope, affected, erased or not reachable)
            elif isinstance(statement, Conditional):
                expression(statement.left)
                expression(statement.right)
                # Reuse the existing IR predicate boundary, including structural
                # dependencies that numeric cancellation must not erase.
                from .instance_compiler import _predicate_degree
                nodes = {}
                def scalar(expr, memo=None):
                    # One predicate root with fixed active indices and node map.
                    # Keep original objects alive; never share across loop scopes.
                    if memo is None:
                        memo = {}
                    key = id(expr)
                    if key in memo:
                        return memo[key][1]
                    if expr.op == 'index':
                        if expr.value not in model.arrays:
                            fail('indexed identifier is not a declared variable array', expr.token)
                        try:
                            index = constant(expr.args[0], active)
                        except CompileError as error:
                            if error.diagnostic['code'] == 'resource_budget':
                                raise
                            from .array_elaboration import gate_dynamic_index
                            gate_dynamic_index(expr.args[0], model)
                            result = Expr('parameter', expr.value, (), expr.token)
                            memo[key] = (expr, result)
                            return result
                        first, last = (constant(bound, active) for bound in model.arrays[expr.value])
                        if not min(first,last) <= index <= max(first,last):
                            fail('event predicate array index is outside its declaration', expr.token)
                        result = Expr('parameter', f'{expr.value}[{index}]', (), expr.token)
                    elif expr.op == 'node':
                        name = node_name(expr, active)
                        nodes.setdefault(name, len(nodes))
                        result = replace(expr, value=name, args=())
                    else:
                        result = replace(expr, args=tuple(scalar(arg, memo) for arg in expr.args))
                    memo[key] = (expr, result)
                    return result
                for expr in (statement.left, statement.right):
                    from .ir import StateRef
                    def resolve(name):
                        return StateRef(0) if name in model.variables or name.split('[',1)[0] in model.arrays else parameter(name)
                    scalar_expr = scalar(substitute(expr, active))
                    from .syntax import contains_decision
                    if contains_decision(scalar_expr):
                        from .predicate_structure import lower_predicate_structure
                        value = lower_predicate_structure(scalar_expr, resolve, nodes, model.source)
                    else:
                        value = lower(scalar_expr, resolve, nodes,
                                      model.source, preserve_structure=True, memo={})
                    if _predicate_degree(value) is None:
                        fail('event conditions require affine voltage/state predicates', expr.token)
                    if dependencies(expr, active)[0] & affected:
                        fail('event condition may depend on state through the voltage network', expr.token)
                validate_event_body(statement.then_body, active, affected, erased)
                validate_event_body(statement.else_body, active, affected, erased)
            elif isinstance(statement, Display):
                for arg in statement.args:
                    expression(arg)
            else:
                if not isinstance(statement, Assignment):
                    fail('event bodies require assignments or supported conditionals', statement.token)
                if statement.name in model.genvars:
                    fail('genvar can only be assigned in its for control', statement.token)
                expression(statement.rhs, assignment_root=(model.variables.get(statement.name) == 'integer'))
                if erased and model.variables.get(statement.name) == 'integer':
                    if not integral_type(statement.rhs):
                        fail('erased loop integer assignment requires integral source arithmetic', statement.token)
                if statement.index is not None:
                    expression(substitute(statement.index, active))
                    if erased:
                        # Reuse the same read-side structural/type/range gate.
                        expression(Expr('index', statement.name, (statement.index,), statement.token))

    def validate_initial_body(statements, active, in_loop=False):
        # Validate the unexpanded tree too: a zero-trip loop cannot erase a
        # dynamic initializer, index, illegal nested control or declaration.
        for statement in statements:
            if isinstance(statement, Loop):
                validate_loop(statement, active)
                start = constant(statement.start, active)
                scope = {**active, statement.name: start}
                constant(statement.limit, scope)
                constant(statement.update, scope)
                validate_initial_body(statement.body, scope, True)
            elif in_loop:
                if not isinstance(statement, Assignment) or statement.name not in model.variables:
                    fail('initialization loops require declared variable assignments', statement.token,
                         code='unsupported_initial_event')
                if statement.index is not None:
                    if statement.name not in model.arrays:
                        fail('initialization loop indexed target must be a variable array', statement.token,
                             code='unsupported_initial_event')
                    try:
                        index = constant(statement.index, active)
                    except CompileError as error:
                        if error.diagnostic['code'] == 'resource_budget':
                            raise
                        fail(f'initialization loop array index requires an instance-constant integer: {error}',
                             statement.index.token, code='unsupported_initial_event')
                    first, last = (constant(bound, active) for bound in model.arrays[statement.name])
                    if not min(first, last) <= index <= max(first, last):
                        fail('initialization loop array index is outside its declaration', statement.index.token,
                             code='unsupported_initial_event')
                elif statement.name in model.arrays:
                    fail('initialization loop array assignment requires an explicit element index', statement.token,
                         code='unsupported_initial_event')
                try:
                    value = lower(substitute(statement.rhs, active), parameter, {}, model.source,
                                  preserve_structure=True)
                    if not isinstance(value, Affine) or value.terms:
                        raise CompileError('initializer is not an instance constant')
                except CompileError as error:
                    if error.diagnostic['code'] == 'resource_budget':
                        raise
                    fail(f'initialization loop values must be instance constants: {error}',
                         statement.token, code='unsupported_initial_event')

    validate_initial_body(model.initial, {})
    event_bodies = []

    def body(statements, indices, depth=0, runtime=False, in_runtime_loop=False):
        nonlocal count, iterations
        if depth > MAX_SOURCE_NESTING:
            fail('static loop nesting budget exceeded', statements[0].token, code="resource_budget")
        result = []
        for statement in statements:
            if isinstance(statement, Loop):
                integer_local = validate_loop(statement, indices)
                # State-dependent event controls execute against the candidate
                # frame. Static genvars retain the original elaboration path.
                dynamic = in_runtime_loop and integer_local
                if runtime and integer_local:
                    pending = [statement.start, statement.limit]
                    while pending:
                        item = pending.pop()
                        dynamic |= item.op == 'parameter' and item.value in model.variables
                        pending.extend(item.args)
                if dynamic:
                    result.append(replace(statement,
                        start=substitute(statement.start, indices),
                        limit=substitute(statement.limit, indices),
                        update=substitute(statement.update, indices),
                        body=body(statement.body, indices, depth+1, runtime=True, in_runtime_loop=True),
                        token=origin(statement.token, indices)))
                    continue
                value = constant(statement.start, indices)
                seen = set()
                while True:
                    scope = {**indices, statement.name:value}
                    end = constant(statement.limit,scope)
                    active = {'<': value<end, '<=':value<=end, '>':value>end, '>=':value>=end}[statement.relation]
                    if not active:
                        break
                    if value in seen or len(seen) == budget:
                        fail('nonterminating or over-budget static loop', statement.token,
                             code='compile_error' if value in seen else 'resource_budget')
                    iterations += 1
                    if iterations > budget:
                        fail('total static iteration budget (4096) exceeded', statement.token, code="resource_budget")
                    seen.add(value)
                    if integer_local:
                        count += 1
                        if count > budget:
                            fail('elaborated statement budget (4096) exceeded', statement.token, code="resource_budget")
                        result.append(Assignment(statement.name, Expr('number', float(value), (), statement.token), origin(statement.token, scope)))
                    result.extend(body(statement.body, scope, depth+1, runtime=runtime, in_runtime_loop=in_runtime_loop))
                    value = constant(statement.update, scope)
                if integer_local:
                    count += 1
                    if count > budget:
                        fail('elaborated statement budget (4096) exceeded', statement.token, code="resource_budget")
                    result.append(Assignment(statement.name, Expr('number', float(value), (), statement.token), origin(statement.token, indices)))
            elif isinstance(statement, Conditional):
                result.append(replace(statement, left=substitute(statement.left,indices), right=substitute(statement.right,indices),
                                      then_body=body(statement.then_body,indices,depth+1,runtime=runtime,in_runtime_loop=in_runtime_loop),
                                      else_body=body(statement.else_body,indices,depth+1,runtime=runtime,in_runtime_loop=in_runtime_loop), token=origin(statement.token,indices)))
            else:
                if isinstance(statement, Assignment) and statement.name in model.genvars:
                    fail('genvar can only be assigned in its for control',statement.token)
                count += 1
                if count > budget:
                    fail('elaborated statement budget (4096) exceeded', statement.token, code="resource_budget")
                if isinstance(statement, Event):
                    event_bodies.append((statement.body, indices))
                    result.append(replace(statement, token=origin(statement.token,indices),
                        body=body(statement.body,indices,depth+1,runtime=all(t.kind in ("timer", "cross", "final_step") for t in statement.triggers),
                                  in_runtime_loop=has_runtime_control(statement.body)), triggers=tuple(
                            replace(leaf, token=origin(leaf.token,indices), arguments=tuple(
                                substitute(arg,indices) if arg is not None else None for arg in leaf.arguments))
                            for leaf in statement.triggers)))
                    continue
                if isinstance(statement, Display):
                    result.append(replace(statement, token=origin(statement.token, indices),
                        args=tuple(substitute(arg, indices) for arg in statement.args)))
                    continue
                updates = {'rhs': substitute(statement.rhs, indices)}
                if isinstance(statement, Assignment) and statement.index is not None:
                    updates['index'] = substitute(statement.index, indices)
                if isinstance(statement, ContributionStatement):
                    updates['branch'] = substitute(statement.branch, indices)
                result.append(replace(statement, **updates))
        return tuple(result)

    def has_runtime_control(statements):
        def held(expr):
            return (expr.op == 'parameter' and expr.value in model.variables or
                    any(held(arg) for arg in expr.args))
        for item in statements:
            if isinstance(item, Loop) and (held(item.start) or held(item.limit) or has_runtime_control(item.body)):
                return True
            if isinstance(item, Conditional) and (has_runtime_control(item.then_body) or has_runtime_control(item.else_body)):
                return True
        return False

    expanded_initial = body(model.initial,{})
    expanded = body(model.analog,{})
    # Inspect already-expanded continuous relations, so separate static vector
    # bits retain their dependencies when validating an erased event body.
    relations, affected = [], set()
    pending = list(expanded)
    while pending:
        statement = pending.pop()
        if isinstance(statement, Conditional):
            pending.extend((*statement.then_body, *statement.else_body))
        elif isinstance(statement, ContributionStatement):
            targets = {node_name(arg, {}) for arg in statement.branch.args
                       if model.directions.get(str(arg.value).split('[')[0]) not in ('input', 'inout')
                       and arg.value != '0'}
            reads, held = dependencies(statement.rhs, {})
            relations.append((targets, reads))
            if held:
                affected |= targets
    while True:
        propagated = affected | {target for targets, reads in relations
                                 if (targets | reads) & affected for target in targets}
        if propagated == affected:
            break
        affected = propagated
    for statements, indices in event_bodies:
        validate_event_body(statements, indices, affected)
    # Preserve structural diagnostics, then check names in the original tree,
    # including events erased by an outer zero-trip loop.
    _validate_loop_node_declarations(model)
    return replace(model, initial=list(expanded_initial), analog=list(expanded))


def unroll_loops(model: Model, parameter):
    """Compatibility entry for consumers of already elaborated analog bodies."""
    return tuple(elaborate_loops(model, parameter).analog)
