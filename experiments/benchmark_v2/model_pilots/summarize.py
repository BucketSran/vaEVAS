"""Summarize only complete public projections. Never infer an electrical score."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one_shot_rows(document):
    attempts = {r["join_id"]: r for r in document["attempts"]}
    assert len(attempts) == document["model_attempt_denominator"] == 106
    rows = []
    for index, row in enumerate(document["cells"]):
        attempt = attempts[row["selected_attempt_join_id"]]
        provider = attempt["provider"]
        assert provider["latest_eligible"] and provider["request_attempted"]
        assert (provider["task_id"], provider["requested_model"]) == (row["task_id"], row["model"])
        result = row["current_result"]
        score = result["electrical_score"]
        terminal = result["terminal"]
        submission = provider["derived_submission_classification"]
        if terminal == "electrical_pass":
            assert score == 1
            outcome = "pass"
        elif terminal == "electrical_failure":
            assert score == 0
            outcome = "electrical-fail"
        else:
            assert score is None
            if terminal == "invalid_candidate":
                outcome = "invalid-va"
            else:
                outcome = {
                    "output_budget_exhausted_no_submission": "output-budget-no-submission",
                    "invalid_submission_format_after_stop": "submission-format-error",
                    "provider_no_response_attribution_unknown": "no-response-cause-unknown",
                    "provider_context_limit_rejection": "context-rejection",
                }[submission]
        rows.append({
            "task_id": row["task_id"], "model": row["model"], "mode": "one-shot",
            "outcome": outcome, "electrical_score": score,
            "raw_classification": terminal, "submission_classification": submission,
            "has_complete_submission": submission == "valid_submission",
            "evidence_file": "one-shot-final.json", "evidence_row_index": index,
            "selected_attempt_join_id": row["selected_attempt_join_id"],
            "canonical_instruction_sha256": row["public_files_sha256"]["instruction.md"],
            "canonical_public_files_sha256": {
                name.removeprefix("public/"): sha for name, sha in row["public_files_sha256"].items()
                if name != "instruction.md"
            },
        })
    return rows


def agentic_rows(document):
    assert document["complete"] is True, "Incomplete Agentic projection is not publishable"
    rows = []
    for index, row in enumerate(document["rows"]):
        assert row["status"] == "completed"
        score = row["electrical_score"]
        original = row["classification"]
        if original in ("valid-task-pass", "valid-task-fail", "model-budget-exhaustion"):
            # A completed candidate remains scoreable when solving stops at its budget.
            assert score in (0, 1) and row["candidate_sha256"] is not None
            evidence = row["actual_evidence"]
            conditions = evidence["conditions"]
            configured = evidence["configured_condition_ids"]
            actual = [condition["condition_id"] for condition in conditions]
            assert len(actual) == len(set(actual)) == len(configured) > 0
            assert set(actual) == set(configured)
            assert all(condition["status"] in ("graded", "regraded", "ok")
                       for condition in conditions)
            assert score == int(all(condition["passed"] for condition in conditions))
            assert all(condition["electrical_score"] == int(condition["passed"])
                       for condition in conditions)
            if original == "valid-task-pass":
                assert score == 1
            elif original == "valid-task-fail":
                assert score == 0
            outcome = "pass" if score == 1 else "electrical-fail"
        else:
            assert score is None and row["candidate_sha256"] is None
            outcome = {
                "model-completed-without-protocol-submission": "protocol-no-submission",
                "model-output-budget-exhaustion-no-submission": "output-budget-no-submission",
                "model-output-budget-exhaustion-no-submission-after-successful-native-transport-recovery": "output-budget-no-submission",
                "wall-time-budget-exhausted-no-submission": "time-budget-no-submission",
            }[original]
        rows.append({
            "task_id": row["task_id"], "model": row["model"], "mode": "agentic",
            "outcome": outcome, "electrical_score": score, "raw_classification": original,
            "has_complete_submission": row["candidate_sha256"] is not None,
            "evidence_file": "agentic-final.json", "evidence_row_index": index,
            "candidate_sha256": row["candidate_sha256"],
            "canonical_instruction_sha256": row["canonical_public_identity"]["instruction_sha256"],
            "canonical_public_files_sha256": row["canonical_public_identity"]["public_files_sha256"],
        })
    return rows


def counts(rows):
    outcomes = dict(sorted(Counter(r["outcome"] for r in rows).items()))
    passed = sum(r["electrical_score"] == 1 for r in rows)
    graded = sum(r["electrical_score"] in (0, 1) for r in rows)
    return {
        "design_cells": len(rows),
        "complete_submissions": sum(r["has_complete_submission"] for r in rows),
        "electrically_graded": graded, "passed": passed,
        "outcomes": outcomes,
        "task_completion": {"numerator": passed, "denominator": len(rows)},
        "graded_subset_pass": {"numerator": passed, "denominator": graded},
    }


def tables(rows):
    result = {}
    for mode in ("one-shot", "agentic"):
        selected = [r for r in rows if r["mode"] == mode]
        result[mode] = {
            "all_models": counts(selected),
            "by_model": {model: counts([r for r in selected if r["model"] == model])
                         for model in ("glm-5.3", "glm-5.3-flash")},
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--one-shot", type=Path, required=True)
    parser.add_argument("--agentic", type=Path, required=True)
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Do not overwrite a frozen summary"
    sources = json.loads(args.source_map.read_text())
    metadata = {r["task_id"]: r for r in sources["rows"]}
    assert len(metadata) == 37
    documents = {name: json.loads(path.read_text()) for name, path in
                 (("one-shot", args.one_shot), ("agentic", args.agentic))}
    rows = one_shot_rows(documents["one-shot"]) + agentic_rows(documents["agentic"])
    expected = {(task, model, mode) for task in metadata
                for model in ("glm-5.3", "glm-5.3-flash") for mode in ("one-shot", "agentic")}
    assert len(rows) == len(expected) == 148
    assert {(r["task_id"], r["model"], r["mode"]) for r in rows} == expected
    indexed = {(r["task_id"], r["model"], r["mode"]): r for r in rows}
    for task, model, mode in expected:
        row = indexed[task, model, mode]
        other = indexed[task, model, "one-shot" if mode == "agentic" else "agentic"]
        assert row["canonical_instruction_sha256"] == other["canonical_instruction_sha256"]
        assert row["canonical_public_files_sha256"] == other["canonical_public_files_sha256"]
        meta = metadata[task]
        row.update({key: meta[key] for key in
                    ("primary_category", "p1_owning_source_id", "mandatory_extra_representative",
                     "relation_group_ids", "system_task_kind", "task_weight")})
        assert row["task_weight"] == 1
    p1_rows = [r for r in rows if r["p1_owning_source_id"] is not None]
    assert len(p1_rows) == 128
    output = {
        "schema_version": 1,
        "complete": True,
        "input_sha256": {"one-shot-final.json": digest(args.one_shot),
                         "agentic-final.json": digest(args.agentic),
                         "../task-source-map.json": digest(args.source_map)},
        "curation_script_sha256": digest(Path(__file__)),
        "denominator_policy": "37 tasks x2 models x2 modes; all cells retained; weight1; no best-of",
        "no_equal_compute_or_independent_circuit_claim": True,
        "material_parity": {"task_model_pairs": 74, "same_canonical_bytes": True,
                            "equal_representation_or_model_use_claimed": False},
        "overall": tables(rows),
        "by_category": {category: tables([r for r in rows if r["primary_category"] == category])
                        for category in sources["category_counts"]},
        "p1_owner_subset": tables(p1_rows),
        "mandatory_extra_subset": tables([r for r in rows if r["mandatory_extra_representative"]]),
        "system_subset": tables([r for r in rows if r["task_id"] in sources["system_tasks"]]),
        "relation_groups": [{"group_id": group["group_id"], "relation_kind": group["relation_kind"],
                             "adds_weight": False, "groups_may_overlap": True,
                             "task_ids": group["task_ids"],
                             "results": tables([r for r in rows if r["task_id"] in group["task_ids"]])}
                            for group in sources["relation_groups"]],
        "cells": sorted(rows, key=lambda r: (r["task_id"], r["model"], r["mode"])),
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"sha256": digest(args.output), "overall": output["overall"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
