"""One native/event audit owner; new held targets opt into its aggregate ceiling.

Event-local legacy charges keep their old verdicts. Aggregate counters include
actual delegated work from the beginning, even before a new target activates it.
"""
from collections import Counter
from dataclasses import fields, is_dataclass

from .errors import CompileError
from .limits import MAX_IR_ITEMS


class NativeAudit:
    def __init__(self):
        self.active = False
        self.used = 0
        self.counts = Counter()
        self.events = {}
        self.event_serial = 0
        self.event_views = {}
        self.event_view_calls = 0
        self.activations = 0
        self.debit("ir_cache_create")
        self.ir_cache = {}

    def debit(self, kind, amount=1, item=None, *, event=None, legacy=False):
        if amount < 0:
            raise ValueError('native audit cannot refund work')
        self.used += amount
        self.counts[kind] += amount
        if legacy:
            self.events[event] = self.events.get(event, 0) + amount
            if self.events[event] > MAX_IR_ITEMS:
                self.fail(item, 'original event audit exceeds expression budget')
        if self.active and self.used > MAX_IR_ITEMS:
            self.fail(item, 'typed held-target aggregate audit exceeds 100000 work items')

    @staticmethod
    def fail(item, message):
        token = getattr(item, 'token', getattr(item, 'origin', item))
        if not all(hasattr(token, key) for key in ('source','line','column')):
            token = None
        raise CompileError(message, code='resource_budget', token=token)

    def activate(self, item):
        self.active = True
        self.activations += 1
        self.debit('activation', 0, item)

    def event_view(self, event):
        # The logical bound instance/event owns its original local allowance.
        # Parsed AST bodies may be shared; retry retrieves the same view object.
        self.event_view_calls += 1
        if event not in self.event_views:
            self.event_serial += 1
            self.event_views[event] = Charge(self, event)
        return self.event_views[event]

    def target_view(self, item):
        self.activate(item)
        return Charge(self, None)

    def extra(self, item, kind, amount=1):
        self.debit(kind, amount, item)

    def ir_work(self, kind, amount):
        self.debit(kind, amount)

    def materialize(self, value):
        # Actual expanded occurrences: sharing never deduplicates wire copies.
        self.debit('wire_visit')
        if is_dataclass(value):
            self.debit('copy_container')
            result = {}
            for field in fields(value):
                self.debit('copy_field')
                result[field.name] = self.materialize(getattr(value, field.name))
            return result
        if isinstance(value, (tuple, list)):
            self.debit('copy_container')
            items = []
            for child in value:
                self.debit('copy_element')
                items.append(self.materialize(child))
            return tuple(items) if isinstance(value, tuple) else items
        if isinstance(value, dict):
            self.debit('copy_container')
            result = {}
            for key, child in value.items():
                self.debit('copy_field')
                result[key] = self.materialize(child)
            return result
        self.debit('copy_atom')
        return value


class Charge:
    def __init__(self, owner, event):
        self.owner, self.event = owner, event

    def __call__(self, item, kind='source_visit', amount=1):
        self.owner.debit(kind, amount, item, event=self.event, legacy=self.event is not None)

    def extra(self, item, kind, amount=1):
        self.owner.debit(kind, amount, item)
