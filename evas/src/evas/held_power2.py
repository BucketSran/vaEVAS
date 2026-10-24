"""Fresh nonnegative integer projections for the existing held Transition role."""
import math
from dataclasses import fields, is_dataclass
from . import integer_bits
from .errors import CompileError
from .limits import MAX_IR_ITEMS
from .syntax import (Expr, Assignment, ContributionStatement, Conditional, Loop,
                     Display, BoundStep, Event, OPERATOR_NAMES)
from .ir import Affine, StateRef, IntegerState, IntegerLiteral, IntegerPrimitive, Origin


# Shared structural grammar only; source typing, domains and roles stay fresh.
_SOURCE_PLAN_OPS = ('number', 'parameter', '/', '%', '<', '<=', '>', '>=',
                    '==', '!=', '&&', '||', 'unary!', 'ternary')


def reserve(owner, kind, amount=1, source=None):
    # Optional probes may stop only BEFORE new work. An active failure is never
    # caught or reset; every already performed debit remains on the same owner.
    if not owner.active and owner.used + amount > MAX_IR_ITEMS:
        return False
    owner.debit(kind, amount, source)
    return True



def compatible_program(compiler, source):
    """Fresh representation exclusion over original ordinary and initial roles.

    The old independent held-table calendar owns ordinary history consumers.
    This does not authorize history execution or replace the original full
    source/event/IR audits. Runtime event probes and contribution LHS declarations are
    not ordinary value reads. No semantic result is cached across candidates.
    """
    owner = compiler.compilation.native_audit
    if not reserve(owner, 'held_power2_program_dispatch', 4, source):
        return False
    bindings = getattr(compiler.compilation, 'held_power2_bindings', None)
    models = getattr(compiler.compilation, 'held_power2_source_models', None)
    if type(bindings) not in (tuple, list) or type(models) is not dict:
        return False
    if not reserve(owner, 'held_power2_program_roots', 4 + 8 * len(bindings), source):
        return False
    statements, expressions = [], []
    blocked = False
    for binding in bindings:
        if type(binding) is not tuple or len(binding) != 3:
            return False
        # Binding scalarization may erase zero-trip loops. Match the same
        # original source model used by the mandatory original-source audits.
        if not reserve(owner, 'held_power2_program_original_model', 4, source):
            return False
        qualified = getattr(compiler.compilation, 'held_power2_qualified_sources', None)
        if qualified:
            if not reserve(owner, 'held_power2_program_qualified_model', 4, source):
                return False
            model = qualified.get(binding[0].name, models.get(binding[1].name))
        else:
            model = models.get(binding[1].name)
        if model is None:
            return False
        # Prepay the added initial-root reference before reading its metadata.
        if not reserve(owner, 'held_power2_program_initial_roots', 2, source):
            return False
        body, initial = model.analog, model.initial
        if type(body) not in (tuple, list) or type(initial) not in (tuple, list):
            return False
        # Initial voltage reads also consume the held seed representation.
        # Keep every original initial arm/loop before scalarization erases it.
        if not reserve(owner, 'held_power2_program_statements', 2 * (len(body) + len(initial)), source):
            return False
        statements.extend(body)
        statements.extend(initial)
    while statements:
        if not reserve(owner, 'held_power2_program_statement', 4, source):
            return False
        item = statements.pop()
        if type(item) is ContributionStatement:
            # Inspect the RHS root directly; do not manufacture a role record
            # for every descendant or mistake its declared LHS for a read.
            rhs = item.rhs
            if not reserve(owner, 'held_power2_program_contribution', 4, source):
                return False
            if type(rhs) is Expr and rhs.op == 'transition':
                if type(rhs.args) is not tuple:
                    return False
                if not reserve(owner, 'held_power2_program_root_args', 2 * len(rhs.args), source):
                    return False
                expressions.extend(rhs.args)
            else:
                expressions.append(rhs)
        elif type(item) is Assignment:
            if not reserve(owner, 'held_power2_program_assignment', 4, source):
                return False
            expressions.append(item.rhs)
            if item.index is not None:
                expressions.append(item.index)
        elif type(item) is Conditional:
            if not reserve(owner, 'held_power2_program_conditional', 8 + 2 * (len(item.then_body) + len(item.else_body)), source):
                return False
            expressions.extend((item.left, item.right))
            statements.extend(item.then_body)
            statements.extend(item.else_body)
        elif type(item) is Loop:
            if not reserve(owner, 'held_power2_program_loop', 10 + 2 * len(item.body), source):
                return False
            expressions.extend((item.start, item.limit, item.update))
            statements.extend(item.body)
        elif type(item) is Display:
            if not reserve(owner, 'held_power2_program_display', 2 + 2 * len(item.args), source):
                return False
            expressions.extend(item.args)
        elif type(item) is BoundStep:
            if not reserve(owner, 'held_power2_program_boundstep', 2, source):
                return False
            expressions.append(item.rhs)
        elif type(item) is Event:
            if not reserve(owner, 'held_power2_program_event_roles', 2 + 2 * len(item.triggers), source):
                return False
            if any(trigger.kind == 'initial_step' for trigger in item.triggers):
                if not reserve(owner, 'held_power2_program_initial_body', 2 * len(item.body), source):
                    return False
                statements.extend(item.body)
        else:
            return False
        # Runtime cross/timer bodies retain their original event/IR audits.
    while expressions:
        if not reserve(owner, 'held_power2_program_expr', 4, source):
            return False
        item = expressions.pop()
        if type(item) is not Expr or type(item.args) is not tuple:
            return False
        if item.op == 'voltage' or item.op in OPERATOR_NAMES:
            blocked = True
        if not reserve(owner, 'held_power2_program_edges', 2 * len(item.args), source):
            return False
        expressions.extend(item.args)
    return not blocked


def target_aliases(compiler, statements):
    owner = compiler.compilation.native_audit
    if not reserve(owner, 'held_power2_alias_presence', 2):
        return None
    if not getattr(compiler.compilation, 'has_waveform_operators', True):
        return None
    if not reserve(owner, 'held_power2_alias_containers', 16):
        return None
    candidates, writes, reads, targets = {}, {}, {}, {}
    for statement in statements:
        if not reserve(owner, 'held_power2_alias_candidate', 8, statement):
            return None
        if isinstance(statement, Assignment) and statement.index is None and compiler.model.variables.get(statement.name) == 'real':
            # A structurally impossible root cannot become an eligible alias.
            # Pay before inspecting it, so no full original read/write proof is
            # constructed merely for an unsupported multiply or operator root.
            if not reserve(owner, 'held_power2_alias_root', 16, statement):
                return None
            # Two unconditional source writes already disprove the existing
            # unique-writer requirement. Reject that candidate before paying
            # for a full read/transition-target scan of unrelated expressions.
            if not reserve(owner, 'held_power2_alias_shallow_writer', 3, statement):
                return None
            writes[statement.name] = writes.get(statement.name, 0) + 1
            root = statement.rhs
            if type(root) is Expr and type(root.args) is tuple and root.op in _SOURCE_PLAN_OPS:
                candidates[statement.name] = statement
    if not candidates:
        return candidates
    if not reserve(owner, 'held_power2_alias_repeated_filter', 3 * len(candidates) + len(writes)):
        return None
    candidates = {name: statement for name, statement in candidates.items() if writes[name] == 1}
    # The full qualification below counts all writes, including conditional
    # and event writes; the shallow counts are only a decisive negative hint.
    writes.clear()
    if not candidates:
        return candidates
    pending = [(statements, False), (compiler.model.initial, False), (compiler.model.events, False)]
    while pending:
        if not reserve(owner, 'held_power2_alias_visit', 16):
            return None
        item, target = pending.pop()
        if isinstance(item, Expr):
            if type(item.args) is not tuple:
                return None
            if item.op == 'parameter' and item.value in candidates:
                reads[item.value] = reads.get(item.value, 0) + 1
                if target:
                    targets[item.value] = targets.get(item.value, 0) + 1
            if not reserve(owner, 'held_power2_alias_edges', 4 * len(item.args)):
                return None
            pending.extend((arg, item.op == 'transition' and index == 0) for index, arg in enumerate(item.args))
        elif isinstance(item, Assignment):
            writes[item.name] = writes.get(item.name, 0) + 1
            pending.append((item.rhs, False))
            if item.index is not None:
                pending.append((item.index, False))
        elif is_dataclass(item):
            if not reserve(owner, 'held_power2_alias_fields', 4 * len(item.__dataclass_fields__)):
                return None
            pending.extend((getattr(item, f.name), False) for f in fields(item) if f.name not in ('token', 'expansion'))
        elif isinstance(item, (tuple, list)):
            if not reserve(owner, 'held_power2_alias_elements', 4 * len(item)):
                return None
            pending.extend((child, False) for child in item)
    if not reserve(owner, 'held_power2_alias_result', 12 * len(candidates)):
        return {}
    return {name: statement for name, statement in candidates.items()
            if writes.get(name) == 1 and reads.get(name, 0) > 0 and reads.get(name) == targets.get(name)}


def source_plan(compiler, root):
    """Exact source identities, fresh whole-domain bounds, never a semantic cache."""
    owner = compiler.compilation.native_audit
    if not reserve(owner, 'held_power2_source_containers', 12, root):
        return None
    facts = {}
    found = False
    state_read = False
    def visit(item):
        nonlocal found, state_read
        if not reserve(owner, 'held_power2_source_visit', 32, item):
            return None
        if type(item) is not Expr or type(item.args) is not tuple or item.op not in _SOURCE_PLAN_OPS:
            return None
        if not reserve(owner, 'held_power2_source_origin', 16, item):
            return None
        if (not (item.token.source or compiler.model.source) or item.token.line <= 0 or item.token.column <= 0 or
                type(item.expansion) is not tuple):
            return None
        if not reserve(owner, 'held_power2_source_expansion', 8 * len(item.expansion), item):
            return None
        if any(type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str or type(pair[1]) is not int
               for pair in item.expansion):
            return None
        if not reserve(owner, 'held_power2_source_children', 8 * len(item.args), item):
            return None
        children = []
        for child in item.args:
            value = visit(child)
            if value is None:
                return None
            children.append(value)
        typed = integer_bits.integer_type(item, compiler.model.variables, compiler.model.parameter_types,
                                           compiler.model.genvars, child_types=[c[1] for c in children])
        constant = None
        if item.op == 'number' and not children:
            constant = float(item.value)
            if not math.isfinite(constant):
                return None
            bounds = (constant, constant)
        elif item.op == 'parameter' and not children:
            name = str(item.value)
            if name in compiler.state_ids:
                index = compiler.state_ids[name]
                state = compiler.compilation.states[index]
                if state.kind != 'integer' or state.instance != compiler.instance.name:
                    return None
                domains = compiler.ordinary_integer_bounds
                bounds = (domains if domains is not None else compiler.integer_state_ranges).get(index, (-2147483648, 2147483647))
                state_read = True
            elif name in compiler.model.parameters:
                constant = float(compiler.parameter(name))
                if not math.isfinite(constant):
                    return None
                bounds = (constant, constant)
            else:
                return None
        elif item.op in ('/', '%') and len(children) == 2:
            left, right = children
            divisor = right[3]
            # A remainder's legacy structural enclosure may be wider than its
            # true range. Never use our tighter bound to bypass a parent bin gate.
            if (not left[1] or not right[1] or divisor is None or not divisor.is_integer() or
                    divisor <= 0 or divisor > 2147483647 or item.args[0].op not in ('number', 'parameter', '/')):
                return None
            divisor = int(divisor)
            low, high = left[2]
            if low < 0 or high > 2147483647 or int(low) != low or int(high) != high or divisor & (divisor - 1):
                return None
            first, last = int(low) // divisor, int(high) // divisor
            if last - first + 1 > 256:
                return None  # The original producer retains its original bin refusal.
            bounds = (first, last) if item.op == '/' else (0, min(divisor - 1, high))
            if left[3] is not None:
                constant = float(int(left[3]) // divisor if item.op == '/' else int(left[3]) % divisor)
                bounds = (constant, constant)
            found = True
        elif item.op == 'ternary' and len(children) == 3:
            bounds = (min(children[1][2][0], children[2][2][0]), max(children[1][2][1], children[2][2][1]))
        elif (item.op in ('<', '<=', '>', '>=', '==', '!=', '&&', '||') and len(children) == 2 or
              item.op == 'unary!' and len(children) == 1):
            bounds = (0, 1)
        else:
            return None
        if bounds[0] > bounds[1] or typed and (bounds[0] < -2147483648 or bounds[1] > 2147483647):
            return None
        if not reserve(owner, 'held_power2_source_fact', 8, item):
            return None
        value = (item, typed, bounds, constant)
        facts[id(item)] = value
        return value
    result = visit(root)
    return facts if result is not None and found and state_read else None


def arithmetic(compiler, facts, expr, numerator, denominator):
    owner = compiler.compilation.native_audit
    owner.debit('held_power2_arithmetic_lookup', 8, expr)
    fact = facts.get(id(expr))
    if fact is None or fact[0] is not expr or expr.op not in ('/', '%'):
        raise CompileError('held projection source binding changed', token=expr.token)
    right = facts[id(expr.args[1])]
    divisor = int(right[3])
    owner.debit('held_power2_operand_dispatch', 32, expr)
    if not isinstance(denominator, Affine) or denominator.terms or denominator.constant != divisor:
        raise CompileError('held projection divisor binding changed', token=expr.token)
    if expr.op == '/' and fact[3] is not None and isinstance(numerator, Affine) and not numerator.terms:
        # Keep the original constant integer producer. Its fresh typing, integral,
        # signed32 and bin checks retain an Affine result for an outer divisor
        # or numerator; accepting arbitrary IntegerPrimitive divisors would lose
        # the exact source-to-binding contract instead of fixing this regression.
        owner.debit('held_power2_constant_dispatch', 8, expr)
        if facts[id(expr.args[0])][3] != numerator.constant:
            raise CompileError('held projection constant binding changed', token=expr.token)
        return compiler.integer_arithmetic(expr, numerator, denominator)
    if isinstance(numerator, StateRef):
        original = expr.args[0]
        if (original.op != 'parameter' or compiler.state_ids.get(str(original.value)) != numerator.state or
                not 0 <= numerator.state < len(compiler.compilation.states)):
            raise CompileError('held projection state binding changed', token=expr.token)
        state = compiler.compilation.states[numerator.state]
        if state.kind != 'integer' or state.instance != compiler.instance.name:
            raise CompileError('held projection state owner changed', token=expr.token)
        operand = compiler.make_ir(IntegerState, numerator.state)
    elif isinstance(numerator, Affine) and not numerator.terms and numerator.constant.is_integer():
        if facts[id(expr.args[0])][3] != numerator.constant:
            raise CompileError('held projection constant binding changed', token=expr.token)
        operand = compiler.make_ir(IntegerLiteral, int(numerator.constant))
    elif isinstance(numerator, IntegerPrimitive):
        owner.debit('held_power2_nested_binding', 16, expr)
        child = expr.args[0]
        if (child.op != '/' or numerator.function != 'shift_right' or
                type(numerator.args) is not tuple or len(numerator.args) != 2 or
                not isinstance(numerator.args[1], IntegerLiteral) or
                numerator.args[1].value != int(facts[id(child.args[1])][3]).bit_length() - 1 or
                numerator.origin.instance != compiler.instance.name or
                numerator.origin.source != (child.token.source or compiler.model.source) or
                numerator.origin.line != child.token.line or numerator.origin.column != child.token.column or
                numerator.origin.expansion is not child.expansion):
            raise CompileError('held projection nested source binding changed', token=expr.token)
        operand = numerator
    else:
        raise CompileError('held projection operand binding changed', token=expr.token)
    value = divisor.bit_length() - 1 if expr.op == '/' else divisor - 1
    literal = compiler.make_ir(IntegerLiteral, value)
    origin = compiler.make_ir(Origin, expr.token.source or compiler.model.source, expr.token.line,
                              expr.token.column, compiler.instance.name, expr.expansion)
    owner.debit('held_power2_operand_container', 3, expr)
    result = compiler.make_ir(IntegerPrimitive, 'shift_right' if expr.op == '/' else 'bit_and', (operand, literal), origin)
    compiler.checked_ir(result, origin)
    return result
