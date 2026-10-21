"""Candidate marker for a new ordinary representation, never a topology proof.

Only called after an old owning representation check fails. The kernel audits
actual driven nodes, original ownership and disjoint output components again.
The full expression is retained, including masked arms and zero references.
"""
import math
from .ir import Affine, Binary, Select, Transition


def source_forcing_tree(value, allowed_nodes, compiler):
    from .syntax import CompileError
    # Immutable DAG nodes are inspected once, but every queued edge is charged.
    # This owner is the existing per-compilation source proof budget.
    def charge(amount):
        compiler.compilation.initial_math_work -= amount
        if compiler.compilation.initial_math_work < 0:
            raise CompileError('forcing expression proof budget exceeded', code='resource_budget')

    memo, active, pending = {}, set(), [(value, False, 1)]
    while pending:
        item, exiting, depth = pending.pop()
        charge(1)
        if depth > 96:
            raise CompileError('forcing expression proof depth exceeded', code='resource_budget')
        if id(item) in memo:
            continue
        if isinstance(item, Affine):
            charge(len(item.terms))
            memo[id(item)] = (bool(item.terms) if math.isfinite(item.constant) and all(
                math.isfinite(t.coefficient) and t.node in allowed_nodes
                for t in item.terms) else None)
            continue
        if isinstance(item, Binary) and item.op in ('add', 'multiply'):
            children = (item.left, item.right)
        elif isinstance(item, Select):
            children = (item.left,item.right,item.then_value,item.else_value)
        else:
            memo[id(item)] = None
            continue
        if not exiting:
            if id(item) in active:
                raise CompileError('cyclic forcing expression', code='compile_error')
            active.add(id(item))
            charge(1+len(children))
            pending.append((item, True, depth))
            pending.extend((child,False,depth+1) for child in reversed(children))
        else:
            results = [memo[id(child)] for child in children]
            if any(x is None for x in results):
                result = None
            elif isinstance(item, Select):
                # Guard dependence does not turn constant arms into a varying
                # coefficient; every selected leaf remains source affine.
                result = results[2] or results[3]
            elif item.op == 'multiply' and all(results):
                result = None
            else:
                result = any(results)
            memo[id(item)] = result
            active.remove(id(item))
    return memo[id(value)] is not None


def audit_original_reads(compilation, model, node_ids, forbidden):
    """Original pre-scalarization AST; discarded aliases/zero loops count too.

    Only contribution target probes are writes. Every other voltage reference,
    including unused assignments and all event/function arms, is a read. The
    existing per-compilation proof ledger owns scans and queued references.
    """
    from dataclasses import fields, is_dataclass
    from .syntax import Expr, ContributionStatement, Conditional, Trigger, CompileError
    seen, pending, numeric_reads = set(), [(model, True)], set()

    def enqueue(value, numeric=True):
        compilation.initial_math_work -= 1
        if compilation.initial_math_work < 0:
            raise CompileError('original forcing dependency proof budget exceeded', code='resource_budget')
        pending.append((value, numeric))

    while pending:
        item, numeric = pending.pop()
        if isinstance(item, (str, int, float, bool, type(None))):
            continue
        if (id(item), numeric) in seen:
            continue
        seen.add((id(item), numeric))
        if isinstance(item, Expr) and item.op == 'voltage':
            # Indexed probes require a separate original expansion mapping.
            if any(arg.op != 'node' for arg in item.args):
                raise CompileError('forcing original indexed read needs a provider mapping',
                                   code='unsupported_forcing_scope', token=item.token)
            if any(node_ids.get(str(arg.value)) in forbidden for arg in item.args):
                raise CompileError('forcing output is read by the original component tree',
                                   code='unsupported_forcing_scope', token=item.token)
            if numeric:
                numeric_reads.update(node_ids[str(arg.value)] for arg in item.args
                                     if str(arg.value) in node_ids and node_ids[str(arg.value)] != 0)
        if isinstance(item, Expr):
            for k, arg in enumerate(item.args):
                predicate = item.op in ('<','<=','>','>=','==','!=','&&','||','unary!') or (item.op == 'ternary' and k == 0)
                enqueue(arg, numeric and not predicate)
        elif isinstance(item, Trigger):
            for k,arg in enumerate(item.arguments):
                enqueue(arg, not (item.kind == 'cross' and k == 0))
        elif isinstance(item, dict):
            for value in item.values():
                enqueue(value)
        elif isinstance(item, (list, tuple, set, frozenset)):
            for value in item:
                enqueue(value)
        elif is_dataclass(item):
            for f in fields(item):
                if isinstance(item, ContributionStatement) and f.name == 'branch':
                    continue
                # Token/expansion metadata carries no voltage read edges.
                if f.name not in ('token', 'declaration_token', 'expansion'):
                    enqueue(getattr(item, f.name), not (isinstance(item, Conditional) and f.name in ('left','right')))
    return numeric_reads


def residual_checks(compiler, roots, checks):
    """Retain new checked work that output trees do not already certify.

    Proof traversal deduplicates immutable nodes; transport remains a tree and
    check_ir retains its original expanded-wire budget. Larger checked roots
    cover earlier subexpressions, avoiding a second copy of the entire output.
    """
    from .syntax import CompileError
    covered = set()

    def include(root):
        pending = [root]
        while pending:
            compiler.compilation.initial_math_work -= 8
            if compiler.compilation.initial_math_work < 0:
                raise CompileError('forcing checked tree budget exceeded', code='resource_budget')
            item = pending.pop()
            if id(item) in covered:
                continue
            covered.add(id(item))
            if isinstance(item, Binary):
                pending.extend((item.left,item.right))
            elif isinstance(item, Select):
                pending.extend((item.left,item.right,item.then_value,item.else_value))

    for root in roots:
        include(root)
    result = []
    for value in reversed(tuple(checks.values())):
        compiler.compilation.initial_math_work -= 1
        if compiler.compilation.initial_math_work < 0:
            raise CompileError('forcing checked tree budget exceeded', code='resource_budget')
        if id(value) not in covered:
            result.append(value)
            include(value)
    return tuple(result)


def split_source_quadratic(value, allowed_nodes, compiler):
    """One source-only quadratic Add term beside an unchanged legacy term.

    Candidate typing is charged to the existing native request audit. The full
    original role/health audit runs only after a marker is actually emitted.
    Branch orientation is handled by emit_contributions, without distributing
    general coefficients or crossing decisions.
    """
    if not isinstance(value, Binary) or value.op not in ('add','multiply'):
        return None
    operators = compiler.compilation.operators
    compiler.compilation.native_audit.debit('forcing_candidate_history_scope', 1 + len(operators))
    # This marker serves the held Transition consumer. Pure polynomial and
    # continuous/implicit relations retain their existing kernel route. This
    # table is complete before emission; final whole-Program audits still apply.
    if not operators or any(not isinstance(op, Transition) for op in operators):
        return None
    def degree(root):
        memo, pending = {}, [(root, False)]
        while pending:
            item, exiting = pending.pop()
            compiler.compilation.native_audit.debit('forcing_candidate_visit')
            if id(item) in memo:
                continue
            if isinstance(item, Affine):
                compiler.compilation.native_audit.debit('forcing_candidate_term',len(item.terms))
                memo[id(item)] = (int(bool(item.terms)) if math.isfinite(item.constant) and all(
                    math.isfinite(t.coefficient) and t.node in allowed_nodes for t in item.terms) else None)
            elif isinstance(item, Binary) and item.op in ('add','multiply'):
                if not exiting:
                    pending.append((item,True))
                    pending.extend(((item.right,False),(item.left,False)))
                else:
                    a,b=memo[id(item.left)],memo[id(item.right)]
                    degree=None if a is None or b is None else (a+b if item.op=='multiply' else max(a,b))
                    memo[id(item)]=degree if degree is not None and degree<=2 else None
            else:
                memo[id(item)]=None
        return memo[id(root)]
    if degree(value)==2 and compiler.compilation.operators:
        return value, compiler.make_ir(Affine,0.,())
    if value.op!='add':
        return None
    left,right=degree(value.left),degree(value.right)
    if left==2 and right is None:
        return value.left,value.right
    if right==2 and left is None:
        return value.right,value.left
    return None
