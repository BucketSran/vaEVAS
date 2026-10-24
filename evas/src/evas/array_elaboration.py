"""Scalarize instance-sized variable arrays before shared semantic lowering.

Constant indices become ordinary element states here. Event and final_step
bodies may keep *dynamic* typed-integer indices as residual ``index`` nodes;
the instance compiler lowers those into balanced Select reads and single-path
balanced If writes with per-use range admission (N02). The source provenance
gate below runs before any constant-subscript array read is rewritten into a
plain parameter name, so index-of-index and function-origin indices stay
rejected even though scalarization or function inlining could execute them.
"""
from dataclasses import replace
from .errors import CompileError
from .ir import Affine
from .lowering import lower
from .syntax import Loop, Assignment, Conditional, Expr, Display, Event
from .elaboration import unroll_loops

ARRAY_BUDGET = 4096

#: Source grammar admitted for a dynamic index in this first N02 slice.
INDEX_OPS = frozenset(('number', 'parameter', '+', '-', '*', '/', '%', 'unary+', 'unary-'))
#: Event leaves whose bodies execute per firing, not during initialization.
DYNAMIC_EVENT_KINDS = frozenset(('timer', 'cross', 'final_step'))


def _index_fail(message, token, model, *, code="array_index_type"):
    raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}',
                       code=code, token=token)


def gate_dynamic_index(expr, model):
    """Reject every index source outside the approved typed-integer grammar.

    This is a syntactic provenance gate on the pre-scalarized tree: nested array
    reads (including constant subscripts), function results (marked ``real`` or
    wrapped in ``checked`` after inlining), analog calls, voltage/operator/time
    access and decision or real operands are all rejected here, before
    scalarization could disguise them as ordinary parameters.
    """
    def visit(item):
        if item.result_type == 'real' or item.op not in INDEX_OPS:
            _index_fail(f"dynamic array index requires typed integer arithmetic over literals, "
                        f"integer parameters and integer states; {item.op!r} sources are rejected",
                        item.token, model)
        if item.op == 'number' and not (item.token.text.isdecimal() or item.token.kind == 'name'):
            _index_fail("dynamic array index literals must be integers", item.token, model)
        if item.op == 'parameter' and item.value not in model.genvars and model.variables.get(item.value) != 'integer' and model.parameter_types.get(item.value) != 'integer':
            _index_fail("array index identifiers must have integer source type", item.token, model)
        for arg in item.args:
            visit(arg)

    visit(expr)


def scalarize_arrays(model, parameter, *, native_audit=None):
    def fail(message, token, *, code="compile_error"):
        raise CompileError(f'{token.source or model.source}:{token.line}:{token.column}: {message}', code=code, token=token)

    def integer(expr):
        try:
            value = lower(expr, parameter, {}, model.source)
        except CompileError as error:
            fail(f'array bound/index requires an instance-constant integer: {error}', expr.token)
        if (not isinstance(value, Affine) or value.terms or not value.constant.is_integer()
                or not -2147483648 <= value.constant <= 2147483647):
            fail('array bound/index requires a signed 32-bit instance-constant integer', expr.token)
        return int(value.constant)

    def constant_index(expr):
        """Instance-constant index, or None when the index is dynamic."""
        try:
            value = lower(expr, parameter, {}, model.source)
        except CompileError as error:
            if error.diagnostic['code'] == 'resource_budget':
                raise
            return None
        if (isinstance(value, Affine) and not value.terms and value.constant.is_integer()
                and -2147483648 <= value.constant <= 2147483647):
            return int(value.constant)
        return None

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
            fail('total array element budget (4096) exceeded', left.token, code="resource_budget")
        indices = range(first, last + (1 if last >= first else -1), 1 if last >= first else -1)
        ranges[name] = indices
        for index in indices:
            variables[f'{name}[{index}]'] = kind

    def element(name, index, token, dynamic):
        if name not in ranges:
            fail(f'indexed identifier {name!r} is not a variable array', token)
        gate_dynamic_index(index, model)
        value = constant_index(index)
        if value is None:
            if not dynamic:
                fail('dynamic array indices are supported only in event and final_step bodies', index.token,
                     code='unsupported_array_index')
            gate_dynamic_index(index, model)
            return None
        if value not in ranges[name]:
            fail(f'array index {value} is outside {name!r} declaration', index.token)
        return f'{name}[{value}]'

    # This cache belongs to one instance's scalarization, with fixed bounds.
    # Keep the input alive as well as its replacement to avoid ID reuse.
    expressions = {}
    def expression(expr, dynamic):
        key = (id(expr), dynamic)
        if key not in expressions:
            expressions[key] = (expr, transform_expression(expr, dynamic))
        return expressions[key][1]

    def transform_expression(expr, dynamic):
        if expr.op == 'index':
            name = element(expr.value, expr.args[0], expr.token, dynamic)
            if name is None:
                # Residual dynamic read; lowered to a balanced Select by the
                # instance compiler with its own use-site admission.
                return Expr('index', expr.value, (expression(expr.args[0], dynamic),), expr.token)
            return Expr('parameter', name, (), expr.token)
        if expr.op == 'parameter' and expr.value in ranges:
            fail('array value requires an explicit element index', expr.token)
        if native_audit is None:
            return replace(expr, args=tuple(expression(a, dynamic) for a in expr.args))
        # Required child validation still runs in this exact array/dynamic
        # context. Preserve immutable identity only when no rewrite occurred.
        native_audit.debit('source_structure_array_edges', 1+len(expr.args), expr)
        changed = None
        for index, arg in enumerate(expr.args):
            child = expression(arg, dynamic)
            if child is not arg:
                if changed is None:
                    native_audit.debit('source_structure_array_children_copy', 1+len(expr.args), expr)
                    changed = list(expr.args)
                changed[index] = child
        if changed is None:
            return expr
        native_audit.debit('source_structure_array_replace', 2+len(changed)+len(expr.__dataclass_fields__), expr)
        return replace(expr, args=tuple(changed))

    def body(statements, dynamic=False):
        result = []
        for statement in statements:
            if isinstance(statement, Loop):
                if not dynamic:
                    fail('runtime loops require an event or final_step body', statement.token)
                result.append(replace(statement, start=expression(statement.start, dynamic),
                    limit=expression(statement.limit, dynamic), update=expression(statement.update, dynamic),
                    body=body(statement.body, dynamic)))
            elif isinstance(statement, Conditional):
                result.append(replace(statement, left=expression(statement.left, dynamic),
                                      right=expression(statement.right, dynamic),
                                      then_body=body(statement.then_body, dynamic),
                                      else_body=body(statement.else_body, dynamic)))
            elif isinstance(statement, Display):
                result.append(replace(statement, args=tuple(expression(arg, dynamic) for arg in statement.args)))
            elif isinstance(statement, Assignment):
                name = statement.name
                if statement.index is not None:
                    element_name = element(name, statement.index, statement.token, dynamic)
                    if element_name is None:
                        # Residual dynamic write; the compiler expands it into a
                        # single-path balanced If dispatch over all slots.
                        result.append(replace(statement, rhs=expression(statement.rhs, dynamic),
                                              index=expression(statement.index, dynamic)))
                        continue
                    name = element_name
                elif name in ranges:
                    fail('array assignment requires an explicit element index', statement.token)
                result.append(replace(statement, name=name, rhs=expression(statement.rhs, dynamic), index=None))
            else:
                result.append(replace(statement, rhs=expression(statement.rhs, dynamic)))
        return tuple(result)

    def event_body(event):
        # Bodies that also execute during initialization keep the constant-only
        # rule; shared initial timers and initial_step leaves never admit them.
        dynamic = all(leaf.kind in DYNAMIC_EVENT_KINDS for leaf in event.triggers)
        return body(event.body, dynamic)

    analog = list(body(unroll_loops(model, parameter)))
    initial = list(body(model.initial))
    events = [replace(event, body=event_body(event), triggers=tuple(
        replace(leaf, arguments=tuple(expression(a, False) if a is not None else None
                                     for a in leaf.arguments)) for leaf in event.triggers))
        for event in model.events]
    procedure = []
    for statement in model.procedure:
        if isinstance(statement, Event):
            procedure.append(replace(statement, body=event_body(statement), triggers=tuple(
                replace(leaf, arguments=tuple(expression(a, False) if a is not None else None
                                             for a in leaf.arguments)) for leaf in statement.triggers)))
        else:
            procedure.extend(body((statement,)))
    scopes = dict(model.local_alias_scopes)
    # Syntax retains the exact preceding unconditional indexed assignments.
    # Bind each index in this instance, using the same type/bounds gate as the
    # assignment itself. An array name never makes unwritten slots available.
    for token, assignments in getattr(model, 'local_array_alias_scopes', {}).items():
        names = set(scopes.get(token, ()))
        for assignment in assignments:
            if assignment.index is not None:
                names.add(element(assignment.name, assignment.index, assignment.token, False))
        scopes[token] = frozenset(names)

    # Element bounds stay on the model so the instance compiler can rebuild the
    # slot list for residual dynamic indices.
    return replace(model, variables=variables,
                   analog=analog, initial=initial, events=events, procedure=tuple(procedure),
                   local_alias_scopes=scopes)
