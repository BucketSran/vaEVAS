"""Independently verify a bundle prepared by prepare_bundle.py (PR6 E1, CI 40584762318, head fa5556de).

Usage: python3 -B verify.py --prepared RUN-DIR --output NEW-UNUSED-DIRECTORY   (both under this folder)

Re-derives every consumed-input digest, the ten role files, the stream boundaries, the draft obligation map and
the proof from the original inputs and trusted Git blobs, compares them byte for byte, runs the production
evidence/mapping functions on the bytes found on disk, and exercises expected rejections (tampered copies exist
only in memory). Writes only inside the new output folder. Nothing here authorizes, approves, registers or
qualifies anything.
"""
import argparse
import datetime
import importlib.util
import json
import subprocess
import sys
import traceback
from pathlib import Path, PurePosixPath

from common import *

A = D / "artifacts"
OLD_REPORT = D / "artifacts-274/python-regression-timings/python-regression.json"
NEW_SHA = "35d74e62f8933cb10c8f8298f5a65389fa56b1cd6faadb4f8a09108f14d3fa75"
OLD_SHA = "9cb0aa443f6f3d3298fa5261f554f1c58bf28819241cf756cd7103dae6b9978a"
KERNEL = "b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe"
DUT_REVISION = "842bde7101164330fa03e7aee58b45d1789cbed1"
ROLES = ("composition_recipe", "snapshot_manifest", "dut_build", "kernel_binary", "collector_manifest", "artifact_manifest", "stdout", "stderr", "shard_reports")
CHECKS = {}


def check(name, ok, **detail):
    CHECKS[name] = dict(ok=bool(ok), **detail)
    return bool(ok)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify(P, out):
    guard_start = guard()
    check("real_workspace_guard_start", guard_start["head_ok"] and guard_start["candidates_match_main_plan"] and guard_start["config_equals_accepted_baseline"])
    receipt = load(P / "receipt.json")
    raw_dir = Path(receipt["raw_verification_dir"])
    raw = load(raw_dir / "raw-verification.json")
    check("raw_verification_input", sha_file(raw_dir / "raw-verification.json")[0] == receipt["raw_verification_sha256"] and raw["identity_findings"] == []
          and raw["guard_equal_before_after"] is True and raw["scientific_qualification"] is False and raw["admission"]["expected_rejection_reproduced"] is True)
    # trusted code: re-read from Git and require the prepared copy to match, then import that copy
    code = P / "code"
    for name in ("regression_gate.py", "regression_context_registration.py"):
        blob = git("show", TRUSTED + ":scripts/" + name)
        check("trusted_code_" + name, (code / "trusted" / name).read_bytes() == blob == git("show", HEAD + ":scripts/" + name) == (S / "scripts" / name).read_bytes(), sha256=sha(blob))
    ci_blob = git("show", HEAD + ":scripts/ci_evidence.py")
    check("candidate_code_ci_evidence", (code / "candidate/ci_evidence.py").read_bytes() == ci_blob == (S / "scripts/ci_evidence.py").read_bytes()
          and ci_blob != git("show", TRUSTED + ":scripts/ci_evidence.py"), sha256=sha(ci_blob), note="PR6 changes the collector: ci_evidence.py head differs from the base")
    gate = load_module("verify_gate6", code / "trusted/regression_gate.py")
    reg = load_module("verify_reg6", code / "trusted/regression_context_registration.py")
    (code / "candidate/regression_gate.py").is_file()
    ci = load_module("verify_ci6", code / "candidate/ci_evidence.py")

    changed = []
    for path, row in receipt["consumed_inputs"].items():
        h, n = sha_file(path)
        if (h, n) != (row["sha256"], row["bytes"]):
            changed.append(path)
    check("consumed_inputs_unchanged", not changed and len(receipt["consumed_inputs"]) >= 25, count=len(receipt["consumed_inputs"]), changed=changed)

    bundle = P / "bundle"
    names = sorted(p.name for p in bundle.iterdir())
    check("ten_role_files", names == sorted(("report.json",) + ROLES) and all((bundle / n).is_file() and not (bundle / n).is_symlink() for n in names), names=names)
    rawb = {n: (bundle / n).read_bytes() for n in names if n != "kernel_binary"}

    report_bytes = (A / "python-regression-timings/python-regression.json").read_bytes()
    check("report_original_bytes", rawb["report.json"] == report_bytes and sha(report_bytes) == NEW_SHA)
    report = json.loads(report_bytes)
    old_bytes = OLD_REPORT.read_bytes()
    check("old_report_identity", sha(old_bytes) == OLD_SHA)
    old = json.loads(old_bytes)
    subject, old_subject = gate.execution_subject(report), gate.execution_subject(old)
    check("report_valid_whole_merged", gate.validate_report(report)["valid"] and gate._whole(report) and report["merged"] and report["shard_count"] == 4)

    # snapshot
    assets = load(A / "catalog-inventory/assets-before.json")
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
    snap = json.loads(rawb["snapshot_manifest"])
    check("snapshot_entries_and_order", snap == dict(schema_version=1, entries=entries) and rawb["snapshot_manifest"] == dump(dict(schema_version=1, entries=entries))
          and len(entries) == raw["inventory"]["execution_input_count"] and digest(entries) == raw["inventory"]["execution_input_list_sha256"], count=len(entries))
    keys = []
    for i in range(4):
        identity = load(A / ("python-regression-shard-%d/regression-identity.json" % i))
        keys.append(digest(dict(version=3, report_schema_version=3, files=snap["entries"], environment=identity["environment"])) == identity["key"])
    check("snapshot_reproduces_four_shard_identity_keys", all(keys), per_shard=keys)
    check("snapshot_order_is_not_path_sorted", [e[0] for e in entries] != sorted((e[0] for e in entries), key=PurePosixPath),
          note="git ls-files order reproduces the CI identity keys; Path or string re-sorting would not")

    # collector, kernel, recipe
    paths = dict(runner="scripts/run_regression.py", environment_policy="scripts/ci_evidence.py", assertion_capture="scripts/regression_reason_identity.py",
                 assertion_policy="scripts/regression_observation_policy.json")
    collector = {role: sha(git("show", HEAD + ":" + p)) for role, p in paths.items()}
    check("collector_manifest", rawb["collector_manifest"] == dump(collector) and digest(collector) == report["metadata"]["collector_sha256"]
          and all({e[0]: e[3] for e in entries}[p] == collector[r] for r, p in paths.items()) and all(sha((S / p).read_bytes()) == collector[r] for r, p in paths.items()), collector=collector)
    ks = [sha_file(A / ("python-regression-shard-%d/regression-build/evas-kernel" % i)) for i in range(4)]
    kh, kn = sha_file(bundle / "kernel_binary")
    pr5_kernel = [f for f in load(B / "pr5/context-registration-20261027/bundle-preparation-sonnet/run-r3/bundle-byte-binding.json")["files"] if f["path"] == "bundle/kernel_binary"][0]
    check("kernel_binary", kh == KERNEL == subject["kernel_sha256"] == old_subject["kernel_sha256"] and all(k == (KERNEL, kn) for k in ks)
          and not ((bundle / "kernel_binary").stat().st_mode & 0o111), bytes=kn, executable_bit=bool((bundle / "kernel_binary").stat().st_mode & 0o111),
          equals_pr5_bundle_kernel=(pr5_kernel["sha256"], pr5_kernel["bytes"]) == (kh, kn))
    recipe = json.loads(rawb["composition_recipe"])
    profile = {k: report["metadata"][k] for k in ("language_profile", "runtime_profile", "invocation")}
    check("composition_recipe", rawb["composition_recipe"] == dump(dict(
        schema_version=1, dut_revision=recipe["dut_revision"], snapshot_sha256=sha(rawb["snapshot_manifest"]), dut_manifest_sha256=subject["dut_files_sha256"],
        kernel_sha256=subject["kernel_sha256"], criteria_id=report["metadata"]["criteria_id"], collector_sha256=report["metadata"]["collector_sha256"],
        profile_sha256=digest(profile))) and recipe["dut_revision"] == DUT_REVISION)
    build = json.loads(rawb["dut_build"])
    texts = build["toolchain_reference"] + build["build_reference"]
    merge_verified = raw["merge_checkout"].get("verified") is True
    check("dut_build_bindings", set(build) == {"schema_version", "dut_revision", "dut_manifest_sha256", "kernel_sha256", "toolchain_reference", "build_reference"}
          and build["kernel_sha256"] == KERNEL and build["dut_manifest_sha256"] == subject["dut_files_sha256"] and RUN_URL in texts and MERGE_OBJECT in texts
          and (("is locally observed" in texts and "signature header present but not verified" in texts and raw["merge_checkout"]["observed_tree"] in texts)
               if merge_verified else "NOT locally verified" in texts) and KERNEL in texts and all(sha((A / ("python-regression-shard-%d/regression-identity.json" % i)).read_bytes()) in texts for i in range(4))
          and all(sha((A / ("python-regression-shard-%d/regression-build/stderr.txt" % i)).read_bytes())[:16] in texts for i in range(4)))

    # streams and shard reports
    shard_bytes = [(A / ("python-regression-shard-%d/regression-evidence/report.json" % i)).read_bytes() for i in range(4)]
    check("shard_reports_exact_text_and_order", [t.encode("utf-8") for t in json.loads(rawb["shard_reports"])] == shard_bytes
          and rawb["shard_reports"] == dump([x.decode("utf-8") for x in shard_bytes]) and [json.loads(x)["shard_index"] for x in shard_bytes] == [0, 1, 2, 3])
    boundaries = load(P / "stream-boundaries.json")
    for role in ("stdout", "stderr"):
        parts = [(A / ("python-regression-shard-%d/regression-evidence/%s.txt" % (i, role))).read_bytes() for i in range(4)]
        rows_b = boundaries[role]["parts"]
        offs, o = [], 0
        for x in parts:
            offs.append(o)
            o += len(x)
        check("stream_" + role, rawb[role] == b"".join(parts) and [r["offset"] for r in rows_b] == offs and [r["bytes"] for r in rows_b] == [len(x) for x in parts]
              and [r["sha256"] for r in rows_b] == [sha(x) for x in parts] and boundaries[role]["total_sha256"] == sha(rawb[role]) and boundaries[role]["total_bytes"] == len(rawb[role]),
              lengths=[len(x) for x in parts], total=len(rawb[role]))
    manifest = json.loads(rawb["artifact_manifest"])
    check("artifact_manifest", manifest["raw_report_sha256"] == NEW_SHA and manifest["stdout_sha256"] == sha(rawb["stdout"]) and manifest["stderr_sha256"] == sha(rawb["stderr"])
          and manifest["shard_report_sha256"] == [sha(x) for x in shard_bytes] and RUN_URL in manifest["capture_reference"]
          and sha_file(raw_dir / "archive-download-manifest.json")[0] in manifest["capture_reference"])

    # production functions on bytes found on disk
    kernel_bytes = (bundle / "kernel_binary").read_bytes()
    blobs = {role: (kernel_bytes if role == "kernel_binary" else rawb[role]) for role in ROLES}
    auth = dict(artifacts={r: dict(sha256=sha(blobs[r]), locator="bundle/" + r) for r in ROLES},
                current_dut=dict(manifest_sha256=old_subject["dut_files_sha256"], kernel_sha256=old_subject["kernel_sha256"]),
                e1=dict(raw_sha256=sha(report_bytes), execution_subject=subject))
    binding = load(P / "bundle-byte-binding.json")
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
            if (after is None or before["outcome"] != after["outcome"] or gate._retention_condition(before) != gate._retention_condition(after)
                    or a[owner]["outcome"] != b[owner]["outcome"]):
                unmapped.append([owner, before["id"]])
                continue
            expected.append(dict(old_owner=owner, old_condition=before["id"], old_signature_sha256=reg.digest(gate._retention_condition(before)),
                                 new_owner=owner, new_condition=after["id"], new_signature_sha256=reg.digest(gate._retention_condition(after)),
                                 classification="preserved", review_reference=mapping[0]["review_reference"], attribution=None))
    check("obligation_map_recomputed_exact", not unmapped and mapping == expected and len(mapping) == raw["conditions"]
          and mapping_bytes == (json.dumps(expected, indent=2) + "\n").encode(), unmapped=len(unmapped), entries=len(mapping))
    check("obligation_map_draft_label", all("DRAFT" in m["review_reference"] and "PENDING" in m["review_reference"] and m["attribution"] is None and m["classification"] == "preserved" for m in mapping))
    check("obligation_counts", len(a) == len(b) == raw["methods"] == raw["c274_methods"] and set(a) == set(b) and sum(len(t["conditions"]) for t in b.values()) == raw["conditions"] == raw["c274_conditions"]
          and old["fixtures"] == report["fixtures"] == [] and len({(m["old_owner"], m["old_condition"]) for m in mapping}) == raw["conditions"]
          and len({(m["new_owner"], m["new_condition"]) for m in mapping}) == raw["conditions"])
    try:
        reg.mapped_obligations(dict(obligation_mapping=mapping), gate, old, report)
        check("production_mapped_obligations", True)
    except Exception as error:  # noqa: BLE001
        check("production_mapped_obligations", False, error=repr(error))
    baseline = json.loads(git("show", TRUSTED + ":" + BASELINE_PATH))
    matched, host = gate._matching_contexts(baseline["contexts"], gate._context(old))
    try:
        expansion = gate._expand_baseline_observations(matched[0])
        reg.mapped_obligations(dict(obligation_mapping=mapping), gate, expansion, report)
        check("production_mapped_obligations_against_trusted_context_expansion", len(matched) == 1 and host is None, context_index=baseline["contexts"].index(matched[0]))
    except Exception as error:  # noqa: BLE001
        check("production_mapped_obligations_against_trusted_context_expansion", False, error=repr(error))
    proof = load(P / "obligation-map-proof.json")
    check("proof_matches_file", proof["draft_file"]["sha256"] == sha(mapping_bytes) and proof["draft_file"]["bytes"] == len(mapping_bytes)
          and proof["draft_file"]["canonical_mapping_sha256"] == reg.digest(mapping) and proof["classification_counts"] == dict(preserved=len(mapping))
          and proof["conditions"]["exactly_identical_retention_signature"] == len(mapping) and not proof["source_bindings"]["unresolved_or_changed"]
          and proof["independent_review_approved"] is False and proof["semantic_qualification"] is False
          and proof["trusted_context_expansion"]["mapping_identical_when_old_side_is_trusted_context_expansion"] is True
          and not proof["changed_criteria_documents_with_condition_sites"] and "DRAFT" in proof["status"] and "PENDING" in proof["status"],
          canonical_mapping_sha256=reg.digest(mapping))
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
    check("source_bindings_actual_blobs", not bad and len(modules) == len(proof["source_bindings"]["rows"]), distinct=len(modules), bad=bad)

    # recorded outputs vs actual bytes; status flags
    actual = {}
    for row in receipt["outputs"]:
        h, n = sha_file(P / row["path"])
        actual[row["path"]] = h == row["sha256"] and n == row["bytes"]
    check("receipt_output_digests", all(actual.values()) and len(actual) == 16, count=len(actual))
    check("binding_file_digests", all(sha_file(P / r["path"])[0] == r["sha256"] for r in binding["files"]) and len(binding["files"]) == 10
          and binding["ci_merge_checkout_locally_verified"] is merge_verified and binding["governance_authorization_created"] is False and binding["semantic_qualification"] is False)
    st = receipt["status"]
    check("status_flags", st["execution_success"] is True and st["structure_complete"] is True and st["expected_rejection_reproduced"] is True and st["semantic_qualification"] is False
          and st["scientific_qualification"] is False and st["merge_allowed"] is False and st["independent_review_approved"] is False and st["authorization_created"] is False
          and st["baseline_written"] is False)
    check("expected_rejection_text", st["expected_rejection_text"] == "expected exactly one matching trusted baseline context"
          and gate.compare_report(report, baseline)["differences"] == ["expected exactly one matching trusted baseline context"] and gate.compare_report(old, baseline)["merge_allowed"] is True)
    check("receipt_identity", receipt["identity"]["head"] == HEAD and receipt["identity"]["ci_run"] == RUN and receipt["identity"]["ci_merge_checkout_verified"] is merge_verified
          and receipt["queue_time"] == "unknown" and receipt["queue_time_seconds"] is None and receipt["actual_model"]["model"] == "claude-sonnet-5-5"
          and receipt["identity"]["current_context_report"]["ci_run"] == OLD_RUN)

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

    tampered("stdout", rawb["stdout"] + b"x", "captured stdout")
    tampered("kernel_binary", bytes([kernel_bytes[0] ^ 1]) + kernel_bytes[1:], "retrievable binary differs from D0")
    swapped = [t.encode() for t in json.loads(rawb["shard_reports"])]
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
        result = subprocess.run([sys.executable, "-B", str(D / "prepare_bundle.py"), "--raw", str(raw_dir), "--output", argument], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(D))
        probes[label] = dict(exit_code=result.returncode, message=result.stderr.decode().strip().splitlines()[-1] if result.stderr else "")
    check("output_path_refusals", all(v["exit_code"] != 0 and v["message"].startswith("refusing") for v in probes.values()) and not Path("/tmp/vaEVAS-refusal-probe").exists(), probes=probes)

    # guard
    guard_end = guard()
    check("real_workspace_guard_unchanged", guard_end == guard_start and guard_start["head"] == REAL_HEAD, candidates=len(guard_end["candidate_sha256"]))
    (out / "guard-before.json").write_bytes(dump(guard_start))
    (out / "guard-after.json").write_bytes(dump(guard_end))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prepared = existing_plain_directory(args.prepared)
    target = safe_new_directory(args.output)
    target.mkdir()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    failure = None
    try:
        verify(prepared, target)
    except BaseException:
        failure = traceback.format_exc()
    result = dict(prepared=str(prepared), started_at_utc=started, finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  all_checks_ok=failure is None and all(c["ok"] for c in CHECKS.values()), checks=CHECKS, unhandled_failure=failure, execution_success=failure is None,
                  semantic_qualification=False, scientific_qualification=False, python=sys.version.split()[0])
    (target / "verification.json").write_bytes(dump(result))
    print(json.dumps(dict(all_checks_ok=result["all_checks_ok"], checks=len(CHECKS), failed=[k for k, v in CHECKS.items() if not v["ok"]], unhandled=bool(failure))))
    sys.exit(0 if result["all_checks_ok"] else 1)
