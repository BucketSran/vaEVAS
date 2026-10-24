"""Discharge unsupported calls only beneath instance-constant dead arms.

This does not implement a system function, fold ordinary source, or remove its
writer/domain obligations. A dead call becomes an unreachable numeric placeholder;
all process views retain their original branch structure. Runtime state, voltage,
time, and algebraic cancellation of such dependencies never prove reachability.
"""
from dataclasses import fields, is_dataclass, replace
import math

from . import syntax, integer_bits
from .errors import CompileError
from .ir import Affine
from .integer_constants import check_integer_expression
from .lowering import lower
from .parameters import attach_constant_integer_arithmetic
from .syntax import Expr, Conditional, Function, Token, OPERATOR_ARITIES
from .array_elaboration import gate_dynamic_index
from .condition_domains import compact_condition, compact_domains

# Fixed metadata is read once, not before each runtime copy's prepayment.
_FIELDS = {value: tuple(field.name for field in fields(value))
           for value in vars(syntax).values()
           if isinstance(value, type) and is_dataclass(value)}
# Keep the proof below unsettled parameter-expression arithmetic contracts.
# Direct comparisons and sign are exact for the already bound binary64 values.
_FROZEN_SOURCE = frozenset(cls for cls in _FIELDS if cls.__dataclass_params__.frozen)
_CLOSED = frozenset(('number', 'parameter', 'unary+', 'unary-')) | syntax.DECISION_NAMES
_RELATIONS = {'<': lambda a,b: a < b, '<=': lambda a,b: a <= b,
              '>': lambda a,b: a > b, '>=': lambda a,b: a >= b,
              '==': lambda a,b: a == b, '!=': lambda a,b: a != b}


def qualify(model, parameters, instance, owner):
    """Use the request's existing NativeAudit; exhausted retries stay exhausted."""
    charge = owner.target_view(model.declaration_token)

    def constant(expr, bindings):
        charge(expr, 'dead_call_proof_stack')
        pending, count = [expr], 0
        while pending:
            charge(expr, 'dead_call_proof_visit')
            item = pending.pop()
            count += 1
            if item.op not in _CLOSED or item.op == 'parameter' and item.value not in bindings:
                return None
            charge(item, 'dead_call_proof_attach', len(item.args))
            pending.extend(item.args)
        # Existing integer checking/typed division may walk each nested subtree.
        # Prepay their conservative quadratic bound before entering the helpers.
        charge(expr, 'dead_call_constant_helpers', 16 * count * count + 4 * len(model.parameter_types))
        def lookup(name):
            return bindings[name]
        attach_constant_integer_arithmetic(lookup, model, instance)
        lookup.native_work = owner.ir_work
        try:
            check_integer_expression(expr, model, bindings, check_literals=True, allow_division=True)
            def select(source, relation, left, right, yes, no):
                charge(source, 'dead_call_closed_decision', 5)
                if not all(isinstance(value, Affine) and not value.terms
                           and math.isfinite(value.constant) for value in (left, right)):
                    raise CompileError('constant decision has unproved operands', token=source.token)
                compare = _RELATIONS[{'lt':'<', 'le':'<=', 'gt':'>', 'ge':'>='}[relation]]
                return yes if compare(left.constant, right.constant) else no
            value = lower(expr, lookup, {}, model.source, decisions=select)
        except CompileError as error:
            if error.diagnostic.get('code') == 'resource_budget':
                raise
            return None
        if isinstance(value, Affine) and not value.terms and math.isfinite(value.constant):
            return value.constant
        return None

    def relation(item, bindings):
        if compact_condition(item.relation, item.left, item.right):
            return truth(item.left, bindings)
        compare = _RELATIONS.get(item.relation)
        if compare is None:
            return None
        left, right = constant(item.left, bindings), constant(item.right, bindings)
        return None if left is None or right is None else compare(left, right)

    charge(model, 'dead_call_truth_cache_container')
    truth_cache = {}

    def truth(expr, bindings):
        # A bound parameter can settle a compound predicate even when another
        # operand is runtime state. Use the same ordered comparison skeleton
        # as source-domain refinement, with three-valued reachability leaves.
        # Unknown operands remain unknown; their nominal/current values are
        # never substituted into this proof.
        if expr.op not in syntax.BOOLEAN_OPS:
            value = constant(expr, bindings)
            return None if value is None else value != 0
        charge(expr, 'dead_call_truth_cache_lookup', 4)
        key = (id(expr), bindings is parameters)
        cached = truth_cache.get(key)
        if cached is not None:
            return cached[1]
        charge(expr, 'dead_call_truth_forwarders', 20)
        def refine(op, left, right, current):
            a, b = constant(left, bindings), constant(right, bindings)
            if a is None or b is None:
                return current, current
            return (current, None) if _RELATIONS[op](a,b) else (None, current)
        zero = Expr('number', 0., (), expr.token)
        domains = compact_domains('>', expr, zero, {}, refine=refine,
            hull=lambda a,b: a or b,
            work=lambda amount: charge(expr, 'dead_call_partial_truth_work', amount))
        yes, no = domains
        result = False if yes is None and no is not None else True if no is None and yes is not None else None
        charge(expr, 'dead_call_truth_cache_insert', 4)
        truth_cache[key] = (expr, result)
        return result

    charge(model, 'dead_call_type_environment_container')
    type_environments = {}

    def type_tables(scope):
        charge(scope or model.declaration_token, 'dead_call_type_table_reference', 3)
        if scope is None:
            return model.variables, model.parameter_types
        charge(scope, 'dead_call_type_environment_lookup')
        key = id(scope)
        if key not in type_environments:
            # Function locals/inputs shadow module variables AND parameters.
            # Retain the function object with its tables for this invocation.
            charge(scope, 'dead_call_type_shadow_copy', len(scope.inputs) + len(scope.variables) + 4)
            shadow = set(scope.inputs) | scope.variables | {scope.name}
            charge(scope, 'dead_call_type_variable_copy', len(model.variables) + len(scope.variable_types) + 4)
            variables = dict(model.variables)
            variables.update(scope.variable_types)
            variables[scope.name] = scope.return_type
            charge(scope, 'dead_call_type_parameter_copy', 2 * len(model.parameter_types) + 1)
            parameter_types = {name: kind for name, kind in model.parameter_types.items() if name not in shadow}
            charge(scope, 'dead_call_type_environment_insert', 5)
            type_environments[key] = (scope, variables, parameter_types)
        return type_environments[key][1:]

    def argument_names(expr, scope):
        """Validate source references without evaluating a discarded argument.

        An unreachable argument has no numerical value. Its declarations,
        function identity and static index constraints still have to be legal.
        """
        charge(expr, 'dead_call_argument_visit')
        def fail(message, code='compile_error'):
            token = expr.token
            raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}',
                               code=code, token=token, instance=instance)
        if expr.op == 'parameter':
            if scope is not None:
                charge(expr, 'dead_call_argument_scope', len(scope.inputs) + 2)
            local = scope is not None and (expr.value in scope.inputs
                                            or expr.value in scope.variables or expr.value == scope.name)
            if not local and expr.value not in model.parameters and expr.value not in model.variables and expr.value not in model.genvars:
                fail(f'unknown parameter {expr.value!r}')
        elif expr.op == 'call':
            function = model.functions.get(expr.value)
            if function is None:
                fail(f'unknown analog function {expr.value!r}')
            if len(expr.args) != len(function.inputs):
                fail(f'analog function {expr.value!r} argument count mismatch')
        elif expr.op == 'node':
            if expr.value != '0' and expr.value not in model.nodes:
                fail(f'undeclared electrical node {expr.value!r}', 'undeclared_node')
            bounds = model.node_ranges.get(expr.value)
            if expr.args:
                if bounds is None:
                    fail(f'indexed electrical node {expr.value!r} is not a vector', 'unsupported_vector')
                index = static_integer(expr.args[0], required=True)
                first, last = (static_integer(value, required=True) for value in bounds)
                if not min(first, last) <= index <= max(first, last):
                    fail(f'electrical index {index} outside {expr.value!r}', 'unsupported_vector')
            elif bounds is not None:
                fail(f'electrical vector {expr.value!r} requires an explicit bit index', 'unsupported_vector')
        elif expr.op == 'index':
            if expr.value not in model.arrays:
                fail(f'indexed identifier {expr.value!r} is not a variable array')
            charge(expr, 'dead_call_index_helper', 16 * expression_size(expr.args[0]) ** 2)
            gate_dynamic_index(expr.args[0], model)
            index = static_integer(expr.args[0])
            if index is not None:
                first, last = (static_integer(value, required=True) for value in model.arrays[expr.value])
                if not min(first, last) <= index <= max(first, last):
                    fail(f'array index {index} is outside {expr.value!r} declaration')
        elif expr.op in OPERATOR_ARITIES:
            fail('waveform operators are only allowed in contributions; nesting is unsupported')
        # Type every original argument node bottom-up using the same source
        # typing grammar as ordinary lowering. This is type-only: no operand
        # value, overflow bound, division or math function is evaluated.
        charge(expr, 'dead_call_argument_types_container')
        child_types = []
        for child in expr.args:
            typed = argument_names(child, scope)
            charge(expr, 'dead_call_argument_type_append')
            child_types.append(typed)
        variables, parameter_types = type_tables(scope)
        typed = integer_bits.integer_type(expr, variables, parameter_types, model.genvars,
                    child_types=child_types,
                    visit=lambda item: charge(item, 'dead_call_argument_typing_visit'))
        if expr.op in integer_bits.OPS or expr.op == '%':
            charge(expr, 'dead_call_operand_type_check', len(child_types))
        if expr.op in integer_bits.OPS and not all(child_types):
            fail('bitwise operands require typed integer expressions', 'unsupported_integer_bitwise')
        if expr.op == '%' and not all(child_types):
            fail('modulo requires integer typed operands and a supported constant divisor')
        # These two source forms are normally resolved before integer_type is
        # called by InstanceCompiler. Their declaration types survive here.
        if expr.result_type in ('real', 'integer'):
            return typed
        if expr.op == 'index':
            return variables.get(expr.value) == 'integer'
        if expr.op == 'call':
            return model.functions[expr.value].return_type == 'integer'
        return typed

    def expression_size(expr):
        charge(expr, 'dead_call_index_size_visit')
        count = 1
        for child in expr.args:
            count += expression_size(child)
        return count

    def static_integer(expr, *, required=False):
        # Only structural array/electrical bounds and indices enter this helper;
        # discarded numeric operands such as 1/0 or sqrt(-1) never enter it.
        charge(expr, 'dead_call_static_index_helper', 16 * expression_size(expr) ** 2 + 4 * len(model.parameter_types))
        dynamic = False
        def lookup(name):
            nonlocal dynamic
            if name not in parameters:
                dynamic = True
                raise CompileError('dynamic index', token=expr.token)
            return parameters[name]
        attach_constant_integer_arithmetic(lookup, model, instance)
        lookup.native_work = owner.ir_work
        try:
            check_integer_expression(expr, model, parameters, check_literals=True, allow_division=True)
            value = lower(expr, lookup, {}, model.source)
            if isinstance(value, Affine) and not value.terms and math.isfinite(value.constant) and value.constant.is_integer() and -2147483648 <= value.constant <= 2147483647:
                return int(value.constant)
        except CompileError as error:
            if error.diagnostic.get('code') == 'resource_budget' or not dynamic:
                raise
        if required:
            raise CompileError('electrical bound/index requires a signed 32-bit instance-constant integer',
                               code='unsupported_vector', token=expr.token, instance=instance)
        return None

    def rebuild(value, updates):
        if not updates:
            return value
        charge(value, 'dead_call_dataclass_copy', 1 + len(_FIELDS[type(value)]))
        return replace(value, **updates)

    # One instance, one fixed parameter environment. Compatibility/process views
    # share AST nodes; reuse only the identical node and identical dead/live
    # context. A dead occurrence can never discharge a live one. Function
    # declarations use a separate no-parameter proof context.
    # Structural relevance is independent of parameter values, dead/live state,
    # and function scope. Build it once for this immutable source snapshot; the
    # table retains each object and is discarded with this qualification call.
    # Mutable model/container objects are never cached across calls or writes.
    # Unrelated branches need neither a reachability proof nor a copied tree.
    charge(model, 'dead_call_relevance_container')
    relevance = {}
    # Enable cross-instance indexing only after this original source model is
    # actually revisited. A one-use module pays no immutable graph proof.
    charge(model, 'dead_call_source_models_lookup', 2)
    source_models = getattr(owner, 'dead_call_source_models', None)
    if source_models is None:
        charge(model, 'dead_call_source_models_container', 2)
        source_models = {}
        owner.dead_call_source_models = source_models
    shared_enabled = id(model) in source_models
    if not shared_enabled:
        charge(model, 'dead_call_source_models_insert', 2)
        source_models[id(model)] = model
    shared = None
    if shared_enabled:
        charge(model, 'dead_call_shared_context_lookup', 2)
        shared = getattr(owner, 'dead_call_immutable_irrelevance', None)
        if shared is None:
            charge(model, 'dead_call_shared_context_container', 2)
            shared = {}
            owner.dead_call_immutable_irrelevance = shared

    def immutable_child(value):
        charge(value, 'dead_call_shared_immutable_child', 2)
        if isinstance(value, Token) or type(value) in (str, int, float, bool, type(None)):
            return True
        record = relevance.get(id(value))
        return record is not None and record[2]

    def relevant(value):
        if isinstance(value, Token):
            return False
        structured = type(value) in _FIELDS or isinstance(value, (tuple, list, dict))
        if not structured:
            return False
        charge(value, 'dead_call_relevance_lookup', 2)
        key = id(value)
        cached = relevance.get(key)
        if cached is not None:
            return cached[1]
        if shared_enabled:
            charge(value, 'dead_call_shared_kind', 1)
        shareable_type = shared_enabled and (type(value) is tuple or type(value) in _FROZEN_SOURCE)
        if shareable_type:
            charge(value, 'dead_call_shared_lookup', 2)
            prior = shared.get(key)
            if prior is not None:
                charge(value, 'dead_call_relevance_insert', 3)
                relevance[key] = (value, False, True)
                return False
        found, immutable = False, False
        if isinstance(value, Expr):
            # Expr semantic children are args. op/value/type, Token, expansion
            # and call-occurrence metadata are not expression subtrees. Keep
            # them unchanged; this index neither validates nor rewrites them.
            charge(value, 'dead_call_relevance_expression_fields', 2)
            found = value.op == 'unsupported_system_call'
            if type(value.args) is tuple and value.op != 'unsupported_system_call':
                # An expression owns these child edges, not a second source
                # statement. Do not index its argument tuple unless a later
                # rewrite actually needs that tuple as a separate frontier.
                charge(value, 'dead_call_relevance_edges', len(value.args))
                for child in value.args:
                    found = relevant(child) or found
                if shared_enabled and not found and type(value) is Expr and type(value.op) is str:
                    immutable = True
                    for child in value.args:
                        immutable = immutable_child(child) and immutable
            else:
                # Opaque-call arguments are a real rewrite frontier and will
                # always be visited in the current scope. Index that tuple now.
                # Mutable argument containers likewise keep the old full walk.
                found = relevant(value.args) or found
        elif type(value) in _FIELDS:
            names = _FIELDS[type(value)]
            charge(value, 'dead_call_relevance_fields', len(names))
            immutable = shared_enabled and type(value) in _FROZEN_SOURCE
            for name in names:
                child = getattr(value, name)
                found = relevant(child) or found
                if immutable:
                    immutable = not found and immutable_child(child)
        else:
            charge(value, 'dead_call_relevance_edges', len(value))
            children = value.values() if isinstance(value, dict) else value
            immutable = shared_enabled and type(value) is tuple
            for child in children:
                found = relevant(child) or found
                if immutable:
                    immutable = not found and immutable_child(child)
        charge(value, 'dead_call_relevance_insert', 3)
        relevance[key] = (value, found, immutable)
        if immutable and not found:
            charge(value, 'dead_call_shared_insert', 2)
            shared[key] = (value, False)
        return found

    relevant(model)
    charge(model, 'dead_call_rewrite_cache_container')
    memo = {}

    def walk(value, dead=False, bindings=parameters, scope=None):
        # Keep this lookup local to the same source graph. In particular the
        # cached fact never means a call was proved dead in another instance.
        if not isinstance(value, Token) and (type(value) in _FIELDS or isinstance(value, (tuple, list, dict))):
            charge(value, 'dead_call_relevance_read', 2)
            record = relevance.get(id(value))
            related = record[1] if record is not None else relevant(value)
            if not related:
                return value
        if (not isinstance(value, Token)
                and (type(value) in _FIELDS or isinstance(value, (tuple, list, dict)))):
            charge(value, 'dead_call_rewrite_cache_key', 5)
            key = (id(value), dead, bindings is parameters, id(scope))
            charge(value, 'dead_call_rewrite_cache_lookup')
            if key in memo:
                return memo[key]
            result = transform(value, dead, bindings, scope)
            charge(value, 'dead_call_rewrite_cache_insert', 2)
            memo[key] = result
            return result
        return transform(value, dead, bindings, scope)

    def transform(value, dead=False, bindings=parameters, scope=None):
        charge(value, 'dead_call_source_visit')
        if isinstance(value, Token):
            return value
        if isinstance(value, Expr) and value.op == 'unsupported_system_call':
            if value.value == 'rdist_normal':
                # This known call is represented, never evaluated or replaced.
                # Static validity is independent of reachability and sigma.
                charge(value, 'deferred_system_call_signature', 5+len(value.args))
                if len(value.args) != 3:
                    raise CompileError('$rdist_normal requires seed, mean and sigma',
                        code='unsupported_system_function', token=value.token, instance=instance)
                seed = value.args[0]
                if (scope is not None or seed.op != 'parameter'
                        or model.variables.get(seed.value) != 'integer'
                        or seed.value in model.arrays):
                    raise CompileError('$rdist_normal seed requires a writable scalar module integer variable',
                        code='unsupported_system_function', token=seed.token, instance=instance)
                for argument in value.args:
                    argument_names(argument, scope)
                args = walk(value.args, dead, bindings, scope)
                return value if args is value.args else rebuild(value, {'args':args})
            if not dead:
                token = value.token
                raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: '
                                   f'system function ${value.value} is not supported',
                                   code='unsupported_system_function', token=token, instance=instance)
            # Walk even the discarded arguments: dead syntax remains bounded.
            for argument in value.args:
                argument_names(argument, scope)
            walk(value.args, True, bindings, scope)
            charge(value, 'dead_call_placeholder', 1 + len(_FIELDS[Expr]))
            return Expr('number', 0.0, (), value.token, value.expansion, 'real')
        if isinstance(value, Expr) and value.op in ('&&', '||'):
            verdict = None if dead else truth(value.args[0], bindings)
            right_dead = dead or value.op == '&&' and verdict is False or value.op == '||' and verdict is True
            left = walk(value.args[0], dead, bindings, scope)
            right = walk(value.args[1], right_dead, bindings, scope)
            if left is value.args[0] and right is value.args[1]:
                return value
            charge(value, 'dead_call_short_circuit_copy', 5)
            return rebuild(value, {'args': (left, right)})
        if isinstance(value, Expr) and value.op == 'ternary':
            verdict = None if dead else truth(value.args[0], bindings)
            charge(value, 'dead_call_ternary_copy', 4)
            args = (walk(value.args[0], dead, bindings, scope),
                    walk(value.args[1], dead or verdict is False, bindings, scope),
                    walk(value.args[2], dead or verdict is True, bindings, scope))
            return rebuild(value, {'args': args})
        if isinstance(value, Expr):
            # Only args can change when an opaque descendant is discharged.
            # replace below still copies every field and preserves full Origin,
            # source-call identity, type and rounding-boundary metadata.
            charge(value, 'dead_call_expression_args_read')
            args = walk(value.args, dead, bindings, scope)
            if args is value.args:
                return value
            charge(value, 'dead_call_expression_update', 2)
            return rebuild(value, {'args': args})
        if isinstance(value, Conditional):
            verdict = None if dead else relation(value, bindings)
            charge(value, 'dead_call_update_container')
            updates = {}
            for name in _FIELDS[Conditional]:
                charge(value, 'dead_call_field_visit')
                original = getattr(value, name)
                child_dead = dead or name == 'then_body' and verdict is False or name == 'else_body' and verdict is True
                changed = walk(original, child_dead, bindings, scope)
                if changed is not original:
                    charge(value, 'dead_call_update_field')
                    updates[name] = changed
            return rebuild(value, updates)
        if type(value) in _FIELDS:
            # Retained function declarations can shadow module parameters.
            # They confer no call-path proof; caller expansions are independent.
            if isinstance(value, Function):
                bindings = {}
                scope = value
            charge(value, 'dead_call_update_container')
            updates = {}
            for name in _FIELDS[type(value)]:
                charge(value, 'dead_call_field_visit')
                original = getattr(value, name)
                changed = walk(original, dead, bindings, scope)
                if changed is not original:
                    charge(value, 'dead_call_update_field')
                    updates[name] = changed
            return rebuild(value, updates)
        if isinstance(value, (tuple, list)):
            charge(value, 'dead_call_sequence_container')
            result, changed = [], False
            for original in value:
                child = walk(original, dead, bindings, scope)
                charge(value, 'dead_call_sequence_append')
                result.append(child)
                changed |= child is not original
            if not changed:
                return value
            if isinstance(value, tuple):
                charge(value, 'dead_call_tuple_copy', len(result) + 1)
                return tuple(result)
            return result
        if isinstance(value, dict):
            charge(value, 'dead_call_mapping_container')
            result, changed = {}, False
            for key, original in value.items():
                child = walk(original, dead, bindings, scope)
                charge(value, 'dead_call_mapping_insert')
                result[key] = child
                changed |= child is not original
            return result if changed else value
        return value

    return walk(model)
