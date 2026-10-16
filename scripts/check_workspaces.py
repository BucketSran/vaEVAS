#!/usr/bin/env python3
"""Check local worktree visibility and report Git state without changing any checkout."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
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


def status(repo, all_untracked=False):
    fields = iter(git(repo, "status", "--porcelain=v1", "-z",
                      "--untracked-files=" + ("all" if all_untracked else "normal"),
                      "--ignored=matching").split("\0"))
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


def digest(data):
    return hashlib.sha256(data).hexdigest()


def diff(repo, *revisions):
    # Raw blob IDs preserve the staged state without expanding large binary diffs.
    # Working-file content is hashed separately under the explicit byte budget.
    return git(repo, "diff", "--no-ext-diff", "--no-textconv", "--raw", "-z",
               "--no-abbrev", "--no-renames", *revisions, "--")


def hidden_index_paths(repo):
    return [entry[2:] for entry in git(repo, "ls-files", "-v", "-z").split("\0")
            if entry and (entry[0].islower() or entry[0] == "S")]


def branch_patch_id(repo, base, head):
    # Stream the patch through Git instead of keeping a potentially large diff in RAM.
    command = ["git", "-C", str(repo), "diff", "--no-ext-diff", "--no-textconv",
               "--binary", "--full-index", "--no-renames", base, head, "--"]
    producer = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    try:
        result = subprocess.run(["git", "patch-id", "--stable"], stdin=producer.stdout,
                                capture_output=True, text=True, timeout=30, check=True)
        if producer.wait(timeout=30):
            raise ValueError("branch diff failed")
        return result.stdout.split()[0] if result.stdout.strip() else None
    finally:
        producer.stdout.close()
        if producer.poll() is None:
            producer.kill()
        producer.wait()


def file_stamp(path):
    info = path.lstat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def file_identity(root, relative, remaining):
    """Hash changed files only; never follow symlinks or read special files."""
    path = root / relative
    row = {"path": relative, "sha256": None, "kind": None}
    try:
        if not path.parent.resolve().is_relative_to(root):
            raise ValueError("parent symlink escapes checkout")
        before = path.lstat()
        row["mode"] = stat.S_IMODE(before.st_mode)
        row["bytes"] = before.st_size
        if stat.S_ISLNK(before.st_mode):
            row.update(kind="symlink", sha256=digest(os.fsencode(os.readlink(path))))
        elif stat.S_ISREG(before.st_mode):
            row["kind"] = "file"
            if before.st_size > remaining[0]:
                raise ValueError("content hash budget exhausted")
            remaining[0] -= before.st_size
            hashed = hashlib.sha256()
            # O_NOFOLLOW also rejects replacement of the final path by a symlink.
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            with os.fdopen(fd, "rb") as source:
                opened = os.fstat(source.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise ValueError("file replaced while opening")
                read = 0
                while chunk := source.read(min(1024 * 1024, before.st_size - read + 1)):
                    read += len(chunk)
                    if read > before.st_size:
                        raise ValueError("file grew while hashing")
                    hashed.update(chunk)
            row["sha256"] = hashed.hexdigest()
        else:
            raise ValueError("directory, submodule or special file needs separate inspection")
        after = path.lstat()
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("file changed while hashing")
        row["_stamp"] = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    except FileNotFoundError:
        if "before" in locals():
            row.update(sha256=None, error="file disappeared while hashing")
        else:
            # A tracked deletion is an observed state, not a zero-byte file.
            row.update(kind="missing", sha256=None, _stamp=None)
    except (OSError, ValueError) as exc:
        row.update(sha256=None, error=str(exc))
    return row


def disk_usage(root, seconds, excluded=(), seen=None, anchor=None):
    """Bounded metadata scan; allocated bytes are not exclusive/reclaimable bytes."""
    result = dict(logical_bytes=0, allocated_bytes=0, entries=0, symlinks=0,
                  hardlinks_skipped=0, complete=True, errors=[])
    seen = seen if seen is not None else set()
    deadline = time.monotonic() + seconds
    if os.open not in os.supports_dir_fd or os.scandir not in os.supports_fd or not hasattr(os, "O_NOFOLLOW"):
        result.update(complete=False, errors=["safe directory descriptor scanning unavailable"])
        return result
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    anchor = anchor or root

    def failure(path, message):
        result["complete"] = False
        if len(result["errors"]) < 10:
            result["errors"].append(f"{path}: {message}")

    def budget():
        if time.monotonic() >= deadline:
            raise TimeoutError("scan time budget exhausted; sizes are lower bounds")

    def visit(parent_fd, name, path, device):
        budget()
        if path in excluded or path.name == ".git":
            return
        try:
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False) if name else os.fstat(parent_fd)
            if info.st_dev != device:
                raise ValueError("nested filesystem skipped")
            key = (info.st_dev, info.st_ino)
            if key in seen:
                result["hardlinks_skipped"] += 1
                return
            seen.add(key)
            result["entries"] += 1
            result["allocated_bytes"] += info.st_blocks * 512
            if stat.S_ISLNK(info.st_mode):
                result["symlinks"] += 1
                result["logical_bytes"] += info.st_size
            elif stat.S_ISDIR(info.st_mode):
                fd = os.open(name, flags, dir_fd=parent_fd) if name else os.dup(parent_fd)
                try:
                    opened = os.fstat(fd)
                    if (opened.st_dev, opened.st_ino) != key:
                        raise ValueError("directory replaced before opening")
                    with os.scandir(fd) as entries:
                        for entry in entries:
                            visit(fd, entry.name, path / entry.name, device)
                    after = os.fstat(fd)
                    if (opened.st_mtime_ns, opened.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns):
                        raise ValueError("directory changed during scan")
                finally:
                    os.close(fd)
            else:
                result["logical_bytes"] += info.st_size
        except TimeoutError:
            raise
        except (OSError, ValueError) as exc:
            failure(path, exc)

    fd = None
    try:
        # Open each category's ancestors relative to the checkout descriptor.
        # Replacing an ancestor with a symlink cannot redirect the scan elsewhere.
        fd = os.open(anchor, flags)
        parts = root.relative_to(anchor).parts
        for part in parts[:-1]:
            child_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child_fd
        name = parts[-1] if parts else None
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False) if name else os.fstat(fd)
        except FileNotFoundError:
            return result
        visit(fd, name, root, info.st_dev)
    except FileNotFoundError:
        # A missing category or ancestor means this checkout has no such assets.
        pass
    except (OSError, ValueError, RecursionError) as exc:
        failure(root, exc)
    finally:
        if fd is not None:
            os.close(fd)
    return result


def recommendation(row, assets, base):
    if row["primary"]:
        code, reason = "keep_daily_entry", "Primary checkout remains the daily entry"
    elif not assets["complete"] or not base:
        code, reason = "inspect_incomplete", "Inspection or base identity is incomplete; retain assets"
    elif row["changes"]:
        code, reason = "preserve_local_changes", "Uncommitted/untracked assets need an owner and recoverable snapshot"
    elif row["commits_not_in_base"]:
        code, reason = "review_commits", "Commits are not reachable from base; patch matches do not prove integration"
    else:
        code, reason = "review_retirement", "No local changes or commits outside base; confirm task owner and retained evidence"
    return {"code": code, "reason": reason,
            "before_retirement": "Confirm no active writer/process, preserve required ignored evidence and binaries, obtain cleanup authorization"}


def inspect_assets(row, base, scan_seconds, hash_limit):
    root = Path(row["path"])
    observed_at = datetime.now(timezone.utc).isoformat()
    start_head = git(root, "rev-parse", "HEAD").strip()
    staged, unstaged = diff(root, "--cached", "HEAD"), diff(root)
    assets = {"observed_at": observed_at, "complete": True, "commits": [], "branch_paths": [], "files": [],
              "staged_diff_sha256": digest(staged.encode()) if staged else None,
              "unstaged_diff_sha256": digest(unstaged.encode()) if unstaged else None,
              "branch_patch_id": None, "source_state_sha256": None, "warnings": []}
    hidden = hidden_index_paths(root)
    missing_hidden = set()
    for name in hidden:
        try:
            (root / name).lstat()
        except FileNotFoundError:
            missing_hidden.add(name)
        except OSError:
            pass  # Preserve inspection errors in file_identity below.
    assets["index_hidden_path_count"] = len(hidden)
    assets["index_hidden_missing_count"] = len(missing_hidden)
    assets["index_hidden_paths"] = [name for name in hidden if name not in missing_hidden]
    if hidden:
        assets["warnings"].append("assume-unchanged or skip-worktree entries hide changes from ordinary Git diff/status")
    if base:
        merge_base = git(root, "merge-base", base["commit"], start_head).strip()
        assets["merge_base"] = merge_base
        fields = git(root, "log", "-z", "--format=%H%x00%s",
                     f"{base['commit']}..{start_head}").strip("\0").split("\0")
        equivalents = dict(line.split()[:2][::-1] for line in
                           git(root, "cherry", base["commit"], start_head).splitlines())
        for i in range(0, len(fields) - 1, 2):
            commit = fields[i]
            assets["commits"].append({"commit": commit, "subject": fields[i + 1],
                                     "patch_equivalent_in_base":
                                     equivalents[commit] == "-" if commit in equivalents else None})
        assets["branch_paths"] = [p for p in git(root, "diff", "--no-renames", "--name-only", "-z",
                                                 merge_base, start_head, "--").split("\0") if p]
        if assets["branch_paths"]:
            assets["branch_patch_id"] = branch_patch_id(root, merge_base, start_head)
    else:
        assets["warnings"].append("base unavailable; branch comparison unknown")
    affected = set(assets["branch_paths"]) | set(assets["index_hidden_paths"])
    for change in row["changes"]:
        affected.add(change["path"])
        if "original_path" in change:
            affected.add(change["original_path"])
    remaining = [hash_limit]
    assets["files"] = [file_identity(root, name, remaining) for name in sorted(affected)]
    source_complete = not hidden and not any("error" in file for file in assets["files"])
    build, runs = root / "evas/rust_core/target", root / "runs"
    seen = set()
    assets["disk"] = {}
    for label, folder in (("build", build), ("runs", runs), ("other", root)):
        assets["disk"][label] = disk_usage(folder, scan_seconds,
                                           excluded=(build, runs) if folder == root else (), seen=seen, anchor=root)
    # Recheck Git state after scanning; a report must not certify a moving target.
    end_changes, _ = status(root, all_untracked=True)
    if (git(root, "rev-parse", "HEAD").strip() != start_head or start_head != row["head"]
            or diff(root, "--cached", "HEAD") != staged or diff(root) != unstaged
            or end_changes != row["changes"] or hidden_index_paths(root) != hidden):
        source_complete = False
        assets["warnings"].append("Git state changed during inspection")
    for file in assets["files"]:
        stamp = file.pop("_stamp", None)
        if "error" in file:
            continue
        try:
            if file_stamp(root / file["path"]) != stamp:
                raise ValueError("file changed after hashing")
        except FileNotFoundError:
            if stamp is None:
                continue
            file.update(sha256=None, error="file disappeared after hashing")
        except (OSError, ValueError) as exc:
            file.update(sha256=None, error=str(exc))
        if "error" in file:
            source_complete = False
    if source_complete:
        # Compare all tracked content through the HEAD tree plus both index/worktree
        # diffs. Untracked files need explicit identities; ignored assets are excluded.
        local_paths = {c["path"] for c in row["changes"]}
        local_paths.update(c["original_path"] for c in row["changes"] if "original_path" in c)
        state = [git(root, "rev-parse", f"{start_head}^{{tree}}").strip(), staged, unstaged,
                 [f for f in assets["files"] if f["path"] in local_paths]]
        assets["source_state_sha256"] = digest(json.dumps(state, sort_keys=True).encode())
    assets["complete"] = (source_complete and bool(base)
                           and all(d["complete"] for d in assets["disk"].values()))
    assets["recommendation"] = recommendation(row, assets, base)
    return assets


def asset_summary(rows):
    states, patches, contents, overlaps = (defaultdict(list) for _ in range(4))
    for row in rows:
        assets = row.get("assets", {})
        for field, groups in (("source_state_sha256", states), ("branch_patch_id", patches)):
            if assets.get(field):
                groups[assets[field]].append(row["path"])
        for file in assets.get("files", []):
            overlaps[file["path"]].append(row["path"])
            if file.get("sha256") and "error" not in file:
                key = (file["path"], file["kind"], file["mode"], file["sha256"])
                contents[key].append(row["path"])
    return {"matching_source_states": [{"sha256": k, "worktrees": v} for k, v in states.items() if len(v) > 1],
            "matching_branch_patches": [{"patch_id": k, "worktrees": v} for k, v in patches.items() if len(v) > 1],
            "matching_changed_files": [{"path": k[0], "kind": k[1], "mode": k[2], "sha256": k[3], "worktrees": v}
                                       for k, v in sorted(contents.items()) if len(v) > 1],
            "overlapping_paths": [{"path": k, "worktrees": v} for k, v in sorted(overlaps.items()) if len(v) > 1],
            "limits": "Source matches exclude ignored assets and commit history. Patch IDs ignore whitespace. Overlap is not equivalence. Sizes are not reclaimable space; no owner/process or archive inventory was checked."}


def inspect(repo, requested_base=None, assets=False, scan_seconds=2, hash_limit=64 * 1024 * 1024):
    rows = worktrees(repo)
    primary = Path(rows[0]["worktree"]).resolve()
    common = Path(git(primary, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve()
    project = primary.parent
    visible = project / "worktrees"
    index = visible / "README.md"
    base = resolve_base(primary, requested_base)
    report = {"primary": str(primary), "visible_root": str(visible),
              "index": str(index), "base": base, "worktrees": [], "errors": []}
    if assets:
        report.update(asset_schema_version=1, observed_at=datetime.now(timezone.utc).isoformat(),
                      asset_options={"scan_seconds_per_category": scan_seconds, "hash_limit_bytes_per_checkout": hash_limit})

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
            row["changes"], row["ignored"] = status(path, all_untracked=assets)
            if base and row["head"]:
                row["commits_not_in_base"] = int(git(
                    primary, "rev-list", "--count", f"{base['commit']}..{row['head']}").strip())
            if assets:
                print(f"Inspecting assets: {path}", file=sys.stderr, flush=True)
                row["assets"] = inspect_assets(row, base, scan_seconds, hash_limit)
        except (ValueError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
            error("INSPECTION_FAILED", path, str(exc))
    if assets:
        report["asset_summary"] = asset_summary(report["worktrees"])
        report["assets_complete"] = all(row.get("assets", {}).get("complete", False) for row in report["worktrees"])
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
        if "assets" in row:
            assets = row["assets"]
            print(f"  Recommendation: {assets['recommendation']['code']} — {assets['recommendation']['reason']}")
            if assets["index_hidden_path_count"]:
                print(f"  Hidden index paths: {assets['index_hidden_path_count']}; absent paths counted only: {assets['index_hidden_missing_count']}")
            for commit in assets["commits"]:
                print(f"    Commit {commit['commit'][:12]} {commit['subject']!r}; patch equivalent in base: {commit['patch_equivalent_in_base']}")
            print(f"  Changed/branch/hidden paths: {len(assets['files'])}; full identities in --json")
            for file in assets["files"][:8]:
                print(f"    Asset {file['path']!r}: {file.get('error') or file['sha256'] or file['kind']}")
            for label, disk in assets["disk"].items():
                print(f"  Disk {label}: logical={disk.get('logical_bytes')} allocated={disk.get('allocated_bytes')} bytes; complete={disk['complete']}")
                for message in disk["errors"]:
                    print(f"    {message}")
            for message in assets["warnings"]:
                print(f"    {message}")
    for item in report["errors"]:
        print(f"\n{item['code']}: {item['path']}\n  {item['message']}")
    print("\nVisibility check: " + ("FAIL" if report["errors"] else "PASS"))
    print("Git state is an observation, not proof of integration or permission to retire a worktree.")
    if "asset_summary" in report:
        labels = {r["path"]: Path(r["visible_entry"] or r["path"]).name for r in report["worktrees"]}
        for kind, groups in report["asset_summary"].items():
            if not isinstance(groups, list):
                print(f"\n{kind}: {groups}")
                continue
            print(f"\n{kind}: {len(groups)} groups; showing at most 10")
            for group in sorted(groups, key=lambda g: len(g["worktrees"]), reverse=True)[:10]:
                identity = group.get("path") or group.get("sha256") or group.get("patch_id")
                print(f"  {identity}: {', '.join(labels[p] for p in group['worktrees'])}")
        print(f"Asset inspection complete: {report['assets_complete']}")


def nonnegative(value):
    number = float(value)
    if not 0 <= number < float("inf"):
        raise argparse.ArgumentTypeError("must be a finite nonnegative number")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Any checkout of the repository")
    parser.add_argument("--base", help="Local ref for commit reachability; default origin/main, then main")
    parser.add_argument("--json", action="store_true", help="Print the full inspection as JSON")
    parser.add_argument("--assets", action="store_true", help="Inspect local changes, duplicate candidates and disk usage (read-only)")
    parser.add_argument("--scan-seconds", type=nonnegative, default=2,
                        help="Metadata scan time budget per checkout/category; default 2 seconds")
    parser.add_argument("--hash-limit-mib", type=nonnegative, default=64,
                        help="Changed-file content hash budget per checkout; default 64 MiB")
    args = parser.parse_args()
    try:
        report = inspect(args.repo, args.base, args.assets, args.scan_seconds, int(args.hash_limit_mib * 1024 * 1024))
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        report = {"primary": None, "worktrees": [], "errors": [
            {"code": "INSPECTION_FAILED", "path": str(args.repo), "message": str(exc)}]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        display(report)
    if any(e["code"] == "INSPECTION_FAILED" for e in report["errors"]) or report.get("assets_complete") is False:
        return 2
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
