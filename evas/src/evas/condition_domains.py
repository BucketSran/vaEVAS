"""Apply the original ordered source comparisons to a compact boolean guard.

Parser used to put this comparison skeleton around complete statement bodies.
Keep the same source decision rules here, with domain continuations as leaves;
no statement or alternate IR is created. Existing consumers own atomic narrowing,
hulls and work limits. An unsupported expression retains its old leaf result.
"""
from .syntax import BOOLEAN_OPS


def compact_condition(relation, left, right):
    return (relation == '>' and right.op == 'number' and right.value == 0
            and left.op in BOOLEAN_OPS)


def compact_domains(relation, left, right, env, *, refine, hull, work, plan_cache=None):
    if not compact_condition(relation, left, right):
        return None
    if plan_cache is not None:
        cache = plan_cache(work)
        plan = cache.get(relation, left, right, work)
        if plan is not None:
            return _apply_plan(plan, env, refine, hull, work)
    # Prepay helper callables and captured references before constructing any.
    # All debits use the consumer's existing proof owner and ceiling.
    work(64)

    def merge(a, b):
        if a is None:
            return b
        if b is None:
            return a
        work(1 + 3 * len(a))
        return {name: hull(a[name], b[name]) for name in a}

    def terminal(truth):
        work(3)  # callable and captured truth/work references
        def apply(current):
            work(3)
            return (current, None) if truth else (None, current)
        return apply

    def comparison(op, a, b, yes, no):
        work(9)  # callable plus its eight captured references
        def apply(current):
            work(3)
            if current is None:
                return None, None
            true_env, false_env = refine(op, a, b, current)
            true_result, false_result = yes(true_env), no(false_env)
            work(3)
            return (merge(true_result[0], false_result[0]),
                    merge(true_result[1], false_result[1]))
        return apply

    def condition(expr, yes, no):
        # This is the former Parser.condition short-circuit comparison
        # skeleton, moved rather than duplicated. Leaves are domains, not
        # copies of source bodies. In particular != and negative truth retain
        # their exact original ordered comparisons and strict boundaries.
        work(1)
        if expr.op == '&&':
            return condition(expr.args[0], condition(expr.args[1], yes, no), no)
        if expr.op == '||':
            return condition(expr.args[0], yes, condition(expr.args[1], yes, no))
        if expr.op == 'unary!':
            return condition(expr.args[0], no, yes)
        if expr.op in ('==', '!='):
            if expr.op == '!=':
                yes, no = no, yes
            a, b = expr.args
            return comparison('<=', a, b, comparison('>=', a, b, yes, no), no)
        if expr.op in ('<', '<=', '>', '>='):
            return comparison(expr.op, *expr.args, yes, no)
        # Existing truth semantics accept either sign. Reuse the caller's
        # source zero expression; no numerical operation is evaluated here.
        return comparison('>', expr, right, yes,
                          comparison('<', expr, right, yes, no))

    result = condition(left, terminal(True), terminal(False))(env)
    # Integer/real interval consumers return both abstract arms. A logical
    # reachability consumer may explicitly return None for an impossible arm;
    # never turn that absence back into an entry domain.
    return result


class ConditionPlans:
    """Same-proof immutable syntax only; every application gets fresh callbacks."""
    def __init__(self):
        self.immutable = {}
        self.plans = {}

    def _immutable(self, value, work):
        from .syntax import Expr, Token
        work(2)
        if type(value) in (str, int, float, bool, type(None)):
            return True
        work(2)
        old = self.immutable.get(id(value))
        if old is value:
            return True
        if type(value) is tuple:
            work(1 + len(value))
            valid = all(self._immutable(child, work) for child in value)
        elif type(value) in (Expr, Token):
            fields = type(value).__dataclass_fields__
            work(1 + 2 * len(fields))
            valid = all(self._immutable(getattr(value, name), work) for name in fields)
        else:
            return False
        if valid:
            work(2)
            self.immutable[id(value)] = value
        return valid

    def get(self, relation, left, right, work):
        work(5)  # key allocation, its fields and dictionary lookup
        key = (relation, id(left), id(right))
        old = self.plans.get(key)
        if old is not None and old[0] is left and old[1] is right:
            return old[2]
        if not self._immutable(left, work) or not self._immutable(right, work):
            return None
        # Strong source references and complete metadata are retained. No
        # bound parameter or abstract environment is part of a stored plan.
        yes = _plan_terminal(True, work)
        no = _plan_terminal(False, work)
        plan = _build_plan(left, right, yes, no, work)
        work(5)
        self.plans[key] = (left, right, plan)
        return plan


def _plan_terminal(truth, work):
    work(3)
    return ('terminal', truth)


def _plan_comparison(op, left, right, yes, no, work):
    work(7)
    return ('compare', op, left, right, yes, no)


def _build_plan(expr, zero, yes, no, work):
    work(1)
    if expr.op == '&&':
        return _build_plan(expr.args[0], zero, _build_plan(expr.args[1], zero, yes, no, work), no, work)
    if expr.op == '||':
        return _build_plan(expr.args[0], zero, yes, _build_plan(expr.args[1], zero, yes, no, work), work)
    if expr.op == 'unary!':
        return _build_plan(expr.args[0], zero, no, yes, work)
    if expr.op in ('==', '!='):
        if expr.op == '!=':
            yes, no = no, yes
        a, b = expr.args
        inner = _plan_comparison('>=', a, b, yes, no, work)
        return _plan_comparison('<=', a, b, inner, no, work)
    if expr.op in ('<', '<=', '>', '>='):
        return _plan_comparison(expr.op, expr.args[0], expr.args[1], yes, no, work)
    inner = _plan_comparison('<', expr, zero, yes, no, work)
    return _plan_comparison('>', expr, zero, yes, inner, work)


def _apply_plan(plan, env, refine, hull, work):
    work(3)
    if plan[0] == 'terminal':
        return (env, None) if plan[1] else (None, env)
    if env is None:
        return None, None
    _, op, left, right, yes, no = plan
    true_env, false_env = refine(op, left, right, env)
    a = _apply_plan(yes, true_env, refine, hull, work)
    b = _apply_plan(no, false_env, refine, hull, work)
    return (_merge_plan(a[0], b[0], hull, work), _merge_plan(a[1], b[1], hull, work))


def _merge_plan(a, b, hull, work):
    work(1)
    if a is None:
        return b
    if b is None:
        return a
    work(1 + 3 * len(a))
    return {name: hull(a[name], b[name]) for name in a}
