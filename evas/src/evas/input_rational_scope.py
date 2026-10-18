"""Structural candidate scope; Rust rechecks the complete actual driven program."""
import math
from .ir import Affine, Binary, Select


def input_rational_tree(value, allowed_nodes):
    """Return whether a pure input tree contains division, or None if unsupported.

    A False result is a supported tree without division, not a rejection.
    This never proves a sample's denominator or condition sign. Every arm and
    zero-coefficient dependency remains in the audit; existing IR limits count
    its full wire expansion before this memoized structural walk.
    """
    memo = {}
    def inspect(item):
        key = id(item)
        if key in memo:
            return memo[key]
        result = None
        if isinstance(item, Affine):
            if (math.isfinite(item.constant)
                    and all(term.node in allowed_nodes and math.isfinite(term.coefficient) for term in item.terms)):
                result = False
        elif isinstance(item, Binary) and item.op in ('add', 'multiply', 'divide'):
            left, right = inspect(item.left), inspect(item.right)
            if left is not None and right is not None:
                result = item.op == 'divide' or left or right
        elif isinstance(item, Select):
            children = [inspect(child) for child in
                        (item.left, item.right, item.then_value, item.else_value)]
            if all(child is not None for child in children):
                result = any(children)
        memo[key] = result
        return result
    return inspect(value)
