"""Conservative local check selection; delivery obligations are never inferred passed."""

from __future__ import annotations

import argparse
import json
import re
import runpy
import sys
from pathlib import Path

PROTOCOL_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
_VALIDATION = ".agents/skills/evas-validate/SKILL.md#select-the-necessary-checks"
_ACCEPTANCE = "docs/contributing/validation.md"
_TEST = re.compile(r"evas/tests/(test_[A-Za-z0-9_]+\.py)\Z")
_DOC_SUFFIXES = (".md", ".rst")
_REPRESENTATION_PATHS = tuple('evas/src/evas/'+name for name in (
    'instance_compiler.py', 'lowering.py', 'compact_source_select.py',
    'integer_prefix.py', 'input_rational_scope.py'))
_BUDGET_PATHS = ('evas/src/evas/event_index_domains.py', 'evas/src/evas/integer_invariants.py')
_PROOF_PATHS = _BUDGET_PATHS + (
    'evas/src/evas/initial_constant_math.py', 'evas/src/evas/integer_bits.py',
    'evas/rust_core/src/source_math.rs', 'evas/rust_core/src/dc_projection.rs',
    'evas/rust_core/src/transition_source_plan.rs',
    'evas/rust_core/src/initial_state_invariance.rs',
    'evas/rust_core/src/transient_initialization.rs',
)
# Deliberately limited to inspected source boundaries. Unknown/shared changes use
# full Python coverage until their owning tests and consumers have been checked.
_RULES = (
    (
        _REPRESENTATION_PATHS,
        ('affine', 'analog_conditions', 'stateless_expressions', 'event_conditions',
         'display', 'initial_display_transition', 'initial_observer_horizon'),
        ('*',),
        'representation/admission consumers; early representation contract also required',
    ),
    (
        ('evas/src/evas/display.py', 'evas/rust_core/src/display.rs'),
        ('affine', 'display', 'display_node_declarations', 'strobe',
         'initial_display_transition', 'initial_observer_horizon'),
        ('*',),
        'output formatting and initial observation consumers',
    ),
    (
        tuple('evas/rust_core/src/'+name for name in (
            'analog.rs', 'solver.rs', 'source_math.rs', 'observation.rs')),
        ('affine', 'reuse', 'accuracy', 'nonlinear', 'events', 'precision_chain',
         'observation_evidence', 'observation_evidence_helper'),
        ('*',),
        'voltage relation and exported enclosure consumers; affected histories still need review',
    ),
    (
        _BUDGET_PATHS,
        ('affine', 'integer_loops', 'event_body_loops', 'event_runtime_loops'),
        ('*',),
        'integer analysis consumers; early shared-work budget contract also required',
    ),
    (
        ("evas/src/evas/scs.py", "evas/src/evas/scs_sources.py"),
        ("scs", "scs_pulse_delay", "scs_save", "scs_bsource", "scs_driven_nodes",
         "scs_vectors", "source_uncertainty", "ansi_ports", "case_statements",
         "held_transition_targets", "r01_language", "strobe"),
        ("*",),
        "SCS loading/source generation and all direct public consumers; full delivery retained",
    ),
    (
        tuple("evas/rust_core/src/" + name for name in (
            "operators.rs", "transition.rs", "transition_source_plan.rs",
            "transition_source_state.rs", "transition_filter.rs", "transition_integral.rs",
            "transition_filter_input.rs", "transient.rs", "transient_event_acceptance.rs",
            "transient_history_calendar.rs", "transient_root_refinement.rs",
            "transient_initialization.rs", "event_conditions.rs", "event_control.rs",
            "initial_state_invariance.rs",
            "event_accuracy.rs", "event_numeric.rs", "event_time_provenance.rs")),
        ("affine", "timer", "transition", "transition_accuracy", "timed_composition",
         "event_window_sampling", "lifecycle_closure", "semantic_invariants",
         "timer_history_order", "continuous_dynamics", "event_accuracy",
         "event_history_continuation", "passive_events", "passive_history_phase", "display",
         "initial_display_transition", "initial_observer_horizon"),
        ("*",),
        "shared event/history iteration; complete Python coverage remains a delivery obligation",
    ),
    (
        ("evas/rust_core/src/linear.rs", "evas/rust_core/src/linear/"),
        ("affine", "sparse"),
        ("affine", "reuse", "accuracy", "sparse", "sparse_transient"),
        "dense/sparse factorization and reuse",
    ),
    (
        ("evas/rust_core/src/nonlinear.rs", "evas/rust_core/src/nonlinear/"),
        ("affine", "nonlinear"),
        ("affine", "nonlinear", "accuracy", "precision_chain"),
        "Newton and point-polynomial solve",
    ),
    (
        ("evas/src/evas/syntax.py", "evas/src/evas/parameters.py"),
        ("affine", "contracts"),
        ("affine", "contracts", "parameter_constraints"),
        "syntax and parameter binding; operator consumers still need review",
    ),
    (
        ("evas/rust_core/src/schedule.rs",),
        ("affine", "timer"),
        (
            "affine",
            "timer",
            "event_horizons",
            "lifecycle_closure",
            "semantic_invariants",
        ),
        "scheduling and horizons; preserved history and query invariance",
    ),
)


def select_checks(
    paths: list[str], frozen: Path, ci_required: dict, stage: str, *, per_path: dict
) -> dict:
    """Return executable checks, reasons, and outstanding delivery requirements."""
    if stage not in ("iteration", "delivery"):
        raise ValueError("stage must be iteration or delivery")
    selections = {"iteration": {}, "delivery": {}}
    pending = {}

    def obligation(identifier, reason, rule=_ACCEPTANCE, **fields):
        pending[identifier] = dict(
            id=identifier, status="pending", reason=reason, rule=rule, **fields
        )

    def add(which, check, reason):
        selections[which].setdefault(check, []).append(reason)

    def both(check, reason):
        for which in selections:
            add(which, check, reason)

    behavior = False
    for path in paths:
        if path.endswith(_DOC_SUFFIXES):
            obligation(
                "documentation-review",
                "Review changed text, contracts and links; no simulator run.",
            )
            if path.startswith((".agents/", "docs/contributing/")):
                obligation(
                    "selection-rule-review",
                    "Confirm local check mapping still matches changed validation rules.",
                )
            continue
        reason = dict(path=path, rule=_VALIDATION)
        if path in (
            "scripts/ci_selection.py",
            "scripts/tests/test_ci_selection.py",
        ) or path.startswith(".github/"):
            both(
                "ci-routing",
                {
                    **reason,
                    "why": "CI routing changed; exercise its decision tests locally.",
                },
            )
            continue
        match = _TEST.fullmatch(path)
        if match:
            both(
                "python:" + match[1],
                {
                    **reason,
                    "why": (
                        "Changed test module, including deletion: coverage must be accounted for."
                    ),
                },
            )
            continue
        if path.startswith(("evas/src/", "evas/rust_core/")):
            behavior = True
            if path in _REPRESENTATION_PATHS:
                obligation('representation-compatibility',
                           'Before dependent integration, inspect changed old IR/routes and '
                           'run affected complete consumers; the small Select contract is a starting set.',
                           _ACCEPTANCE+'#early-integration-checks',
                           before='dependent-integration',
                           command='python3 -B scripts/evas_check_policy.py --early-checks --checks representation')
            if path in _PROOF_PATHS:
                obligation('proof-budget',
                           'Before dependent integration, account for new work, inherited '
                           'allowances, delegated traversals, old successful routes, exhaustion '
                           'and same-request retry. Generic early checks do not qualify a new '
                           'proof helper; its case-specific evidence remains pending.',
                           _ACCEPTANCE+'#early-integration-checks',
                           before='dependent-integration',
                           command='python3 -B scripts/evas_check_policy.py --early-checks')
            if path.startswith("evas/rust_core/"):
                obligation(
                    "rust-tests",
                    "Run relevant Rust tests; building the kernel does not run them.",
                    _VALIDATION,
                )
            for prefixes, iteration, delivery, area in _RULES:
                if any(
                    path.startswith(p) if p.endswith("/") else path == p
                    for p in prefixes
                ):
                    for which, modules in (
                        ("iteration", iteration),
                        ("delivery", delivery),
                    ):
                        for module in modules:
                            add(
                                which,
                                "python-regression" if module == "*" else f"python:test_{module}.py",
                                {**reason, "why": area},
                            )
                    break
            else:
                both(
                    "python-regression",
                    {
                        **reason,
                        "why": (
                            "Shared or unmapped source/build boundary: narrower coverage is "
                            "not established."
                        ),
                    },
                )
            continue
        if path.startswith(("evas/validation/", "experiments/")):
            obligation(
                "checker-calibration",
                (
                    "Check whether checker, thresholds or model inputs changed; "
                    "calibrate and reanalyse affected evidence before delivery."
                ),
                _VALIDATION,
            )
        obligation(
            "unmapped-changes",
            "Review changed paths without a focused executor; "
            "CI flags alone do not establish coverage.",
            _VALIDATION,
        )
        # Evaluate every unmapped path independently: a focused change must not
        # mask a simultaneous shared/build dependency's regression requirement.
        if per_path[path].get("regression"):
            both(
                "python-regression",
                {
                    **reason,
                    "rule": "scripts/ci_selection.py",
                    "why": "This unmapped path requires regression; "
                    "no narrower local coverage is established.",
                },
            )
    if "checker-calibration" in pending:
        pending["checker-calibration"]["paths"] = [
            p
            for p in paths
            if p.startswith(("evas/validation/", "experiments/"))
            and not p.endswith(_DOC_SUFFIXES)
        ]
    if "unmapped-changes" in pending:
        pending["unmapped-changes"]["reason"] += (
            " Inspect the plan's captured paths.json."
        )
    for checks in selections.values():
        if (
            any(c.startswith("python:") for c in checks)
            and "python-regression" not in checks
        ):
            checks.setdefault(
                "python:test_affine.py",
                [
                    dict(
                        path=None,
                        rule=_VALIDATION,
                        why="Kernel smoke accompanies focused EVAS checks.",
                    )
                ],
            )

    missing = {}
    for checks in selections.values():
        for check in checks:
            target = (
                "evas/tests/" + check.removeprefix("python:")
                if check.startswith("python:")
                else "scripts/tests/test_ci_selection.py"
                if check == "ci-routing"
                else None
            )
            if target and not (frozen / target).is_file():
                missing[check] = target
    for check, path in missing.items():
        obligation(
            "missing:" + check,
            "Required test module is missing; restore it or review its replacement explicitly.",
            _VALIDATION,
            check=check,
            path=path,
        )
    selection = {}
    for which, checks in selections.items():
        # Full discovery subsumes individual modules, but never hides a missing
        # required test or the reason why broader coverage was selected.
        if "python-regression" in checks:
            for check in list(checks):
                if check.startswith("python:"):
                    checks["python-regression"].extend(checks.pop(check))
        selection[which] = [
            dict(check=c, reasons=reasons) for c, reasons in checks.items()
        ]
    for item in selection["delivery"]:
        obligation(
            "local:" + item["check"],
            "Delivery check has not passed in this plan's evidence.",
            _VALIDATION,
            check=item["check"],
        )
    if paths:
        obligation(
            "original-request",
            (
                "Verify the original request on the final integrated candidate; a "
                "reduced reproduction is insufficient."
            ),
        )
    if behavior:
        obligation(
            "affected-consumers",
            (
                "Review capability IDs and affected consumers/compositions; path "
                "mapping is only the starting point."
            ),
            _VALIDATION,
        )
        obligation(
            "spectre-alignment",
            (
                "Provide relevant actual Spectre comparisons or justified "
                "identity-compatible reuse; record any alignment gap."
            ),
            _ACCEPTANCE + "#spectre-alignment-acceptance",
        )
    for lane, required in ci_required.items():
        if required:
            obligation(
                "ci:" + lane,
                "Required CI lane remains separate from local checks.",
                "scripts/ci_selection.py",
                lane=lane,
            )
    selected = [item["check"] for item in selection[stage]]
    return dict(
        stage=stage,
        checks=selected,
        check_selection=selection,
        pending_acceptance=list(pending.values()),
        acceptance_complete=False,
        blocked_checks=[
            dict(check=c, path=p)
            for c, p in missing.items()
            if c in selected
            or (c.startswith("python:") and "python-regression" in selected)
        ],
    )


def acceptance_state(plan: dict, results: list[dict]) -> dict:
    """Only close successful local checks; external evidence needs explicit review."""
    passed = {r["check"] for r in results if r["passed"]}
    return dict(
        stage=plan["stage"],
        check_selection=plan["check_selection"],
        pending_acceptance=[
            item
            for item in plan["pending_acceptance"]
            if not (
                item["id"].startswith("local:")
                and (
                    item["check"] in passed
                    or (
                        item["check"].startswith("python:")
                        and "python-regression" in passed
                    )
                )
            )
        ],
        acceptance_complete=False,
        ci_required=plan["ci_required"],
        ci_complete=False,
    )


def evaluate(request: dict) -> dict:
    """Evaluate policy for this source tree; execution facts come from its caller."""
    if (
        type(request.get("protocol_version")) is not int
        or request["protocol_version"] != PROTOCOL_VERSION
    ):
        raise ValueError("unsupported EVAS check policy protocol")
    operation = request.get("operation")
    if operation == "plan" and set(request) == {
        "protocol_version",
        "operation",
        "paths",
        "stage",
    }:
        paths = request["paths"]
        if not isinstance(paths, list) or any(
            not isinstance(p, str) or not p for p in paths
        ):
            raise ValueError("policy paths must be nonempty strings")
        classify = runpy.run_path(str(ROOT / "scripts/ci_selection.py"))["classify"]
        required = classify(paths)
        per_path = {p: classify([p]) for p in paths}
        if any(
            not isinstance(flags, dict)
            or not flags
            or any(type(value) is not bool for value in flags.values())
            for flags in [required, *per_path.values()]
        ):
            raise ValueError("invalid CI selection result")
        selected = select_checks(
            paths, ROOT, required, request["stage"], per_path=per_path
        )
        result = dict(**selected, ci_required=required, ci_complete=False)
    elif operation == "acceptance" and set(request) == {
        "protocol_version",
        "operation",
        "plan",
        "results",
    }:
        results = request["results"]
        if not isinstance(results, list) or any(
            not isinstance(r, dict)
            or set(r) != {"check", "passed"}
            or not isinstance(r["check"], str)
            or type(r["passed"]) is not bool
            for r in results
        ):
            raise ValueError("acceptance requires observed check/pass facts")
        result = acceptance_state(request["plan"], results)
    else:
        raise ValueError("invalid EVAS check policy request")
    return dict(protocol_version=PROTOCOL_VERSION, result=result)


def document_text(text: str) -> str:
    """Replace only the policy-owned table; keep explanatory prose unchanged."""
    begin, end = "<!-- evas-check-policy:begin -->", "<!-- evas-check-policy:end -->"
    if (
        text.count(begin) != 1
        or text.count(end) != 1
        or text.index(begin) > text.index(end)
    ):
        raise ValueError("expected one ordered EVAS policy marker pair")
    rows = [
        "| Source paths | Iteration modules | Delivery modules |",
        "| --- | --- | --- |",
    ]
    for prefixes, iteration, delivery, _ in _RULES:
        cells = (
            ", ".join(f"`{p}`" for p in prefixes),
            " ".join(f"`test_{m}`" for m in iteration),
            " ".join("Full Python regression" if m == "*" else f"`test_{m}`" for m in delivery),
        )
        rows.append("| " + " | ".join(cells) + " |")
    start, finish = text.index(begin) + len(begin), text.index(end)
    return text[:start] + "\n\n" + "\n".join(rows) + "\n\n" + text[finish:]


def early_checks_for_plan(plan):
    """Use the actual delta, without treating a focused result as acceptance."""
    from evas_integration_checks import CHECKS
    paths = plan.get('iteration_paths') if plan.get('mode') == 'iteration' else None
    if paths is None:
        paths = plan.get('paths')
    # Missing/manual identities retain all contracts. An identified empty diff
    # can skip them; unknown EVAS sources/build inputs conservatively select all.
    if (not isinstance(paths, list) or any(not isinstance(p, str) or not p for p in paths)
            or not plan.get('base') or not plan.get('head')):
        return list(CHECKS)
    selected = set()
    for path in paths:
        if path.endswith(_DOC_SUFFIXES):
            continue
        if path in _REPRESENTATION_PATHS:
            selected.add('representation')
        elif path in _BUDGET_PATHS:
            selected.add('integer-budget')
        elif path.startswith('evas/') or path in ('rust-toolchain.toml', 'rust-toolchain'):
            selected.update(CHECKS)
    return [check for check in CHECKS if check in selected]


def early_runtime_for_plan(plan):
    paths = plan.get('iteration_paths') if plan.get('mode') == 'iteration' else None
    paths = plan.get('paths') if paths is None else paths
    return (not plan.get('base') or not plan.get('head') or not isinstance(paths, list)
            or any(p.startswith('evas/rust_core/')
                   or p in ('rust-toolchain.toml', 'rust-toolchain') for p in paths))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--request", type=Path)
    mode.add_argument("--check-docs", action="store_true")
    mode.add_argument("--write-docs", action="store_true")
    mode.add_argument('--early-checks', action='store_true')
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--python-root', type=Path)
    parser.add_argument('--kernel', type=Path)
    parser.add_argument('--checks', nargs='+', choices=('representation', 'integer-budget', 'initial-budget'))
    parser.add_argument('--report', type=Path)
    parser.add_argument('--plan', type=Path, help='CI delta plan; skip unaffected early contracts')
    parser.add_argument(
        "--document", type=Path, default=ROOT / ".agents/skills/evas-validate/SKILL.md"
    )
    args = parser.parse_args()
    try:
        if args.early_checks:
            sys.path.insert(0, str(ROOT/'scripts'))
            from evas_integration_checks import run
            if args.plan and args.checks:
                raise ValueError('--plan and --checks are mutually exclusive')
            plan = json.loads(args.plan.read_text()) if args.plan else None
            selected = early_checks_for_plan(plan) if plan is not None else args.checks
            if selected == []:
                result = dict(source_root=str(args.source_root.resolve()), checks=[], passed=True,
                              needs_runtime=False, selection='no affected early contracts in identified delta',
                              acceptance_complete=False, full400=False)
            else:
                result = run(args.source_root, python_root=args.python_root,
                             kernel=args.kernel, checks=selected, absent_is_inapplicable=bool(args.plan),
                             require_runtime=early_runtime_for_plan(plan) if plan is not None else False)
            if args.plan:
                result['selection_plan'] = plan
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result))
            if result['passed']:
                return 0
            return 2 if all(r['status'] in ('passed', 'not-applicable', 'needs-runtime')
                            for r in result['checks']) and result['needs_runtime'] else 1
        elif args.request:
            request = json.loads(args.request.read_text())
            if not isinstance(request, dict):
                raise ValueError("policy request must be an object")
            print(json.dumps(evaluate(request)))
        else:
            text = args.document.read_text()
            expected = document_text(text)
            if args.check_docs and expected != text:
                raise ValueError("EVAS policy documentation differs; run --write-docs")
            if args.write_docs:
                args.document.write_text(expected)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
