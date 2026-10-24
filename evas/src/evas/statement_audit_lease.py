"""One statement's completed, read-only integer source audit receipts.

This lease never enters actual lowering. Its scope is the source Assignment
handling in event_specialization, including the final integral check. Each
finite table row still lowers with its own binding and strict intermediate checks.
"""
import math
from .syntax import Expr, Token
from .integer_bits import OPS, small_domain

_MISSING = object()
_ALLOWED = OPS | frozenset(('number', 'parameter', '+', '-', '*', '/', '%', 'unary+', 'unary-'))
_LEAVES = frozenset(('number', 'parameter'))


class StatementAuditLease:
    @classmethod
    def create(cls, compiler, statement, work):
        root = statement.rhs
        # Avoid a second whole-tree eligibility walk for elementary assignments.
        # This is a representation choice, never a source admission decision.
        if root.op not in _ALLOWED or root.op in _LEAVES:
            return None
        compiler.compilation.native_audit.activate(root)
        work(root, 'statement_audit_candidate', 1 + len(root.args))
        if root.op not in OPS and not any(child.op in OPS for child in root.args):
            # Do not build a second whole-tree guard for unrelated arithmetic.
            # A deeper bit expression simply retains its original audit path.
            return None
        work(root, 'statement_audit_create', 5)
        pending, retained, names, has_bits = [root], {}, set(), False
        while pending:
            work(root, 'statement_audit_source_pop', 2)
            item = pending.pop()
            if id(item) in retained:
                continue
            work(item, 'statement_audit_source_fields', len(Expr.__dataclass_fields__) + len(Token.__dataclass_fields__))
            if (type(item) is not Expr or item.op not in _ALLOWED
                    or type(item.args) is not tuple or type(item.token) is not Token
                    or type(item.value) not in (str, int, float, type(None))
                    or type(item.result_type) not in (str, type(None))
                    or item.real_boundary_kind is not None or item.source_call is not None):
                return None
            token = item.token
            if (type(token.text) is not str or type(token.kind) is not str
                    or type(token.line) is not int or type(token.column) is not int
                    or type(token.source) is not str
                    or type(token.default_transition) not in (int, float, type(None))):
                return None
            for expansion in (item.expansion, token.expansion):
                if type(expansion) is not tuple:
                    return None
                work(item, 'statement_audit_source_expansion', 1 + len(expansion))
                for pair in expansion:
                    if (type(pair) is not tuple or len(pair) != 2
                            or type(pair[0]) is not str or type(pair[1]) is not int):
                        return None
            if item.op == 'parameter':
                work(item, 'statement_audit_name', 1)
                names.add(item.value)
            has_bits |= item.op in OPS
            work(item, 'statement_audit_source_edges', 2 + len(item.args))
            retained[id(item)] = item
            pending.extend(item.args)
        if not has_bits:
            return None
        work(root, 'statement_audit_retain', 16 + len(names))
        lease = cls()
        lease.compiler, lease.statement, lease.work = compiler, statement, work
        lease.model, lease.instance, lease.nodes = compiler.model, compiler.instance, compiler.node_ids
        lease.builder = getattr(compiler, "procedure_builder", None)
        lease.source, lease.names, lease.results = retained, tuple(names), {}
        lease.valid = True
        lease.context = lease._context()
        if lease.context is None or not names:
            return None
        work(root, "statement_audit_domain_guard", 2 + 2 * len(names))
        if not small_domain([row[3] for row in lease.context[-1]]):
            return None
        return lease

    def _context(self):
        c, root = self.compiler, self.statement.rhs
        self.work(root, 'statement_audit_context', 12 + 8 * len(self.names))
        if c.model is not self.model or c.instance is not self.instance or c.node_ids is not self.nodes:
            return None
        if getattr(c, 'ordinary_integer_bounds', None) is not None:
            return None
        builder = getattr(c, 'procedure_builder', None)
        if builder is not self.builder:
            return None
        generation = getattr(builder, 'scope_generation', 0)
        if type(generation) is not int:
            return None
        bindings = builder.bindings if builder is not None else ()
        ranges = getattr(c, 'integer_state_ranges', {})
        result = []
        for name in self.names:
            # No ordinary/alias binding may masquerade as a persistent integer.
            if (name in bindings or name in c.active_event_aliases
                    or name in c.local_variables or name not in c.state_ids
                    or c.model.variables.get(name) != 'integer'):
                return None
            index = c.state_ids[name]
            state = c.compilation.states[index]
            bounds = ranges.get(index, (-2147483648, 2147483647))
            if (state.kind != 'integer' or type(bounds) is not tuple or len(bounds) != 2
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in bounds)):
                return None
            result.append((name, index, state, bounds))
        resolve = c.symbol
        return (getattr(resolve, "__self__", None), getattr(resolve, "__func__", resolve),
                c.model.source, c.instance.name, generation, tuple(result))

    def get(self, root, flags):
        self.work(root, 'statement_audit_receipt_lookup', 3)
        if not self.valid or self.source.get(id(root)) is not root:
            return _MISSING
        if self._context() != self.context:
            self.valid = False
            return _MISSING
        return self.results.get((id(root), flags), _MISSING)

    def put(self, root, flags, value):
        if not self.valid or self.source.get(id(root)) is not root:
            return
        if self._context() != self.context:
            self.valid = False
            return
        self.work(root, 'statement_audit_receipt_record', 3)
        self.results[id(root), flags] = value
