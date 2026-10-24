"""Independent Fraction oracle. GUARDS: LANG, EVENT-ORDER, COMPOSE.

The knots and query windows in this file are the working source. The JSON
snapshot is derived. Default invocation compares that snapshot in memory and
does not write. Pass --write to replace it.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse, hashlib, json, math, struct

ROOT = Path(__file__).resolve().parents[3]
ORACLE_SEMANTICS = "fraction_value_slope_enclosure_binary64_bits"


def bits(x):
    return struct.unpack(">Q", struct.pack(">d", x))[0]


def box(x):
    try:
        y = float(x)
    except OverflowError:
        return None
    if not math.isfinite(y):
        return None
    return [math.nextafter(y, -math.inf) if F(y) > x else y,
            math.nextafter(y, math.inf) if F(y) < x else y]


def value(knots, t):
    for (a, x), (b, y) in zip(knots, knots[1:]):
        if a <= t <= b:
            return x + (y - x) * (t - a) / (b - a)
    raise ValueError(t)


def oracle(knots, lo, hi):
    v = [value(knots, F(lo)), value(knots, F(hi))]
    d = []
    pairs = []
    for i, ((a, x), (b, y)) in enumerate(zip(knots, knots[1:])):
        if a < F(hi) and b > F(lo) or lo == hi and a <= F(lo) <= b:
            d.append((y - x) / (b - a))
            pairs.append(i)
        if F(lo) < b < F(hi):
            v.append(y)
    boxes = [box(x) for x in v]
    slopes = [box(x) for x in d]
    if any(x is None for x in boxes + slopes):
        return None, pairs
    return [[bits(min(x[0] for x in boxes)), bits(max(x[1] for x in boxes))],
            [bits(min(x[0] for x in slopes)), bits(max(x[1] for x in slopes))] if slopes else [0, 0]], pairs


def fixture_path():
    return ROOT / "evas/rust_core/tests/fixtures/shaped-range-oracle.json"


def build_cases():
    cases = []

    def add(name, raw, queries, error=2.):
        knots = [(F(t), F(v)) for t, v in raw]
        results = []
        for lo, hi in queries:
            expected, pairs = oracle(knots, lo, hi)
            results.append(dict(lo=lo, hi=hi, expected=expected, pairs=pairs))
        cases.append(dict(
            name=name,
            knots=[dict(time_numerator=str(t.numerator), time_denominator=str(t.denominator), value_V=float(v)) for t, v in knots],
            stop=float(knots[-1][0]),
            error=error,
            queries=results,
        ))

    knots = [(F(0), -1.), (F(1, 3), .5), (F(1, 2), -0.), (F(3, 5), 1.), (F(2, 3), -.5), (F(1), 0.)]
    q = [(0., 1.), (.25, .75), (.5, .5), (0., 0.), (1., 1.),
         (math.nextafter(1 / 3, -math.inf), math.nextafter(1 / 3, math.inf)),
         (math.nextafter(.5, -math.inf), .5), (.5, math.nextafter(.5, math.inf)), (.125, .25)]
    add("nonbinary_multicorner_twosided", knots, q)
    add("signedzero_and_cancel", [(0., -0.), (.25, +0.), (.5, -1.), (.75, 1.), (1., -0.)],
        [(0., .25), (.25, .25), (.5, .75), (0., 1.)])
    tiny = math.ulp(0.)
    add("subnormal_time_and_value", [(F(0), 0.), (F(tiny), tiny), (F(tiny) * 2, -tiny), (F(tiny) * 4, 0.)],
        [(0., tiny), (tiny, tiny), (0., 4 * tiny)])
    add("finite_values_overflow_slope",
        [(0., -float.fromhex("0x1.fffffffffffffp+1023")), (F(1, 2), float.fromhex("0x1.fffffffffffffp+1023")), (1., 0.)],
        [(0., .5)], float.fromhex("0x1.fffffffffffffp+1023"))
    return cases


def render(cases):
    return json.dumps(cases, indent=2) + "\n"


def specification(cases):
    return [{
        "name": case["name"],
        "knots": case["knots"],
        "stop": case["stop"],
        "error": case["error"],
        "queries": [{"lo": query["lo"], "hi": query["hi"]} for query in case["queries"]],
    } for case in cases]


def receipt(cases):
    source = json.dumps(specification(cases), sort_keys=True, separators=(",", ":"))
    return {
        "oracle_semantics": ORACLE_SEMANTICS,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "case_count": len(cases),
        "query_count": sum(len(case["queries"]) for case in cases),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check or write the shaped-range Fraction oracle snapshot.")
    parser.add_argument("--check", action="store_true", help="compare the snapshot in memory; this is the default")
    parser.add_argument("--write", action="store_true", help="replace the snapshot")
    parser.add_argument("--output", type=Path, help="snapshot path; default is the committed fixture")
    args = parser.parse_args(argv)
    if args.check and args.write:
        raise SystemExit("pass only one of --check and --write")
    path = args.output if args.output is not None else fixture_path()
    cases = build_cases()
    rendered = render(cases)
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered)
    elif not path.is_file() or path.read_text() != rendered:
        raise SystemExit(f"shaped-range oracle snapshot differs from generator: {path}")
    print(json.dumps(receipt(cases)))


if __name__ == "__main__":
    main()
