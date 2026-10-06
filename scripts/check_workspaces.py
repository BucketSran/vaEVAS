#!/usr/bin/env python3
"""Check local worktree visibility and report Git state without changing any checkout."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), timeout=30,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def worktrees(repo):
    rows = []
    row = {}
    for field in git(repo, "worktree", "list", "--porcelain", "-z").split("\0"):
        if not field:
            if row:
                rows.append(row)
                row = {}
            continue
        key, _, value = field.partition(" ")
        row[key] = value
    if not rows or "bare" in rows[0]:
        raise ValueError("A non-bare primary checkout is required")
    return rows


def navigation_text(source):
    """Exclude comments and code from the index's simple inline-link format."""
    source = re.sub(r"<!--.*?(?:-->|\Z)", "", source, flags=re.DOTALL)
    lines = []
    fence = None
    for line in source.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                    and not marker[2].strip()):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        if not line.startswith(("    ", "\t")):
            lines.append(line)
    return re.sub(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", "", "".join(lines),
                  flags=re.DOTALL)


def local_links(document, directories_only=False):
    """Resolve Markdown link paths without resolving a visible symlink away."""
    if not document.is_file():
        return []
    links = []
    source = navigation_text(document.read_text())
    for target in re.findall(r"(?<![!\\])\[[^\]\n]+\]\((<[^>\n]+>|[^\s)]+)\)", source):
        url = urlsplit(target.strip("<>"))
        if url.scheme or url.netloc or not url.path:
            continue
        entry = Path(os.path.abspath(document.parent / unquote(url.path)))
        # Missing targets must survive filtering: a retired directory no longer
        # satisfies is_dir(), whether or not its link has a trailing slash.
        if directories_only and entry.is_file():
            continue
        links.append(entry)
    return links


def status(repo):
    fields = iter(git(repo, "status", "--porcelain=v1", "-z",
                      "--untracked-files=normal", "--ignored=matching").split("\0"))
    changes, ignored = [], []
    for field in fields:
        if not field:
            continue
        code, path = field[:2], field[3:]
        if code == "!!":
            ignored.append(path)
            continue
        change = {"status": code, "path": path}
        if "R" in code or "C" in code:
            change["original_path"] = next(fields)
        changes.append(change)
    return changes, ignored


def resolve_base(repo, requested):
    refs = [requested] if requested else ["refs/remotes/origin/main", "refs/heads/main"]
    for ref in refs:
        try:
            commit = git(repo, "rev-parse", "--verify", "--end-of-options",
                         f"{ref}^{{commit}}").strip()
            return {"ref": ref, "commit": commit}
        except ValueError:
            if requested:
                raise
    return None


def inspect(repo, requested_base=None):
    rows = worktrees(repo)
    primary = Path(rows[0]["worktree"]).resolve()
    common = Path(git(primary, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve()
    project = primary.parent
    visible = project / "worktrees"
    index = visible / "README.md"
    base = resolve_base(primary, requested_base)
    report = {"primary": str(primary), "visible_root": str(visible),
              "index": str(index), "base": base, "worktrees": [], "errors": []}

    def error(code, path, message):
        report["errors"].append({"code": code, "path": str(path), "message": message})

    registered = {Path(row["worktree"]).resolve() for row in rows}
    entries = {}
    for entry in local_links(index, directories_only=True):
        if not entry.is_relative_to(visible) or entry == index:
            continue
        target = entry.resolve()
        if not entry.is_dir() or target not in registered or target == primary:
            error("STALE_ENTRY", entry, "Update the worktree index; this entry is not a live linked checkout")
        else:
            entries[target] = entry

    if len(rows) > 1 or index.is_file():
        if not index.is_file():
            error("MISSING_INDEX", index, "Create a visible worktree index with purpose and handoff state")
        if index.resolve() not in {p.resolve() for p in local_links(project / "README.md")}:
            error("MISSING_NAVIGATION", project / "README.md", "Link worktrees/README.md from the project entry")

    for raw in rows:
        path = Path(raw["worktree"]).resolve()
        entry = entries.get(path)
        row = {"path": str(path), "primary": path == primary,
               "head": raw.get("HEAD"), "branch": raw.get("branch"),
               "visible_entry": str(entry) if entry else None,
               "changes": None, "ignored": None, "commits_not_in_base": None,
               "locked": raw.get("locked"), "prunable": raw.get("prunable")}
        report["worktrees"].append(row)
        if path != primary and entry is None:
            error("HIDDEN_WORKTREE", path, "Expose this checkout under worktrees/ and link it from the index")
        try:
            actual_common = Path(git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve()
            if actual_common != common:
                raise ValueError("Registered path now resolves to a different repository")
            row["changes"], row["ignored"] = status(path)
            if base and row["head"]:
                row["commits_not_in_base"] = int(git(
                    primary, "rev-list", "--count", f"{base['commit']}..{row['head']}").strip())
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            error("INSPECTION_FAILED", path, str(exc))
    return report


def display(report):
    print(f"Daily entry: {report['primary']}")
    if report.get("base"):
        print(f"Local base: {report['base']['ref']} ({report['base']['commit']})")
    else:
        print("Local base unavailable; commit comparison is unknown. Supply --base if needed.")
    for row in report["worktrees"]:
        print(f"\n{row['path']} [{row['branch'] or 'detached HEAD'}]")
        if row["visible_entry"]:
            print(f"  Visible entry: {row['visible_entry']}")
        if row["changes"] is not None:
            print(f"  Changed/untracked entries: {len(row['changes'])}; ignored entries: {len(row['ignored'])}")
            for item in row["changes"][:5]:
                print(f"    {item['status']} {item['path']!r}")
            if row["ignored"]:
                print(f"  Ignored paths to assess before retirement: {row['ignored'][:5]!r}")
        print(f"  Commits not reachable from local base: {row['commits_not_in_base']}")
    for item in report["errors"]:
        print(f"\n{item['code']}: {item['path']}\n  {item['message']}")
    print("\nVisibility check: " + ("FAIL" if report["errors"] else "PASS"))
    print("Git state is an observation, not proof of integration or permission to retire a worktree.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Any checkout of the repository")
    parser.add_argument("--base", help="Local ref for commit reachability; default origin/main, then main")
    parser.add_argument("--json", action="store_true", help="Print the full inspection as JSON")
    args = parser.parse_args()
    try:
        report = inspect(args.repo, args.base)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        report = {"primary": None, "worktrees": [], "errors": [
            {"code": "INSPECTION_FAILED", "path": str(args.repo), "message": str(exc)}]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        display(report)
    if any(e["code"] == "INSPECTION_FAILED" for e in report["errors"]):
        return 2
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
