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
# Deliberately limited to inspected source boundaries. Unknown/shared changes use
# full Python coverage until their owning tests and consumers have been checked.
_RULES = (
    (
        tuple("evas/rust_core/src/" + name for name in (
            "operators.rs", "transition.rs", "transition_source_plan.rs",
            "transition_source_state.rs", "transition_filter.rs", "transition_integral.rs",
            "transition_filter_input.rs", "transient.rs", "transient_event_acceptance.rs",
            "transient_history_calendar.rs", "transient_root_refinement.rs",
            "transient_initialization.rs", "event_conditions.rs", "event_control.rs",
            "event_accuracy.rs", "event_numeric.rs", "event_time_provenance.rs")),
        ("affine", "timer", "transition", "transition_accuracy", "timed_composition",
         "event_window_sampling", "lifecycle_closure", "semantic_invariants",
         "timer_history_order", "continuous_dynamics", "event_accuracy",
         "event_history_continuation", "passive_events", "passive_history_phase", "display"),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--request", type=Path)
    mode.add_argument("--check-docs", action="store_true")
    mode.add_argument("--write-docs", action="store_true")
    parser.add_argument(
        "--document", type=Path, default=ROOT / ".agents/skills/evas-validate/SKILL.md"
    )
    args = parser.parse_args()
    try:
        if args.request:
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
