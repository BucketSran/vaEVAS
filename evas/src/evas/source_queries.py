"""Paid immutable source-DAG facts, scoped to one structural query context.

The caller owns the predicate/array bindings and the compilation work owner.
No semantic values, lowering results or activation state are cached here.
"""
from .syntax import Expr


class SourceQuery:
    def __init__(self, owner, kind, local, merge):
        owner.activate(None)
        owner.debit(kind+'_setup', 4)
        self.owner, self.kind, self.local, self.merge = owner, kind, local, merge
        self.memo = {}

    def __call__(self, root):
        owner, kind, memo = self.owner, self.kind, self.memo
        owner.debit(kind+'_pending', 2, root)
        pending = [(root, False, None)]
        while pending:
            owner.debit(kind+'_pop', 2, root)
            item, exiting, local_value = pending.pop()
            owner.debit(kind+'_lookup', 2, item)
            key = id(item)
            if key in memo:
                continue
            if type(item) is not Expr:
                raise TypeError('source query requires immutable Expr nodes')
            if not exiting:
                owner.debit(kind+'_local', 2, item)
                value, descend = self.local(item)
                if not descend:
                    owner.debit(kind+'_insert', 2, item)
                    memo[key] = (item, value)
                    continue
                owner.debit(kind+'_edges', 3+2*len(item.args), item)
                pending.append((item, True, value))
                for child in item.args:
                    pending.append((child, False, None))
            else:
                owner.debit(kind+'_merge_container', 1+len(item.args), item)
                values = [memo[id(child)][1] for child in item.args]
                value = self.merge(item, local_value, values)
                owner.debit(kind+'_insert', 2, item)
                memo[key] = (item, value)
        owner.debit(kind+'_result', 2, root)
        return memo[id(root)][1]


_EMPTY_STRUCTURE = (False, frozenset(), frozenset())
_TIME_STRUCTURE = (True, frozenset(), frozenset())
_STRUCTURE_KIND = {'time': 1, 'parameter': 2, 'index': 3}


class SourceStructure:
    """Joint syntax facts for one bound instance; never execution values.

    A cursor frame visits each outgoing edge once. Completed children merge
    directly into their waiting parent, without a second exit-frame lookup or
    a temporary list of all child facts. Empty facts share immutable metadata.
    """
    def __init__(self, owner):
        owner.activate(None)
        owner.debit('source_structure_setup', 4)
        self.owner = owner
        self.memo = {}

    def _enter(self, item, pending):
        owner, memo = self.owner, self.memo
        while True:
            owner.debit('source_structure_shape', 3, item)
            if type(item) is not Expr or type(item.args) is not tuple or type(item.op) is not str:
                raise TypeError('source structure requires immutable Expr children')
            owner.debit('source_structure_kind', 1, item)
            kind = _STRUCTURE_KIND.get(item.op)
            value = _EMPTY_STRUCTURE
            if kind == 1:
                value = _TIME_STRUCTURE
            elif kind in (2, 3):
                name = item.value
                if type(name) is not str:
                    raise TypeError('source identifier must be a string')
                owner.debit('source_structure_name', 5+len(name), item)
                reference = frozenset((name,))
                value = (False, reference, frozenset()) if kind == 2 else (False, frozenset(), reference)
            if not item.args:
                owner.debit('source_structure_leaf_insert', 2, item)
                memo[id(item)] = (item, value)
                return value
            if len(item.args) == 1 and value is _EMPTY_STRUCTURE:
                # Identity facts need no mutable cursor or accumulator. The
                # immutable source node itself is the waiting continuation.
                owner.debit('source_structure_unary', 2, item)
                pending.append(item)
                item = item.args[0]
                owner.debit('source_structure_lookup', 2, item)
                cached = memo.get(id(item))
                if cached is not None:
                    return cached[1]
                continue
            owner.debit('source_structure_frame', 5, item)
            pending.append([item, 0, value])
            return None

    def fact(self, root):
        owner, memo = self.owner, self.memo
        owner.debit('source_structure_root_lookup', 2, root)
        result = memo.get(id(root))
        if result is not None:
            return result[1]
        owner.debit('source_structure_pending', 1, root)
        pending = []
        value = self._enter(root, pending)
        while pending:
            frame = pending[-1]
            if type(frame) is Expr:
                owner.debit('source_structure_complete', 3, frame)
                memo[id(frame)] = (frame, value)
                pending.pop()
            elif value is not None:
                frame[2] = self._merge(frame[2], value, frame[0])
                value = None
            elif frame[1] < len(frame[0].args):
                item, position, _ = frame
                owner.debit('source_structure_edge', 3, item)
                child = item.args[position]
                frame[1] = position+1
                owner.debit('source_structure_lookup', 2, child)
                cached = memo.get(id(child))
                value = cached[1] if cached is not None else self._enter(child, pending)
            else:
                item, _, value = frame
                owner.debit('source_structure_complete', 3, item)
                memo[id(item)] = (item, value)
                pending.pop()
        return value

    def _merge(self, left, right, item):
        self.owner.debit('source_structure_merge', 1, item)
        if right is _EMPTY_STRUCTURE or left is right:
            return left
        if left is _EMPTY_STRUCTURE:
            return right
        self.owner.debit('source_structure_merge_fields', 3, item)
        return (left[0] or right[0], self._union(left[1], right[1], item),
                self._union(left[2], right[2], item))

    def _union(self, left, right, item):
        if not right or left is right:
            return left
        if not left:
            return right
        self.owner.debit('source_structure_union_scan', len(left)+len(right), item)
        for name in left:
            self.owner.debit('source_structure_union_name', 1+len(name), item)
        for name in right:
            self.owner.debit('source_structure_union_name', 1+len(name), item)
        self.owner.debit('source_structure_union', 1+len(left)+len(right), item)
        return left | right

    def reads(self, root, arrays):
        _, names, indexed = self.fact(root)
        if not indexed:
            return names
        self.owner.debit('source_structure_array_names_container', 1+len(names), root)
        result = set(names)
        self.owner.debit('source_structure_array_scan', len(indexed), root)
        for base in indexed:
            self.owner.debit('source_structure_array_lookup', 2+len(base), root)
            indices = arrays.get(base, ())
            self.owner.debit('source_structure_array_elements', len(indices), root)
            for index in indices:
                self.owner.debit('source_structure_array_name', 4+len(base)+2+max(1, abs(index).bit_length())+(index < 0), root)
                result.add(f'{base}[{index}]')
        self.owner.debit('source_structure_array_names_freeze', 1+len(result), root)
        return frozenset(result)
