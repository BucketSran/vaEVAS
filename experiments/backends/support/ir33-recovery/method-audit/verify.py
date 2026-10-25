"""Check the frozen audit's coverage, identities, cross references and counts.

This checks record consistency, not the correctness of human oracle judgments.
Source hashes are read from the fixed Git commit, so later main changes do not
silently reinterpret the historical audit.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess


def verify(root, bundle):
    summary = json.loads((bundle / "summary.json").read_text())
    with (bundle / "methods.tsv").open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    findings = json.loads((bundle / "findings.json").read_text())["findings"]
    ids = {row["id"] for row in rows}
    assert len(rows) == len(ids) == summary["method_count"] == 3257
    modules = summary["source_modules"]
    assert len(modules) == summary["source_module_count"] == 332
    assert {row["source_file"] for row in rows} == set(modules)
    assert len({(row["source_file"], row["source_line"]) for row in rows}) == summary["definition_positions"]
    assert sum(json.loads(row["generated"]) for row in rows) == summary["generated_methods"]
    cross = defaultdict(Counter)
    for row in rows:
        cross[row["execution_outcome"]][row["verdict"]] += 1
    assert dict(cross) == summary["outcome_by_verdict"]
    for field, key in [("execution_outcome", "execution_counts"), ("verdict", "verdict_counts"), ("role", "role_counts")]:
        assert Counter(row[field] for row in rows) == summary[key]
    source = {}
    for name, expected in modules.items():
        raw = subprocess.check_output(["git", "show", f'{summary["source_commit"]}:{name}'], cwd=root)
        assert hashlib.sha256(raw).hexdigest() == expected, name
        source[name] = raw.decode().splitlines(keepends=True)
    finding_ids = {finding["id"] for finding in findings}
    assert len(findings) == len(finding_ids) == summary["finding_count"] == 86
    links = defaultdict(set)
    refs = set()
    for row in rows:
        name = row["source_file"]
        body = "".join(source[name][int(row["source_line"]) - 1:int(row["source_end_line"])])
        assert hashlib.sha256(body.encode()).hexdigest() == row["source_method_sha256"], row["id"]
        assert row["source_module_sha256"] == modules[name]
        for finding_id in json.loads(row["finding_ids"]):
            assert finding_id in finding_ids, finding_id
            links[finding_id].add(row["id"])
        refs.update(json.loads(row["refs"]))
        # Reviewers recorded contracts as either a reference list or prose.
        contract = row["contract"]
        refs.update(json.loads(contract) if contract.startswith("[") else [contract])
    for finding in findings:
        assert set(finding["affected_ids"]) <= ids
        assert links[finding["id"]] == set(finding["affected_ids"]), finding["id"]
        refs.update(finding["evidence_refs"])
    checked_refs = 0
    for ref in refs:
        match = re.match(r"^((?:evas|experiments|docs|scripts)/[^:#\s]+)", ref)
        if match:
            path = root / match[1]
            assert path.is_file(), f"missing reference: {ref}"
            checked_refs += 1
    return {"methods": len(rows), "modules": len(modules), "findings": len(findings),
            "checked_repository_references": checked_refs, "source_commit": summary["source_commit"],
            "scope": "record consistency only; no new simulator or oracle qualification"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repository.resolve(), Path(__file__).resolve().parent), indent=2))
