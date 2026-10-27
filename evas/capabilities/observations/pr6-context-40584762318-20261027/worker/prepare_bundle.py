"""Stage 2: compose the ten-role registration bundle and the draft obligation map for PR6 E1 (CI 40584762318).

Usage: python3 -B prepare_bundle.py --raw RAW-VERIFIED-DIRECTORY --output NEW-UNUSED-DIRECTORY   (both under this folder)

Data composition and proof only. This script never executes the kernel or any test, never fetches, never writes
Git state, and never creates an authorization, baseline, review record or approval. All consumed inputs are
read-only; every first failure is kept in the output directory.
"""
import argparse
import datetime
import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path, PurePosixPath

from common import *

A = D / "artifacts"
OLD_REPORT = D / "artifacts-274/python-regression-timings/python-regression.json"
PR5_BINDING = B / "pr5/context-registration-20261027/bundle-preparation-sonnet/run-r3/bundle-byte-binding.json"
DUT_REVISION = "842bde7101164330fa03e7aee58b45d1789cbed1"
OLD_REPORT_SHA = "9cb0aa443f6f3d3298fa5261f554f1c58bf28819241cf756cd7103dae6b9978a"
OLD_CRITERIA = "145a6118739af5c1419269c4d46faae6cd666d766843d41dd38150d8da77d21b"
NEW_REPORT_SHA = "35d74e62f8933cb10c8f8298f5a65389fa56b1cd6faadb4f8a09108f14d3fa75"
KERNEL_SHA = "b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe"
GATE_SCRIPTS = ("regression_gate.py", "regression_context_registration.py")
COLLECTOR = dict(runner="scripts/run_regression.py", environment_policy="scripts/ci_evidence.py",
                 assertion_capture="scripts/regression_reason_identity.py", assertion_policy="scripts/regression_observation_policy.json")
CONSUMED = {}
DRAFT_REFERENCE = ("DRAFT primary source-bound mapping; independent exact-context acceptance PENDING; "
                   "not an approval, authority or baseline; see obligation-map-proof.json")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def consume(path):
    data = Path(path).read_bytes()
    CONSUMED[str(path)] = dict(bytes=len(data), sha256=sha(data))
    return data


def consume_streamed(path):
    h, n = sha_file(path)
    CONSUMED[str(path)] = dict(bytes=n, sha256=h)
    return h, n


class Stages:
    def __init__(self, out):
        self.path = out / "stages.jsonl"

    def __call__(self, name, **extra):
        with self.path.open("a") as stream:
            stream.write(json.dumps(dict(at=utc(), stage=name, **extra), sort_keys=True) + "\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bring_code(out):
    """Gate and registration: trusted base == head == source export. ci_evidence: the head (collector) version CI ran."""
    trusted_dir, candidate_dir = out / "code/trusted", out / "code/candidate"
    trusted_dir.mkdir(parents=True)
    candidate_dir.mkdir()
    rows = {}
    for name in GATE_SCRIPTS + ("ci_evidence.py",):
        trusted = git("show", TRUSTED + ":scripts/" + name)
        head = git("show", HEAD + ":scripts/" + name)
        exported = (S / "scripts" / name).read_bytes()
        assert head == exported, name
        if name in GATE_SCRIPTS:
            assert trusted == head, name
        (trusted_dir / name).write_bytes(trusted)
        (candidate_dir / name).write_bytes(head)
        rows[name] = dict(trusted_sha256=sha(trusted), head_sha256=sha(head), trusted_equals_head=trusted == head)
    (candidate_dir / "regression_gate.py").write_bytes((trusted_dir / "regression_gate.py").read_bytes())  # ci_evidence loads its sibling gate
    gate = load_module("trusted_gate_bundle6", trusted_dir / "regression_gate.py")
    reg = load_module("trusted_reg_bundle6", trusted_dir / "regression_context_registration.py")
    ci = load_module("candidate_ci_evidence_bundle6", candidate_dir / "ci_evidence.py")
    return gate, reg, ci, rows


def dut_manifest_digest(gate, rev):
    paths = {}
    for line in git("ls-tree", "-r", "-z", rev).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        path = path.decode()
        if kind == "blob" and path.startswith(("evas/src/", "evas/rust_core/")) and not ({"__pycache__", "target", "baselines", ".git", "runs"} & set(path.split("/"))):
            paths[path] = oid
    files = []  # collector order: evas/src then evas/rust_core, each in Path order
    for directory in ("evas/src/", "evas/rust_core/"):
        for path in sorted((p for p in paths if p.startswith(directory)), key=PurePosixPath):
            files.append([path, sha(git("cat-file", "blob", paths[path]))])
    return sha(gate._json(files).encode()), len(files)


def condition_identity(owner, c):
    if c.get("kind") == "subtest":
        return dict(method=owner, **{k: c[k] for k in ("phase", "params", "message", "site", "context")})
    if c.get("kind") in ("method_completion", "method_status"):
        return dict(method=owner, **{k: c[k] for k in ("phase", "kind", "site")})
    return dict(method=owner, **{k: c[k] for k in ("phase", "site")}, context=c["reason"]["context"])


def recompute_condition_ids(report):
    direct = repeated = 0
    mismatches = []
    for test in report["tests"]:
        seen = {}
        for c in test["conditions"]:
            base = sha(json.dumps(condition_identity(test["id"], c), sort_keys=True).encode())
            if "repeated_identity" in c:
                ok = c["repeated_identity"] == base and c["id"] == digest(dict(identity=base, occurrence=seen.get(base, 0)))
                repeated += ok
            else:
                ok = c["id"] == base
                direct += ok
            if not ok:
                mismatches.append([test["id"], c["id"]])
            seen[c.get("repeated_identity", c["id"])] = seen.get(c.get("repeated_identity", c["id"]), 0) + 1
    return dict(direct_exact=direct, repeated_identity_exact=repeated, mismatches=mismatches)


def count(values):
    result = {}
    for v in values:
        result[v] = result.get(v, 0) + 1
    return result


def build_mapping(gate, reg, a, b):
    mapping, outcomes, kinds = [], {}, {}
    unmapped = dict(method_outcome_mismatch=[], condition_id_set_mismatch=[], retention_signature_differs=[], condition_outcome_differs=[])
    order_differs = []
    for owner in a:
        ac, bc = a[owner]["conditions"], b[owner]["conditions"]
        if a[owner]["outcome"] != b[owner]["outcome"]:
            unmapped["method_outcome_mismatch"].append(owner)
        da, db = {c["id"]: c for c in ac}, {c["id"]: c for c in bc}
        assert len(da) == len(ac) and len(db) == len(bc)
        if da.keys() != db.keys():
            unmapped["condition_id_set_mismatch"].append(owner)
            continue
        if [c["id"] for c in ac] != [c["id"] for c in bc]:
            order_differs.append(owner)
        for before in ac:
            after = db[before["id"]]
            if before["outcome"] != after["outcome"]:
                unmapped["condition_outcome_differs"].append([owner, before["id"]])
            if gate._retention_condition(before) != gate._retention_condition(after):
                unmapped["retention_signature_differs"].append([owner, before["id"]])
            outcomes[before["outcome"]] = outcomes.get(before["outcome"], 0) + 1
            kinds[str(before.get("kind"))] = kinds.get(str(before.get("kind")), 0) + 1
            mapping.append(dict(old_owner=owner, old_condition=before["id"], old_signature_sha256=reg.digest(gate._retention_condition(before)),
                                new_owner=owner, new_condition=after["id"], new_signature_sha256=reg.digest(gate._retention_condition(after)),
                                classification="preserved", review_reference=DRAFT_REFERENCE, attribution=None))
    return mapping, outcomes, kinds, unmapped, order_differs


def main(out, raw_dir, stage):
    started = utc()
    guard_before = guard()
    assert guard_before["head_ok"] and guard_before["candidates_match_main_plan"] and guard_before["config_equals_accepted_baseline"]
    stage("guard-before", head=guard_before["head"])
    raw_verification = load(raw_dir / "raw-verification.json")
    assert raw_verification["identity_findings"] == [] and raw_verification["guard_equal_before_after"] is True
    members = load(raw_dir / "archive-members-verified.json")
    index = {(m["artifact"], m["path"]): m["sha256"] for m in members if m["original_path"].startswith(str(A) + "/")}  # E1 archives only; #274 also has a python-regression-timings archive
    start = load(D / "start.json")
    merge = raw_verification["merge_checkout"]
    assert merge["commit"] == MERGE_OBJECT
    merge_verified = merge.get("verified") is True
    if merge_verified:
        assert merge["observed_parents"] == [TRUSTED, HEAD] and merge["observed_tree"] == TREE
        merge_text = ("is locally observed (parents " + ", ".join(merge["observed_parents"]) + "; tree " + merge["observed_tree"]
                      + "; GitHub signature header present but not verified)")
    else:
        merge_text = "is NOT locally verified"
    gate, reg, ci, code_rows = bring_code(out)
    stage("code", sha256=code_rows)

    # ---- inputs actually consumed ---------------------------------------------------------------------------
    report_path = A / "python-regression-timings/python-regression.json"
    report_raw = consume(report_path)
    assert sha(report_raw) == NEW_REPORT_SHA == index[("python-regression-timings", "python-regression.json")] == raw_verification["raw_sha256"]
    report = json.loads(report_raw)
    old_raw = consume(OLD_REPORT)
    assert sha(old_raw) == OLD_REPORT_SHA == raw_verification["c274_raw_sha256"]
    old = json.loads(old_raw)
    assert old["metadata"]["criteria_id"] == OLD_CRITERIA
    subject, old_subject = gate.execution_subject(report), gate.execution_subject(old)
    assert subject["dut_files_sha256"] == old_subject["dut_files_sha256"]
    assert subject["kernel_sha256"] == old_subject["kernel_sha256"] == KERNEL_SHA
    assert gate.validate_report(report)["valid"] and gate._whole(report) and report["merged"] and report["shard_count"] == 4
    stage("reports", new_sha=NEW_REPORT_SHA, old_sha=OLD_REPORT_SHA)

    assets = load(A / "catalog-inventory/assets-before.json")
    consume(A / "catalog-inventory/assets-before.json")
    assert assets == load(A / "catalog-inventory/assets-after.json")
    consume(A / "catalog-inventory/assets-after.json")
    assert assets["source_tree"] == TREE and not assets["dirty_paths"] and assets["source_commit"] == MERGE_OBJECT
    rows = {r["path"]: r for r in assets["assets"]}
    assert len(rows) == len(assets["assets"])
    expected = {}
    for line in git("ls-tree", "-r", "-z", HEAD).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        assert kind == "blob"
        expected[path.decode()] = (mode, oid)
    assert set(rows) == set(expected) and git("rev-parse", HEAD + "^{tree}", text=True).strip() == TREE
    entries = []
    for path, (mode, oid) in expected.items():  # git ls-files order, as ci_evidence.fingerprint writes it
        if path in ci.EXCLUDED:
            continue
        r = rows[path]
        assert (r["git_mode"], r["observed_blob_oid"], r["index_blob_oid"]) == (mode, oid, oid), path
        entries.append([path, r["git_mode"], r["actual_mode"], r["sha256"]])
    input_list_sha = digest(entries)
    assert len(entries) == raw_verification["inventory"]["execution_input_count"] and input_list_sha == raw_verification["inventory"]["execution_input_list_sha256"]
    path_order_differs = [e[0] for e in entries] != sorted((e[0] for e in entries), key=PurePosixPath)
    shard_identities = []
    for i in range(4):
        raw_identity = consume(A / ("python-regression-shard-%d/regression-identity.json" % i))
        assert sha(raw_identity) == index[("python-regression-shard-%d" % i, "regression-identity.json")]
        identity = json.loads(raw_identity)
        env = identity["environment"]
        assert digest(dict(version=3, report_schema_version=3, files=entries, environment=env)) == identity["key"]
        assert identity["input_count"] == len(entries)
        assert ci.comparison_subject(entries, env) == identity["comparison_subject"]
        assert identity["excluded"] == sorted(ci.EXCLUDED)
        shard_identities.append(identity)
    stage("snapshot", entries=len(entries), input_list_sha256=input_list_sha, git_order_differs_from_path_order=path_order_differs)

    files_by_path = {e[0]: e[3] for e in entries}
    collector = {role: files_by_path[path] for role, path in COLLECTOR.items()}
    assert digest(collector) == report["metadata"]["collector_sha256"]
    for path in COLLECTOR.values():
        assert sha(git("show", HEAD + ":" + path)) == files_by_path[path] == sha((S / path).read_bytes()), path
    assert files_by_path["evas/capabilities/data/language-profile.json"] == report["metadata"]["language_profile"]

    dut_checks = {rev: dut_manifest_digest(gate, rev) for rev in (DUT_REVISION, TRUSTED, HEAD)}
    for rev, (value, n) in dut_checks.items():
        assert value == subject["dut_files_sha256"] and n == len(report["source_identity"]["dut_files"]), rev
    stage("dut-manifest", revisions={k: v[0] for k, v in dut_checks.items()})

    # ---- ten role files --------------------------------------------------------------------------------------
    bundle = out / "bundle"
    bundle.mkdir()
    written = {}

    def put(name, data):
        with (bundle / name).open("xb") as stream:
            stream.write(data)
        written[name] = data
        return sha(data)

    put("report.json", report_raw)
    snapshot_sha = put("snapshot_manifest", dump(dict(schema_version=1, entries=entries)))
    put("collector_manifest", dump(collector))

    kernel_rows = []
    for i in range(4):
        path = A / ("python-regression-shard-%d/regression-build/evas-kernel" % i)
        h, n = consume_streamed(path)
        assert h == index[("python-regression-shard-%d" % i, "regression-build/evas-kernel")] == KERNEL_SHA
        kernel_rows.append(dict(shard_index=i, path=str(path), bytes=n, sha256=h))
    assert len({r["bytes"] for r in kernel_rows}) == 1
    import hashlib
    h = hashlib.sha256()
    with open(A / "python-regression-shard-0/regression-build/evas-kernel", "rb") as src, (bundle / "kernel_binary").open("xb") as dst:
        for block in iter(lambda: src.read(1 << 20), b""):
            h.update(block)
            dst.write(block)
    assert h.hexdigest() == KERNEL_SHA and (bundle / "kernel_binary").stat().st_size == kernel_rows[0]["bytes"]
    pr5 = load(PR5_BINDING)
    pr5_kernel = [f for f in pr5["files"] if f["path"] == "bundle/kernel_binary"][0]
    kernel_equals_pr5 = pr5_kernel["sha256"] == KERNEL_SHA and pr5_kernel["bytes"] == kernel_rows[0]["bytes"]
    stage("kernel-copied-not-executed", sha256=KERNEL_SHA, mode=oct((bundle / "kernel_binary").stat().st_mode & 0o777), equals_pr5_bundle_kernel=kernel_equals_pr5)

    boundaries, streams = {}, {}
    for role in ("stdout", "stderr"):
        pieces, parts, offset = [], [], 0
        for i in range(4):
            path = A / ("python-regression-shard-%d/regression-evidence/%s.txt" % (i, role))
            data = consume(path)
            assert sha(data) == index[("python-regression-shard-%d" % i, "regression-evidence/%s.txt" % role)]
            parts.append(dict(shard_index=i, source=str(path.relative_to(B)), offset=offset, bytes=len(data), sha256=sha(data)))
            pieces.append(data)
            offset += len(data)
        joined = b"".join(pieces)
        put(role, joined)
        streams[role] = joined
        boundaries[role] = dict(parts=parts, total_bytes=len(joined), total_sha256=sha(joined), order="ascending shard_index 0..3, plain byte concatenation without separator")
    (out / "stream-boundaries.json").write_bytes(dump(boundaries))

    shard_bytes, shard_texts = [], []
    for i in range(4):
        path = A / ("python-regression-shard-%d/regression-evidence/report.json" % i)
        data = consume(path)
        assert sha(data) == index[("python-regression-shard-%d" % i, "regression-evidence/report.json")]
        text = data.decode("utf-8")
        assert text.encode("utf-8") == data
        shard_bytes.append(data)
        shard_texts.append(text)
    assert report["parts"] and [p["shard_index"] for p in report["parts"]] == [0, 1, 2, 3]
    put("shard_reports", dump(shard_texts))
    assert [t.encode("utf-8") for t in json.loads(written["shard_reports"])] == shard_bytes

    profile = {k: report["metadata"][k] for k in ("language_profile", "runtime_profile", "invocation")}
    recipe = dict(schema_version=1, dut_revision=DUT_REVISION, snapshot_sha256=snapshot_sha, dut_manifest_sha256=subject["dut_files_sha256"],
                  kernel_sha256=subject["kernel_sha256"], criteria_id=report["metadata"]["criteria_id"], collector_sha256=report["metadata"]["collector_sha256"],
                  profile_sha256=digest(profile))
    put("composition_recipe", dump(recipe))

    build_rows = []
    for i in range(4):
        row = {}
        for name in ("stdout.txt", "stderr.txt"):
            data = consume(A / ("python-regression-shard-%d/regression-build/%s" % (i, name)))
            assert sha(data) == index[("python-regression-shard-%d" % i, "regression-build/" + name)]
            row[name] = dict(bytes=len(data), sha256=sha(data))
        build_rows.append(row)
    env0 = shard_identities[0]["environment"]
    identity_shas = [CONSUMED[str(A / ("python-regression-shard-%d/regression-identity.json" % i))]["sha256"] for i in range(4)]
    toolchain = (RUN_URL + " attempt 1; actual regression-identity.json environment of all four shards (sha256 " + ", ".join(identity_shas)
                 + "): python " + env0["python"].split()[0] + ", " + env0["rustc"].splitlines()[0] + ", " + env0["cargo"].splitlines()[0]
                 + ", platform " + env0["platform"] + "; originals under e1-bundle-sonnet-20261027/artifacts/python-regression-shard-{0,1,2,3}/")
    build_reference = (RUN_URL + " attempt 1, head " + HEAD + " (tree " + TREE + "); CI checked out refs/pull/269/merge " + MERGE_OBJECT
                       + " whose commit object " + merge_text + " (inventory tree equals the head tree); original regression-build/{stdout.txt,stderr.txt,evas-kernel} "
                       "of all four shards retained and bound: kernel sha256 " + KERNEL_SHA + " identical in 4 shards; build stdout sha256 "
                       + "/".join(r["stdout.txt"]["sha256"][:16] for r in build_rows) + " (all empty); build stderr sha256 "
                       + "/".join(r["stderr.txt"]["sha256"][:16] for r in build_rows) + "; DUT manifest equals reviewed " + DUT_REVISION + " (also " + TRUSTED
                       + " and " + HEAD + "); kernel not executed here")
    put("dut_build", dump(dict(schema_version=1, dut_revision=DUT_REVISION, dut_manifest_sha256=subject["dut_files_sha256"], kernel_sha256=subject["kernel_sha256"],
                               toolchain_reference=toolchain, build_reference=build_reference)))
    download_receipt = D / "archive-download-manifest.json"
    capture_reference = (RUN_URL + " attempt 1; original zipped artifact index " + str(raw_dir / "archive-download-manifest.json") + " (sha256 "
                         + sha_file(raw_dir / "archive-download-manifest.json")[0] + "), 13 archives / 467 members verified in " + str(raw_dir / "archive-members-verified.json")
                         + "; report.json is the original python-regression-timings/python-regression.json byte for byte; shard_reports are the four original "
                         "regression-evidence/report.json texts in shard-index order; stdout/stderr are exact shard-index-order concatenations with byte boundaries in ../stream-boundaries.json")
    del download_receipt
    put("artifact_manifest", dump(dict(schema_version=1, raw_report_sha256=sha(report_raw), capture_reference=capture_reference,
                                       stdout_sha256=sha(streams["stdout"]), stderr_sha256=sha(streams["stderr"]), shard_report_sha256=[sha(x) for x in shard_bytes])))
    assert len(written) == 9 and len(list(bundle.iterdir())) == 10
    stage("bundle-written", files=10)

    # ---- production evidence function probe (in-memory harness; no authorization is created) ---------------------
    kernel_bytes = (bundle / "kernel_binary").read_bytes()
    locators = {role: "bundle/" + role for role in ("composition_recipe", "snapshot_manifest", "dut_build", "kernel_binary", "collector_manifest", "artifact_manifest", "stdout", "stderr", "shard_reports")}
    blobs = {role: (kernel_bytes if role == "kernel_binary" else (bundle / role).read_bytes()) for role in locators}
    harness_auth = dict(artifacts={role: dict(sha256=sha(blobs[role]), locator=locators[role]) for role in locators},
                        current_dut=dict(manifest_sha256=old_subject["dut_files_sha256"], kernel_sha256=old_subject["kernel_sha256"]),
                        e1=dict(raw_sha256=sha(report_raw), execution_subject=subject))
    provenance = dict(schema_version=1, snapshot_revision=HEAD,
                      snapshot_reference=(REPO_URL + "/tree/" + HEAD + "; CI inventory checkout " + MERGE_OBJECT + " " + merge_text + "; its recorded tree equals the head tree " + TREE),
                      raw_reference=RUN_URL + " attempt 1; original zipped artifact index and members retained in e1-bundle-sonnet-20261027",
                      recipe_sha256=sha(blobs["composition_recipe"]), artifact_manifest_sha256=sha(blobs["artifact_manifest"]))
    reg.evidence(harness_auth, blobs, gate, report, dict(source_identity=provenance), old_subject)
    stage("production-evidence-function-pass")
    del blobs, kernel_bytes

    # ---- trusted-gate behaviour on the unchanged baseline (expected rejection) -------------------------------------
    baseline_raw = git("show", TRUSTED + ":" + BASELINE_PATH)
    baseline = json.loads(baseline_raw)
    assert baseline_raw == git("show", HEAD + ":" + BASELINE_PATH) and len(baseline["contexts"]) == 4 and len(baseline_raw) == 89943276
    new_compare, old_compare = gate.compare_report(report, baseline), gate.compare_report(old, baseline)
    expected_rejection = (new_compare["merge_allowed"] is False and new_compare["valid"] is True
                          and new_compare["differences"] == ["expected exactly one matching trusted baseline context"])
    assert expected_rejection, new_compare["differences"][:3]
    assert old_compare["merge_allowed"] is True and old_compare["differences"] == [] and "host_runtime_difference" not in old_compare
    matched, host = gate._matching_contexts(baseline["contexts"], gate._context(old))
    assert len(matched) == 1 and host is None
    matched_index = baseline["contexts"].index(matched[0])
    stage("trusted-gate-compare", new_merge_allowed=new_compare["merge_allowed"], old_merge_allowed=old_compare["merge_allowed"], matched_context_index=matched_index)

    # ---- obligation map: #274 report (matches trusted context) -> E1 --------------------------------------------------
    a = {t["id"]: t for t in old["tests"]}
    b = {t["id"]: t for t in report["tests"]}
    assert a.keys() == b.keys() and list(a) == list(b)
    assert old["fixtures"] == report["fixtures"] == [] and old["setup_skipped_test_ids"] == report["setup_skipped_test_ids"] == []
    mapping, outcomes, kinds, unmapped, order_differs = build_mapping(gate, reg, a, b)
    if any(unmapped.values()):
        (out / "unmapped-obligations.json").write_bytes(dump(unmapped))
        raise RuntimeError("old obligations not exactly identical in the new report; see unmapped-obligations.json")
    assert len(mapping) == 7737
    reg.mapped_obligations(dict(obligation_mapping=mapping), gate, old, report)
    stage("mapped-obligations-pass", count=len(mapping))
    # the same mapping must also hold when the old side is the trusted baseline's own expanded observations of context `matched_index`
    expanded = gate._expand_baseline_observations(matched[0])
    ctx_mapping, _, _, ctx_unmapped, _ = build_mapping(gate, reg, {t["id"]: t for t in expanded["tests"]}, b)
    context_side_same = (not any(ctx_unmapped.values()) and sorted(ctx_mapping, key=lambda m: (m["old_owner"], m["old_condition"]))
                         == sorted(mapping, key=lambda m: (m["old_owner"], m["old_condition"])))
    reg.mapped_obligations(dict(obligation_mapping=ctx_mapping), gate, expanded, report)
    stage("mapped-obligations-pass-against-trusted-context-expansion", same_mapping=context_side_same)

    crit_new, crit_old = dict(report["source_identity"]["criteria_files"]), dict(old["source_identity"]["criteria_files"])
    modules = {}
    for t in report["tests"]:
        for c in t["conditions"]:
            modules.setdefault((c["site"]["module"], c["site"]["source_sha256"]), []).append(c["site"]["line"])
    source_rows, source_problems = [], []
    for (module, checksum), lines in sorted(modules.items()):
        paths = [p for p, hh in crit_new.items() if hh == checksum and p.endswith("/" + module + ".py")]
        if len(paths) != 1:
            source_problems.append([module, checksum, paths])
            continue
        path = paths[0]
        blob = git("show", HEAD + ":" + path)
        text = blob.decode("utf-8")
        ok = sha(blob) == checksum and crit_old.get(path) == checksum and files_by_path[path] == checksum
        in_range = max(lines) <= len(text.splitlines())
        source_rows.append(dict(module=module, path=path, sha256=checksum, git_blob_sha256_matches=sha(blob) == checksum, same_in_old_criteria=crit_old.get(path) == checksum,
                                in_snapshot=files_by_path[path] == checksum, condition_sites=len(lines), max_line=max(lines), lines_within_file=in_range))
        if not ok or not in_range:
            source_problems.append([module, checksum, path])
    new_ids, old_ids = recompute_condition_ids(report), recompute_condition_ids(old)
    stage("source-bindings", modules=len(source_rows), problems=len(source_problems))

    mapping_bytes = (json.dumps(mapping, indent=2) + "\n").encode()
    with (out / "obligation-map-draft.json").open("xb") as stream:
        stream.write(mapping_bytes)
    nonpass = {k: v for k, v in outcomes.items() if k != "passed"}
    proof = dict(
        schema_version=1, status="DRAFT; independent exact-context acceptance PENDING; not an approval, authority, baseline or review record",
        old_report=dict(path=str(OLD_REPORT), sha256=OLD_REPORT_SHA, criteria_id=OLD_CRITERIA, ci_run=OLD_RUN, ci_head=OLD_HEAD,
                        matched_trusted_context_index=matched_index, trusted_compare_merge_allowed=old_compare["merge_allowed"], host_runtime_difference=None),
        new_report=dict(path=str(report_path), sha256=NEW_REPORT_SHA, criteria_id=report["metadata"]["criteria_id"], ci_run=RUN, ci_head=HEAD),
        methods=dict(old=len(a), new=len(b), id_sets_equal=True, order_equal=True, outcome_mismatch=unmapped["method_outcome_mismatch"],
                     outcomes=count(t["outcome"] for t in b.values())),
        conditions=dict(old=sum(len(t["conditions"]) for t in a.values()), new=sum(len(t["conditions"]) for t in b.values()), mapped=len(mapping),
                        id_set_mismatch_methods=unmapped["condition_id_set_mismatch"], order_differs_methods=order_differs,
                        outcome_differs=unmapped["condition_outcome_differs"], retention_signature_differs=unmapped["retention_signature_differs"],
                        exactly_identical_retention_signature=len(mapping) - len(unmapped["retention_signature_differs"]), outcomes=outcomes, nonpassing=nonpass, kinds=kinds),
        classification_counts=dict(preserved=len(mapping)),
        classification_basis=("gate._retention_condition equal for every old/new condition bound by condition id and method id, equal outcomes, attribution null; "
                              "matches the existing 'preserved' contract in regression_context_registration.mapped_obligations"),
        no_mechanical_remap_needed=True, corrected_variants=[], unknown_or_unmapped=unmapped,
        fixtures=dict(old=0, new=0, setup_skipped_old=0, setup_skipped_new=0),
        condition_id_recomputation=dict(old={k: (v if k != "mismatches" else len(v)) for k, v in old_ids.items()},
                                        new={k: (v if k != "mismatches" else len(v)) for k, v in new_ids.items()},
                                        old_mismatches=old_ids["mismatches"], new_mismatches=new_ids["mismatches"],
                                        formula="collector.condition identity digest; repeated_identity form json_digest(identity, occurrence)"),
        source_bindings=dict(distinct_module_hash_pairs=len(source_rows), unresolved_or_changed=source_problems, rows=source_rows,
                             basis="site.source_sha256 -> unique criteria path -> equals new criteria, #274 criteria, snapshot entry and actual fa5556de Git blob bytes; "
                                   "the 4 changed criteria documents contain no condition site"),
        trusted_context_expansion=dict(context_index=matched_index, mapping_identical_when_old_side_is_trusted_context_expansion=context_side_same,
                                       production_mapped_obligations_pass_against_expansion=True),
        draft_file=dict(path="obligation-map-draft.json", bytes=len(mapping_bytes), sha256=sha(mapping_bytes), canonical_mapping_sha256=reg.digest(mapping)),
        production_function_results=dict(mapped_obligations="pass", evidence="pass (in-memory harness authorization, none written)"),
        trusted_gate_on_unchanged_baseline=dict(new_report=dict(valid=new_compare["valid"], merge_allowed=new_compare["merge_allowed"], differences=new_compare["differences"]),
                                                old_report_merge_allowed=old_compare["merge_allowed"]),
        independent_review_approved=False, semantic_qualification=False, scientific_qualification=False, scientific_thresholds_added=False)
    changed_docs_have_sites = [p for p in raw_verification["criteria_changed_paths_vs_c274"] if any(r["path"] == p for r in source_rows)]
    proof["changed_criteria_documents_with_condition_sites"] = changed_docs_have_sites
    (out / "obligation-map-proof.json").write_bytes(dump(proof))

    # ---- bindings and receipt -----------------------------------------------------------------------------------------
    ten = []
    for name in sorted(p.name for p in bundle.iterdir()):
        h2, n2 = sha_file(bundle / name)
        ten.append(dict(path="bundle/" + name, bytes=n2, sha256=h2))
    (out / "bundle-byte-binding.json").write_bytes(dump(dict(
        run=RUN, attempt=1, head=HEAD, tree=TREE, trusted_base=TRUSTED, ci_merge_checkout=MERGE_OBJECT, ci_merge_checkout_locally_verified=merge_verified, files=ten,
        ten_file_bundle_bytes_verified_by_production_evidence_function=True,
        evidence_function="regression_context_registration.evidence (4d6ebc71 blob) with an in-memory harness; no authorization object exists in any output",
        snapshot_entries=len(entries), snapshot_entry_order="git ls-files order as written by ci_evidence.fingerprint; reproduces each shard identity key",
        snapshot_order_differs_from_Path_sort=path_order_differs, entry_provenance_preview=provenance,
        role_sources=dict(report="python-regression-timings/python-regression.json (byte copy)",
                          shard_reports="4 x python-regression-shard-N/regression-evidence/report.json texts as JSON array",
                          kernel_binary="python-regression-shard-0/regression-build/evas-kernel (byte copy, 4 shards identical, never executed)",
                          stdout="shard-index-order concatenation", stderr="shard-index-order concatenation",
                          snapshot_manifest="catalog-inventory/assets-before.json x git ls-tree order, reproduces input_list_sha256 and 4 identity keys",
                          collector_manifest="four collector source SHA256 from snapshot + fa5556de blobs", composition_recipe="derived",
                          dut_build="derived from shard build records and identities", artifact_manifest="derived"),
        kernel_equals_pr5_bundle_kernel=kernel_equals_pr5, pr5_bundle_kernel_path=str(PR5_BINDING.parent / "bundle/kernel_binary"),
        governance_authorization_created=False, E1_or_new_context_accepted=False, semantic_qualification=False)))
    _, guard_after = None, guard()
    assert guard_after == guard_before
    (out / "guard-before.json").write_bytes(dump(guard_before))
    (out / "guard-after.json").write_bytes(dump(guard_after))
    finished = utc()
    receipt = dict(
        purpose="Compose PR6 E1 (CI 40584762318) ten-role bundle and draft obligation map (data composition and proof only)",
        started_at_utc=started, finished_at_utc=finished, queue_time_seconds=None, queue_time="unknown",
        actual_model=dict(providerInstanceId=start["providerInstanceId"], model=start["model"], options=start["options"]), delegation_task_id=start["task_id"],
        identity=dict(ci_run=RUN, attempt=1, ci_conclusion="failure", head=HEAD, tree=TREE, trusted_base=TRUSTED, trusted_tree=TRUSTED_TREE, ci_merge_checkout=MERGE_OBJECT,
                      ci_merge_checkout_verified=merge_verified, ci_merge_checkout_observed=dict(parents=merge.get("observed_parents"), tree=merge.get("observed_tree"), signature_verified=False),
                      ci_merge_checkout_expectation=dict(parents=[TRUSTED, HEAD], tree=TREE, status=("expected and observed" if merge_verified else "expected, not observed")),
                      current_context_report=dict(ci_run=OLD_RUN, ci_head=OLD_HEAD, sha256=OLD_REPORT_SHA, criteria_id=OLD_CRITERIA, matched_trusted_context_index=matched_index),
                      new_context_report=dict(sha256=NEW_REPORT_SHA, criteria_id=report["metadata"]["criteria_id"], collector_sha256=report["metadata"]["collector_sha256"])),
        status=dict(execution_success=True, structure_complete=True, expected_rejection_reproduced=expected_rejection,
                    expected_rejection_text="expected exactly one matching trusted baseline context", semantic_qualification=False, scientific_qualification=False,
                    merge_allowed=False, raw_successful=report["successful"], independent_review_approved=False, authorization_created=False, baseline_written=False),
        counts=dict(methods=len(b), conditions=len(mapping), snapshot_entries=len(entries), shards=4, bundle_files=10, method_outcomes=count(t["outcome"] for t in b.values())),
        code_sha256=code_rows, dut_manifest_checks={k: dict(sha256=v[0], files=v[1]) for k, v in dut_checks.items()}, dut_revision_used_in_recipe=DUT_REVISION,
        kernel=dict(sha256=KERNEL_SHA, bytes=kernel_rows[0]["bytes"], executed=False, equals_pr5_bundle_kernel=kernel_equals_pr5, shards=kernel_rows),
        stream_boundaries="stream-boundaries.json", consumed_inputs=CONSUMED, raw_verification_dir=str(raw_dir), raw_verification_sha256=sha_file(raw_dir / "raw-verification.json")[0],
        outputs=ten + [dict(path=n, bytes=(out / n).stat().st_size, sha256=sha_file(out / n)[0])
                       for n in ("obligation-map-draft.json", "obligation-map-proof.json", "bundle-byte-binding.json", "stream-boundaries.json", "guard-before.json", "guard-after.json")],
        guard_equal_before_after=True, new_scientific_thresholds=False, fetch_performed=False, fixture_created=False, python=sys.version.split()[0],
        command=[sys.executable, "-B", str(Path(__file__).resolve()), "--raw", str(raw_dir), "--output", str(out)])
    (out / "receipt.json").write_bytes(dump(receipt))
    print(json.dumps(dict(output=str(out), files=10, methods=len(b), conditions=len(mapping), expected_rejection=expected_rejection, kernel_equals_pr5=kernel_equals_pr5,
                          semantic_qualification=False), indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = existing_plain_directory(args.raw)
    target = safe_new_directory(args.output)
    target.mkdir()
    log = Stages(target)
    try:
        main(target, raw, log)
    except BaseException:
        (target / "failure.json").write_bytes(dump(dict(at=utc(), traceback=traceback.format_exc(), kept="all partial outputs retained")))
        raise
