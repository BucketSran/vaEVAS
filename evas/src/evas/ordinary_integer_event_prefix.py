"""Transfer event-only input Floor prefixes to existing scalar event statements.

The public state trace includes the slot and its engineering zero seed. Every
original model read follows the same callback's prefix assignment. This module
grants no continuous Floor, trigger, history or observer capability.
"""
from dataclasses import dataclass, fields, is_dataclass

from .syntax import Assignment, Conditional, Event, Expr, Loop


@dataclass(frozen=True)
class Plan:
    names: frozenset
    event_prefixes: dict
    moved_tokens: frozenset

    def body(self, event, owner):
        owner.debit('integer_prefix_body_lookup', 2, event)
        prefix = self.event_prefixes.get(event.token, ())
        if not prefix:
            return event.body
        owner.debit('integer_prefix_body_copy', 1 + len(prefix) + len(event.body), event)
        return (*prefix, *event.body)


EMPTY = Plan(frozenset(), {}, frozenset())


def qualify(compiler):
    owner = compiler.compilation.native_audit
    owner.debit('integer_prefix_dispatch', 8)
    source = compiler.event_body_source_model
    if source is None or source.arrays or compiler.model.arrays:
        return EMPTY

    def pay(kind, amount=1, item=None):
        owner.debit('integer_prefix_' + kind, amount, item)

    pay('helper_setup', 8)

    def references(root, name):
        pay('reference_container', 2)
        pending = [root]
        while pending:
            pay('reference_visit')
            item = pending.pop()
            if isinstance(item, Expr):
                if item.op == 'parameter' and str(item.value) == name:
                    return True
                pay('reference_edges', len(item.args))
                pending.extend(item.args)
            elif is_dataclass(item):
                # Prepay fields() and its filtered reference container before
                # either can allocate; retain the existing per-field charge.
                pay('reference_field_container', 2 + 2 * len(item.__dataclass_fields__))
                fs = [f for f in fields(item) if f.name not in ('token', 'expansion')]
                pay('reference_fields', len(fs))
                pending.extend(getattr(item, f.name) for f in fs)
            elif isinstance(item, (tuple, list)):
                pay('reference_items', len(item))
                pending.extend(item)
        return False

    def writes(root, name):
        count = len(root) if isinstance(root, (list, tuple)) else 1
        pay('write_container', 1 + count)
        pending = list(root) if isinstance(root, (list, tuple)) else [root]
        while pending:
            pay('write_visit')
            item = pending.pop()
            if isinstance(item, (Assignment, Loop)) and item.name == name:
                return True
            for attr in ('body', 'then_body', 'else_body'):
                children = getattr(item, attr, ())
                pay('write_edges', len(children))
                pending.extend(children)
        return False

    def constant(expr, model):
        pay('constant_visit', item=expr)
        if expr.op == 'number':
            return not expr.args
        if expr.op == 'parameter':
            return str(expr.value) in model.parameters and not expr.args
        if expr.op not in ('+', '-', '*', '/', 'unary+', 'unary-'):
            return False
        pay('constant_results', 1 + len(expr.args), expr)
        results = [constant(child, model) for child in expr.args]
        return all(results)

    def input_expression(expr, model):
        pay('input_visit', item=expr)
        if expr.op == 'voltage':
            pay('input_nodes', len(expr.args), expr)
            return bool(expr.args) and all(
                child.op == 'node' and str(child.value) != '$abstime'
                and compiler.node_ids.get(str(child.value)) in compiler.allowed_condition_nodes
                for child in expr.args)
        if expr.op in ('number', 'parameter'):
            return constant(expr, model)
        if expr.op not in ('+', '-', '*', '/', 'unary+', 'unary-'):
            return False
        pay('input_results', 1 + len(expr.args), expr)
        results = [input_expression(child, model) for child in expr.args]
        return all(results)

    def clamp_statement(item, name, model):
        pay('clamp_visit', item=item)
        if isinstance(item, Assignment):
            return (item.name == name and item.index is None
                    and constant(item.rhs, model))
        if not isinstance(item, Conditional):
            return False
        left = item.left
        if not (left.op == 'parameter' and str(left.value) == name
                and not left.args and constant(item.right, model)):
            return False
        pay('clamp_results', 2 + 2 * (len(item.then_body) + len(item.else_body)), item)
        results = [clamp_statement(child, name, model)
                   for child in (*item.then_body, *item.else_body)]
        return bool(results) and all(results)

    def collect(model, name):
        if (model.variables.get(name) != 'integer' or name in model.arrays
                or name in model.variable_initializers
                or references(model.initial, name) or writes(model.initial, name)):
            return None
        pay('collect_containers', 2)
        prefix, used_events = [], []
        first = None
        for item in model.analog:
            pay('statement_visit', item=item)
            if isinstance(item, Event):
                # Check original and executable callback layouts below.
                continue
            if writes(item, name):
                if first is None:
                    if not (isinstance(item, Assignment) and item.name == name
                            and item.index is None and item.rhs.op == 'floor'
                            and len(item.rhs.args) == 1
                            and input_expression(item.rhs.args[0], model)):
                        return None
                    first = item
                elif not clamp_statement(item, name, model):
                    return None
                pay('prefix_retain')
                prefix.append(item)
            elif references(item, name):
                # Includes zero-masked ordinary contributions and aliases.
                return None
        if first is None:
            return None
        # The retained parser Model keeps callbacks in analog. Executable
        # elaboration moves them into events. Inspect both actual layouts.
        pay('event_roots', 1 + len(model.events) + len(model.analog))
        pay('event_identity_container')
        events = [*model.events, *(item for item in model.analog if isinstance(item, Event))]
        seen_events = set()
        for event in events:
            pay('event_identity', 2, event)
            if event.token in seen_events:
                continue
            pay('event_identity_insert')
            seen_events.add(event.token)
            pay('event_visit', item=event)
            if writes(event.body, name):
                return None
            for trigger in event.triggers:
                if references(trigger.arguments, name):
                    return None
            if not references(event.body, name):
                continue
            if any(t.kind in ('initial_step', 'final_step') for t in event.triggers):
                return None
            for trigger in event.triggers:
                if trigger.kind == 'timer':
                    # Keep startup/zero-time event initialization separate.
                    from .lowering import lower
                    from .ir import Affine
                    pay('timer_lower_setup', 4, event)
                    value = lower(trigger.arguments[0], compiler.typed_resolve(compiler.parameter), {}, model.source)
                    if not isinstance(value, Affine) or value.terms or value.constant <= 0:
                        return None
            for statement in prefix:
                pay('source_order', 4, statement)
                a, b = statement.token, event.token
                if a.source != b.source or (a.line, a.column) >= (b.line, b.column):
                    return None
            pay('event_retain')
            used_events.append(event.token)
        if not used_events:
            return None
        pay('collect_result', 3 + len(prefix) + len(used_events))
        return tuple(prefix), tuple(used_events)

    pay('candidate_container', 1 + len(source.analog))
    candidates = [item.name for item in source.analog
                  if isinstance(item, Assignment) and item.index is None
                  and source.variables.get(item.name) == 'integer'
                  and item.rhs.op == 'floor']
    # Keep this first slice at one complete original prefix per Model, so no
    # independent variable grouping can reorder original statement evaluation.
    if len(candidates) != 1:
        pay('plan_finalize', 3)
        return EMPTY
    pay('plan_containers', 3)
    names, event_prefixes, moved = set(), {}, set()
    for name in candidates:
        pay('candidate_visit')
        original = collect(source, name)
        if original is None:
            continue
        executable = collect(compiler.model, name)
        if executable is None:
            continue
        a, ae = original
        b, be = executable
        pay('identity_compare', len(a) + len(b) + len(ae) + len(be))
        if tuple(s.token for s in a) != tuple(s.token for s in b) or ae != be:
            continue
        owner.activate(a[0])
        pay('plan_storage', 4 + len(b) + len(be))
        names.add(name)
        moved.update(s.token for s in b)
        for token in be:
            old = event_prefixes.get(token, ())
            pay('event_prefix_copy', 1 + len(old) + len(b))
            event_prefixes[token] = (*old, *b)
    pay('plan_finalize', 3 + len(names) + len(moved))
    return Plan(frozenset(names), event_prefixes, frozenset(moved))
