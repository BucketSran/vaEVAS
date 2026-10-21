"""Bound recursive compiler work and the size of the expanded wire tree.

IR is a tree on the wire even when Python objects share subexpressions.
Measure that expansion with memoized, iterative traversal before allocating it.
These are implementation budgets, not Verilog-A language restrictions.
"""
from dataclasses import fields, is_dataclass

from .errors import CompileError

MAX_SOURCE_NESTING = 64
# Retain the existing 64-node star/dense circuits, including their enclosing
# arithmetic. Lowered IR gets its own container-depth check before transport.
MAX_EXPRESSION_DEPTH = 80
MAX_PARAMETER_DEPTH = 64
# Leave room for the enclosing request under serde_json's depth limit of 128.
MAX_IR_DEPTH = 96
MAX_IR_ITEMS = 100_000


def check_expression(expression, source):
    pending = [(expression, 1)]
    while pending:
        expr, depth = pending.pop()
        if depth > MAX_EXPRESSION_DEPTH:
            token = expr.token
            raise CompileError(f"{token.source or source}:{token.line}:{token.column}: expression depth limit ({MAX_EXPRESSION_DEPTH}) exceeded",
                               code="resource_budget", token=token)
        pending.extend((arg, depth + 1) for arg in expr.args)


def _children(value):
    if is_dataclass(value):
        return [getattr(value, field.name) for field in fields(value)]
    if isinstance(value, (tuple, list)):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return None


def check_ir(value, origin=None, *, work=None, cache=None):
    """Count expanded values/containers without expanding shared objects.

    Depth is JSON container depth, counting dataclasses as objects. A cached
    child's cost is added at *each* reference; memoization is not deduplication
    of the transmitted tree. Cycles are invalid even for manually built IR.
    """
    if cache is not None and work is not None:
        return _check_ir_cached(value, origin, work=work, cache=cache)
    if origin is None:
        contributions = getattr(value, 'contributions', ())
        origin = contributions[0].origin if contributions else getattr(value, 'origin', None)
    location = f"{origin.source}:{origin.line}:{origin.column}" if origin else '<IR>:1:1'

    def fail(message, code="compile_error"):
        raise CompileError(f"{location}: {message}", code=code, token=origin)

    memo, active = {}, set()
    pending = [(value, False)]
    while pending:
        if work is not None:
            work("ir_walk", 1)
        item, exiting = pending.pop()
        identity = id(item)
        if identity in memo:
            continue
        children = _children(item)
        if work is not None and children is not None:
            work("ir_fields", len(children))
        if children is None:
            memo[identity] = (0, 1)
            continue
        if not exiting:
            if identity in active:
                fail('cyclic IR exceeds the tree serialization limit', code='compile_error')
            active.add(identity)
            pending.append((item, True))
            pending.extend((child, False) for child in reversed(children))
            continue
        depth = 1 + max((memo[id(child)][0] for child in children), default=0)
        size = 1 + sum(memo[id(child)][1] for child in children)
        if depth > MAX_IR_DEPTH:
            fail(f'generated IR depth limit ({MAX_IR_DEPTH}) exceeded', code='resource_budget')
        if size > MAX_IR_ITEMS:
            fail(f'expanded IR size limit ({MAX_IR_ITEMS} values/containers) exceeded', code='resource_budget')
        memo[identity] = (depth, size)
        active.remove(identity)

    return memo[id(value)]


def _check_ir_cached(value,origin=None,*,work,cache):
    shared=cache
    if origin is None:
        contributions=getattr(value,'contributions',())
        origin=contributions[0].origin if contributions else getattr(value,'origin',None)
    location=f"{origin.source}:{origin.line}:{origin.column}" if origin else '<IR>:1:1'
    memo={};active=set();pending=[(value,None)]
    def fail(msg,code='resource_budget'): raise CompileError(f'{location}: {msg}',code=code,token=origin)
    while pending:
        work('ir_walk',1)
        item,children=pending.pop(); ident=id(item)
        if children is None:
            if ident in memo: continue
            if not is_dataclass(item) and not isinstance(item,(tuple,list,dict)):
                memo[ident]=(0,1,True);continue
            work('ir_cache_lookup',1)
            cached=shared.get(ident)
            if cached is not None:
                assert cached[0] is item
                memo[ident]=cached[1];continue
            if is_dataclass(item):
                # The schema dictionary already exists on the dataclass. Its
                # length bounds fields(), including any excluded pseudo-fields.
                # Pay before fields() scans or allocates its metadata tuple.
                schema=item.__dataclass_fields__
                work('ir_fields',len(schema))
                metadata=fields(item)
                children=tuple(getattr(item,f.name) for f in metadata)
            else:
                work('ir_fields',len(item))
                children=tuple(item.values()) if isinstance(item,dict) else item
            if ident in active: fail('cyclic IR exceeds the tree serialization limit','compile_error')
            active.add(ident);pending.append((item,children));pending.extend((c,None) for c in reversed(children));continue
        work('ir_cache_guard',1)
        immutable=(isinstance(item,tuple) or is_dataclass(item) and item.__dataclass_params__.frozen)
        # Combine the new transitive guard with the existing size/depth scan.
        # No second walk or child copy is created.
        depth,size=1,1
        for child in children:
            child_depth,child_size,child_immutable=memo[id(child)]
            depth=max(depth,1+child_depth);size+=child_size
            immutable &= child_immutable
        if depth>MAX_IR_DEPTH: fail('generated IR depth limit (96) exceeded')
        if size>MAX_IR_ITEMS: fail('expanded IR size limit (100000 values/containers) exceeded')
        memo[ident]=(depth,size,immutable);active.remove(ident)
        if immutable:
            work('ir_cache_insert',2)
            work('ir_cache_keepalive',1)
            shared[ident]=(item,memo[ident])
    work('ir_cache_result',2)
    return memo[id(value)][:2]
