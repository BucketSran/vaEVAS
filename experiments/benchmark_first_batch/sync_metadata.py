"""Normalize first-batch metadata without changing executable task criteria."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = {
    "specification": "specification-modeling",
    "repair": "diagnosis-repair",
    "from-data-modeling": "from-data-modeling",
    "extension-integration": "extension-integration",
    "verification-tools": "verification-tools",
    "measurement-characterization": "measurement-characterization",
    "simulation-implementation-optimization": "simulation-implementation-optimization",
}
GROUPS = {
    "va07-triangle-repair": "repository-triangle-oscillator",
    "va08-adc-linearity": "repository-owned-original-adc-linearity",
    "verify-sh-settling-checker": "original-periodic-sh-observation",
    "measure-sh-acquisition-droop": "original-periodic-sh-observation",
}
FIELDS = ("engineering_action", "source_group", "context_level", "provenance", "data_provenance")
START = "<!-- generated first-batch metadata -->"
END = "<!-- end generated first-batch metadata -->"


def protected_identity(root):
    """All task bytes except the two explicitly editable metadata files."""
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (root / "benchmark/tasks").rglob("*")
            if p.is_file() and p.name not in {"task.toml", "SOURCE.md"}}


def toml_metadata(text, metadata):
    match = re.search(r"(?ms)^\[metadata\]\n(.*?)(?=^\[|\Z)", text)
    if not match:
        raise ValueError("missing metadata section")
    body = match.group(1)
    for key in (*FIELDS, "action", "context"):
        body = re.sub(r"(?m)^" + key + r"\s*=.*\n?", "", body)
    body = body.rstrip() + "\n" + "".join(f"{key} = {json.dumps(metadata[key])}\n" for key in FIELDS)
    return text[:match.start(1)] + body + text[match.end(1):]


def source_metadata(text, metadata, previous_group):
    text = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", "", text, flags=re.S).rstrip()
    if previous_group and previous_group != metadata["source_group"]:
        text = text.replace(previous_group, metadata["source_group"])
    block = "\n\n" + START + "\n" + "\n".join(f"- `{key}`: `{metadata[key]}`" for key in FIELDS) + "\n" + END + "\n"
    return text + block


def normalize(root, check=False):
    root = Path(root).resolve()
    before = protected_identity(root)
    changes = {}
    seen = set()
    for filename in ("model_repair.json", "identification.json", "integration.json", "verification_measurement.json", "optimization.json"):
        path = root / "benchmark/first_batch" / filename
        document = json.loads(path.read_text())
        for row in document.get("tasks", []) + document.get("candidates", []):
            ident = row.get("id", row.get("task_id", row.get("candidate_id")))
            if not ident or ident in seen:
                raise ValueError("missing or duplicate first-batch identity: " + str(ident))
            seen.add(ident)
            old_group = row["source_group"]
            legacy = row.get("engineering_action", row.get("action", row.get("category", document.get("category"))))
            if legacy not in ACTIONS and legacy not in ACTIONS.values():
                raise ValueError("unknown action: " + str(legacy))
            action = ACTIONS.get(legacy, legacy)
            context = ("complete-repository" if ident == "integrate-tdc-measurement-chain" else
                       "bounded-small-project" if ident.startswith("integrate-") else "bounded-work-unit")
            provenance = ("development-regression" if ident == "va07-triangle-repair" else
                          "injected-semantic-fault" if action == "diagnosis-repair" else "original-engineering-requirement")
            metadata = dict(engineering_action=action, source_group=GROUPS.get(ident, old_group),
                            context_level=context, provenance=provenance,
                            data_provenance="not-applicable" if ident == "va07-triangle-repair" else "behavioral_synthetic")
            row.pop("action", None)
            row.pop("category", None)
            row.update(metadata)
            task_path = row.get("path", row.get("task_path"))
            if task_path:
                folder = root / task_path
                toml = folder / "task.toml"
                source = folder / "SOURCE.md"
                changes[toml] = toml_metadata(toml.read_text(), metadata)
                changes[source] = source_metadata(source.read_text(), metadata, old_group)
        changes[path] = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    stale = [str(p.relative_to(root)) for p, data in changes.items() if p.read_text() != data]
    if not check:
        for p, data in changes.items():
            if p.read_text() != data:
                p.write_text(data)
    if protected_identity(root) != before:
        raise RuntimeError("executable task criteria changed")
    return len(seen), stale


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count, stale = normalize(args.root, args.check)
    print(json.dumps({"entries": count, "stale_metadata": stale, "mode": "check" if args.check else "sync"}))
    raise SystemExit(1 if args.check and stale else 0)
