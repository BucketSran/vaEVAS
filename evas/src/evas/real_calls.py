"""Lower one validated pure real function as an executable, scoped call.

The legacy source expansion remains the whole-source semantic audit. This module
owns execution order only; it never evaluates a predicate to discard source.
"""
from dataclasses import replace
from .errors import CompileError
from .syntax import Expr, Assignment, Conditional
from .ir import (Origin, Affine, RealBinding, RealLocal, RealBoundary, RealBind,
                 RealCall, ProcedureStep, ProcedureConditional, Select)
from .lowering import lower


def lower_call(c, expr, parameters, nodes, source, operators, preserve_structure,
               decisions, validate_decision, decision_scope, indices, *, node_declarations):
    name, start, count = expr.source_call
    function = c.model.functions[name]
    owner = c.compilation.native_audit
    owner.activate(expr.token)
    owner.debit('real_call_setup', 8+count, expr)
    builder = c.procedure_builder
    if builder is None:
        raise CompileError('real call requires a retained procedure', token=expr.token)
    expansion = expr.expansion
    def path(item):
        existing = getattr(item, 'expansion', item.token.expansion)
        return existing if expansion and existing[-len(expansion):] == expansion else (*existing, *expansion)
    def origin(item):
        return c.make_ir(Origin, item.token.source or source, item.token.line,
                         item.token.column, c.instance.name, path(item))
    call_origin = c.make_ir(Origin, expr.token.source or source, expr.token.line,
                           expr.token.column, c.instance.name, expansion)
    # An actual function argument is a program-real expression even when its
    # caller is a physical contribution. Only this lexical lookup changes;
    # the surrounding physical arithmetic keeps its original context.
    owner.debit('real_call_argument_context', 1, expr)
    if getattr(parameters, 'program_real', False) is True:
        # This lookup already owns the required lexical arithmetic context.
        # Reuse only the lookup, never a value or actual execution result.
        argument_lookup = parameters
    else:
        owner.debit('real_call_argument_lookup_copy', 2+len(parameters.__dict__), expr)
        def argument_lookup(local):
            return parameters(local)
        argument_lookup.__dict__.update(parameters.__dict__)
        argument_lookup.program_real = True
    # A single real identity return has no local mutation or discarded effect.
    # Its argument is evaluated once; copy-in and return still own RN boundaries
    # and the original source call identity. Other functions retain the scoped
    # executor below, including unused arguments and overwritten assignments.
    owner.debit('real_call_identity_qualification', 6, expr)
    if (function.return_type == 'real' and len(function.inputs) == 1
            and count == 1 and len(function.body) == 1
            and function.variable_types[function.inputs[0]] == 'real'):
        statement = function.body[0]
        owner.debit('real_call_identity_statement', 4, statement)
        if (isinstance(statement, Assignment) and statement.name == name
                and statement.rhs.op == 'parameter'
                and statement.rhs.value == function.inputs[0]
                and not statement.rhs.args and statement.rhs.source_call is None):
            argument = lower(expr.args[start], argument_lookup, nodes, source, operators,
                True, decisions, validate_decision, decision_scope, indices,
                node_declarations=node_declarations)
            copied = c.make_ir(RealBoundary, argument, 'argument', call_origin)
            return c.make_ir(RealBoundary, copied, 'return', origin(statement))
    owner.debit('real_call_declaration_order', 3+len(function.variables)*(3+len(function.variables).bit_length()), expr)
    slots = {}
    # Declaration order must be deterministic and independent of set/hash order.
    for local in (*function.inputs, *sorted(function.variables-set(function.inputs)), name):
        owner.debit('real_call_owned_binding', 4, expr)
        if local in slots:
            continue
        binding = len(c.compilation.real_bindings)
        c.compilation.real_bindings.append(c.make_ir(RealBinding,
            builder.procedure_id, local, call_origin, 'call'))
        slots[local] = binding
    ordinal = 0
    def step(action):
        nonlocal ordinal
        result = c.make_ir(ProcedureStep, ordinal, action)
        ordinal += 1
        return result
    def annotate(item):
        owner.debit('real_call_source_copy', 2+len(item.args)+len(item.expansion)+len(expansion), item)
        args = tuple(annotate(a) for a in item.args)
        kind = function.variable_types.get(str(item.value)) if item.op == 'parameter' else item.result_type
        if item.op == 'parameter' and item.value == name:
            kind = function.return_type
        item_path = path(item)
        if item.op == 'call':
            # This raw nested occurrence was already checked by full expansion.
            # Its source position plus outer expansion, not expression equality,
            # identifies the child activation.
            sites = getattr(c, '_real_nested_sites', None)
            if sites is None:
                c._real_nested_sites = sites = {}
            key = (id(item), expansion)
            if key not in sites:
                owner.debit('real_call_nested_identity', 3, item)
                sites[key] = (item, len(sites)+1)
            return replace(item, args=args, source_call=(str(item.value), 0, len(args)),
                result_type=c.model.functions[str(item.value)].return_type,
                expansion=(*item_path, ('function_call', sites[key][1])))
        return replace(item, args=args, result_type=kind, expansion=item_path)
    def value(item, env, conditional=False):
        def resolve(local):
            if local in slots:
                if local not in env:
                    raise CompileError('function local is not assigned before use', token=item.token)
                return env[local]
            return parameters(local)
        owner.debit('real_call_lookup_copy', 2+len(parameters.__dict__), item)
        scoped = c.typed_resolve(resolve, program_real=True)
        scoped.__dict__.update(parameters.__dict__)
        scoped.program_real = True
        scoped.defer_numeric_domain = conditional
        scoped.is_program_real_expression = lambda part: not c.integer_type(part)
        scoped.real_call = lambda *args, **kwargs: lower_call(c, *args, **kwargs)
        prepared = annotate(item)
        def select(part, relation, left, right, yes, no):
            return c.make_ir(Select, relation, left, right, yes, no, origin(part))
        return lower(prepared, scoped, nodes, source,
                     (lambda op: c.waveform(op, scoped)), True,
                     select, None, True, indices, node_declarations=node_declarations)
    def bind(local, rhs, role, at, env):
        owner.debit('real_call_bind', 5, at)
        boundary = c.make_ir(RealBoundary, rhs, role, origin(at))
        action = c.make_ir(RealBind, slots[local], boundary, origin(at))
        read = c.make_ir(RealLocal, slots[local])
        builder.degree_facts[id(read)] = (read, c.predicate_degree(rhs))
        c.program_facts.record_read(read, (rhs,))
        dependencies = c.expression_nodes(rhs)
        owner.debit('real_call_binding_dependencies', 2+len(dependencies), at)
        builder.binding_nodes.setdefault(slots[local], set()).update(dependencies)
        env[local] = read
        return step(action)
    env = {}
    body = []
    for local, argument in zip(function.inputs, expr.args[start:start+count]):
        if function.variable_types[local] == 'integer':
            argument = Expr('function_assign', 'integer', (argument,), argument.token,
                expansion=argument.expansion, result_type='integer')
        rhs = lower(argument, argument_lookup, nodes, source, operators, True,
                    decisions, validate_decision, decision_scope, indices,
                    node_declarations=node_declarations)
        body.append(bind(local, rhs, 'argument', expr, env))
    if function.return_type == 'integer':
        # Existing language elaboration gives integer functions an explicit
        # default return. This is an emitted assignment, never a runtime read
        # fallback for an uninitialised slot.
        body.append(bind(name, c.make_ir(Affine, 0.0, ()), 'store', expr, env))
    def statements(sources, env, conditional=False):
        nonlocal ordinal
        result = []
        for statement in sources:
            owner.debit('real_call_statement', 3, statement)
            if isinstance(statement, Assignment):
                kind = function.return_type if statement.name == name else function.variable_types[statement.name]
                operand = statement.rhs
                if kind != 'real':
                    # Reuse the original typed conversion contract rather than
                    # interpreting integer assignment in this emitter.
                    operand = Expr('function_assign', kind, (statement.rhs,), statement.token,
                                   result_type=kind)
                rhs = value(operand, env, conditional)
                result.append(bind(statement.name, rhs,
                    'return' if statement.name == name else 'store', statement, env))
            elif isinstance(statement, Conditional):
                left, right = value(statement.left, env, conditional), value(statement.right, env, conditional)
                index = ordinal
                ordinal += 1
                owner.debit('real_call_branch_env_copy', 2+2*len(env), statement)
                yes_env, no_env = dict(env), dict(env)
                yes = statements(statement.then_body, yes_env, True)
                no = statements(statement.else_body, no_env, True)
                relation = {'<':'lt','<=':'le','>':'gt','>=':'ge'}[statement.relation]
                result.append(c.make_ir(ProcedureStep, index,
                    c.make_ir(ProcedureConditional, relation, left, right, tuple(yes), tuple(no), origin(statement))))
                owner.debit('real_call_branch_merge', (len(yes_env)+len(no_env))*(2+len(yes_env).bit_length()), statement)
                for local in sorted(yes_env.keys() & no_env.keys()):
                    a, b = yes_env[local], no_env[local]
                    if a is b:
                        env[local] = a
                        continue
                    read = c.make_ir(RealLocal, slots[local])
                    c.program_facts.record_read(read, (left, right, a, b), relation=relation)
                    degrees = tuple(c.predicate_degree(part) for part in (left, right, a, b))
                    builder.degree_facts[id(read)] = (read, None if None in degrees else max(degrees))
                    env[local] = read
            else:
                raise CompileError('pure function requires scalar assignments and finite branches', token=statement.token)
        return result
    body.extend(statements(function.body, env))
    if name not in env:
        raise CompileError('function must assign its return value', token=function.token)
    result = c.make_ir(RealCall, call_origin, tuple(slots.values()), tuple(body), env[name])
    owner.debit('real_call_result_metadata', 4+len(slots), expr)
    builder.degree_facts[id(result)] = (result, c.predicate_degree(env[name]))
    if not hasattr(c, 'real_call_nodes'):
        c.real_call_nodes = {}
    owner.debit('real_call_result_dependency_container', 1, expr)
    result_nodes = set()
    for slot in slots.values():
        owner.debit('real_call_result_dependency_handle', 2, expr)
        dependencies = builder.binding_nodes.get(slot)
        if dependencies is not None:
            # This is another traversal of every accumulated binding set.
            # Charge source entries before iteration/insertion, not the size
            # of the deduplicated output or the earlier per-bind updates.
            owner.debit('real_call_result_dependency_entry', 2*len(dependencies), expr)
            result_nodes.update(dependencies)
    c.real_call_nodes[id(result)] = result_nodes
    from .real_call_arguments import bind_argument_chain
    return bind_argument_chain(c, result, function)
