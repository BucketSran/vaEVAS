"""Bound human review output and record observed development time locally."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time


REVIEW_LIMITS = {"clean": 300, "findings": 800}


def visible_length(text: str) -> int:
    # Link destinations are evidence addresses, not prose. Keep their labels.
    text = re.sub(r"\[([^\]\n]*)\]\([^\n)]*\)", r"\1", text)
    return len(re.sub(r"\s", "", text))


def check_review(paths: list[Path], findings: int) -> dict:
    """Check one human summary. Never truncate findings or edit source reports."""
    if findings < 0:
        raise ValueError("findings must be nonnegative")
    errors = []
    if len(paths) != 1:
        errors.append("Submit one consolidated human summary; keep reviewer evidence in the task record.")
    limit = REVIEW_LIMITS["findings" if findings else "clean"]
    counts = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        count = visible_length(text)
        counts.append({"path": str(path), "characters": count})
        if not text.strip():
            errors.append(f"{path}: summary is empty")
        if count > limit:
            errors.append(f"{path}: {count} visible characters exceed {limit}; link evidence instead of copying it.")
    return {"passed": not errors, "limit": limit, "findings": findings,
            "summaries": counts, "errors": errors}


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    active, seen = {}, set()
    for row in rows:
        identifier = row["id"]
        if row["kind"] == "start":
            if identifier in seen:
                raise ValueError(f"duplicate timer id: {identifier}")
            seen.add(identifier)
            active[identifier] = row
        elif row["kind"] == "stop":
            if identifier not in active:
                raise ValueError(f"timer has no open start: {identifier}")
            active.pop(identifier)
        else:
            raise ValueError(f"unknown timing record: {row['kind']}")
    return rows


def append_event(path: Path, event: dict) -> None:
    # The task coordinator owns this append-only file; workers return receipts.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def stamp() -> dict:
    return {"at": datetime.now(timezone.utc).isoformat(), "monotonic_s": time.monotonic()}


def start(path: Path, identifier: str, phase: str, actor: str) -> dict:
    if any(row["id"] == identifier for row in read_events(path)):
        raise ValueError(f"timer id already used: {identifier}")
    event = dict(kind="start", id=identifier, phase=phase, actor=actor, **stamp())
    append_event(path, event)
    return event


def stop(path: Path, identifier: str, status: str, evidence: str, reason: str) -> dict:
    rows = read_events(path)
    starts = [row for row in rows if row["kind"] == "start" and row["id"] == identifier]
    if not starts or any(row["kind"] == "stop" and row["id"] == identifier for row in rows):
        raise ValueError(f"timer is not open: {identifier}")
    began, now = starts[0], stamp()
    elapsed = now["monotonic_s"] - began["monotonic_s"]
    wall = (datetime.fromisoformat(now["at"]) - datetime.fromisoformat(began["at"])).total_seconds()
    clock_ok = elapsed >= 0 and abs(elapsed - wall) <= 5
    event = dict(kind="stop", id=identifier, status=status, evidence=evidence, reason=reason,
                 elapsed_s=elapsed if clock_ok else None, clock_consistent=clock_ok, **now)
    append_event(path, event)
    return event


def summarize(path: Path) -> dict:
    rows = read_events(path)
    active, totals, intervals, unknown = {}, {}, [], []
    for row in rows:
        if row["kind"] == "start":
            active[row["id"]] = row
            continue
        began = active.pop(row["id"])
        elapsed = row["elapsed_s"]
        if elapsed is None:
            unknown.append(row["id"])
            continue
        key = began["actor"] + ":" + began["phase"]
        totals[key] = totals.get(key, 0) + elapsed
        intervals.append((datetime.fromisoformat(began["at"]).timestamp(),
                          datetime.fromisoformat(row["at"]).timestamp()))
    merged = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return {"actor_phase_seconds": totals,
            "observed_union_s": sum(hi - lo for lo, hi in merged),
            "observed_span_s": merged[-1][1] - merged[0][0] if merged else 0,
            "unfinished": list(active), "unknown_duration": unknown,
            "scope": "Observed intervals only. Actor totals can overlap; never sum them as wall time. Unrecorded time is unknown."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("check-review")
    review.add_argument("paths", nargs="+", type=Path)
    review.add_argument("--findings", type=int, required=True)
    begin = commands.add_parser("time-start")
    begin.add_argument("path", type=Path)
    begin.add_argument("--id", required=True)
    begin.add_argument("--phase", choices=("research", "implementation", "validation", "review", "rework", "ci-wait", "publication"), required=True)
    begin.add_argument("--actor", default="coordinator")
    end = commands.add_parser("time-stop")
    end.add_argument("path", type=Path)
    end.add_argument("--id", required=True)
    end.add_argument("--status", choices=("complete", "failed", "cancelled"), required=True)
    end.add_argument("--evidence", required=True)
    end.add_argument("--reason", default="")
    summary = commands.add_parser("time-summary")
    summary.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check-review":
            result = check_review(args.paths, args.findings)
        elif args.command == "time-start":
            result = start(args.path, args.id, args.phase, args.actor)
        elif args.command == "time-stop":
            result = stop(args.path, args.id, args.status, args.evidence, args.reason)
        else:
            result = summarize(args.path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
