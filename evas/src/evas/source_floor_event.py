"""Original source-only event Floor admission under one compile proof owner.

This route retains real Floor and original Divide. It does not infer a source
range or permit continuous Floor/transition targets.
"""
import math
from .errors import CompileError
from .ir import Affine, Binary, EventMath, Origin, RealBinary, RealBoundary
from .lowering import lower
from .syntax import Assignment, Conditional, Loop
from .integer_invariants import ProofBudgetExceeded


def source_floor(compiler, expr, lower_operand, resolve):
    work = compiler.compilation.integer_proof_owner
    try:
        work.activate()
    except ProofBudgetExceeded as error:
        raise CompileError(str(error), code='resource_budget', token=expr.token,
                           instance=compiler.instance.name) from error

    def charge():
        try:
            work.charge()
        except ProofBudgetExceeded as error:
            raise CompileError(str(error), code='resource_budget', token=expr.token,
                               instance=compiler.instance.name) from error

    def fail(message):
        raise CompileError(message, code='unsupported_floor', token=expr.token,
                           instance=compiler.instance.name)

    def constant_syntax(item):
        charge()
        return (item.op == 'parameter' and item.value in compiler.model.parameters
                or item.op == 'number'
                or item.op in ('+', '-', '*', '/', 'unary+', 'unary-')
                and all(constant_syntax(child) for child in item.args))

    if not hasattr(compiler, '_source_floor_constants'):
        writers = {}
        def scan(body):
            for item in body:
                charge()
                if isinstance(item, Assignment):
                    if item.name in compiler.model.variables:
                        writers.setdefault(item.name, []).append(item.rhs)
                elif isinstance(item, Conditional):
                    scan(item.then_body)
                    scan(item.else_body)
                elif isinstance(item, Loop):
                    # A loop-controlled binding is never an immutable scalar.
                    writers.setdefault(item.name, []).append(None)
                    scan(item.body)
        scan(compiler.model.initial)
        for event in compiler.model.events:
            charge()
            scan(event.body)
        bindings = {}
        for name, rhs_list in writers.items():
            charge()
            if compiler.model.variables[name] != 'real':
                continue
            values = []
            for rhs in rhs_list:
                if rhs is None or not constant_syntax(rhs):
                    break
                try:
                    if compiler.procedure_builder is None:
                        value = lower(rhs, compiler.parameter, {}, compiler.model.source)
                    else:
                        # A storage-constant certificate uses the same per-op
                        # binary64 arithmetic as its actual real assignments.
                        lookup = compiler.typed_resolve(compiler.parameter, program_real=True)
                        tree = lower(rhs, lookup, {}, compiler.model.source, preserve_structure=True)
                        fact = compiler.program_real_closed(tree)
                        value = compiler.make_ir(Affine, fact.value, ()) if fact.closed and fact.finite else None
                except CompileError as error:
                    if error.diagnostic['code'] == 'resource_budget':
                        raise
                    break
                if not isinstance(value, Affine) or value.terms or not math.isfinite(value.constant):
                    break
                values.append(value)
            if values and len(values) == len(rhs_list) and all(
                    (v == values[0] if compiler.procedure_builder is None else
                     v.constant.hex() == values[0].constant.hex()) for v in values):
                # The declaration/initial value must already agree. This is an
                # all-writer constant, never a guess from just one cold seed.
                initial = compiler.initials.get(name)
                if compiler.procedure_builder is not None and not isinstance(initial, (int, float)):
                    fact = compiler.program_real_closed(initial)
                    initial = fact.value if fact.closed and fact.finite else None
                if (type(initial) is float and initial.hex() == values[0].constant.hex()
                        or compiler.procedure_builder is None and initial == values[0].constant):
                    bindings[name] = values[0]
        compiler._source_floor_constants = bindings
    bindings = compiler._source_floor_constants

    def audit(item):
        charge()
        if item.op == 'voltage':
            return all(compiler.node_ids.get(str(node.value)) in compiler.allowed_condition_nodes
                       and str(node.value) != '$abstime' for node in item.args)
        if item.op == 'parameter':
            return item.value in compiler.model.parameters or item.value in bindings
        return (item.op in ('number', '+', '-', '*', '/', 'unary+', 'unary-')
                and all(audit(child) for child in item.args))
    if not audit(expr.args[0]):
        fail('source floor requires original driven/ground inputs and instance constants')
    argument = lower_operand(bindings)

    def degree(value):
        charge()
        if isinstance(value, Affine):
            for term in value.terms:
                charge()
                if term.node not in compiler.allowed_condition_nodes or term.node == compiler.node_ids.get('$abstime'):
                    fail('source floor contains a nonphysical input')
            if not math.isfinite(value.constant):
                fail('source floor contains a nonfinite constant')
            return int(bool(value.terms)), value.constant if not value.terms else None
        if isinstance(value, RealBoundary):
            # Admission observes source shape only. The executable sample/store
            # boundary stays in the returned Floor operand with its Origin.
            return degree(value.value)
        operation = value.operation if isinstance(value, RealBinary) else getattr(value, 'op', None)
        if (isinstance(value, RealBinary) and operation in ('add', 'subtract', 'multiply', 'divide')
                or isinstance(value, Binary) and operation in ('add', 'multiply', 'divide')):
            a, av = degree(value.left)
            b, bv = degree(value.right)
            if operation == 'divide':
                if b or bv is None or bv == 0:
                    fail('source floor requires a finite nonzero constant denominator')
                d = a
                result = av / bv if av is not None else None
            elif operation == 'multiply':
                d = a+b
                result = av*bv if av is not None and bv is not None else None
            else:
                d = max(a, b)
                result = ((av-bv if operation == 'subtract' else av+bv)
                          if av is not None and bv is not None else None)
            if d > 1 or result is not None and not math.isfinite(result):
                fail('source floor requires finite affine original arithmetic')
            return d, result
        fail('source floor has an unsupported original child')
    degree(argument)
    return EventMath('floor', (argument,), Origin(expr.token.source or compiler.model.source,
        expr.token.line, expr.token.column, compiler.instance.name, expr.expansion))
