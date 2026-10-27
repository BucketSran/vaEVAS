"""Independently verify a bundle prepared by prepare_bundle.py (PR266 head 983b, run 40454789703).

Usage: python3 -B verify.py --prepared run-r3 --output NEW-UNUSED-DIRECTORY   (both under this folder)

Re-derives every consumed-input digest, the ten role files, the stream boundaries, the draft
obligation map and the proof from the original inputs and trusted Git blobs, compares them byte for
byte, runs the production evidence/mapping functions on the bytes found on disk, and exercises
expected rejections (tampered copies are in memory only). Writes only inside the new output folder.
Nothing here authorizes, approves, registers or qualifies anything.
"""
import argparse
import datetime
import hashlib
import importlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

D = Path(__file__).resolve().parent
B = D.parents[2]
C = B / "pr5/comparison-continuation-fix-20261027/fixture-root-finalization/ci-40454789703"
I = C / "raw-intake-sol"
A = I / "artifacts"
OLD_REPORT = B / ("pr4/post-review-integration-20261027/catalog-index-recovery-20261027/ci-40429826545/"
                  "raw-intake-grok/artifacts/python-regression-timings/python-regression.json")
W = Path("/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night")
GD = Path("/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night")
GIT = "/usr/bin/git"
REAL_HEAD = "168a9d7a4305e7ce21d1577b4ca1dda65beae4ce"
HEAD = "983b1ef6a4804c29483279ca34a7a92fce56a858"
TREE = "7a99e40b4a58e00c138e4c721f3deaab1bdb2ba6"
TRUSTED = "e10e1af5796f0cc7af3b6b5f5d26c420c0c03325"
RUN_URL = "https://github.com/BucketSran/vaEVAS/actions/runs/40454789703"
MERGE_OBJECT = "33ed0fa1a516627d7d418fcf563a47a0d9e272b0"
NEW_SHA = "531016babc8a288fd130f3af99364dbcaf20f25c225201d1f35e73e6b0a6c995"
OLD_SHA = "9097c8dce35461961b76782234c75e67d11f2c33a4f90d3abd98cc947ec9d981"
KERNEL = "b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe"
INPUT_LIST = "d6079c1ebd89a9d944e4643e289dd8f82365b1144fd044d3f46b55fa207fda55"
ROLES = ("composition_recipe", "snapshot_manifest", "dut_build", "kernel_binary", "collector_manifest",
         "artifact_manifest", "stdout", "stderr", "shard_reports")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
CHECKS = {}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(path):
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as s:
        for block in iter(lambda: s.read(1 << 20), b""):
            h.update(block)
            n += len(block)
    return h.hexdigest(), n


def digest(v):
    return sha(json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def dump(v):
    return (json.dumps(v, ensure_ascii=False, indent=2) + "\n").encode()


def git(*argv):
    return subprocess.run([GIT, "--no-lazy-fetch", "--git-dir=" + str(GD), "--work-tree=" + str(W), *argv],
                          env=ENV, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def check(name, ok, **detail):
    CHECKS[name] = dict(ok=bool(ok), **detail)
    return bool(ok)


def new_dir(argument, must_exist=False):
    p = Path(os.path.abspath(Path(argument) if Path(argument).is_absolute() else D / argument))
    if D not in p.parents:
        raise SystemExit("refusing path outside " + str(D))
    if must_exist:
        if p.is_symlink() or not p.is_dir():
            raise SystemExit("prepared path is not a plain directory")
        return p
    if os.path.lexists(p):
        raise SystemExit("refusing existing path: " + str(p))
    walk = D
    for part in p.relative_to(D).parts[:-1]:
        walk = walk / part
        if walk.is_symlink() or not walk.is_dir():
            raise SystemExit("refusing symlink or missing parent: " + str(walk))
    return p


def guard(rows=None):
    assert git("rev-parse", "HEAD").decode().strip() == REAL_HEAD
    if rows is None:
        plan = json.loads((B / "main-plan.json").read_bytes())
        rows = [dict(path=x["path"], sha256=x["sha256"]) for x in plan["handoff"]["files"] if x["path"].startswith("evas/tests/")]
    assert len(rows) == 20
    state = {str(p): sha_file(p)[0] for p in (GD / "HEAD", GD / "index", GD.parents[1] / "config", GD.parents[1] / "packed-refs") if p.exists()}
    files = {r["path"]: sha((W / r["path"]).read_bytes()) for r in rows}
    assert all(files[r["path"]] == r["sha256"] for r in rows)
    return rows, dict(head=REAL_HEAD, git_state_sha256=state, candidate_sha256=files)


def verify(P, out):
    plan_rows, guard_start = guard()
    receipt = json.loads((P / "receipt.json").read_bytes())
    # trusted code: re-read from Git and require the prepared copy to match, then import that copy
    code = P / "code/trusted"
    for name in ("regression_gate.py", "regression_context_registration.py", "ci_evidence.py"):
        blob = git("show", TRUSTED + ":scripts/" + name)
        check("trusted_code_" + name, (code / name).read_bytes() == blob == git("show", HEAD + ":scripts/" + name)
              == (C.parent / "source/scripts" / name).read_bytes(), sha256=sha(blob))
    sys.path.insert(0, str(code))
    gate = importlib.import_module("regression_gate")
    reg = importlib.import_module("regression_context_registration")
    ci = importlib.import_module("ci_evidence")

    # consumed inputs: hash again what prepare actually consumed
    changed = []
    for path, row in receipt["consumed_inputs"].items():
        h, n = sha_file(path)
        if (h, n) != (row["sha256"], row["bytes"]):
            changed.append(path)
    check("consumed_inputs_unchanged", not changed and len(receipt["consumed_inputs"]) >= 25, count=len(receipt["consumed_inputs"]), changed=changed)

    bundle = P / "bundle"
    names = sorted(p.name for p in bundle.iterdir())
    check("ten_role_files", names == sorted(("report.json",) + ROLES) and all((bundle / n).is_file() and not (bundle / n).is_symlink() for n in names), names=names)
    raw = {n: (bundle / n).read_bytes() for n in names if n != "kernel_binary"}

    report_bytes = (A / "python-regression-timings/python-regression.json").read_bytes()
    check("report_original_bytes", raw["report.json"] == report_bytes and sha(report_bytes) == NEW_SHA)
    report = json.loads(report_bytes)
    old_bytes = OLD_REPORT.read_bytes()
    check("old_report_identity", sha(old_bytes) == OLD_SHA)
    old = json.loads(old_bytes)
    subject, old_subject = gate.execution_subject(report), gate.execution_subject(old)
    check("report_valid_whole_merged", gate.validate_report(report)["valid"] and gate._whole(report) and report["merged"] and report["shard_count"] == 4)

    # snapshot
    assets = json.loads((A / "catalog-inventory/assets-before.json").read_bytes())
    rows = {r["path"]: r for r in assets["assets"]}
    entries = []
    for line in git("ls-tree", "-r", "-z", HEAD).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        path = path.decode()
        if path in ci.EXCLUDED:
            continue
        r = rows[path]
        assert kind == "blob" and (r["git_mode"], r["observed_blob_oid"], r["index_blob_oid"]) == (mode, oid, oid)
        entries.append([path, r["git_mode"], r["actual_mode"], r["sha256"]])
    snap = json.loads(raw["snapshot_manifest"])
    check("snapshot_entries_and_order", snap == dict(schema_version=1, entries=entries) and raw["snapshot_manifest"] == dump(dict(schema_version=1, entries=entries))
          and len(entries) == 49562 and digest(entries) == INPUT_LIST, count=len(entries))
    keys = []
    for i in range(4):
        identity = json.loads((A / f"python-regression-shard-{i}/regression-identity.json").read_bytes())
        keys.append(digest(dict(version=3, report_schema_version=3, files=snap["entries"], environment=identity["environment"])) == identity["key"])
    check("snapshot_reproduces_four_shard_identity_keys", all(keys), per_shard=keys)
    check("snapshot_order_is_not_path_sorted", [e[0] for e in entries] != sorted((e[0] for e in entries), key=PurePosixPath),
          note="git ls-files order reproduces the CI identity keys; Path or string re-sorting would not")

    # collector, kernel, recipe
    paths = dict(runner="scripts/run_regression.py", environment_policy="scripts/ci_evidence.py",
                 assertion_capture="scripts/regression_reason_identity.py", assertion_policy="scripts/regression_observation_policy.json")
    collector = {role: sha(git("show", HEAD + ":" + p)) for role, p in paths.items()}
    check("collector_manifest", raw["collector_manifest"] == dump(collector) and digest(collector) == report["metadata"]["collector_sha256"]
          and all({e[0]: e[3] for e in entries}[p] == collector[r] for r, p in paths.items()), collector=collector)
    ks = [sha_file(A / f"python-regression-shard-{i}/regression-build/evas-kernel") for i in range(4)]
    kh, kn = sha_file(bundle / "kernel_binary")
    check("kernel_binary", kh == KERNEL == subject["kernel_sha256"] and all(k == (KERNEL, kn) for k in ks)
          and not ((bundle / "kernel_binary").stat().st_mode & 0o111), bytes=kn, executable_bit=bool((bundle / "kernel_binary").stat().st_mode & 0o111))
    recipe = json.loads(raw["composition_recipe"])
    profile = {k: report["metadata"][k] for k in ("language_profile", "runtime_profile", "invocation")}
    check("composition_recipe", raw["composition_recipe"] == dump(dict(
        schema_version=1, dut_revision=recipe["dut_revision"], snapshot_sha256=sha(raw["snapshot_manifest"]),
        dut_manifest_sha256=subject["dut_files_sha256"], kernel_sha256=subject["kernel_sha256"],
        criteria_id=report["metadata"]["criteria_id"], collector_sha256=report["metadata"]["collector_sha256"],
        profile_sha256=digest(profile))) and recipe["dut_revision"] == "842bde7101164330fa03e7aee58b45d1789cbed1")
    build = json.loads(raw["dut_build"])
    texts = build["toolchain_reference"] + build["build_reference"]
    check("dut_build_bindings", set(build) == {"schema_version", "dut_revision", "dut_manifest_sha256", "kernel_sha256", "toolchain_reference", "build_reference"}
          and build["kernel_sha256"] == KERNEL and build["dut_manifest_sha256"] == subject["dut_files_sha256"] and RUN_URL in texts
          and MERGE_OBJECT in texts and "NOT locally verified" in texts and KERNEL in texts
          and all(sha((A / f"python-regression-shard-{i}/regression-identity.json").read_bytes()) in texts for i in range(4))
          and all(sha((A / f"python-regression-shard-{i}/regression-build/stderr.txt").read_bytes())[:16] in texts for i in range(4)))

    # streams and shard reports
    shard_bytes = [(A / f"python-regression-shard-{i}/regression-evidence/report.json").read_bytes() for i in range(4)]
    check("shard_reports_exact_text_and_order", [t.encode("utf-8") for t in json.loads(raw["shard_reports"])] == shard_bytes
          and raw["shard_reports"] == dump([b.decode("utf-8") for b in shard_bytes])
          and [json.loads(b)["shard_index"] for b in shard_bytes] == [0, 1, 2, 3])
    boundaries = json.loads((P / "stream-boundaries.json").read_bytes())
    for role in ("stdout", "stderr"):
        parts = [(A / f"python-regression-shard-{i}/regression-evidence/{role}.txt").read_bytes() for i in range(4)]
        rows_b = boundaries[role]["parts"]
        offs, o = [], 0
        for x in parts:
            offs.append(o)
            o += len(x)
        check("stream_" + role, raw[role] == b"".join(parts) and [r["offset"] for r in rows_b] == offs and [r["bytes"] for r in rows_b] == [len(x) for x in parts]
              and [r["sha256"] for r in rows_b] == [sha(x) for x in parts] and boundaries[role]["total_sha256"] == sha(raw[role])
              and boundaries[role]["total_bytes"] == len(raw[role]), lengths=[len(x) for x in parts], total=len(raw[role]))
    manifest = json.loads(raw["artifact_manifest"])
    check("artifact_manifest", manifest["raw_report_sha256"] == NEW_SHA and manifest["stdout_sha256"] == sha(raw["stdout"])
          and manifest["stderr_sha256"] == sha(raw["stderr"]) and manifest["shard_report_sha256"] == [sha(b) for b in shard_bytes]
          and RUN_URL in manifest["capture_reference"] and sha_file(I / "artifact-download-receipt.json")[0] in manifest["capture_reference"])

    # production functions on bytes found on disk
    kernel_bytes = (bundle / "kernel_binary").read_bytes()
    blobs = {role: (kernel_bytes if role == "kernel_binary" else raw[role]) for role in ROLES}
    auth = dict(artifacts={r: dict(sha256=sha(blobs[r]), locator="bundle/" + r) for r in ROLES},
                current_dut=dict(manifest_sha256=old_subject["dut_files_sha256"], kernel_sha256=old_subject["kernel_sha256"]),
                e1=dict(raw_sha256=sha(report_bytes), execution_subject=subject))
    binding = json.loads((P / "bundle-byte-binding.json").read_bytes())
    entry = dict(source_identity=binding["entry_provenance_preview"])
    try:
        reg.evidence(auth, blobs, gate, report, entry, old_subject)
        check("production_evidence_function", True, note="in-memory harness authorization; no authorization file exists")
    except Exception as error:  # noqa: BLE001
        check("production_evidence_function", False, error=repr(error))

    # obligation map
    mapping_bytes = (P / "obligation-map-draft.json").read_bytes()
    mapping = json.loads(mapping_bytes)
    a, b = {t["id"]: t for t in old["tests"]}, {t["id"]: t for t in report["tests"]}
    expected, unmapped = [], []
    for owner in a:
        new_by_id = {c["id"]: c for c in b[owner]["conditions"]}
        for before in a[owner]["conditions"]:
            after = new_by_id.get(before["id"])
            if (after is None or before["outcome"] != after["outcome"]
                    or gate._retention_condition(before) != gate._retention_condition(after) or a[owner]["outcome"] != b[owner]["outcome"]):
                unmapped.append([owner, before["id"]])
                continue
            expected.append(dict(old_owner=owner, old_condition=before["id"], old_signature_sha256=reg.digest(gate._retention_condition(before)),
                                 new_owner=owner, new_condition=after["id"], new_signature_sha256=reg.digest(gate._retention_condition(after)),
                                 classification="preserved", review_reference=mapping[0]["review_reference"], attribution=None))
    check("obligation_map_recomputed_exact", not unmapped and mapping == expected and len(mapping) == 7737 and mapping_bytes == (json.dumps(expected, indent=2) + "\n").encode(),
          unmapped=len(unmapped), entries=len(mapping))
    check("obligation_map_draft_label", all("DRAFT" in m["review_reference"] and "PENDING" in m["review_reference"] and m["attribution"] is None
                                           and m["classification"] == "preserved" for m in mapping))
    check("obligation_counts", len(a) == len(b) == 3257 and set(a) == set(b) and sum(len(t["conditions"]) for t in b.values()) == 7737
          and old["fixtures"] == report["fixtures"] == [] and len({(m["old_owner"], m["old_condition"]) for m in mapping}) == 7737
          and len({(m["new_owner"], m["new_condition"]) for m in mapping}) == 7737)
    try:
        reg.mapped_obligations(dict(obligation_mapping=mapping), gate, old, report)
        check("production_mapped_obligations", True)
    except Exception as error:  # noqa: BLE001
        check("production_mapped_obligations", False, error=repr(error))
    proof = json.loads((P / "obligation-map-proof.json").read_bytes())
    check("proof_matches_file", proof["draft_file"]["sha256"] == sha(mapping_bytes) and proof["draft_file"]["bytes"] == len(mapping_bytes)
          and proof["draft_file"]["canonical_mapping_sha256"] == reg.digest(mapping) and proof["classification_counts"] == dict(preserved=7737)
          and proof["conditions"]["exactly_identical_retention_signature"] == 7737 and not proof["source_bindings"]["unresolved_or_changed"]
          and proof["independent_review_approved"] is False and proof["semantic_qualification"] is False, canonical_mapping_sha256=reg.digest(mapping))
    modules = {}
    for t in report["tests"]:
        for c in t["conditions"]:
            modules.setdefault((c["site"]["module"], c["site"]["source_sha256"]), set()).add(c["site"]["line"])
    crit = dict(report["source_identity"]["criteria_files"])
    bad = []
    for (module, checksum), lines in modules.items():
        found = [p for p, h in crit.items() if h == checksum and p.endswith("/" + module + ".py")]
        blob = git("show", HEAD + ":" + found[0]) if len(found) == 1 else b""
        if len(found) != 1 or sha(blob) != checksum or max(lines) > len(blob.decode().splitlines()):
            bad.append([module, checksum])
    check("source_bindings_actual_blobs", not bad and len(modules) == len(proof["source_bindings"]["rows"]) == 332, distinct=len(modules), bad=bad)

    # recorded outputs vs actual bytes; status flags
    actual = {}
    for row in receipt["outputs"]:
        h, n = sha_file(P / row["path"])
        actual[row["path"]] = (h == row["sha256"] and n == row["bytes"])
    check("receipt_output_digests", all(actual.values()) and len(actual) == 16, count=len(actual))
    check("binding_file_digests", all(sha_file(P / r["path"])[0] == r["sha256"] for r in binding["files"]) and len(binding["files"]) == 10
          and binding["ci_merge_checkout_locally_verified"] is False and binding["governance_authorization_created"] is False)
    st = receipt["status"]
    check("status_flags", st["execution_success"] is True and st["structure_complete"] is True and st["expected_rejection_reproduced"] is True
          and st["semantic_qualification"] is False and st["scientific_qualification"] is False and st["merge_allowed"] is False
          and st["independent_review_approved"] is False and st["authorization_created"] is False and st["baseline_written"] is False)
    check("expected_rejection_text", st["expected_rejection_text"] == "expected exactly one matching trusted baseline context"
          and gate.compare_report(report, json.loads(git("show", TRUSTED + ":evas/validation/baselines/regression-v1.json")))["differences"]
          == ["expected exactly one matching trusted baseline context"])
    check("receipt_identity", receipt["identity"]["head"] == HEAD and receipt["identity"]["ci_run"] == 40454789703 and receipt["identity"]["ci_merge_checkout_verified"] is False
          and receipt["queue_time"] == "unknown" and receipt["queue_time_seconds"] is None)

    # expected rejections: in-memory tampering must make the production validators refuse
    def refuse(name, call, text):
        try:
            call()
        except ValueError as error:
            check("expected_rejection_" + name, text in str(error), message=str(error)[:200])
        except Exception as error:  # noqa: BLE001
            check("expected_rejection_" + name, False, wrong_error=repr(error)[:200])
        else:
            check("expected_rejection_" + name, False, accepted=True)

    def tampered(role, data, expect, update_auth=True):
        t_blobs = dict(blobs)
        t_blobs[role] = data
        t_auth = json.loads(json.dumps(auth))
        if update_auth:
            t_auth["artifacts"][role]["sha256"] = sha(data)
        refuse("tamper_" + role + "_" + expect[:12].replace(" ", "_"), lambda: reg.evidence(t_auth, t_blobs, gate, report, entry, old_subject), expect)

    tampered("stdout", raw["stdout"] + b"x", "captured stdout", update_auth=True)
    tampered("kernel_binary", bytes([kernel_bytes[0] ^ 1]) + kernel_bytes[1:], "retrievable binary differs from D0")
    swapped = [t.encode() for t in json.loads(raw["shard_reports"])]
    swapped[0], swapped[1] = swapped[1], swapped[0]
    tampered("shard_reports", dump([x.decode() for x in swapped]), "shard raw bytes differ from capture manifest")
    resorted = dump(dict(schema_version=1, entries=sorted(snap["entries"], key=lambda e: PurePosixPath(e[0]))))
    tampered("snapshot_manifest", resorted, "all-input subject differs from fixed snapshot")
    short = dict(mapping[0], new_condition="0" * 64)
    refuse("mapping_unknown_new", lambda: reg.mapped_obligations(dict(obligation_mapping=[short] + mapping[1:]), gate, old, report), "lost, unknown or duplicate")
    refuse("mapping_omitted", lambda: reg.mapped_obligations(dict(obligation_mapping=mapping[1:]), gate, old, report), "omitted")
    wrong = [dict(mapping[0], classification="criterion-correction-reveals-old-dut-defect")] + mapping[1:]
    refuse("mapping_false_pass_class", lambda: reg.mapped_obligations(dict(obligation_mapping=wrong), gate, old, report), "attribution")

    # output refusal probes against prepare_bundle.py (no side effects expected)
    probe = out / "refusal-probe"
    probe.mkdir()
    (probe / "link").symlink_to("/tmp")
    cases = [("existing_prepared_directory", str(P)), ("outside", "/tmp/vaEVAS-refusal-probe"), ("parent_traversal", "../refusal-probe"),
             ("symlink_final", str(probe / "link")), ("through_symlink_parent", str(probe / "link" / "child")), ("existing_file", str(P / "receipt.json"))]
    probes = {}
    for label, argument in cases:
        result = subprocess.run([sys.executable, "-B", str(D / "prepare_bundle.py"), "--output", argument], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        probes[label] = dict(exit_code=result.returncode, message=result.stderr.decode().strip().splitlines()[-1] if result.stderr else "")
    check("output_path_refusals", all(v["exit_code"] != 0 and v["message"].startswith("refusing") for v in probes.values()) and not Path("/tmp/vaEVAS-refusal-probe").exists(), probes=probes)

    # guard
    _, guard_end = guard(plan_rows)
    check("real_workspace_guard_unchanged", guard_end == guard_start and guard_start["head"] == REAL_HEAD, candidates=len(guard_end["candidate_sha256"]))
    (out / "guard-before.json").write_bytes(dump(guard_start))
    (out / "guard-after.json").write_bytes(dump(guard_end))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prepared = new_dir(args.prepared, must_exist=True)
    target = new_dir(args.output)
    target.mkdir()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    failure = None
    try:
        verify(prepared, target)
    except BaseException:
        failure = traceback.format_exc()
    result = dict(prepared=str(prepared), started_at_utc=started, finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  all_checks_ok=failure is None and all(c["ok"] for c in CHECKS.values()), checks=CHECKS, unhandled_failure=failure,
                  execution_success=failure is None, semantic_qualification=False, scientific_qualification=False, python=sys.version.split()[0])
    (target / "verification.json").write_bytes(dump(result))
    print(json.dumps(dict(all_checks_ok=result["all_checks_ok"], checks=len(CHECKS), failed=[k for k, v in CHECKS.items() if not v["ok"]], unhandled=bool(failure))))
    sys.exit(0 if result["all_checks_ok"] else 1)
