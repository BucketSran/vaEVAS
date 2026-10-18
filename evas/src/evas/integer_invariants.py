"""Bounded source candidates for the existing integer post-fixpoint check.

Candidates are guesses, never facts: defaults and every callback must verify
before use. No stimulus, event-count assumption, or initial-value substitution
enters a certificate. Original source validation remains the compiler's job.
"""
from .limits import MAX_IR_ITEMS
from .syntax import Assignment, Conditional, Loop


class ProofBudgetExceeded(ValueError):
    """The optional range certificate exhausted its existing work allowance."""


class ProofWork:
    def __init__(self):
        self.used = 0

    def charge(self):
        self.used += 1
        if self.used > MAX_IR_ITEMS:
            raise ProofBudgetExceeded('integer invariant exceeds source proof budget (100000)')


def proof_parameters(parameters, work):
    if getattr(parameters, 'integer_proof_counter', None) is work:
        return parameters
    def lookup(name):
        return parameters(name)
    lookup.integer_proof_work = work.charge
    lookup.integer_proof_counter = work
    if hasattr(parameters, 'real_floor_bounds'):
        lookup.real_floor_bounds = parameters.real_floor_bounds
    return lookup


def widening_candidate(bodies, initial, current, widened, *, states, arrays, parameters, work):
    """One candidate using copy components and source comparison cutpoints.

    Copy components aggregate all seeds and all non-copy writers. An unknown
    writer invalidates that component's finite envelope. Cutpoints only propose
    moving endpoints; their truth is established by the complete transformer.
    """
    from . import event_index_domains as domain
    for _ in range(4 * len(states)):
        work.charge()
    names = set(states)
    parent = {name:name for name in names}
    seeds = {name:initial.get(name, domain.TOP) for name in names}
    cuts = {name:set() for name in names}
    lookup = proof_parameters(parameters, work)

    def find(name):
        work.charge()
        while parent[name] != name:
            work.charge()
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def connect(a, b):
        work.charge()
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b

    def copies(expr):
        if expr.op == 'parameter' and str(expr.value) in names:
            return (str(expr.value),)
        if expr.op == 'index':
            for _ in arrays.get(str(expr.value), ()):
                work.charge()
            values = tuple(f'{expr.value}[{k}]' for k in arrays.get(str(expr.value), ()))
            for name in values:
                work.charge()
                if name not in names:
                    return None
            return values or None
        return None

    def comparison(relation, left, right):
        for value, other in ((left,right),(right,left)):
            work.charge()
            if value.op != 'parameter' or str(value.value) not in names:
                continue
            bound = domain.evaluate(other, {}, lookup, arrays)
            if bound is not None and bound[0] == bound[1] and domain.within(bound, *domain.TOP):
                cuts[str(value.value)].add(bound[0])

    pending = []
    for body in bodies:
        work.charge()
        for item in body:
            work.charge()
            pending.append(item)
    while pending:
        item = pending.pop()
        work.charge()
        if isinstance(item, Conditional):
            comparison(item.relation, item.left, item.right)
        if isinstance(item, Assignment):
            if item.index is not None:
                for _ in arrays.get(item.name, ()):
                    work.charge()
            targets = ((item.name,) if item.index is None else
                       tuple(f'{item.name}[{k}]' for k in arrays.get(item.name, ())))
            for _ in targets:
                work.charge()
            targets = [name for name in targets if name in names]
            dependencies = copies(item.rhs)
            if dependencies is not None:
                for target in targets:
                    for dependency in dependencies:
                        connect(target, dependency)
            else:
                bound = domain.evaluate(item.rhs, {}, lookup, arrays)
                if bound is None and item.rhs.op == '&':
                    # Reuse the existing signed32 mask transfer, even when a
                    # prior shift has no interval. This bounds successful
                    # values only; original operand typing/domain checks stay.
                    operands = [domain.evaluate(arg, {}, lookup, arrays) for arg in item.rhs.args]
                    bound = domain.integer_bits.bounds('&',
                        [domain.TOP if value is None else value for value in operands])
                if bound is None or not domain.within(bound, *domain.TOP):
                    bound = domain.TOP
                for target in targets:
                    work.charge()
                    seeds[target] = domain.hull(seeds[target], bound)
        elif isinstance(item, Loop) and item.name in names:
            seeds[item.name] = domain.TOP
        expressions = [getattr(item, field) for field in ('rhs','left','right','start','limit','update')
                       if hasattr(item, field)]
        while expressions:
            expr = expressions.pop()
            work.charge()
            if expr is None:
                continue
            if expr.op in ('<','<=','>','>='):
                comparison(expr.op, *expr.args)
            for arg in expr.args:
                work.charge()
                expressions.append(arg)
        for branch in ('then_body','else_body','body'):
            for child in getattr(item, branch, ()):
                work.charge()
                pending.append(child)

    envelopes = {}
    for name in names:
        work.charge()
        root = find(name)
        envelopes[root] = domain.hull(envelopes.get(root, domain.BOTTOM), seeds[name])
    for _ in widened:
        work.charge()
    result = dict(widened)
    for name in names:
        work.charge()
        envelope = envelopes[find(name)]
        if envelope != domain.TOP:
            result[name] = domain.hull(current[name], envelope)
        else:
            low, high = result[name]
            before_low, before_high = current[name]
            if low < before_low:
                eligible = None
                for cut in cuts[name]:
                    work.charge()
                    if cut <= before_low:
                        eligible = cut if eligible is None else max(eligible, cut)
                if eligible is not None:
                    low = eligible
            if high > before_high:
                eligible = None
                for cut in cuts[name]:
                    work.charge()
                    if cut >= before_high:
                        eligible = cut if eligible is None else min(eligible, cut)
                if eligible is not None:
                    high = eligible
            result[name] = low, high
    for _ in result:
        work.charge()
    return None if result == widened else result


def verify_candidate(bodies, initial, candidate, *, arrays, parameters):
    """Check initialization inclusion and every complete callback transformer."""
    from . import event_index_domains as domain
    if not hasattr(parameters, 'integer_proof_work'):
        parameters = proof_parameters(parameters, ProofWork())
    charge = parameters.integer_proof_work
    charge()
    for _ in initial:
        charge()
    for _ in candidate:
        charge()
    if set(initial) - set(candidate):
        return False
    for name, interval in candidate.items():
        charge()
        if not domain.within(interval, *domain.TOP):
            return False
        if domain.hull(interval, initial.get(name, domain.TOP)) != interval:
            return False
    for body in bodies:
        charge()
        exit_bounds = domain.flow(body, candidate, arrays=arrays, parameters=parameters,
                                  invariant_only=True)
        for name, value in exit_bounds.items():
            charge()
            if name in candidate and domain.hull(candidate[name], value) != candidate[name]:
                return False
    return True
