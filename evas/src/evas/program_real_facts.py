"""Compiler admission facts for immutable program-real source reads.

These facts never replace executable expressions or certify a sampled voltage domain.
A closed source, a proved scalar value, and source dependencies are distinct.
StateRef is never a compile-time scalar merely because its seed is known.
"""
from dataclasses import dataclass
import math
from fractions import Fraction

from .errors import CompileError
from .ir import Affine, Binary, Power, RealBinary, RealBoundary, RealLocal, Select, StateRef
from .limits import MAX_IR_DEPTH


@dataclass(frozen=True)
class ClosedProgramValue:
    closed: bool
    value: float | None

    @property
    def finite(self):
        return self.value is not None and math.isfinite(self.value)


UNKNOWN = ClosedProgramValue(False, None)


def same_binary_value(a, b):
    """A proved scalar includes the sign of binary64 zero."""
    return a is not None and b is not None and a.hex() == b.hex()


class ProgramRealFacts:
    def __init__(self, work):
        self.work = work
        work('program_fact_cache_create', 3)
        self.reads = {}
        self.memo = {}
        self.active = set()

    def record_read(self, read, sources, *, relation=None):
        self.work('program_fact_read_record', 2 + len(sources))
        # Keeping the read and its immutable source children prevents identity
        # reuse and future writes to the same binding from changing this fact.
        assert id(read) not in self.reads
        self.reads[id(read)] = (read, tuple(sources), relation)

    def sources(self, read, *, values_only=False):
        self.work('program_fact_read_lookup', 1)
        fact = self.reads.get(id(read))
        if fact is None or fact[0] is not read:
            return None
        return fact[1][2:] if values_only and len(fact[1]) == 4 else fact[1]

    def query(self, value, mode='closed', *, state_sources=None, generation=0, allowed_nodes=frozenset()):
        if mode != 'closed' or not isinstance(value, Affine) or value.terms:
            owner = getattr(self.work, '__self__', None)
            if owner is not None and hasattr(owner, 'activate') and not owner.active:
                # Qualification/role proofs own aggregate work even when a
                # program has only wrappers/Selects and no arithmetic node.
                owner.activate(getattr(value, 'origin', value))
        def visit(item, depth=0):
            self.work('program_fact_lookup', 1)
            if depth > MAX_IR_DEPTH:
                raise CompileError('program-real source fact depth exceeded', code='resource_budget')
            context = (mode, generation, allowed_nodes) if mode != 'closed' else (mode,)
            key = (id(item), context)
            cached = self.memo.get(key)
            if cached is not None:
                assert cached[0] is item
                return cached[1]
            if key in self.active:
                # A state dependency cycle is not a DC/closed certificate.
                if mode in ('leaf_values', 'integer_range', 'selected_interval'):
                    return None
                return True if mode == 'continuous' else False if mode == 'dc' else UNKNOWN
            self.active.add(key)
            try:
                result = compute(item, lambda child: visit(child, depth + 1))
            finally:
                self.active.remove(key)
            self.work('program_fact_insert', 2)
            self.memo[key] = (item, result)
            return result

        def closed(item, child):
            if isinstance(item, Affine):
                return ClosedProgramValue(True, item.constant) if not item.terms else UNKNOWN
            if isinstance(item, StateRef):
                return UNKNOWN
            if isinstance(item, RealLocal):
                sources = self.sources(item)
                if sources is None:
                    return UNKNOWN
                if len(sources) == 1:
                    return child(sources[0])
                facts = [child(source) for source in sources]
                qualified = all(f.closed for f in facts)
                a, b, yes, no = facts
                if same_binary_value(yes.value, no.value):
                    return ClosedProgramValue(qualified, yes.value)
                if a.finite and b.finite:
                    relation = self.reads[id(item)][2]
                    choice = {'lt': a.value < b.value, 'le': a.value <= b.value,
                              'gt': a.value > b.value, 'ge': a.value >= b.value}[relation]
                    return ClosedProgramValue(qualified, yes.value if choice else no.value)
                return ClosedProgramValue(qualified, None)
            if isinstance(item, RealBoundary):
                return child(item.value)
            if isinstance(item, (Binary, RealBinary)):
                a, b = child(item.left), child(item.right)
                qualified = a.closed and b.closed
                if not a.finite or not b.finite:
                    return ClosedProgramValue(qualified, None)
                operation = item.operation if isinstance(item, RealBinary) else item.op
                try:
                    number = {'add': lambda: a.value+b.value, 'subtract': lambda: a.value-b.value,
                              'multiply': lambda: a.value*b.value, 'divide': lambda: a.value/b.value}[operation]()
                    return ClosedProgramValue(qualified, number)
                except (ArithmeticError, KeyError):
                    return ClosedProgramValue(qualified, None)
            if isinstance(item, Power):
                base = child(item.base)
                if not base.finite:
                    return ClosedProgramValue(base.closed, None)
                try:
                    return ClosedProgramValue(base.closed, base.value ** item.exponent)
                except (ArithmeticError, ValueError):
                    return ClosedProgramValue(base.closed, None)
            if isinstance(item, Select):
                facts = [child(source) for source in (item.left, item.right, item.then_value, item.else_value)]
                qualified = all(f.closed for f in facts)
                a, b, yes, no = facts
                if same_binary_value(yes.value, no.value):
                    return ClosedProgramValue(qualified, yes.value)
                if a.finite and b.finite:
                    choice = {'lt': a.value < b.value, 'le': a.value <= b.value,
                              'gt': a.value > b.value, 'ge': a.value >= b.value}[item.relation]
                    return ClosedProgramValue(qualified, yes.value if choice else no.value)
                return ClosedProgramValue(qualified, None)
            return UNKNOWN

        def leaf_values(item, child):
            # This is a conservative finite image of piecewise constant
            # leaves, not a global closed-source certificate. Keep original
            # guards executable; unrelated branch choices form a superset.
            self.work('program_leaf_helpers', 6)
            def finish(points):
                self.work('program_leaf_result', 1 + len(points))
                return tuple(points.values())

            def merge(groups):
                self.work('program_leaf_container', 1)
                points = {}
                for group in groups:
                    if group is None:
                        return None
                    for number in group:
                        self.work('program_leaf_point', 2)
                        if not math.isfinite(number):
                            return None
                        points[number.hex()] = number
                return finish(points)

            if isinstance(item, Affine):
                if item.terms or not math.isfinite(item.constant):
                    return None
                self.work('program_leaf_scalar', 2)
                return (float(item.constant),)
            if isinstance(item, StateRef):
                return None
            if isinstance(item, RealLocal):
                sources = self.sources(item, values_only=True)
                if sources is None:
                    return None
                if len(sources) == 1:
                    return child(sources[0])
                self.work('program_leaf_generator', 2)
                return merge(child(source) for source in sources)
            if isinstance(item, RealBoundary):
                return child(item.value)
            if isinstance(item, Select):
                self.work('program_leaf_branch_pair', 2)
                return merge((child(item.then_value), child(item.else_value)))
            if isinstance(item, (Binary, RealBinary)):
                left, right = child(item.left), child(item.right)
                if left is None or right is None:
                    return None
                operation = item.operation if isinstance(item, RealBinary) else item.op
                self.work('program_leaf_container', 1)
                points = {}
                for a in left:
                    for b in right:
                        self.work('program_leaf_pair', 3)
                        try:
                            if operation == 'add': number = a + b
                            elif operation == 'subtract': number = a - b
                            elif operation == 'multiply': number = a * b
                            elif operation == 'divide': number = a / b
                            else: return None
                        except ArithmeticError:
                            return None
                        if not math.isfinite(number):
                            return None
                        self.work('program_leaf_point', 2)
                        points[number.hex()] = number
                return finish(points)
            if isinstance(item, Power):
                values = child(item.base)
                if values is None:
                    return None
                self.work('program_leaf_container', 1)
                points = {}
                for base in values:
                    self.work('program_leaf_power', 3)
                    try:
                        number = base ** item.exponent
                    except (ArithmeticError, ValueError):
                        return None
                    if not math.isfinite(number):
                        return None
                    self.work('program_leaf_point', 2)
                    points[number.hex()] = number
                return finish(points)
            return None

        def selected_interval(item, child):
            # Source-selected constant domains only: never an actual value,
            # global-closed certificate, or a physical voltage enclosure.
            self.work('program_interval_helpers', 4)
            def hull(bounds):
                self.work('program_interval_hull', 1 + 3 * len(bounds))
                if any(value is None for value in bounds):
                    return None
                low = min(value[0] for value in bounds)
                high = max(value[1] for value in bounds)
                return (low, high)
            if isinstance(item, Affine):
                if item.terms or not math.isfinite(item.constant):
                    return None
                self.work('program_interval_scalar', 2)
                number = float(item.constant)
                return (number, number)
            if isinstance(item, StateRef):
                return None
            if isinstance(item, RealLocal):
                sources = self.sources(item, values_only=True)
                if not sources:
                    return None
                self.work('program_interval_sources', 1 + len(sources))
                return hull(tuple(child(source) for source in sources))
            if isinstance(item, RealBoundary):
                return child(item.value)
            if isinstance(item, Select):
                self.work('program_interval_branch_pair', 2)
                return hull((child(item.then_value), child(item.else_value)))
            if not isinstance(item, (Binary, RealBinary)):
                return None
            a, b = child(item.left), child(item.right)
            if a is None or b is None:
                return None
            operation = item.operation if isinstance(item, RealBinary) else item.op
            if operation == 'divide' and b[0] <= 0 <= b[1]:
                return None
            points = []
            self.work('program_interval_points_container', 1)
            for x in a:
                for y in b:
                    self.work('program_interval_pair', 3)
                    try:
                        if isinstance(item, Binary):
                            # Mathematical Binary has no source round node.
                            # Enclose its exact rational endpoints outward;
                            # premature RN could hide a later zero divisor.
                            nx, dx = x.as_integer_ratio()
                            ny, dy = y.as_integer_ratio()
                            self.work('program_interval_rational', 4 + (abs(nx).bit_length() + dx.bit_length() + abs(ny).bit_length() + dy.bit_length()) // 32)
                            x, y = Fraction(nx, dx), Fraction(ny, dy)
                        value = {'add':lambda:x+y, 'subtract':lambda:x-y,
                                 'multiply':lambda:x*y, 'divide':lambda:x/y}[operation]()
                        number = float(value)
                        if not math.isfinite(number):
                            return None
                        if isinstance(item, Binary):
                            exact = Fraction(number)
                            lower = math.nextafter(number, -math.inf) if value < exact else number
                            upper = math.nextafter(number, math.inf) if value > exact else number
                        else:
                            # Python's four finite float operations perform
                            # the same per-node binary64 RN as program real.
                            lower = upper = number
                        if not math.isfinite(lower) or not math.isfinite(upper):
                            return None
                    except (ArithmeticError, KeyError, ValueError):
                        return None
                    self.work('program_interval_point', 2)
                    points.append((lower, upper))
            return hull(points)

        def compute(item, child):
            if mode == 'closed':
                return closed(item, child)
            if mode == 'leaf_values':
                return leaf_values(item, child)
            if mode == 'selected_interval':
                return selected_interval(item, child)
            if mode == 'integer_range':
                values = self.query(item, 'leaf_values')
                if not values:
                    return None
                low, high = values[0], values[0]
                for value in values:
                    self.work('program_leaf_integer_test', 3)
                    if not value.is_integer():
                        return None
                    low, high = min(low, value), max(high, value)
                self.work('program_leaf_integer_range', 3)
                return low, high
            if isinstance(item, RealLocal):
                sources = self.sources(item, values_only=True)
                if sources is None:
                    return mode == 'continuous'
                return any(child(source) for source in sources) if mode == 'continuous' else all(child(source) for source in sources)
            if isinstance(item, RealBoundary):
                return child(item.value)
            if isinstance(item, StateRef):
                sources = (state_sources or {}).get(item.state)
                if sources is None:
                    return mode == 'dc'
                return any(child(source) for source in sources) if mode == 'continuous' else all(child(source) for source in sources)
            if isinstance(item, Affine):
                return bool(item.terms) if mode == 'continuous' else all(t.node in allowed_nodes for t in item.terms)
            if isinstance(item, Select):
                return (child(item.then_value) or child(item.else_value)) if mode == 'continuous' else (child(item.then_value) and child(item.else_value))
            if isinstance(item, (Binary, RealBinary)):
                operation = item.operation if isinstance(item, RealBinary) else item.op
                if mode == 'continuous':
                    return child(item.left) or child(item.right)
                return operation in ('add', 'subtract', 'multiply') and child(item.left) and child(item.right)
            if isinstance(item, Power):
                return child(item.base) if mode == 'continuous' else False
            return False

        return visit(value)
