"""Compose the ten-role registration bundle and the draft obligation map for PR266 head 983b.

Usage: python3 -B prepare_bundle.py --output NEW-UNUSED-DIRECTORY   (directory must lie under this folder)

Data composition and proof only. This script never executes the kernel or any test, never
fetches, never writes Git state, and never creates an authorization, baseline, review record or
approval. All consumed inputs are read-only; every first failure is kept in the output directory.
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
S = C.parent / "source"
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
SOURCE_CAPTURE = "d9495c77f7d8a574e24d0977c1c49b6339ddfa2a"
MERGE_OBJECT = "33ed0fa1a516627d7d418fcf563a47a0d9e272b0"
DUT_REVISION = "842bde7101164330fa03e7aee58b45d1789cbed1"
RUN = 40454789703
OLD_REPORT_SHA = "9097c8dce35461961b76782234c75e67d11f2c33a4f90d3abd98cc947ec9d981"
OLD_CRITERIA = "f54a2eac6238fa60cd4bc71b5aa74a6717077ad2cc9a8c8b25b4c2ca2880c625"
NEW_REPORT_SHA = "531016babc8a288fd130f3af99364dbcaf20f25c225201d1f35e73e6b0a6c995"
INPUT_LIST_SHA = "d6079c1ebd89a9d944e4643e289dd8f82365b1144fd044d3f46b55fa207fda55"
KERNEL_SHA = "b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe"
REPO_URL = "https://github.com/BucketSran/vaEVAS"
RUN_URL = REPO_URL + "/actions/runs/" + str(RUN)
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
SCRIPTS = ("regression_gate.py", "regression_context_registration.py", "ci_evidence.py")
COLLECTOR = dict(runner="scripts/run_regression.py", environment_policy="scripts/ci_evidence.py",
                 assertion_capture="scripts/regression_reason_identity.py",
                 assertion_policy="scripts/regression_observation_policy.json")
CONSUMED = {}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def load(path):
    return json.loads(Path(path).read_bytes())


def consume(path):
    """Read a whole input once, recording its path, size and SHA256 as actually consumed."""
    data = Path(path).read_bytes()
    CONSUMED[str(path)] = dict(bytes=len(data), sha256=sha(data))
    return data


def consume_streamed(path):
    h, n = sha_file(path)
    CONSUMED[str(path)] = dict(bytes=n, sha256=h)
    return h, n


def git(*argv, text=False):
    result = subprocess.run([GIT, "--no-lazy-fetch", "--git-dir=" + str(GD), "--work-tree=" + str(W), *argv],
                            env=ENV, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode() if text else result.stdout


def safe_new_directory(argument):
    """Return an absolute, not-yet-existing directory path strictly inside D."""
    path = Path(os.path.abspath(Path(argument) if Path(argument).is_absolute() else D / argument))
    if D not in path.parents:
        raise SystemExit("refusing output outside " + str(D))
    if os.path.lexists(path):
        raise SystemExit("refusing existing path (directory, file or symlink): " + str(path))
    walk = D
    for part in path.relative_to(D).parts[:-1]:
        walk = walk / part
        if walk.is_symlink() or not walk.is_dir():
            raise SystemExit("refusing symlink or missing parent: " + str(walk))
    return path


def guard(main_plan_rows=None):
    assert git("rev-parse", "HEAD", text=True).strip() == REAL_HEAD
    rows = main_plan_rows
    if rows is None:
        plan = load(B / "main-plan.json")
        rows = [{"path": x["path"], "sha256": x["sha256"]} for x in plan["handoff"]["files"]
                if x["path"].startswith("evas/tests/")]
    assert len(rows) == 20, len(rows)
    files = {}
    for row in rows:
        files[row["path"]] = sha((W / row["path"]).read_bytes())
        assert files[row["path"]] == row["sha256"], row["path"]
    state = {str(p): sha_file(p)[0] for p in (GD / "HEAD", GD / "index", GD.parents[1] / "config", GD.parents[1] / "packed-refs")
             if p.exists()}
    return rows, dict(head=REAL_HEAD, git_state_sha256=state, candidate_sha256=files)


class Stages:
    def __init__(self, out):
        self.path = out / "stages.jsonl"

    def __call__(self, name, **extra):
        with self.path.open("a") as stream:
            stream.write(json.dumps(dict(at=utc(), stage=name, **extra), sort_keys=True) + "\n")


def bring_trusted_code(out):
    code = out / "code/trusted"
    code.mkdir(parents=True)
    for name in SCRIPTS:
        trusted = git("show", TRUSTED + ":scripts/" + name)
        head = git("show", HEAD + ":scripts/" + name)
        s = (S / "scripts" / name).read_bytes()
        assert trusted == head == s, name
        (code / name).write_bytes(trusted)
    sys.path.insert(0, str(code))
    return importlib.import_module("regression_gate"), importlib.import_module("regression_context_registration"), \
        importlib.import_module("ci_evidence"), {n: sha((code / n).read_bytes()) for n in SCRIPTS}


def dut_manifest_digest(gate, rev):
    listing = git("ls-tree", "-r", "-z", rev).split(b"\0")
    paths = {}
    for line in listing:
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        path = path.decode()
        if kind == "blob" and path.startswith(("evas/src/", "evas/rust_core/")) and not (
                {"__pycache__", "target", "baselines", ".git", "runs"} & set(path.split("/"))):
            paths[path] = oid
    files = []  # collector order: directories as listed (evas/src, then evas/rust_core), each in Path order
    for directory in ("evas/src/", "evas/rust_core/"):
        for path in sorted((p for p in paths if p.startswith(directory)), key=PurePosixPath):
            files.append([path, sha(git("cat-file", "blob", paths[path]))])
    return hashlib.sha256(gate._json(files).encode()).hexdigest(), len(files)


def condition_identity(owner, c):
    if c.get("kind") == "subtest":
        return dict(method=owner, **{k: c[k] for k in ("phase", "params", "message", "site", "context")})
    if c.get("kind") in ("method_completion", "method_status"):
        return dict(method=owner, **{k: c[k] for k in ("phase", "kind", "site")})
    return dict(method=owner, **{k: c[k] for k in ("phase", "site")}, context=c["reason"]["context"])


def recompute_condition_ids(report):
    """Re-derive each condition ID the way the trusted collector does; repeats use the occurrence form."""
    direct = repeated = 0
    mismatches = []
    for test in report["tests"]:
        seen = {}
        for c in test["conditions"]:
            base = sha(json.dumps(condition_identity(test["id"], c), sort_keys=True).encode())
            if "repeated_identity" in c:
                ok = (c["repeated_identity"] == base and c["id"] == digest(dict(identity=base, occurrence=seen.get(base, 0))))
                repeated += ok
            else:
                ok = c["id"] == base
                direct += ok
            if not ok:
                mismatches.append([test["id"], c["id"]])
            seen[c.get("repeated_identity", c["id"])] = seen.get(c.get("repeated_identity", c["id"]), 0) + 1
    return dict(direct_exact=direct, repeated_identity_exact=repeated, mismatches=mismatches)


def main(out, stage):
    started = utc()
    role_index = load(I / "verification-r3/role-original-index.json")["roles"]
    index = {}
    for rows in role_index.values():
        for row in rows:
            if "artifact" in row:
                index[(row["artifact"], row["path"])] = row["sha256"]
    delegation = load(D / "delegation.json")
    plan_rows, guard_before = guard()
    stage("guard-before", guard=guard_before)
    gate, reg, ci_evidence, trusted_code = bring_trusted_code(out)
    stage("trusted-code", sha256=trusted_code)

    # ---- inputs actually consumed -------------------------------------------------------
    report_path = A / "python-regression-timings/python-regression.json"
    report_raw = consume(report_path)
    assert sha(report_raw) == NEW_REPORT_SHA == index[("python-regression-timings", "python-regression.json")]
    report = json.loads(report_raw)
    old_raw = consume(OLD_REPORT)
    assert sha(old_raw) == OLD_REPORT_SHA
    old = json.loads(old_raw)
    assert old["metadata"]["criteria_id"] == OLD_CRITERIA
    subject = gate.execution_subject(report)
    old_subject = gate.execution_subject(old)
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
        if path in ci_evidence.EXCLUDED:
            continue
        r = rows[path]
        assert (r["git_mode"], r["observed_blob_oid"], r["index_blob_oid"]) == (mode, oid, oid), path
        entries.append([path, r["git_mode"], r["actual_mode"], r["sha256"]])
    assert len(entries) == 49562 and digest(entries) == INPUT_LIST_SHA, (len(entries), digest(entries))
    path_order_differs = [e[0] for e in entries] != sorted((e[0] for e in entries), key=PurePosixPath)
    shard_identities = []
    for i in range(4):
        identity_path = A / f"python-regression-shard-{i}/regression-identity.json"
        raw_identity = consume(identity_path)
        assert sha(raw_identity) == index[(f"python-regression-shard-{i}", "regression-identity.json")]
        identity = json.loads(raw_identity)
        env = identity["environment"]
        assert digest(dict(version=3, report_schema_version=3, files=entries, environment=env)) == identity["key"]
        assert identity["input_count"] == len(entries)
        assert ci_evidence.comparison_subject(entries, env) == identity["comparison_subject"]
        assert identity["excluded"] == sorted(ci_evidence.EXCLUDED)
        shard_identities.append(identity)
    stage("snapshot", entries=len(entries), input_list_sha256=INPUT_LIST_SHA, git_order_differs_from_path_order=path_order_differs)

    files_by_path = {e[0]: e[3] for e in entries}
    collector = {role: files_by_path[path] for role, path in COLLECTOR.items()}
    assert digest(collector) == report["metadata"]["collector_sha256"]
    for path in COLLECTOR.values():
        assert sha(git("show", HEAD + ":" + path)) == files_by_path[path] == sha((S / path).read_bytes()), path
    assert files_by_path["evas/capabilities/data/language-profile.json"] == report["metadata"]["language_profile"]

    dut_checks = {rev: dut_manifest_digest(gate, rev) for rev in (DUT_REVISION, TRUSTED, HEAD)}
    for rev, (value, count) in dut_checks.items():
        assert value == subject["dut_files_sha256"] and count == len(report["source_identity"]["dut_files"]), rev
    stage("dut-manifest", revisions={k: v[0] for k, v in dut_checks.items()})

    # ---- ten role files -----------------------------------------------------------------
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
        path = A / f"python-regression-shard-{i}/regression-build/evas-kernel"
        h, n = consume_streamed(path)
        assert h == index[(f"python-regression-shard-{i}", "regression-build/evas-kernel")] == KERNEL_SHA
        kernel_rows.append(dict(shard_index=i, path=str(path), bytes=n, sha256=h))
    assert len({r["bytes"] for r in kernel_rows}) == 1
    kernel_target = bundle / "kernel_binary"
    h = hashlib.sha256()
    with open(A / "python-regression-shard-0/regression-build/evas-kernel", "rb") as src, kernel_target.open("xb") as dst:
        for block in iter(lambda: src.read(1 << 20), b""):
            h.update(block)
            dst.write(block)
    assert h.hexdigest() == KERNEL_SHA and kernel_target.stat().st_size == kernel_rows[0]["bytes"]
    stage("kernel-copied-not-executed", sha256=KERNEL_SHA, mode=oct(kernel_target.stat().st_mode & 0o777))

    boundaries = {}
    streams = {}
    for role in ("stdout", "stderr"):
        pieces, rows_out, offset = [], [], 0
        for i in range(4):
            path = A / f"python-regression-shard-{i}/regression-evidence/{role}.txt"
            data = consume(path)
            assert sha(data) == index[(f"python-regression-shard-{i}", f"regression-evidence/{role}.txt")]
            rows_out.append(dict(shard_index=i, source=str(path.relative_to(B)), offset=offset, bytes=len(data), sha256=sha(data)))
            pieces.append(data)
            offset += len(data)
        joined = b"".join(pieces)
        put(role, joined)
        streams[role] = joined
        boundaries[role] = dict(parts=rows_out, total_bytes=len(joined), total_sha256=sha(joined),
                                order="ascending shard_index 0..3, plain byte concatenation without separator")
    (out / "stream-boundaries.json").write_bytes(dump(boundaries))

    shard_bytes, shard_texts = [], []
    for i in range(4):
        path = A / f"python-regression-shard-{i}/regression-evidence/report.json"
        data = consume(path)
        assert sha(data) == index[(f"python-regression-shard-{i}", "regression-evidence/report.json")]
        text = data.decode("utf-8")
        assert text.encode("utf-8") == data  # no newline translation or lossy decode
        shard_bytes.append(data)
        shard_texts.append(text)
    assert report["parts"] and [p["shard_index"] for p in report["parts"]] == [0, 1, 2, 3]
    shard_file = put("shard_reports", dump(shard_texts))
    assert [t.encode() for t in json.loads(written["shard_reports"])] == shard_bytes

    profile = {k: report["metadata"][k] for k in ("language_profile", "runtime_profile", "invocation")}
    recipe = dict(schema_version=1, dut_revision=DUT_REVISION, snapshot_sha256=snapshot_sha,
                  dut_manifest_sha256=subject["dut_files_sha256"], kernel_sha256=subject["kernel_sha256"],
                  criteria_id=report["metadata"]["criteria_id"], collector_sha256=report["metadata"]["collector_sha256"],
                  profile_sha256=digest(profile))
    put("composition_recipe", dump(recipe))

    build_rows = []
    for i in range(4):
        row = {}
        for name in ("stdout.txt", "stderr.txt"):
            path = A / f"python-regression-shard-{i}/regression-build/{name}"
            data = consume(path)
            assert sha(data) == index[(f"python-regression-shard-{i}", "regression-build/" + name)]
            row[name] = dict(bytes=len(data), sha256=sha(data))
        build_rows.append(row)
    env0 = shard_identities[0]["environment"]
    identity_shas = [CONSUMED[str(A / f"python-regression-shard-{i}/regression-identity.json")]["sha256"] for i in range(4)]
    toolchain = (RUN_URL + " attempt 1; actual regression-identity.json environment of all four shards (sha256 "
                 + ", ".join(identity_shas) + "): python " + env0["python"].split()[0] + ", " + env0["rustc"].splitlines()[0]
                 + ", " + env0["cargo"].splitlines()[0] + ", platform " + env0["platform"]
                 + "; originals under raw-intake-sol/artifacts/python-regression-shard-{0,1,2,3}/")
    build_reference = (RUN_URL + " attempt 1, head " + HEAD + " (tree " + TREE + "); CI checked out refs/pull/266/merge "
                       + MERGE_OBJECT + " whose commit object is NOT locally verified (inventory tree equals the head tree); "
                       "original regression-build/{stdout.txt,stderr.txt,evas-kernel} of all four shards retained and bound: kernel sha256 "
                       + KERNEL_SHA + " identical in 4 shards; build stdout sha256 "
                       + "/".join(r["stdout.txt"]["sha256"][:16] for r in build_rows) + " (all empty); build stderr sha256 "
                       + "/".join(r["stderr.txt"]["sha256"][:16] for r in build_rows)
                       + "; DUT manifest equals reviewed " + DUT_REVISION + " (also " + TRUSTED + " and " + HEAD + "); kernel not executed here")
    put("dut_build", dump(dict(schema_version=1, dut_revision=DUT_REVISION, dut_manifest_sha256=subject["dut_files_sha256"],
                               kernel_sha256=subject["kernel_sha256"], toolchain_reference=toolchain, build_reference=build_reference)))
    receipt_digest = sha_file(I / "artifact-download-receipt.json")[0]
    capture_reference = (RUN_URL + " attempt 1; original zipped artifact index " + str(I / "artifact-download-receipt.json")
                         + " (sha256 " + receipt_digest + "), 13 archives / 467 members verified in raw-intake-sol/verification-r3/archive-members-verified.json; "
                         "report.json is the original python-regression-timings/python-regression.json byte for byte; "
                         "shard_reports are the four original regression-evidence/report.json texts in shard-index order; "
                         "stdout/stderr are exact shard-index-order concatenations with byte boundaries in ../stream-boundaries.json")
    artifact_manifest = dict(schema_version=1, raw_report_sha256=sha(report_raw), capture_reference=capture_reference,
                             stdout_sha256=sha(streams["stdout"]), stderr_sha256=sha(streams["stderr"]),
                             shard_report_sha256=[sha(x) for x in shard_bytes])
    put("artifact_manifest", dump(artifact_manifest))
    kernel_bytes = None  # streamed copy above; role payload re-read below for the production probe
    assert len(written) == 9 and (bundle / "kernel_binary").exists() and len(list(bundle.iterdir())) == 10
    stage("bundle-written", files=10)

    # ---- production evidence function probe (in-memory harness; no authorization is created) --
    kernel_bytes = (bundle / "kernel_binary").read_bytes()
    locators = {role: "bundle/" + role for role in ("composition_recipe", "snapshot_manifest", "dut_build", "kernel_binary",
                                                  "collector_manifest", "artifact_manifest", "stdout", "stderr", "shard_reports")}
    blobs = {role: (bundle / role).read_bytes() for role in locators}
    harness_auth = dict(
        artifacts={role: dict(sha256=sha(blobs[role]), locator=locators[role]) for role in locators},
        current_dut=dict(manifest_sha256=old_subject["dut_files_sha256"], kernel_sha256=old_subject["kernel_sha256"]),
        e1=dict(raw_sha256=sha(report_raw), execution_subject=subject))
    provenance = dict(schema_version=1, snapshot_revision=HEAD,
                      snapshot_reference=(REPO_URL + "/tree/" + HEAD + "; CI inventory checkout " + MERGE_OBJECT
                                          + " is unverified locally, its recorded tree equals the head tree " + TREE),
                      raw_reference=RUN_URL + " attempt 1; original zipped artifact index and members retained in raw-intake-sol",
                      recipe_sha256=sha(blobs["composition_recipe"]), artifact_manifest_sha256=sha(blobs["artifact_manifest"]))
    reg.evidence(harness_auth, blobs, gate, report, dict(source_identity=provenance), old_subject)
    stage("production-evidence-function-pass")
    del blobs, kernel_bytes

    # ---- trusted-gate behaviour on the unchanged baseline (expected rejection) ----------------
    baseline_raw = git("show", TRUSTED + ":evas/validation/baselines/regression-v1.json")
    baseline = json.loads(baseline_raw)
    assert baseline_raw == git("show", HEAD + ":evas/validation/baselines/regression-v1.json")
    new_compare = gate.compare_report(report, baseline)
    old_compare = gate.compare_report(old, baseline)
    expected_rejection = (new_compare["merge_allowed"] is False and new_compare["valid"] is True
                          and new_compare["differences"] == ["expected exactly one matching trusted baseline context"])
    assert expected_rejection, new_compare["differences"][:3]
    stage("trusted-gate-compare", new_merge_allowed=new_compare["merge_allowed"], old_merge_allowed=old_compare["merge_allowed"],
          old_differences=old_compare["differences"][:3], new_differences=new_compare["differences"])

    # ---- obligation map ---------------------------------------------------------------------
    a = {t["id"]: t for t in old["tests"]}
    b = {t["id"]: t for t in report["tests"]}
    assert a.keys() == b.keys() and list(a) == list(b)
    assert old["fixtures"] == report["fixtures"] == [] and old["setup_skipped_test_ids"] == report["setup_skipped_test_ids"] == []
    mapping, outcomes, kinds = [], {}, {}
    method_mismatch, id_set_mismatch, retention_differs, outcome_differs, order_differs = [], [], [], [], []
    for owner in a:
        ac, bc = a[owner]["conditions"], b[owner]["conditions"]
        if a[owner]["outcome"] != b[owner]["outcome"]:
            method_mismatch.append(owner)
        da, db = {c["id"]: c for c in ac}, {c["id"]: c for c in bc}
        assert len(da) == len(ac) and len(db) == len(bc)
        if da.keys() != db.keys():
            id_set_mismatch.append(owner)
            continue
        if [c["id"] for c in ac] != [c["id"] for c in bc]:
            order_differs.append(owner)
        for before in ac:
            after = db[before["id"]]
            if before["outcome"] != after["outcome"]:
                outcome_differs.append([owner, before["id"]])
            if gate._retention_condition(before) != gate._retention_condition(after):
                retention_differs.append([owner, before["id"]])
            outcomes[before["outcome"]] = outcomes.get(before["outcome"], 0) + 1
            kinds[str(before.get("kind"))] = kinds.get(str(before.get("kind")), 0) + 1
            mapping.append(dict(
                old_owner=owner, old_condition=before["id"],
                old_signature_sha256=reg.digest(gate._retention_condition(before)),
                new_owner=owner, new_condition=after["id"],
                new_signature_sha256=reg.digest(gate._retention_condition(after)),
                classification="preserved",
                review_reference=("DRAFT primary source-bound mapping; independent exact-context acceptance PENDING; "
                                  "not an approval, authority or baseline; see obligation-map-proof.json"),
                attribution=None))
    unmapped = dict(method_outcome_mismatch=method_mismatch, condition_id_set_mismatch=id_set_mismatch,
                    retention_signature_differs=retention_differs, condition_outcome_differs=outcome_differs)
    if any(unmapped.values()):
        # Do not invent a mapping for what is not identical: keep the evidence and stop.
        (out / "unmapped-obligations.json").write_bytes(dump(unmapped))
        raise RuntimeError("old obligations not exactly identical in the new report; see unmapped-obligations.json")
    assert len(mapping) == 7737
    reg.mapped_obligations(dict(obligation_mapping=mapping), gate, old, report)
    stage("mapped-obligations-pass", count=len(mapping))

    # per-condition source verification: module hash -> unique criteria path -> actual S blob bytes
    crit_new, crit_old = dict(report["source_identity"]["criteria_files"]), dict(old["source_identity"]["criteria_files"])
    modules = {}
    for t in report["tests"]:
        for c in t["conditions"]:
            modules.setdefault((c["site"]["module"], c["site"]["source_sha256"]), []).append(c["site"]["line"])
    source_rows, source_problems = [], []
    for (module, checksum), lines in sorted(modules.items()):
        paths = [p for p, h in crit_new.items() if h == checksum and p.endswith("/" + module + ".py")]
        if len(paths) != 1:
            source_problems.append([module, checksum, paths])
            continue
        path = paths[0]
        blob = git("show", HEAD + ":" + path)
        text = blob.decode("utf-8")
        ok = sha(blob) == checksum and crit_old.get(path) == checksum and files_by_path[path] == checksum
        in_range = max(lines) <= len(text.splitlines())
        source_rows.append(dict(module=module, path=path, sha256=checksum, git_blob_sha256_matches=sha(blob) == checksum,
                                same_in_old_criteria=crit_old.get(path) == checksum, in_snapshot=files_by_path[path] == checksum,
                                condition_sites=len(lines), max_line=max(lines), lines_within_file=in_range))
        if not ok or not in_range:
            source_problems.append([module, checksum, path])
    new_ids, old_ids = recompute_condition_ids(report), recompute_condition_ids(old)
    stage("source-bindings", modules=len(source_rows), problems=len(source_problems))

    mapping_bytes = (json.dumps(mapping, indent=2) + "\n").encode()
    with (out / "obligation-map-draft.json").open("xb") as stream:
        stream.write(mapping_bytes)
    nonpass = {k: v for k, v in outcomes.items() if k != "passed"}
    proof = dict(
        schema_version=1,
        status="DRAFT; independent exact-context acceptance PENDING; not an approval, authority, baseline or review record",
        old_report=dict(path=str(OLD_REPORT), sha256=OLD_REPORT_SHA, criteria_id=OLD_CRITERIA),
        new_report=dict(path=str(report_path), sha256=NEW_REPORT_SHA, criteria_id=report["metadata"]["criteria_id"]),
        methods=dict(old=len(a), new=len(b), id_sets_equal=True, order_equal=True, outcome_mismatch=method_mismatch,
                     outcomes=_count(t["outcome"] for t in b.values())),
        conditions=dict(old=sum(len(t["conditions"]) for t in a.values()), new=sum(len(t["conditions"]) for t in b.values()),
                        mapped=len(mapping), id_set_mismatch_methods=id_set_mismatch, order_differs_methods=order_differs,
                        outcome_differs=outcome_differs, retention_signature_differs=retention_differs,
                        exactly_identical_retention_signature=len(mapping) - len(retention_differs),
                        outcomes=outcomes, nonpassing=nonpass, kinds=kinds),
        classification_counts=dict(preserved=len(mapping)),
        classification_basis=("gate._retention_condition equal for every old/new condition bound by condition id and method id, "
                              "equal outcomes, attribution null; matches the existing 'preserved' contract in regression_context_registration.mapped_obligations"),
        no_mechanical_remap_needed=True, corrected_variants=[], unknown_or_unmapped=unmapped,
        fixtures=dict(old=0, new=0, setup_skipped_old=0, setup_skipped_new=0),
        condition_id_recomputation=dict(old={k: (v if k != "mismatches" else len(v)) for k, v in old_ids.items()},
                                        new={k: (v if k != "mismatches" else len(v)) for k, v in new_ids.items()},
                                        old_mismatches=old_ids["mismatches"], new_mismatches=new_ids["mismatches"],
                                        formula="collector.condition identity digest; repeated_identity form json_digest(identity, occurrence)"),
        source_bindings=dict(distinct_module_hash_pairs=len(source_rows), unresolved_or_changed=source_problems, rows=source_rows,
                             basis="site.source_sha256 -> unique criteria path -> equals new criteria, old criteria, snapshot entry and actual 983b Git blob bytes"),
        draft_file=dict(path="obligation-map-draft.json", bytes=len(mapping_bytes), sha256=sha(mapping_bytes),
                        canonical_mapping_sha256=reg.digest(mapping)),
        production_function_results=dict(mapped_obligations="pass", evidence="pass (in-memory harness authorization, none written)"),
        trusted_gate_on_unchanged_baseline=dict(new_report=dict(valid=new_compare["valid"], merge_allowed=new_compare["merge_allowed"],
                                                                   differences=new_compare["differences"]),
                                                old_report_merge_allowed=old_compare["merge_allowed"]),
        independent_review_approved=False, semantic_qualification=False, scientific_qualification=False,
        scientific_thresholds_added=False)
    (out / "obligation-map-proof.json").write_bytes(dump(proof))

    # ---- bindings and receipt ----------------------------------------------------------------
    ten = []
    for name in sorted(p.name for p in bundle.iterdir()):
        h2, n2 = sha_file(bundle / name)
        ten.append(dict(path="bundle/" + name, bytes=n2, sha256=h2))
    (out / "bundle-byte-binding.json").write_bytes(dump(dict(
        run=RUN, attempt=1, head=HEAD, tree=TREE, trusted_base=TRUSTED, ci_merge_checkout=MERGE_OBJECT,
        ci_merge_checkout_locally_verified=False, files=ten,
        ten_file_bundle_bytes_verified_by_production_evidence_function=True,
        evidence_function="regression_context_registration.evidence (e10 blob) with an in-memory harness; no authorization object exists in any output",
        snapshot_entries=len(entries), snapshot_entry_order="git ls-files order as written by ci_evidence.fingerprint; reproduces each shard identity key",
        snapshot_order_differs_from_Path_sort=path_order_differs,
        entry_provenance_preview=provenance, role_sources=dict(
            report="python-regression-timings/python-regression.json (byte copy)",
            shard_reports="4 x python-regression-shard-N/regression-evidence/report.json texts as JSON array",
            kernel_binary="python-regression-shard-0/regression-build/evas-kernel (byte copy, 4 shards identical, never executed)",
            stdout="shard-index-order concatenation", stderr="shard-index-order concatenation",
            snapshot_manifest="catalog-inventory/assets-before.json x git ls-tree order, reproduces input_list_sha256 and 4 identity keys",
            collector_manifest="four collector source SHA256 from snapshot + 983b blobs",
            composition_recipe="derived", dut_build="derived from shard build records and identities", artifact_manifest="derived"),
        governance_authorization_created=False, E1_or_new_context_accepted=False, semantic_qualification=False)))
    after_rows, guard_after = guard(plan_rows)
    assert guard_after == guard_before
    (out / "guard-before.json").write_bytes(dump(guard_before))
    (out / "guard-after.json").write_bytes(dump(guard_after))
    finished = utc()
    receipt = dict(
        purpose="Compose PR266 983b ten-role bundle and draft obligation map (data composition and proof only)",
        started_at_utc=started, finished_at_utc=finished, queue_time_seconds=None, queue_time="unknown",
        actual_model=dict(providerInstanceId=delegation.get("providerInstanceId"), model=delegation.get("model"), options=delegation.get("options")),
        delegation_task_id=delegation.get("taskId"),
        identity=dict(ci_run=RUN, attempt=1, ci_conclusion="failure", head=HEAD, tree=TREE, trusted_base=TRUSTED,
                      source_capture=SOURCE_CAPTURE, ci_merge_checkout=MERGE_OBJECT, ci_merge_checkout_verified=False,
                      ci_merge_checkout_expectation=dict(parents=[TRUSTED, HEAD], tree=TREE, status="expected, not observed"),
                      current_context_report=dict(sha256=OLD_REPORT_SHA, criteria_id=OLD_CRITERIA),
                      new_context_report=dict(sha256=NEW_REPORT_SHA, criteria_id=report["metadata"]["criteria_id"])),
        status=dict(
            execution_success=True,
            structure_complete=True,
            expected_rejection_reproduced=expected_rejection,
            expected_rejection_text="expected exactly one matching trusted baseline context",
            semantic_qualification=False, scientific_qualification=False, merge_allowed=False, raw_successful=report["successful"],
            independent_review_approved=False, authorization_created=False, baseline_written=False),
        counts=dict(methods=len(b), conditions=len(mapping), snapshot_entries=len(entries), shards=4, bundle_files=10,
                    method_outcomes=_count(t["outcome"] for t in b.values())),
        trusted_code_sha256=trusted_code, dut_manifest_checks={k: dict(sha256=v[0], files=v[1]) for k, v in dut_checks.items()},
        kernel=dict(sha256=KERNEL_SHA, bytes=kernel_rows[0]["bytes"], executed=False, shards=kernel_rows),
        stream_boundaries="stream-boundaries.json", consumed_inputs=CONSUMED,
        reused_not_reverified=dict(archives=13, members=467, source="raw-intake-sol/verification-r3/archive-members-verified.json",
                                   index_sha256=sha_file(I / "verification-r3/archive-members-verified.json")[0]),
        outputs=ten + [dict(path=n, bytes=(out / n).stat().st_size, sha256=sha_file(out / n)[0])
                       for n in ("obligation-map-draft.json", "obligation-map-proof.json", "bundle-byte-binding.json",
                                 "stream-boundaries.json", "guard-before.json", "guard-after.json")],
        guard_equal_before_after=True, new_scientific_thresholds=False, fetch_performed=False, fixture_created=False,
        python=sys.version.split()[0], command=[sys.executable, "-B", str(Path(__file__).resolve()), "--output", str(out)])
    (out / "receipt.json").write_bytes(dump(receipt))
    print(json.dumps(dict(output=str(out), files=10, methods=len(b), conditions=len(mapping), expected_rejection=expected_rejection,
                          semantic_qualification=False), indent=1))


def _count(values):
    result = {}
    for v in values:
        result[v] = result.get(v, 0) + 1
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = safe_new_directory(args.output)
    target.mkdir()
    log = Stages(target)
    try:
        main(target, log)
    except BaseException:
        (target / "failure.json").write_bytes(dump(dict(at=utc(), traceback=traceback.format_exc(), kept="all partial outputs retained")))
        raise
