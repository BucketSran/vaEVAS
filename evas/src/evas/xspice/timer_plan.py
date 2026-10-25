"""Admission of bounded independent fixed-clock batches, including t=0."""

from fractions import Fraction
from math import gcd, lcm


def may_overlap(a, b):
    """Exact binary64 calendar lattice; nonnegative cycle indices are unbounded."""
    pa, pb = Fraction(a["period"]), Fraction(b["period"])
    denominator = lcm(pa.denominator, pb.denominator)
    step = Fraction(gcd(int(pa * denominator), int(pb * denominator)), denominator)
    phase = (Fraction(a["start"]) - Fraction(b["start"])) % step
    return min(phase, step - phase) <= max(Fraction(a["time_tolerance"]), Fraction(b["time_tolerance"]))


def plan(events, nodes, unsupported):
    footprints = []
    for event in events:
        writes, reads = set(), set()

        def expression(expr):
            if isinstance(expr, list):
                for item in expr:
                    expression(item)
            elif isinstance(expr, dict):
                if expr.get("op") == "state":
                    reads.add(expr["state"])
                if expr.get("op") == "operator" or (expr.get("op") == "affine" and any(
                    nodes[t["node"]] != "0" for t in expr["terms"]
                )):
                    raise unsupported("independent clock batches require state/constant expressions without input, time or history reads")
                for value in expr.values():
                    if isinstance(value, (dict, list)):
                        expression(value)

        def statements(body):
            for stmt in body:
                if stmt["kind"] == "assign":
                    writes.add(stmt["state"])
                    expression(stmt["rhs"])
                elif stmt["kind"] == "if":
                    expression(stmt["left"]); expression(stmt["right"])
                    statements(stmt["then_body"]); statements(stmt["else_body"])
                else:
                    raise unsupported("clock batch body requires assignments and finite conditions")

        statements(event["body"])
        footprints.append({"writes": sorted(writes), "reads": sorted(reads)})
    for i, a in enumerate(footprints):
        for j, b in enumerate(footprints[:i]):
            conflict = (set(a["writes"]) & (set(b["writes"]) | set(b["reads"]))
                        or set(b["writes"]) & set(a["reads"]))
            if conflict and may_overlap(events[i]["trigger"], events[j]["trigger"]):
                raise unsupported(f"timer batch conflict or cross-block dependency between events {j} and {i}")
    return footprints
