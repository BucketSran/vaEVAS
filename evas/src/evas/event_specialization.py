"""Audit the original event tree, then specialize parameter-only branches.

Unselected pure values need valid structure, not a runtime domain proof. Names,
types, index proofs, checked obligations and control boundaries are audited
before pruning. State values, input voltages and initial values never decide
which source statements to remove.
"""
from dataclasses import replace
import math

from .errors import CompileError
from .ir import Affine, Binary, Origin, Power, Select
from .limits import MAX_IR_ITEMS, check_ir
from .lowering import lower, lower_decision
from .syntax import Loop, Assignment, Conditional, Display, OPERATOR_NAMES, DECISION_NAMES
from .display import validate_format
from .integer_bits import OPS as BIT_OPS
from .compact_source_select import compact_source_assignment

PURE_MATH = frozenset(("sin", "cos", "exp", "ln", "sqrt"))
VALUE_OPS = frozenset(("number", "parameter", "voltage", "time", "index", "checked",
                       "+", "-", "*", "/", "%", "power", "floor", "unary+", "unary-")) | DECISION_NAMES | PURE_MATH | BIT_OPS
UNKNOWN = object()



def parameter_value(expr, parameters, memo, work=None):
    key = id(expr)
    if key in memo:
        return memo[key][1]
    if expr.op == "number":
        result = float(expr.value)
    elif expr.op == "parameter":
        result = parameters.get(str(expr.value), UNKNOWN)
    else:
        if expr.op == "function_assign" and work is not None:
            work.extra(expr, "function_assignment_parameter_metadata", 8)
        args = [parameter_value(arg, parameters, memo, work) for arg in expr.args]
        result = UNKNOWN
        if expr.op == "function_assign":
            # Only real copy-through preserves this parameter-only value. The
            # integer conversion remains an obligation of the typed lowerer.
            if expr.value == "real" and expr.result_type == "real" and len(args) == 1:
                result = args[0]
        elif expr.op == "checked":
            result = args[0]
        elif expr.op == "&&":
            if any(a is not UNKNOWN and not a for a in args):
                result = 0.0
            elif UNKNOWN not in args:
                result = float(bool(args[0]) and bool(args[1]))
        elif expr.op == "||":
            if any(a is not UNKNOWN and a for a in args):
                result = 1.0
            elif UNKNOWN not in args:
                result = 0.0
        elif UNKNOWN not in args:
            if expr.op in ("<", "<=", ">", ">=", "==", "!="):
                a, b = args
                result = float({"<": a < b, "<=": a <= b, ">": a > b,
                                ">=": a >= b, "==": a == b, "!=": a != b}[expr.op])
            elif expr.op == "unary!":
                result = float(not args[0])
            elif expr.op in ("unary+", "unary-"):
                result = args[0] if expr.op == "unary+" else -args[0]
            elif expr.op in ("+", "-", "*"):
                a, b = args
                result = {"+": lambda: a+b, "-": lambda: a-b, "*": lambda: a*b}[expr.op]()
                if not math.isfinite(result):
                    result = UNKNOWN
    memo[key] = (expr, result)
    return result


def audit_event_body(compiler, statements, charge_native):
    """Read-only original-tree admission using this instance's bindings/facts."""
    seen = {}
    compiler.native_integer_charge = charge_native

    def fail(message, item, code="compile_error"):
        raise CompileError(message, code=code, token=item.token,
                           instance=compiler.instance.name)

    def index_read(item):
        array = str(item.value)
        value = compiler._dynamic_index(item.args[0], item.token, "read", array)
        return compiler._array_read_tree(array, compiler.array_elements[array], value,
                                         item.token, register=False)

    def selection(item, relation, left, right, yes, no):
        # Sampled scalar guards need not be affine, but parameter pruning must
        # not erase the original input/inout scope of nested decisions.
        if not (compiler.expression_nodes(left) | compiler.expression_nodes(right)).issubset(compiler.allowed_condition_nodes):
            fail("decision predicates must depend only on input/inout ports", item)
        return compiler.event_select(item, relation, left, right, yes, no)

    def budget_select(item, relation, left, right, yes, no):
        # A resource-only shape, never an admission or dependency proof.
        # Unused nonlinear mathematical values retain choices without gaining
        # executable support or inheriting restrictions from surrogate values.
        origin = Origin(item.token.source or compiler.model.source,
                        item.token.line, item.token.column,
                        compiler.instance.name, item.expansion)
        return Select(relation, left, right, yes, no, origin)

    implicit_powers = {}

    def finite_power_tree(root):
        # Only an actual finite lowering contributes implicit Select choices.
        # Unsupported unused pure mathematics keeps its existing opaque shape;
        # probing must not turn resource accounting into a domain admission.
        if root.op != "power" or not compiler.integer_type(root.args[1]):
            return None
        if id(root) not in implicit_powers:
            try:
                value = compiler.lower_event(root, compiler.symbol, compiler.node_ids,
                    preserve_structure=True, node_declarations=True,
                    sampled_values=True, decisions=selection, indices=index_read)
            except CompileError as error:
                if error.diagnostic['code'] == 'resource_budget':
                    raise
                value = None
            implicit_powers[id(root)] = (root, value if isinstance(value, Select) else None)
        return implicit_powers[id(root)][1]

    def needs_choices(root):
        pending, visited = [root], set()
        while pending:
            item = pending.pop()
            if id(item) in visited:
                continue
            visited.add(id(item))
            if (item.op in DECISION_NAMES or item.op in BIT_OPS or item.op in ("index", "floor") or
                    item.op in ("/", "%") and compiler.integer_type(item) or
                    item.op == "power" and finite_power_tree(item) is not None):
                return True
            pending.extend(item.args)
        return False

    def audit_lower(root, *, integer_assignment_root=False, static_integer_audit=False):
        options = dict(preserve_structure=True, node_declarations=True,
                       integer_assignment_root=integer_assignment_root,
                       static_integer_audit=static_integer_audit)
        if needs_choices(root):
            options.update(decisions=selection, indices=index_read)
        else:
            # One fixed binding, no registration/index/decision callbacks.
            # The existing memo contract keeps shared function obligations
            # bounded without memoizing arbitrary semantic callbacks.
            options["memo"] = {}
        if compiler.numeric_observer_candidate():
            options.pop("memo", None)
            return compiler.lower_event_value(root, compiler.symbol, compiler.node_ids, **options)
        return compiler.lower_event(root, compiler.symbol, compiler.node_ids,
                                    sampled_values=True, **options)

    def resource_tree(root, memo=None):
        # Only split_selection/event_assignment consume this private tree.
        # Pure unused mathematics is opaque: its domain, numerical value and
        # physical dependencies cannot be inferred from this resource shape.
        if memo is None:
            memo = {}
        if id(root) in memo:
            return memo[id(root)][1]
        if root.op == "checked":
            value = resource_tree(root.args[0], memo)
        elif root.op == "function_assign":
            charge_native.extra(root, "function_assignment_resource_metadata", 4)
            # Keep the real assignment's complete choice shape. Integer
            # conversion belongs to the existing typed lowerer, never this
            # private resource-only surrogate. Original shape audits all args.
            value = (resource_tree(root.args[0], memo) if root.value == "real"
                     else audit_lower(root))
        elif root.op == "index":
            value = index_read(root)
        elif root.op in BIT_OPS or root.op == "floor" or root.op in ("/", "%") and compiler.integer_type(root):
            # The typed lowerer introduces quotient-bin decisions even when
            # there is no explicit source decision. Retain their real shape.
            value = audit_lower(root)
        elif root.op == "power" and finite_power_tree(root) is not None:
            value = finite_power_tree(root)
        elif root.op in ("number", "parameter", "voltage", "time"):
            value = audit_lower(root)
        else:
            args = tuple(resource_tree(arg, memo) for arg in root.args)
            if root.op in DECISION_NAMES:
                value = lower_decision(root.op, args,
                    lambda relation, left, right, yes, no:
                        budget_select(root, relation, left, right, yes, no))
            elif root.op in PURE_MATH:
                # Retain every operand choice with an opaque non-boolean leaf.
                # It cannot be folded into a fictitious mathematical value.
                value = Binary("add", args[0], Binary("add", Affine(2.0, ()), Affine(2.0, ())))
            elif root.op == "unary+":
                value = args[0]
            elif root.op == "unary-":
                value = (Affine(-args[0].constant, ())
                         if isinstance(args[0], Affine) and not args[0].terms
                         else Binary("multiply", Affine(-1.0, ()), args[0]))
            elif root.op == "power":
                base, exponent = args
                value = None
                if all(isinstance(arg, Affine) and not arg.terms for arg in args):
                    try:
                        number = base.constant ** exponent.constant
                    except (OverflowError, ZeroDivisionError, ValueError):
                        pass
                    else:
                        if isinstance(number, (int, float)) and math.isfinite(number):
                            value = Affine(float(number), ())
                if value is None:
                    if isinstance(exponent, Affine) and not exponent.terms and exponent.constant.is_integer() and exponent.constant >= 0:
                        value = (Affine(1.0, ()) if exponent.constant == 0 else base
                                 if exponent.constant == 1 else Power(base, int(exponent.constant)))
                    else:
                        # An unused power with no finite scalar value is opaque.
                        value = Binary("add", base, exponent)
            else:
                op = {"+": "add", "-": "add", "*": "multiply", "/": "divide"}.get(root.op)
                if op is None:
                    fail("unsupported event resource structure", root)
                right = Binary("multiply", Affine(-1.0, ()), args[1]) if root.op == "-" else args[1]
                value = Binary(op, args[0], right)
                if all(isinstance(arg, Affine) and not arg.terms for arg in args):
                    a, b = (arg.constant for arg in args)
                    try:
                        number = {"+": lambda: a+b, "-": lambda: a-b,
                                  "*": lambda: a*b, "/": lambda: a/b}[root.op]()
                    except (OverflowError, ZeroDivisionError):
                        pass
                    else:
                        if math.isfinite(number):
                            value = Affine(number, ())
        memo[id(root)] = (root, value)
        return value

    def shape(root, *, integer_assignment=False, parameter_dead=False):
        pending = [root]
        while pending:
            item = pending.pop()
            charge_native.extra(item, "source_pop")
            if id(item) in seen:
                continue
            seen[id(item)] = item
            charge_native(item, "event_audit")
            if item.op == "function_assign":
                charge_native.extra(item, "function_assignment_metadata", 4)
                if (item.value not in ("real", "integer") or len(item.args) != 1
                        or item.result_type != item.value):
                    fail("invalid function assignment structure", item)
                # Every child remains in the original-tree walk below. Copy-in,
                # local and return integer conversions use their original proof.
                if item.value == "integer":
                    audit_lower(item, static_integer_audit=parameter_dead)
            elif item.op not in VALUE_OPS:
                message = "event bodies do not support history/operator calls" if item.op in OPERATOR_NAMES else "unsupported event value structure"
                fail(message, item)
            if item.op == "number" and not math.isfinite(float(item.value)):
                fail("nonfinite event literal", item)
            if item.op == "parameter":
                try:
                    compiler.symbol(str(item.value))
                except CompileError as error:
                    if "location" in error.diagnostic:
                        raise
                    raise CompileError(str(error), code=error.diagnostic["code"],
                                       token=item.token, instance=compiler.instance.name) from error
            elif item.op == "voltage":
                lower(item, compiler.symbol, compiler.node_ids, compiler.model.source,
                      preserve_structure=True, node_declarations=True)
                continue
            elif item.op == "index":
                compiler._dynamic_index(item.args[0], item.token, "read", str(item.value))
            elif item.op in PURE_MATH and len(item.args) != 1:
                fail("pure mathematical functions require one operand", item)
            elif item.op == "checked":
                # The primary value may be unused mathematics. Every retained
                # function obligation keeps its original lowering boundary.
                for obligation in item.args[1:]:
                    audit_lower(obligation, static_integer_audit=parameter_dead)
            if item.op in BIT_OPS or item.op in ("+", "-", "*", "/", "%", "unary+", "unary-") and compiler.integer_type(item):
                # A real destination does not erase integer arithmetic in its
                # source. Only a complete integer assignment may defer its
                # final stored-value check to the kernel.
                audit_lower(item, integer_assignment_root=(integer_assignment and item is root),
                            static_integer_audit=parameter_dead)
            pending.extend(item.args)

    def control(expr, parameter_dead=False):
        shape(expr, parameter_dead=parameter_dead)
        audit_lower(expr, static_integer_audit=parameter_dead)
        # Ordinary condition dependency/degree checks keep their existing
        # kernel boundary, including conditions in parameter-unselected code.

    parameter_memo = {}

    def parameter_predicate(statement):
        a = parameter_value(statement.left, compiler.cache, parameter_memo, charge_native)
        b = parameter_value(statement.right, compiler.cache, parameter_memo, charge_native)
        if a is UNKNOWN or b is UNKNOWN:
            return None
        return {"<":a<b, "<=":a<=b, ">":a>b, ">=":a>=b}[statement.relation]

    def body(items, parameter_dead=False):
        for statement in items:
            charge_native(statement, "event_statement")
            if isinstance(statement, Loop):
                compiler.validate_runtime_loop(statement)
                for expr in (statement.start, statement.limit, statement.update):
                    shape(expr, integer_assignment=True, parameter_dead=parameter_dead)
                    audit_lower(expr, integer_assignment_root=True, static_integer_audit=parameter_dead)
                body(statement.body, parameter_dead)
            elif isinstance(statement, Conditional):
                control(statement.left, parameter_dead)
                control(statement.right, parameter_dead)
                selected = parameter_predicate(statement)
                body(statement.then_body, parameter_dead or selected is False)
                body(statement.else_body, parameter_dead or selected is True)
            elif isinstance(statement, Display):
                try:
                    validate_format(statement.format, len(statement.args))
                except ValueError as error:
                    fail(str(error), statement)
                for arg in statement.args:
                    shape(arg, parameter_dead=parameter_dead)
            elif isinstance(statement, Assignment):
                if statement.index is not None:
                    compiler._dynamic_index(statement.index, statement.token, "write", statement.name)
                    kind = compiler.model.variables[f"{statement.name}[{compiler.array_elements[statement.name][0]}]"]
                    compiler.array_audit_dispatch_leaves += len(compiler.array_elements[statement.name])
                    if compiler.array_audit_dispatch_leaves > 4096:
                        fail("dynamic array dispatch budget (4096 leaves) exceeded", statement, "resource_budget")
                else:
                    if statement.name not in compiler.state_ids:
                        fail("assignment target must be an instance state", statement)
                    kind = compiler.model.variables[statement.name]
                shape(statement.rhs, integer_assignment=(kind == "integer"), parameter_dead=parameter_dead)
                if needs_choices(statement.rhs):
                    budget_value = resource_tree(statement.rhs)
                    origin = Origin(statement.token.source or compiler.model.source,
                                    statement.token.line, statement.token.column,
                                    compiler.instance.name, statement.token.expansion)
                    # Reuse the actual bounded assignment expander. A separate
                    # source profiler can miss comparison operand choices.
                    compiler.event_assignment(compiler.state_ids.get(statement.name, 0),
                                              budget_value, origin,
                                              compact_source=compact_source_assignment(compiler, statement, budget_value, origin))
                if kind == "integer":
                    value = audit_lower(statement.rhs, integer_assignment_root=True,
                                        static_integer_audit=parameter_dead)
                    if not compiler.integral(value):
                        fail("integer assignment requires integral state arithmetic", statement)
            else:
                fail("unsupported statement in original event audit", statement)
    body(statements)
    return charge_native


def specialize_event_body(statements, parameters, *, work=None):
    """New execution view after audit; only bound module parameters are known."""
    memo = {}

    def known(expr):
        return parameter_value(expr, parameters, memo, work)

    def body(items):
        result = []
        for statement in items:
            if isinstance(statement, Loop):
                result.append(replace(statement, body=body(statement.body)))
            elif isinstance(statement, Conditional):
                left, right = known(statement.left), known(statement.right)
                if left is not UNKNOWN and right is not UNKNOWN:
                    take_yes = {"<": left < right, "<=": left <= right,
                                ">": left > right, ">=": left >= right}[statement.relation]
                    # Keep every original control predicate for kernel
                    # structural validation. Only unselected actions/records
                    # disappear; no unsupported guard is hidden by pruning.
                    result.append(replace(statement,
                        then_body=body(statement.then_body) if take_yes else controls(statement.then_body),
                        else_body=controls(statement.else_body) if take_yes else body(statement.else_body)))
                else:
                    result.append(replace(statement, then_body=body(statement.then_body),
                                          else_body=body(statement.else_body)))
            else:
                result.append(statement)
        return tuple(result)
    def controls(items):
        return tuple(replace(statement, then_body=controls(statement.then_body),
                             else_body=controls(statement.else_body))
                     for statement in items if isinstance(statement, Conditional))
    return body(statements)
