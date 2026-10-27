"""Stage 1: read-only raw-evidence verification of CI 40584762318 (PR6 E1) against CI 40569530278 (#274).

Usage: python3 -B raw_verify.py --output NEW-UNUSED-DIRECTORY   (directory must lie under this folder)

Only parses JSON, hashes bytes, reads existing Git objects and runs the trusted gate's pure functions
(validate_report, merge_reports, compare_report, execution_subject). It never runs a test body, a kernel,
a DUT, a compiler, a backend, SSH, Spectre or Harbor, never fetches and never writes Git state.
"""
import argparse
import collections
import datetime
import importlib.util
import json
import re
import stat
import subprocess
import sys
import traceback
import zipfile
from pathlib import Path, PurePosixPath

from common import *

OLD_REPORT = D / "artifacts-274/python-regression-timings/python-regression.json"
OLD_INVENTORY_ZIP = R7 / "ci-40569530278/catalog-inventory.zip"
OLD_INVENTORY = R7 / "ci-40569530278/catalog-inventory/assets-before.json"
SOURCE_CAPTURE = "797a21161e224181609f4113a74d719dde6ac9fa"
OLD_BASE_MAIN = "02dee32b2c9b25f166cbd77f8a895953e004f288"
PR5_BINDING = B / "pr5/context-registration-20261027/bundle-preparation-sonnet/run-r3/bundle-byte-binding.json"
COLLECTOR_PATHS = dict(runner="scripts/run_regression.py", environment_policy="scripts/ci_evidence.py",
                       assertion_capture="scripts/regression_reason_identity.py",
                       assertion_policy="scripts/regression_observation_policy.json")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_new(directory, name, value):
    with (directory / name).open("xb") as f:
        f.write(dump(value))


def stream_blobs(oids):
    """Yield (oid, sha256, size) for every blob via one cat-file --batch process; verifies the Git SHA-1."""
    import hashlib
    process = subprocess.Popen([GIT, "--no-lazy-fetch", "--git-dir=" + str(GD), "--work-tree=" + str(W), "cat-file", "--batch"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=ENV)
    import threading

    def feed():
        try:
            process.stdin.write(("\n".join(oids) + "\n").encode())
        finally:
            process.stdin.close()

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    result = {}
    for oid in oids:
        header = process.stdout.readline().decode().rstrip("\n")
        if header.endswith(" missing"):
            result[oid] = None
            continue
        kind, size = header.split()[1:]
        size = int(size)
        s1 = hashlib.sha1(b"blob " + str(size).encode() + b"\0")
        s2 = hashlib.sha256()
        left = size
        while left:
            block = process.stdout.read(min(left, 1 << 20))
            assert block
            s1.update(block)
            s2.update(block)
            left -= len(block)
        assert process.stdout.read(1) == b"\n"
        result[oid] = None if kind != "blob" else (s2.hexdigest(), size, s1.hexdigest() == oid)
    writer.join()
    assert process.wait() == 0
    return result


def verify_archives(zdir, adir, listing, run, head, label, findings):
    """Re-hash every zip against the GitHub digest, re-read every member, compare with extracted bytes and members.json."""
    manifest, archives = [], []
    for item in listing:
        name = item["name"]
        zpath = zdir / (name + ".zip")
        digest_zip, size = sha_file(zpath)
        ok = (digest_zip == item["digest"].removeprefix("sha256:") and size == item["size_in_bytes"]
              and item["workflow_run"]["id"] == run and item["workflow_run"]["head_sha"] == head and item["expired"] is False)
        if not ok:
            findings.append(dict(check=label + "_zip_digest", detail=name))
        recorded = load(zdir / (name + ".members.json"))
        actual, seen = [], set()
        with zipfile.ZipFile(zpath) as z:
            if z.testzip() is not None:
                findings.append(dict(check=label + "_zip_crc", detail=name))
            for m in z.infolist():
                rel = PurePosixPath(m.filename)
                mode = m.external_attr >> 16
                if rel.is_absolute() or ".." in rel.parts or "\\" in m.filename or m.filename in seen:
                    findings.append(dict(check=label + "_unsafe_member", detail=[name, m.filename]))
                    continue
                seen.add(m.filename)
                if m.is_dir():
                    continue
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    findings.append(dict(check=label + "_member_not_regular", detail=[name, m.filename, oct(mode)]))
                extracted = adir / name / m.filename
                h = hashlib_sha256_stream(z.open(m))
                if (extracted.is_symlink() or not extracted.is_file() or not extracted.resolve().is_relative_to((adir / name).resolve())
                        or sha_file(extracted) != (h, m.file_size)):
                    findings.append(dict(check=label + "_extracted_bytes", detail=[name, m.filename]))
                row = dict(path=m.filename, bytes=m.file_size, sha256=h, archive_mode=mode)
                actual.append(row)
                manifest.append(dict(artifact=name, archive_id=item["id"], original_path=str(extracted), **row))
        if actual != recorded:
            findings.append(dict(check=label + "_members_json", detail=name))
        on_disk = sorted(str(p.relative_to(adir / name)) for p in (adir / name).rglob("*") if p.is_file() or p.is_symlink())
        if on_disk != sorted(r["path"] for r in actual):
            findings.append(dict(check=label + "_extracted_file_set", detail=name))
        archives.append(dict(name=name, id=item["id"], bytes=size, sha256=digest_zip, github_digest_matches=ok, file_count=len(actual)))
    return archives, manifest


def hashlib_sha256_stream(stream):
    import hashlib
    h = hashlib.sha256()
    with stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(out):
    started = utc()
    findings, gaps = [], []
    stage_log = out / "stages.jsonl"

    def stage(name, **extra):
        with stage_log.open("a") as f:
            f.write(json.dumps(dict(at=utc(), stage=name, **extra), sort_keys=True) + "\n")
        print(name, file=sys.stderr, flush=True)

    guard_start = guard()
    write_new(out, "guard-before.json", guard_start)
    assert guard_start["head_ok"] and guard_start["candidates_match_main_plan"] and guard_start["config_equals_accepted_baseline"]

    # ---- fixed identity ----------------------------------------------------------------------------
    stage("identity")
    pr = load(C / "pr-initial.json")
    run = load(C / "run-initial.json")
    jobs_doc = load(C / "jobs-initial.json")
    jobs = jobs_doc["jobs"]
    assert pr["headRefOid"] == HEAD and pr["baseRefOid"] == TRUSTED and pr["number"] == 269
    assert "sha" not in (pr.get("head") if isinstance(pr.get("head"), dict) else {})
    assert run["id"] == RUN and run["run_attempt"] == 1 and run["head_sha"] == HEAD and run["event"] == "pull_request"
    pull = run["pull_requests"][0]
    assert pull["head"]["sha"] == HEAD and pull["base"]["sha"] == TRUSTED and pull["number"] == 269
    assert run["status"] == "completed" and run["conclusion"] == "failure"
    job_results = {j["name"]: j["conclusion"] for j in jobs}
    assert len(jobs) == 21 and all(j["status"] == "completed" for j in jobs) and len(job_results) == 21
    counts = dict(collections.Counter(job_results.values()))
    assert counts == {"success": 19, "failure": 2}, counts
    assert {n for n, c in job_results.items() if c == "failure"} == {"regression-admission", "ci-result"}
    refs = run.get("referenced_workflows") or []
    assert refs and all(r["sha"] == MERGE_OBJECT and r["ref"] == "refs/pull/269/merge" for r in refs)
    assert git("rev-parse", HEAD + "^{tree}", text=True).strip() == TREE
    assert git("rev-parse", TRUSTED + "^{tree}", text=True).strip() == TRUSTED_TREE
    head_parents = git("rev-list", "--parents", "-n", "1", HEAD, text=True).split()[1:]
    is_ancestor = git("merge-base", "--is-ancestor", TRUSTED, HEAD, check=False).returncode == 0
    merge_present = object_type(MERGE_OBJECT)
    merge_record = dict(
        commit=MERGE_OBJECT, ref="refs/pull/269/merge", locally_present=merge_present is not None, fetched=False,
        verified=False, fixed_head=HEAD, fixed_head_parents=head_parents, trusted_is_ancestor_of_head=is_ancestor,
        expectation=dict(parents=[TRUSTED, HEAD], tree=TREE, status="expected, NOT observed from the object",
                         basis="job log line 'HEAD is now at 253082c4 Merge fa5556de... into 4d6ebc71...' in regression-admission.txt; "
                               "run-initial.json referenced_workflows ref refs/pull/269/merge; inventory source_tree equals the head tree; "
                               "trusted main is an ancestor of the head, so a GitHub merge of head into base keeps the head tree"))
    log_text = (C / "regression-admission.txt").read_text(errors="replace")
    merge_log_line = [line for line in log_text.splitlines() if "HEAD is now at" in line]
    merge_record["job_log_checkout_line"] = merge_log_line[0].split("Z ", 1)[-1] if merge_log_line else None
    if merge_present == "commit":
        raw_commit = git("cat-file", "commit", MERGE_OBJECT).decode()
        header, _, message = raw_commit.partition("\n\n")
        merge_parents = git("rev-list", "--parents", "-n", "1", MERGE_OBJECT, text=True).split()[1:]
        merge_tree = git("rev-parse", MERGE_OBJECT + "^{tree}", text=True).strip()
        loose = GD.parents[1] / "objects" / MERGE_OBJECT[:2] / MERGE_OBJECT[2:]
        merge_record["expectation"]["status"] = "expected; subsequently observed in the local object (see observed_* fields)"
        merge_record.update(
            observed_parents=merge_parents, observed_tree=merge_tree, observed_committer=[l for l in header.splitlines() if l.startswith("committer ")],
            observed_message_first_line=message.strip().splitlines()[0] if message.strip() else "", has_gpgsig_header="gpgsig " in header,
            signature_verified=False, signature_note="the GitHub signature header is present but was not verified by this worker",
            loose_object_mtime_utc=(datetime.datetime.fromtimestamp(loose.stat().st_mtime, datetime.timezone.utc).isoformat() if loose.is_file() else None),
            presence_history="absent when the worker first checked (cat-file -t failed, about 2026-10-27T21:32Z); present at this run. The worker never fetched; the object was added to the shared object store by another process.",
            verified=merge_parents == [TRUSTED, HEAD] and merge_tree == TREE and message.strip() == "Merge %s into %s" % (HEAD, TRUSTED))
        if not merge_record["verified"]:
            findings.append(dict(check="merge_checkout_object_mismatch", detail=merge_record))
    else:
        gaps.append(dict(check="merge_checkout_object_missing", detail=merge_record))
    s_head = subprocess.run([GIT, "--no-lazy-fetch", "--git-dir=" + str(S / ".git"), "rev-parse", "HEAD"], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    source_export_head = s_head.stdout.decode().strip() if s_head.returncode == 0 else None
    if source_export_head != HEAD:
        findings.append(dict(check="source_export_private_head", detail=source_export_head))
    stage("identity-ok", merge_object_local=merge_present, merge_verified=merge_record.get("verified"), head_parents=head_parents)

    # ---- trusted / candidate code ------------------------------------------------------------------
    stage("code")
    code = out / "code"
    (code / "trusted").mkdir(parents=True)
    (code / "candidate").mkdir()
    code_rows = {}
    for name in ("regression_gate.py", "regression_context_registration.py", "run_trusted_regression_gate.py", "run_regression.py", "ci_evidence.py"):
        trusted = git("show", TRUSTED + ":scripts/" + name)
        candidate = git("show", HEAD + ":scripts/" + name)
        older = git("show", OLD_BASE_MAIN + ":scripts/" + name)
        (code / "trusted" / name).write_bytes(trusted)
        (code / "candidate" / name).write_bytes(candidate)
        code_rows[name] = dict(trusted_sha256=sha(trusted), candidate_sha256=sha(candidate), main_02dee32b_sha256=sha(older),
                               trusted_equals_candidate=trusted == candidate, trusted_equals_02dee32b=trusted == older,
                               source_export_equals_candidate=(S / "scripts" / name).read_bytes() == candidate)
    for name in ("regression_gate.py", "regression_context_registration.py", "run_trusted_regression_gate.py"):
        row = code_rows[name]
        if not (row["trusted_equals_candidate"] and row["trusted_equals_02dee32b"] and row["source_export_equals_candidate"]):
            findings.append(dict(check="gate_code_changed", detail=name))
    gate = load_module("trusted_gate_6", code / "trusted/regression_gate.py")
    reg = load_module("trusted_reg_6", code / "trusted/regression_context_registration.py")
    run_regression = load_module("trusted_run_regression_6", code / "trusted/run_regression.py")
    ci_candidate = load_module("candidate_ci_evidence_6", code / "candidate/ci_evidence.py")
    ci_trusted = load_module("trusted_ci_evidence_6", code / "trusted/ci_evidence.py")
    ci_summary = dict(excluded_equal=ci_candidate.EXCLUDED == ci_trusted.EXCLUDED,
                      kernel_selectors_equal=ci_candidate.KERNEL_SELECTORS == ci_trusted.KERNEL_SELECTORS,
                      candidate_changed_vs_trusted=code_rows["ci_evidence.py"]["trusted_equals_candidate"] is False)
    ci_diff = git("diff", TRUSTED, HEAD, "--", "scripts/ci_evidence.py", text=True)

    # ---- archives ------------------------------------------------------------------------------------
    stage("archives")
    listing = load(C / "artifacts-initial.json")["artifacts"]
    assert len(listing) == 13 and load(C / "artifacts-initial.json")["total_count"] == 13
    archives, manifest = verify_archives(D / "zips", D / "artifacts", listing, RUN, HEAD, "e1", findings)
    receipts = {r["name"]: r for r in load(D / "downloads-0-13.json")}
    for a in archives:
        if receipts[a["name"]]["sha256"] != a["sha256"] or receipts[a["name"]]["file_count"] != a["file_count"]:
            findings.append(dict(check="download_receipt", detail=a["name"]))
    old_listing = [a for a in load(D / "ci-40569530278/artifacts-initial.json")["artifacts"] if a["name"] == "python-regression-timings"]
    old_archives, old_manifest = verify_archives(D / "zips-274", D / "artifacts-274", old_listing, OLD_RUN, OLD_HEAD, "c274", findings)
    old_run = load(D / "ci-40569530278/run-initial.json")
    old_jobs = load(D / "ci-40569530278/jobs-initial.json")["jobs"]
    old_run_ok = (old_run["id"] == OLD_RUN and old_run["run_attempt"] == 1 and old_run["head_sha"] == OLD_HEAD
                  and old_run["status"] == "completed" and old_run["conclusion"] == "success" and len(old_jobs) == 21
                  and all(j["conclusion"] == "success" for j in old_jobs)
                  and all(r["ref"] == "refs/pull/274/merge" for r in old_run["referenced_workflows"]))
    if not old_run_ok:
        findings.append(dict(check="c274_run_identity", detail=None))
    write_new(out, "archive-members-verified.json", manifest + old_manifest)
    write_new(out, "archive-download-manifest.json", dict(
        e1=dict(run=RUN, attempt=1, head=HEAD, archives=archives, member_count=len(manifest)),
        c274=dict(run=OLD_RUN, attempt=1, head=OLD_HEAD, archives=old_archives, member_count=len(old_manifest),
                  referenced_workflow_ref="refs/pull/274/merge", merge_checkout=old_run["referenced_workflows"][0]["sha"])))
    stage("archives-ok", e1_archives=len(archives), e1_members=len(manifest), old_members=len(old_manifest))

    # ---- inventory vs Git tree and execution inputs -----------------------------------------------------
    stage("inventory")
    A = D / "artifacts"
    summary = load(A / "catalog-inventory/summary.json")
    before = load(A / "catalog-inventory/assets-before.json")
    after = load(A / "catalog-inventory/assets-after.json")
    if summary.get("scientific_execution") is not False or summary.get("errors") not in ([], None):
        findings.append(dict(check="catalog_summary", detail=dict(scientific_execution=summary.get("scientific_execution"), errors=summary.get("errors"))))
    for key in ("success", "reconciled", "construction_complete"):
        if summary.get(key) is not True:
            findings.append(dict(check="catalog_summary", detail={key: summary.get(key)}))
    if before != after:
        findings.append(dict(check="assets_before_after_differ", detail=None))
    if before["source_tree"] != TREE or before["dirty_paths"] or before["source_commit"] != MERGE_OBJECT:
        findings.append(dict(check="inventory_identity", detail=dict(tree=before["source_tree"], dirty=before["dirty_paths"], commit=before["source_commit"])))
    rows = {r["path"]: r for r in before["assets"]}
    assert len(rows) == len(before["assets"])
    expected, order = {}, []
    for line in git("ls-tree", "-r", "-z", HEAD).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        assert kind == "blob"
        expected[path.decode()] = (mode, oid)
        order.append(path.decode())
    assert set(rows) == set(expected), (len(rows), len(expected))
    mode_mismatch = [p for p, (m, o) in expected.items()
                     if (rows[p]["git_mode"], rows[p]["observed_blob_oid"], rows[p]["index_blob_oid"]) != (m, o, o)
                     or rows[p]["actual_mode"] != (0o755 if m == "100755" else 0o644)]
    if mode_mismatch:
        findings.append(dict(check="inventory_mode_oid", detail=mode_mismatch[:20]))
    stage("reading-blobs", unique=len({o for _, o in expected.values()}))
    unique_oids = sorted({o for _, o in expected.values()})
    blob_sha = stream_blobs(unique_oids)
    missing_blobs = [o for o, v in blob_sha.items() if v is None]
    bad_oid = [o for o, v in blob_sha.items() if v is not None and not v[2]]
    if missing_blobs or bad_oid:
        findings.append(dict(check="blob_missing_or_oid_mismatch", detail=dict(missing=missing_blobs[:10], bad=bad_oid[:10])))
    sha_mismatch = [p for p, (m, o) in expected.items() if blob_sha.get(o) and blob_sha[o][0] != rows[p]["sha256"]]
    if sha_mismatch:
        findings.append(dict(check="inventory_sha256_vs_git_blob", detail=sha_mismatch[:20]))
    stage("reading-source-export")
    source_mismatch = [p for p in expected if not (S / p).is_file() or (S / p).is_symlink() or sha_file(S / p)[0] != rows[p]["sha256"]]
    if source_mismatch:
        findings.append(dict(check="source_export_bytes", detail=source_mismatch[:20]))
    entries = [[p, rows[p]["git_mode"], rows[p]["actual_mode"], rows[p]["sha256"]] for p in order if p not in ci_candidate.EXCLUDED]
    bound_paths = {e[0] for e in entries}
    unbound = sorted(p for p in order if p not in ci_candidate.EXCLUDED and p not in bound_paths)
    input_list_sha = digest(entries)
    inventory_record = dict(
        inventory_paths=len(rows), git_blob_paths=len(expected), unique_blobs=len(unique_oids), blobs_read=len(blob_sha) - len(missing_blobs),
        bytes_read=sum(v[1] for v in blob_sha.values() if v), reused_from_other_run=0,
        reuse_note="full read of every blob in the fixed head tree; no reuse of #274 inventory rows was needed",
        source_export_files_hashed=len(expected), source_export_mismatch=len(source_mismatch),
        excluded_inputs=sorted(ci_candidate.EXCLUDED), execution_input_count=len(entries), execution_input_list_sha256=input_list_sha,
        execution_input_unbound=unbound, entry_order="git ls-tree order (= git ls-files order), as ci_evidence.fingerprint writes it",
        path_order_differs_from_Path_sort=[e[0] for e in entries] != sorted((e[0] for e in entries), key=PurePosixPath),
        source_commit=before["source_commit"], source_tree=before["source_tree"], dirty_paths=before["dirty_paths"],
        content_binding=before["content_binding"], source_commit_relationship=before["source_commit_relationship"])

    # derived-file binding: capture (797a2116 export) -> final head, and final-candidate receipts
    capture = {r["path"]: r for r in load(R7 / "assets.json")["assets"]}
    capture_commit = load(R7 / "assets.json")["source_commit"]
    delta_capture = set(git("diff", "--name-only", SOURCE_CAPTURE, HEAD, text=True).splitlines())
    binding = dict(matched=0, capture_to_final_deltas=[], unexpected=[], only_inventory=[], only_capture=[])
    for p in sorted(set(rows) | set(capture)):
        r, c = rows.get(p), capture.get(p)
        if r is None:
            binding["only_capture"].append(p)
        elif c is None:
            binding["only_inventory"].append(p)
        elif (c["sha256"], c["git_mode"], c["actual_mode"], c["git_blob_oid"]) == (r["sha256"], r["git_mode"], r["actual_mode"], r["observed_blob_oid"]):
            binding["matched"] += 1
        else:
            item = dict(path=p, capture_sha256=c["sha256"], inventory_sha256=r["sha256"], capture_oid=c["git_blob_oid"], inventory_oid=r["observed_blob_oid"])
            (binding["capture_to_final_deltas"] if p in delta_capture else binding["unexpected"]).append(item)
    if binding["unexpected"] or binding["only_inventory"] or binding["only_capture"] or capture_commit != SOURCE_CAPTURE:
        findings.append(dict(check="capture_assets_binding", detail={k: binding[k] for k in ("unexpected", "only_inventory", "only_capture")}))

    def recorded(label, mapping):
        out_rows = []
        for p, rec in sorted(mapping.items()):
            r = rows.get(p)
            git_sha = blob_sha[expected[p][1]][0] if p in expected and blob_sha.get(expected[p][1]) else None
            item = dict(path=p, recorded_sha256=rec, inventory_sha256=None if r is None else r["sha256"], git_sha256=git_sha,
                        match=r is not None and rec == r["sha256"] == git_sha)
            out_rows.append(item)
            if not item["match"]:
                findings.append(dict(check=label, detail=item))
        return out_rows

    final = load(R7 / "final-candidate.json")
    derive = load(R7 / "derive-acceptance.json")
    final_binding = recorded("final_candidate_binding", final["files"])
    derive_binding = recorded("derive_acceptance_binding", derive["files"])
    final_ok = final["commit"] == HEAD and final["tree"] == TREE and final["base"] == TRUSTED and final["merge_commit"] == SOURCE_CAPTURE
    if not final_ok:
        findings.append(dict(check="final_candidate_identity", detail=None))
    precheck = load(R7 / "precheck-acceptance.json")
    if not (precheck["candidate"] == HEAD and precheck["tree"] == TREE and precheck["base"] == TRUSTED):
        findings.append(dict(check="precheck_identity", detail=None))
    changed_vs_base = git("diff", "--name-only", TRUSTED, HEAD, text=True).splitlines()
    if sorted(changed_vs_base) != sorted(precheck["paths_vs_base"]) or sorted(changed_vs_base) != sorted(final["complete_paths"]):
        findings.append(dict(check="paths_vs_base", detail=dict(git=len(changed_vs_base), precheck=len(precheck["paths_vs_base"]), final=len(final["complete_paths"]))))
    inventory_record.update(
        capture_commit=capture_commit, capture_binding_counts=dict(matched=binding["matched"], capture_to_final_deltas=len(binding["capture_to_final_deltas"]),
                                                                   unexpected=len(binding["unexpected"])),
        capture_to_final_delta_paths=[i["path"] for i in binding["capture_to_final_deltas"]],
        final_candidate_files_bound=len(final_binding), final_candidate_all_match=all(i["match"] for i in final_binding),
        derive_acceptance_files_bound=len(derive_binding), derive_all_match=all(i["match"] for i in derive_binding),
        changed_paths_vs_trusted_base=len(changed_vs_base), precheck_not_rerun=True)
    stage("inventory-ok", mismatches=len(sha_mismatch), source_mismatch=len(source_mismatch))

    # ---- shards ---------------------------------------------------------------------------------------
    stage("shards")
    shards, report_paths, shard_ids, kernels = [], [], [], []
    for i in range(4):
        folder = A / ("python-regression-shard-%d" % i)
        report = load(folder / "regression-evidence/report.json")
        identity = load(folder / "regression-identity.json")
        receipt = load(folder / "regression-evidence/collection.json")
        try:
            ci_candidate.bound_report(report, identity, "%d-of-4" % i)
            bound_ok = True
        except (ValueError, KeyError, TypeError) as error:
            bound_ok = False
            findings.append(dict(check="bound_report", detail=dict(shard=i, error=str(error))))
        report_sha = sha_file(folder / "regression-evidence/report.json")[0]
        if not (receipt.get("valid") is True and receipt.get("cacheable") is False):
            findings.append(dict(check="collection", detail=dict(shard=i, valid=receipt.get("valid"), cacheable=receipt.get("cacheable"))))
        if receipt.get("report_sha256") != report_sha or receipt.get("identity_key") != identity.get("key"):
            findings.append(dict(check="collection_binding", detail=i))
        if identity.get("excluded") != sorted(ci_candidate.EXCLUDED) or identity.get("input_count") != len(entries):
            findings.append(dict(check="identity_inputs", detail=dict(shard=i, input_count=identity.get("input_count"), entries=len(entries))))
        env = identity["environment"]
        expected_key = digest(dict(version=3, report_schema_version=3, files=entries, environment=env))
        key_ok = expected_key == identity.get("key")
        if not key_ok:
            findings.append(dict(check="input_fingerprint", detail=dict(shard=i, expected=expected_key, actual=identity.get("key"))))
        try:
            subject_ok = ci_candidate.comparison_subject(entries, env) == identity.get("comparison_subject")
        except (TypeError, ValueError, KeyError) as error:
            subject_ok = False
            findings.append(dict(check="comparison_subject", detail=dict(shard=i, error=str(error))))
        if not subject_ok:
            findings.append(dict(check="comparison_subject", detail=i))
        kernel = sha_file(folder / "regression-build/evas-kernel")[0]
        kernels.append(kernel)
        variables = env.get("variables", {})
        selectors = {k: variables.get(k) for k in ci_candidate.KERNEL_SELECTORS}
        if not (kernel == env.get("kernel_sha256") == report["source_identity"].get("kernel_sha256")):
            findings.append(dict(check="kernel_identity", detail=dict(shard=i, file=kernel, identity=env.get("kernel_sha256"), report=report["source_identity"].get("kernel_sha256"))))
        events = [json.loads(line) for line in (folder / "regression-evidence/report.jsonl").read_text().splitlines() if line]
        stops = [e for e in events if e.get("event") == "stop"]
        stop_exact = [{k: v for k, v in e.items() if k != "event"} for e in stops] == report["tests"]
        start_exact = collections.Counter(e["id"] for e in events if e.get("event") == "start") == collections.Counter(report["selected_test_ids"])
        if not (stop_exact and start_exact):
            findings.append(dict(check="jsonl", detail=dict(shard=i, stop_exact=stop_exact, start_exact=start_exact)))
        ids = [t["id"] for t in report["tests"]]
        shard_ids.append(ids)
        if len(ids) != len(set(ids)) or report.get("tests_run") != len(ids):
            findings.append(dict(check="shard_method_accounting", detail=i))
        report_paths.append(folder / "regression-evidence/report.json")
        shards.append(dict(
            index=i, methods=report.get("tests_run"), conditions=sum(len(t["conditions"]) for t in report["tests"]),
            collection={k: receipt.get(k) for k in ("valid", "raw_exit", "cacheable", "raw_successful", "report_sha256", "identity_key")},
            input_fingerprint=identity.get("key"), fingerprint_matches_inventory=key_ok, comparison_subject_matches=subject_ok,
            input_count=identity.get("input_count"), kernel_file_sha256=kernel, kernel_identity_sha256=env.get("kernel_sha256"),
            kernel_report_sha256=report["source_identity"].get("kernel_sha256"), kernel_selectors=selectors,
            kernel_selectors_all_null=all(v is None for v in selectors.values()),
            build_parameters={k: variables.get(k) for k in ("CARGO_PROFILE_DEV_OPT_LEVEL", "CARGO_PROFILE_DEV_DEBUG_ASSERTIONS", "CARGO_PROFILE_DEV_OVERFLOW_CHECKS")},
            python=env.get("python"), rustc=env.get("rustc"), cargo=env.get("cargo"), platform=env.get("platform"),
            image_version=variables.get("ImageVersion"), jsonl_stop_exact=stop_exact, jsonl_start_exact=start_exact, bound_report=bound_ok,
            setup_skipped_test_ids=report.get("setup_skipped_test_ids"),
            build_stdout=dict(zip(("bytes", "sha256")[::-1], sha_file(folder / "regression-build/stdout.txt"))),
            build_stderr=dict(zip(("bytes", "sha256")[::-1], sha_file(folder / "regression-build/stderr.txt")))))
    flat = [x for ids in shard_ids for x in ids]
    if len(flat) != len(set(flat)):
        findings.append(dict(check="shard_overlap", detail=len(flat) - len(set(flat))))

    # ---- merged report -----------------------------------------------------------------------------------
    stage("merged")
    new_path = A / "python-regression-timings/python-regression.json"
    new = load(new_path)
    try:
        merged = run_regression.merge_reports(report_paths)
        merged_exact = merged == new
        if not merged_exact:
            findings.append(dict(check="merged_report", detail="merge_reports output differs from python-regression.json"))
    except (ValueError, KeyError, TypeError) as error:
        merged_exact = False
        findings.append(dict(check="merged_report", detail=str(error)))
    valid = gate.validate_report(new)
    if not valid.get("valid"):
        findings.append(dict(check="validate_report", detail=valid))
    collection = load(A / "python-regression-timings/regression-collection.json")
    collection_ok = (collection["collection_valid"] is True and collection["raw_successful"] == new["successful"] and collection["methods"] == new["tests_run"]
                     and collection["discovered"] == len(new["discovered_test_ids"])
                     and all(collection[k] == new[k] for k in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")))
    if not collection_ok:
        findings.append(dict(check="merged_collection_counters", detail=collection))
    old = load(OLD_REPORT)
    old_valid = gate.validate_report(old)
    if not old_valid.get("valid"):
        findings.append(dict(check="c274_validate_report", detail=old_valid))

    # ---- method / condition comparison against #274 ------------------------------------------------------------
    stage("compare")
    a = {t["id"]: t for t in old["tests"]}
    b = {t["id"]: t for t in new["tests"]}
    assert len(a) == len(old["tests"]) and len(b) == len(new["tests"])
    added, missing = sorted(set(b) - set(a)), sorted(set(a) - set(b))
    deltas, retention_diffs = [], []
    for method in sorted(set(a) & set(b)):
        pa = {c["id"]: gate._signature(c) for c in a[method]["conditions"]}
        pb = {c["id"]: gate._signature(c) for c in b[method]["conditions"]}
        if pa != pb or a[method]["outcome"] != b[method]["outcome"]:
            deltas.append(dict(id=method, old_outcome=a[method]["outcome"], new_outcome=b[method]["outcome"],
                               old_ids_only=sorted(pa.keys() - pb.keys()), new_ids_only=sorted(pb.keys() - pa.keys()),
                               same_id_signature_changes=sorted(c for c in pa.keys() & pb.keys() if pa[c] != pb[c])))
        ra = {c["id"]: gate._retention_condition(c) for c in a[method]["conditions"]}
        rb = {c["id"]: gate._retention_condition(c) for c in b[method]["conditions"]}
        if ra != rb:
            retention_diffs.append(method)
    cond_old = [c["id"] for t in old["tests"] for c in t["conditions"]]
    cond_new = [c["id"] for t in new["tests"] for c in t["conditions"]]
    outcomes_new = dict(collections.Counter(t["outcome"] for t in new["tests"]))
    outcomes_old = dict(collections.Counter(t["outcome"] for t in old["tests"]))
    cond_outcomes_new = dict(collections.Counter(c["outcome"] for t in new["tests"] for c in t["conditions"]))
    cond_outcomes_old = dict(collections.Counter(c["outcome"] for t in old["tests"] for c in t["conditions"]))
    nonpass = [dict(id=m, outcome=t["outcome"], condition_outcomes=dict(collections.Counter(c["outcome"] for c in t["conditions"])))
               for m, t in sorted(b.items()) if t["outcome"] not in ("passed", "expected_failure")]
    nonpass_old = [m for m, t in sorted(a.items()) if t["outcome"] not in ("passed", "expected_failure")]
    xfail = sorted(m for m, t in b.items() if t["outcome"] == "expected_failure")
    xfail_old = sorted(m for m, t in a.items() if t["outcome"] == "expected_failure")
    counters_new = {k: new.get(k) for k in gate.COUNTERS}
    counters_old = {k: old.get(k) for k in gate.COUNTERS}
    crit_old, crit_new = dict(old["source_identity"]["criteria_files"]), dict(new["source_identity"]["criteria_files"])
    criteria_diff = [p for p in sorted(set(crit_old) | set(crit_new)) if crit_old.get(p) != crit_new.get(p)]
    metadata_diff = [k for k in sorted(set(old["metadata"]) | set(new["metadata"])) if old["metadata"].get(k) != new["metadata"].get(k)]
    subject_new, subject_old = gate.execution_subject(new), gate.execution_subject(old)
    dut_new, dut_old = new["source_identity"]["dut_files"], old["source_identity"]["dut_files"]
    env_new = new["parts"][0]["source_identity"]["execution_identity"]["environment"]
    env_old = old["parts"][0]["source_identity"]["execution_identity"]["environment"]
    env_diff = [k for k in sorted(set(env_new) | set(env_old)) if k != "shard" and env_new.get(k) != env_old.get(k)]
    var_diff = [k for k in sorted(set(env_new["variables"]) | set(env_old["variables"])) if env_new["variables"].get(k) != env_old["variables"].get(k)]
    top_diff = [k for k in sorted(set(new) | set(old)) if k not in ("tests", "parts", "source_identity", "metadata") and new.get(k) != old.get(k)]
    if added or missing or deltas or retention_diffs or cond_old != cond_new:
        findings.append(dict(check="method_condition_comparison", detail=dict(added=len(added), missing=len(missing), deltas=len(deltas), retention=len(retention_diffs))))
    if criteria_diff != sorted(final["criteria_changes"]) or metadata_diff != ["collector_sha256", "criteria_id"]:
        findings.append(dict(check="criteria_or_metadata_change_unexpected", detail=dict(criteria=criteria_diff, metadata=metadata_diff)))

    # collector bytes at both revisions
    collector_new = {r: sha(git("show", HEAD + ":" + p)) for r, p in COLLECTOR_PATHS.items()}
    collector_old = {r: sha(git("show", TRUSTED + ":" + p)) for r, p in COLLECTOR_PATHS.items()}
    if digest(collector_new) != new["metadata"]["collector_sha256"] or digest(collector_old) != old["metadata"]["collector_sha256"]:
        findings.append(dict(check="collector_digest", detail=dict(new=digest(collector_new), old=digest(collector_old))))
    collector_changed = [r for r in COLLECTOR_PATHS if collector_new[r] != collector_old[r]]
    if collector_changed != ["environment_policy"]:
        findings.append(dict(check="collector_change_unexpected", detail=collector_changed))
    language_ok = rows["evas/capabilities/data/language-profile.json"]["sha256"] == new["metadata"]["language_profile"] == old["metadata"]["language_profile"]
    # #274 criteria/DUT against the #274 checkout tree (== the trusted base tree)
    base_blobs = {}
    for line in git("ls-tree", "-r", "-z", TRUSTED).split(b"\0"):
        if line:
            meta, path = line.split(b"\t", 1)
            base_blobs[path.decode()] = meta.decode().split()[2]
    old_unique = sorted({base_blobs[p] for p, _ in list(crit_old.items()) + list(dut_old)})
    old_blob_sha = stream_blobs(old_unique)
    old_criteria_ok = all(old_blob_sha[base_blobs[p]][0] == h for p, h in crit_old.items())
    old_dut_ok = all(old_blob_sha[base_blobs[p]][0] == h for p, h in dut_old)
    if not (old_criteria_ok and old_dut_ok):
        findings.append(dict(check="c274_source_fields_vs_base_blobs", detail=dict(criteria=old_criteria_ok, dut=old_dut_ok)))
    old_inventory = None
    if OLD_INVENTORY_ZIP.is_file() and OLD_INVENTORY.is_file():
        old_inventory = dict(zip_sha256=sha_file(OLD_INVENTORY_ZIP)[0], zip_matches_github_digest=sha_file(OLD_INVENTORY_ZIP)[0] == "9cf2f8ccca3eac356d73ac6bbe9946ace16dcff83fed2b54132ca6dc244ccc90",
                             source_tree=load(OLD_INVENTORY)["source_tree"], source_commit=load(OLD_INVENTORY)["source_commit"],
                             tree_equals_trusted_base_tree=load(OLD_INVENTORY)["source_tree"] == TRUSTED_TREE)

    def bind_fields(label, pairs, old_map):
        result = []
        for p, h in pairs:
            r = rows[p]
            if not (r["sha256"] == h == blob_sha[expected[p][1]][0] == sha_file(S / p)[0]):
                findings.append(dict(check=label + "_field_binding", detail=p))
            result.append(dict(path=p, sha256=h, inventory_oid=r["observed_blob_oid"], git_blob_oid=expected[p][1],
                               source_export_sha256_checked=True, changed_vs_c274=old_map.get(p) != h,
                               c274_sha256=old_map.get(p)))
        return result

    criteria_bound = bind_fields("criteria", new["source_identity"]["criteria_files"], crit_old)
    dut_bound = bind_fields("dut", new["source_identity"]["dut_files"], dict(dut_old))

    def selected(directories):
        result = []
        for directory in directories:
            for p in sorted(rows, key=PurePosixPath):
                if p.startswith(directory + "/") and not any(part in ("__pycache__", "target", "baselines", ".git", "runs") for part in PurePosixPath(p).parts):
                    result.append([p, rows[p]["sha256"]])
        return result

    manifests_exact = (selected(("evas/tests", "evas/validation", "evas/examples", "experiments")) == new["source_identity"]["criteria_files"]
                       and selected(("evas/src", "evas/rust_core")) == new["source_identity"]["dut_files"])
    if not manifests_exact:
        findings.append(dict(check="manifest_path_sets", detail=None))
    if digest(new["source_identity"]["criteria_files"]) != new["metadata"]["criteria_id"] or digest(old["source_identity"]["criteria_files"]) != old["metadata"]["criteria_id"]:
        findings.append(dict(check="criteria_id_digest", detail=None))
    changed_docs = [dict(path=p, c274_sha256=crit_old.get(p), e1_sha256=crit_new.get(p), source_export_bytes_checked=sha_file(S / p)[0] == crit_new.get(p),
                         git_blob_sha256_at_head=blob_sha[expected[p][1]][0], git_blob_sha256_at_base=sha(git("show", TRUSTED + ":" + p)))
                    for p in criteria_diff]
    if any(not d["source_export_bytes_checked"] or d["git_blob_sha256_at_head"] != d["e1_sha256"] or d["git_blob_sha256_at_base"] != d["c274_sha256"] for d in changed_docs):
        findings.append(dict(check="changed_criteria_docs_binding", detail=changed_docs))

    # ---- PR271 cross-reference and trusted baseline context --------------------------------------------------------
    stage("baseline")
    trusted_baseline_raw = git("show", TRUSTED + ":" + BASELINE_PATH)
    head_baseline_raw = git("show", HEAD + ":" + BASELINE_PATH)
    old_main_baseline_raw = git("show", OLD_BASE_MAIN + ":" + BASELINE_PATH)
    baseline = json.loads(trusted_baseline_raw)
    contexts = baseline["contexts"]
    baseline_record = dict(path=BASELINE_PATH, bytes=len(trusted_baseline_raw), sha256=sha(trusted_baseline_raw), contexts=len(contexts),
                           head_equals_trusted=head_baseline_raw == trusted_baseline_raw, equals_02dee32b=old_main_baseline_raw == trusted_baseline_raw,
                           git_oid_trusted=git("rev-parse", TRUSTED + ":" + BASELINE_PATH, text=True).strip(),
                           git_oid_head=git("rev-parse", HEAD + ":" + BASELINE_PATH, text=True).strip(), review_path_equal=(
                               git("rev-parse", TRUSTED + ":evas/validation/baselines/regression-v1.review.json", text=True)
                               == git("rev-parse", HEAD + ":evas/validation/baselines/regression-v1.review.json", text=True)))
    if not (baseline_record["bytes"] == 89943276 and baseline_record["contexts"] == 4 and baseline_record["head_equals_trusted"]):
        findings.append(dict(check="baseline_bytes_or_contexts", detail=baseline_record))
    old_context = gate._context(old)
    new_context = gate._context(new)
    matched_old, host_old = gate._matching_contexts(contexts, old_context)
    exact_old = [i for i, c in enumerate(contexts) if gate._json(c["context"]) == gate._json(old_context)]
    index_old = contexts.index(matched_old[0]) if len(matched_old) == 1 else None
    matched_new, host_new = gate._matching_contexts(contexts, new_context)
    old_compare = gate.compare_report(old, baseline)
    new_compare = gate.compare_report(new, baseline)
    expected_rejection = (new_compare["valid"] is True and new_compare["merge_allowed"] is False
                          and new_compare["differences"] == ["expected exactly one matching trusted baseline context"])
    if not (len(matched_old) == 1 and exact_old == [index_old] and host_old is None and old_compare["merge_allowed"] is True and old_compare["differences"] == []):
        findings.append(dict(check="c274_matches_one_context", detail=dict(matches=len(matched_old), exact=exact_old, host=host_old, compare=old_compare)))
    if not expected_rejection or matched_new:
        findings.append(dict(check="e1_gate_rejection_unexpected", detail=new_compare))
    expanded = gate._expand_baseline_observations(matched_old[0])
    obs_context = reg.observations(gate, expanded)
    obs_old = reg.observations(gate, old)
    obs_new = reg.observations(gate, new)
    context3_vs_old = dict(
        keys_equal=set(obs_context) == set(obs_old),
        retention_equal=all(gate._retention_condition(obs_context[k]) == gate._retention_condition(obs_old[k]) for k in obs_old if k in obs_context),
        outcome_equal=all(obs_context[k]["outcome"] == obs_old[k]["outcome"] for k in obs_old if k in obs_context),
        discovered_equal=expanded["discovered_test_ids"] == old["discovered_test_ids"],
        counters_equal=all(expanded.get(k) == old.get(k) for k in gate.COUNTERS))
    if not all(context3_vs_old.values()):
        findings.append(dict(check="c274_vs_trusted_context_observations", detail=context3_vs_old))
    pr271 = None
    if CROSS_REPORT.is_file():
        pr271_report = load(CROSS_REPORT)
        o271 = reg.observations(gate, pr271_report)
        pr271 = dict(path=str(CROSS_REPORT), sha256=sha_file(CROSS_REPORT)[0], context_equals_c274=gate._json(gate._context(pr271_report)) == gate._json(old_context),
                     criteria_id=pr271_report["metadata"]["criteria_id"], collector_sha256=pr271_report["metadata"]["collector_sha256"],
                     keys_equal_c274=set(o271) == set(obs_old),
                     retention_equal_c274=all(gate._retention_condition(o271[k]) == gate._retention_condition(obs_old[k]) for k in obs_old if k in o271),
                     matching_trusted_contexts=len(gate._matching_contexts(contexts, gate._context(pr271_report))[0]))
    # control observations of main (precheck, read-only reuse)
    precheck_diff = load(PRE / "context-diff-40584762318.json")
    precheck_obs = load(PRE / "e1-observations-40584762318.json")
    reuse = dict(context_diff_keys=sorted(k for k in precheck_diff if isinstance(k, str))[:20], observations_condition2_holds=precheck_obs.get("condition2_holds"),
                 observations_report_sha256=precheck_obs.get("e1_report_sha256"), old_conditions=precheck_obs.get("old_conditions"),
                 e1_conditions=precheck_obs.get("e1_conditions"), matched_context_index=precheck_obs.get("matched_context_index"))
    if precheck_obs.get("e1_report_sha256") != sha_file(new_path)[0] or precheck_obs.get("matched_context_index") != index_old:
        findings.append(dict(check="precheck_reuse_binding", detail=reuse))

    # ---- admission / bootstrap / bundle-source --------------------------------------------------------------
    stage("admission")
    adm = load(A / "python-regression-admission/regression-admission.json")
    boot = load(A / "python-regression-admission/regression-bootstrap-source.json")
    bsrc = load(A / "python-regression-admission/regression-bundle-source.json")
    workflow = git("show", HEAD + ":.github/workflows/numerical-assurance.yml").decode()
    pins = {}
    for key in ("BOOTSTRAP_COMMIT", "BOOTSTRAP_SHA256", "BOOTSTRAP_PATH"):
        marker = key + ' = "'
        start = workflow.find(marker)
        pins[key] = None if start < 0 else workflow[start + len(marker):].split('"', 1)[0]
    loader = b""
    boot_ok = False
    if pins["BOOTSTRAP_COMMIT"] and pins["BOOTSTRAP_PATH"] and object_type(pins["BOOTSTRAP_COMMIT"]) == "commit":
        loader = git("show", pins["BOOTSTRAP_COMMIT"] + ":" + pins["BOOTSTRAP_PATH"])
        tree_row = git("ls-tree", pins["BOOTSTRAP_COMMIT"], "--", pins["BOOTSTRAP_PATH"], text=True).split()
        boot_ok = (tree_row[0] == boot["bootstrap_mode"] and tree_row[2] == boot["bootstrap_blob"] and sha(loader) == boot["loader_sha256"] == boot["expected_loader_sha256"]
                   == pins["BOOTSTRAP_SHA256"] and boot["bootstrap_commit"] == pins["BOOTSTRAP_COMMIT"] and boot["bootstrap_path"] == pins["BOOTSTRAP_PATH"])
    else:
        gaps.append(dict(check="bootstrap_commit_missing", detail=pins))
    if not boot_ok:
        findings.append(dict(check="bootstrap_binding", detail=dict(pins=pins, receipt=boot)))
    trust = adm["trust"]
    trusted_gate_bytes = (code / "trusted/regression_gate.py").read_bytes()
    admission_ok = (
        adm["valid"] is True and adm["raw_successful"] is False and adm["merge_allowed"] is False and adm["semantic_qualification"] is False
        and adm["differences"] == ["expected exactly one matching trusted baseline context"] and adm["trusted_comparison"] == new_compare
        and adm["raw_successful"] == new["successful"] == new_compare["raw_successful"]
        and trust["trusted_commit"] == TRUSTED and trust["source"] == "event.pull_request.base.sha"
        and trust["code_sha256"] == sha(trusted_gate_bytes) == trust["transition_code_sha256"]
        and trust["baseline_sha256"] == sha(trusted_baseline_raw) and trust["candidate_baseline"].get("is_authority") is False
        and trust["candidate_baseline"].get("evaluated") is False
        and boot["event_trusted_commit"] == TRUSTED and boot["event_trust_source"] == "event.pull_request.base.sha"
        and bsrc == dict(schema_version=1, requested=False, materialized=False, trusted_commit=TRUSTED))
    if not admission_ok:
        findings.append(dict(check="admission_binding", detail=dict(trust=trust, boot=boot, bundle=bsrc)))
    admission_record = dict(
        artifact=dict(valid=adm["valid"], raw_successful=adm["raw_successful"], merge_allowed=adm["merge_allowed"],
                      semantic_qualification=adm["semantic_qualification"], differences=adm["differences"], transition=adm["transition"]),
        recomputed_trusted_comparison=new_compare, trusted_comparison_matches_artifact=adm["trusted_comparison"] == new_compare,
        expected_rejection_reproduced=expected_rejection, candidate_baseline_is_authority=trust["candidate_baseline"].get("is_authority"),
        trust=dict(trusted_commit=trust["trusted_commit"], source=trust["source"], code_sha256=trust["code_sha256"],
                   code_sha256_matches_trusted_blob=trust["code_sha256"] == sha(trusted_gate_bytes),
                   baseline_sha256=trust["baseline_sha256"], baseline_sha256_matches_trusted_blob=trust["baseline_sha256"] == sha(trusted_baseline_raw)),
        shell=dict(pins_from_head_workflow=pins, loader_sha256=sha(loader) if loader else None, loader_matches_pin_and_receipt=boot_ok,
                   bootstrap_receipt=boot, bootstrap_exit_note="1 = the trusted loader reports the expected gate rejection, not a loader fault"),
        bundle_source=bsrc, baseline=baseline_record, merge_checkout=merge_record,
        referenced_workflow_objects=[dict(path=r["path"], sha=r["sha"], ref=r["ref"], locally_present=object_type(r["sha"]) is not None, fetched=False) for r in refs],
        c274_trusted_comparison=dict(valid=old_compare["valid"], merge_allowed=old_compare["merge_allowed"], differences=old_compare["differences"],
                                     host_runtime_difference=old_compare.get("host_runtime_difference"), matched_context_index=index_old,
                                     matched_exactly=exact_old == [index_old]),
        c274_vs_context_observations=context3_vs_old, pr271_cross_reference=pr271, e1_gate_matching_contexts=len(matched_new))

    # ---- runner pool facts recorded by main (not re-derived) ---------------------------------------------
    rerun = load(C / "rerun-log.json")
    runner_pool = dict(source="rerun-log.json written by main control; job logs were not downloaded by this worker",
                       attempt=rerun[-1]["attempt"], same_pool=rerun[-1]["same_pool"],
                       provisioner_header_versions={k: v["header"] for k, v in rerun[-1]["pools"].items()},
                       report_ImageVersion_variable=sorted({s["image_version"] for s in shards} | {env_old["variables"]["ImageVersion"]}),
                       note="log header Version 20261012.334.1 (provisioner) differs from the ImageVersion variable 20261023.334.3 recorded in the reports; "
                            "reports of E1 and #274 carry identical runtime profiles")

    roles = build_roles(manifest, shards)
    write_new(out, "role-original-index.json", roles)
    write_new(out, "inventory-verification.json", dict(inventory=inventory_record, final_candidate_binding=final_binding, derive_binding=derive_binding,
                                                         capture_to_final_deltas=binding["capture_to_final_deltas"]))
    write_new(out, "admission-verification.json", admission_record)
    write_new(out, "condition-deltas.json", deltas)
    write_new(out, "nonpass-methods.json", dict(nonpass=nonpass, expected_failure_methods=xfail))
    write_new(out, "source-identity-field-bindings.json", dict(
        criteria_files=criteria_bound, dut_files=dut_bound, criteria_id=new["metadata"]["criteria_id"], c274_criteria_id=old["metadata"]["criteria_id"],
        criteria_same_as_c274=new["metadata"]["criteria_id"] == old["metadata"]["criteria_id"], changed_criteria_documents=changed_docs,
        collector=dict(paths=COLLECTOR_PATHS, e1_source_sha256=collector_new, c274_source_sha256=collector_old, changed_roles=collector_changed,
                       e1_collector_sha256=new["metadata"]["collector_sha256"], c274_collector_sha256=old["metadata"]["collector_sha256"],
                       ci_evidence_diff=ci_diff, ci_evidence_summary=ci_summary),
        language_profile=new["metadata"]["language_profile"], language_profile_matches_inventory_and_c274=language_ok,
        invocation=new["metadata"]["invocation"], runtime_profile_equal_c274=new["metadata"]["runtime_profile"] == old["metadata"]["runtime_profile"],
        invocation_equal_c274=new["metadata"]["invocation"] == old["metadata"]["invocation"], manifest_path_sets_exact=manifests_exact,
        c274_fields_vs_base_blobs=dict(criteria=old_criteria_ok, dut=old_dut_ok, c274_inventory=old_inventory),
        label="criteria identity differs from #274 by exactly the PR6 documents; each field is bound to the actual fa5556de blobs and the S export"))

    pr5 = load(PR5_BINDING)
    pr5_kernel = [f for f in pr5["files"] if f["path"] == "bundle/kernel_binary"][0]
    kernel_record = dict(sha256=subject_new["kernel_sha256"], bytes=sha_file(A / "python-regression-shard-0/regression-build/evas-kernel")[1],
                         four_shards_identical=len(set(kernels)) == 1, equals_c274_kernel=subject_new["kernel_sha256"] == subject_old["kernel_sha256"],
                         equals_pr5_bundle_kernel=pr5_kernel["sha256"] == subject_new["kernel_sha256"], pr5_bundle_kernel_bytes=pr5_kernel["bytes"],
                         pr5_bundle_kernel_path=str(PR5_BINDING.parent / "bundle/kernel_binary"), executed=False)
    if not (kernel_record["four_shards_identical"] and kernel_record["equals_c274_kernel"] and subject_new["kernel_sha256"] == kernels[0]):
        findings.append(dict(check="kernel_identity_cross", detail=kernel_record))

    verification = dict(
        run=RUN, attempt=1, run_conclusion=run["conclusion"], run_status=run["status"], run_html=run["html_url"], run_started_at=run["run_started_at"],
        run_updated_at=run["updated_at"], head=HEAD, tree=TREE, parents=head_parents, trusted_base=TRUSTED, trusted_tree=TRUSTED_TREE,
        pr_field_source="headRefOid/baseRefOid on the saved flat gh pr view JSON", pr_number=pr["number"], pr_state=pr["state"], pr_mergeable=pr["mergeable"],
        job_count=len(jobs), job_results=job_results, job_conclusion_counts=counts, host_job_success_is_scientific_qualification=False,
        archives=archives, archive_members=len(manifest), c274=dict(run=OLD_RUN, head=OLD_HEAD, conclusion=old_run["conclusion"], html=old_run["html_url"],
                                                                     archive=old_archives, members=len(old_manifest), run_identity_ok=old_run_ok),
        merge_checkout=merge_record, source_export_private_git_head=source_export_head, code=code_rows, ci_evidence=ci_summary, inventory=inventory_record, shards=shards,
        shard_method_sum=sum(s["methods"] for s in shards), shard_condition_sum=sum(s["conditions"] for s in shards), shard_ids_disjoint=len(flat) == len(set(flat)),
        merged_exact=merged_exact, report_valid=valid.get("valid"), merged_collection_counters_match=collection_ok,
        raw_sha256=sha_file(new_path)[0], c274_raw_sha256=sha_file(OLD_REPORT)[0],
        methods=len(b), c274_methods=len(a), conditions=len(cond_new), c274_conditions=len(cond_old), unique_condition_ids=len(set(cond_new)),
        method_outcomes=outcomes_new, c274_method_outcomes=outcomes_old, condition_outcomes=cond_outcomes_new, c274_condition_outcomes=cond_outcomes_old,
        nonpass_method_count=len(nonpass), expected_failure_method_count=len(xfail), nonpass_ids_equal_c274=[r["id"] for r in nonpass] == nonpass_old,
        expected_failure_ids_equal_c274=xfail == xfail_old, unittest_condition_counters=dict(failures=new["failures"], errors=new["errors"], skipped=new["skipped"],
                                                                                        expected_failures=new["expected_failures"], unexpected_successes=new["unexpected_successes"]),
        c274_unittest_condition_counters=dict(failures=old["failures"], errors=old["errors"], skipped=old["skipped"], expected_failures=old["expected_failures"],
                                              unexpected_successes=old["unexpected_successes"]),
        gate_counters=counters_new, gate_counters_equal_c274=counters_new == counters_old, raw_successful=new["successful"], c274_raw_successful=old["successful"],
        methods_added_vs_c274=added, methods_missing_vs_c274=missing, method_outcome_changes=[d["id"] for d in deltas if d["old_outcome"] != d["new_outcome"]],
        condition_delta_methods=[d["id"] for d in deltas], retention_signature_diff_methods=retention_diffs,
        condition_ids_equal_and_ordered=cond_old == cond_new, discovered_equal=new["discovered_test_ids"] == old["discovered_test_ids"],
        selected_equal=[t for p in new["parts"] for t in p["selected_test_ids"]] == [t for p in old["parts"] for t in p["selected_test_ids"]],
        assignment_equal=new["assignment"] == old["assignment"], fixtures=dict(new=len(new["fixtures"]), c274=len(old["fixtures"])),
        setup_skipped=dict(new=new["setup_skipped_test_ids"], c274=old["setup_skipped_test_ids"]),
        top_level_keys_changed_vs_c274=top_diff, criteria_changed_paths_vs_c274=criteria_diff, metadata_changed_keys_vs_c274=metadata_diff,
        criteria_id=new["metadata"]["criteria_id"], c274_criteria_id=old["metadata"]["criteria_id"], collector_sha256=new["metadata"]["collector_sha256"],
        c274_collector_sha256=old["metadata"]["collector_sha256"], collector_changed_roles=collector_changed, language_profile_ok=language_ok,
        dut_files_count=len(dut_new), dut_files_equal_c274=dut_new == dut_old, dut_files_sha256=subject_new["dut_files_sha256"],
        c274_dut_files_sha256=subject_old["dut_files_sha256"], kernel=kernel_record, kernel_selectors_all_null=all(s["kernel_selectors_all_null"] for s in shards),
        build_parameters=shards[0]["build_parameters"], environment_keys_changed_vs_c274=env_diff, environment_variables_changed_vs_c274=var_diff,
        execution_subject_environment_equal_c274=subject_new["comparison_subject"]["environment"] == subject_old["comparison_subject"]["environment"],
        comparison_subject_files_sha256=dict(new=subject_new["comparison_subject"]["files_sha256"], c274=subject_old["comparison_subject"]["files_sha256"]),
        input_count=dict(new=subject_new["comparison_subject"]["input_count"], c274=subject_old["comparison_subject"]["input_count"]),
        runner_pool=runner_pool, baseline=baseline_record, c274_matched_context_index=index_old,
        admission=dict(artifact_valid=adm["valid"], raw_successful=adm["raw_successful"], merge_allowed=adm["merge_allowed"], semantic_qualification=adm["semantic_qualification"],
                       differences=adm["differences"], expected_rejection_reproduced=expected_rejection, binding_ok=admission_ok, bootstrap_ok=boot_ok,
                       bundle_requested=bsrc["requested"], bundle_materialized=bsrc["materialized"]),
        precheck_reuse=reuse, role_index_missing=roles["missing_roles"],
        scientific_execution=False, scientific_qualification=False, semantic_qualification=False, merge_permission=False,
        identity_findings=findings, open_gaps=gaps, started_at_utc=started)
    write_new(out, "raw-verification.json", verification)
    guard_end = guard()
    write_new(out, "guard-after.json", guard_end)
    guard_equal = guard_end == guard_start
    if not guard_equal:
        findings.append(dict(check="real_workspace_guard_changed", detail=None))
    verification["guard_equal_before_after"] = guard_equal
    verification["finished_at_utc"] = utc()
    (out / "raw-verification.json").write_bytes(dump(verification))
    print(json.dumps(dict(methods=len(b), conditions=len(cond_new), outcomes=outcomes_new, findings=[f["check"] for f in findings], gaps=[g["check"] for g in gaps],
                          archive_members=len(manifest), criteria_changed=criteria_diff, guard_equal=guard_equal, blobs=len(unique_oids)), indent=1))


def build_roles(manifest, shards):
    roles = dict(report=[], shard_reports=[], snapshot_manifest_inputs=[], dut_build=[], kernel_binary=[], collector_manifest_inputs=[], artifact_manifest_inputs=[],
                 stdout=[], stderr=[], composition_recipe_inputs=[])
    for m in manifest:
        art, name = m["artifact"], m["path"]
        if art == "python-regression-timings":
            roles["report"].append(m)
        if art.startswith("python-regression-shard-"):
            if name == "regression-evidence/report.json":
                roles["shard_reports"].append(m)
            if name == "regression-identity.json":
                roles["snapshot_manifest_inputs"].append(m)
                roles["composition_recipe_inputs"].append(m)
            if name.startswith("regression-build/") and name != "regression-build/evas-kernel":
                roles["dut_build"].append(m)
            if name == "regression-build/evas-kernel":
                roles["kernel_binary"].append(m)
            if name == "regression-evidence/stdout.txt":
                roles["stdout"].append(m)
            if name == "regression-evidence/stderr.txt":
                roles["stderr"].append(m)
        if art == "catalog-inventory" and name in ("assets-before.json", "assets-after.json"):
            roles["snapshot_manifest_inputs"].append(m)
        roles["artifact_manifest_inputs"].append(m) if art == "python-regression-timings" or name in ("regression-evidence/report.json",) else None
    for role, path in COLLECTOR_PATHS.items():
        roles["collector_manifest_inputs"].append(dict(role=role, source_export_path=str(S / path), git_path=path, sha256=sha_file(S / path)[0]))
    missing = [k for k, v in roles.items() if not v]
    return dict(roles=roles, missing_roles=missing, derived_roles=["composition_recipe", "snapshot_manifest", "dut_build", "collector_manifest", "artifact_manifest"],
                original_byte_roles=["report.json", "kernel_binary", "stdout", "stderr", "shard_reports"], not_a_bundle=True, not_an_authorization=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = safe_new_directory(args.output)
    target.mkdir()
    try:
        main(target)
    except BaseException:
        (target / "failure.json").write_bytes(dump(dict(at=utc(), traceback=traceback.format_exc(), kept="all partial outputs retained")))
        raise
