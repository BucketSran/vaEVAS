"""Verify fixed CI artifacts and record deltas, without invoking a simulator."""
from pathlib import Path
import collections, hashlib, json, os, subprocess, sys
R=Path(__file__).resolve().parent
I=R.parent
B=I.parents[1]
W=Path("/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night")
GD=Path("/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night")
H="168a9d7a4305e7ce21d1577b4ca1dda65beae4ce"
TREE="32034ffd54c8006ac13ff4d475aaf5313b6e436e"
OLD=B/"pr4/bootstrap-integration-20261026/local-only-fix/ci-40358433992"
ENV={k:v for k,v in os.environ.items() if not k.startswith("GIT_")}
def git(*argv):
    return subprocess.check_output(["/usr/bin/git","--no-lazy-fetch","--git-dir="+str(GD),"--work-tree="+str(W),*argv],env=ENV)
def load(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def digest(v):return sha(json.dumps(v,sort_keys=True,separators=(",",":")).encode())
def write(n,v):(R/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n")
assert git("rev-parse",H+"^{tree}").decode().strip()==TREE
for f in ("run_regression.py","regression_gate.py","ci_evidence.py","regression_reason_identity.py","regression_observation_policy.json"):
    assert (I/"source/scripts"/f).read_bytes()==git("show",H+":scripts/"+f),f
sys.path.insert(0,str(I/"source/scripts"))
import ci_evidence,run_regression,regression_gate as gate
A=R/"artifacts"
summary=load(A/"catalog-inventory/summary.json")
assert all(summary[k] is True for k in ("success","reconciled","construction_complete"))
assert summary["errors"]==[] and summary["scientific_execution"] is False
before=load(A/"catalog-inventory/assets-before.json")
after=load(A/"catalog-inventory/assets-after.json")
assert before["assets"]==after["assets"]
assert before["source_tree"]==TREE and not before["dirty_paths"]
rows=before["assets"]
by_path={r["path"]:r for r in rows}; assert len(by_path)==len(rows)
expected={}
for line in git("ls-tree","-r","-z",H).split(b"\0"):
    if line:
        meta,path=line.split(b"\t",1);mode,kind,oid=meta.decode().split()
        assert kind=="blob";expected[path.decode()]=(mode,oid)
assert by_path.keys()==expected.keys()
old_rows={r["path"]:r for r in load(OLD/"artifacts/catalog-inventory/assets-before.json")["assets"]}
changed_assets=[];reused=0
for path,(mode,oid) in expected.items():
    row=by_path[path]
    assert (row["git_mode"],row["observed_blob_oid"],row["index_blob_oid"])==(mode,oid,oid),path
    prior=old_rows.get(path)
    if prior and (prior["git_mode"],prior["observed_blob_oid"],prior["index_blob_oid"])==(mode,oid,oid):
        assert (row["sha256"],row["actual_mode"])==(prior["sha256"],prior["actual_mode"]),path
        reused+=1
    else:
        raw=git("show",H+":"+path)
        assert sha(raw)==row["sha256"],path
        assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==oid,path
        assert row["actual_mode"]==(0o755 if mode=="100755" else 0o644),path
        changed_assets.append(path)
entries=[[p,by_path[p]["git_mode"],by_path[p]["actual_mode"],by_path[p]["sha256"]] for p in expected if p not in ci_evidence.EXCLUDED]
write("snapshot-manifest-observed.json",dict(candidate=H,tree=TREE,actual_checkout=before["source_commit"],input_entries=entries,source_asset_receipt_sha256=sha((A/"catalog-inventory/assets-before.json").read_bytes()),reused_verified_old_assets=reused,changed_assets=changed_assets))
shards=[];paths=[]
for i in range(4):
    F=A/f"python-regression-shard-{i}"
    report=load(F/"regression-evidence/report.json");identity=load(F/"regression-identity.json");receipt=load(F/"regression-evidence/collection.json")
    ci_evidence.bound_report(report,identity,f"{i}-of-4")
    assert receipt["valid"] and receipt["raw_exit"]==1 and receipt["cacheable"] is False
    assert receipt["report_sha256"]==sha((F/"regression-evidence/report.json").read_bytes())
    assert receipt["identity_key"]==identity["key"]
    assert identity["excluded"]==sorted(ci_evidence.EXCLUDED) and identity["input_count"]==len(entries)
    expected_key=digest(dict(version=3,report_schema_version=3,files=entries,environment=identity["environment"]))
    assert expected_key==identity["key"]
    assert ci_evidence.comparison_subject(entries,identity["environment"])==identity["comparison_subject"]
    kernel=sha((F/"regression-build/evas-kernel").read_bytes())
    assert kernel==identity["environment"]["kernel_sha256"]==report["source_identity"]["kernel_sha256"]
    events=[json.loads(x) for x in (F/"regression-evidence/report.jsonl").read_text().splitlines()]
    stops=[e for e in events if e["event"]=="stop"]
    assert [{k:v for k,v in e.items() if k!="event"} for e in stops]==report["tests"]
    assert collections.Counter(e["id"] for e in events if e["event"]=="start")==collections.Counter(report["selected_test_ids"])
    paths.append(F/"regression-evidence/report.json")
    shards.append(dict(index=i,methods=report["tests_run"],raw_exit=receipt["raw_exit"],cacheable=False,input_fingerprint=expected_key,kernel_sha256=kernel,jsonl_exact=True,retained_stdout_bytes=(F/"regression-evidence/stdout.txt").stat().st_size,retained_stderr_bytes=(F/"regression-evidence/stderr.txt").stat().st_size))
rawpath=A/"python-regression-timings/python-regression.json"
report=load(rawpath);assert run_regression.merge_reports(paths)==report
valid=gate.validate_report(report);assert valid["valid"],valid
old=load(OLD/"artifacts/python-regression-timings/python-regression.json")
a={r["id"]:r for r in old["tests"]};b={r["id"]:r for r in report["tests"]};assert a.keys()==b.keys()
assert report["setup_skipped_test_ids"]==old["setup_skipped_test_ids"]==[]
assert report["skipped"]==old["skipped"]==0 and report["expected_failures"]==old["expected_failures"]==3
subject=gate.execution_subject(report);prior_subject=gate.execution_subject(old)
assert subject["dut_files_sha256"]==prior_subject["dut_files_sha256"]=="5e9bf28ad121569a6975811f0b5ea9e60423e676e6dfcf88048948bfd19ba056"
assert subject["kernel_sha256"]==prior_subject["kernel_sha256"]=="b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe"
for key in old["metadata"]:
    if key!="criteria_id":assert report["metadata"][key]==old["metadata"][key],key
criteria_old=dict(old["source_identity"]["criteria_files"]);criteria_new=dict(report["source_identity"]["criteria_files"])
criteria_diff=[p for p in sorted(criteria_old.keys()|criteria_new.keys()) if criteria_old.get(p)!=criteria_new.get(p)]
method_deltas=[]
for method in sorted(a):
    prior={c["id"]:gate._signature(c) for c in a[method]["conditions"]}
    now={c["id"]:gate._signature(c) for c in b[method]["conditions"]}
    if prior!=now or a[method]["outcome"]!=b[method]["outcome"]:
        method_deltas.append(dict(id=method,old_outcome=a[method]["outcome"],new_outcome=b[method]["outcome"],old_conditions=a[method]["conditions"],new_conditions=b[method]["conditions"],old_ids_only=sorted(prior.keys()-now.keys()),new_ids_only=sorted(now.keys()-prior.keys()),same_id_signature_changes=[c for c in prior.keys()&now.keys() if prior[c]!=now[c]]))
write("condition-deltas.json",method_deltas)
baseline=json.loads(git("show","842bde7101164330fa03e7aee58b45d1789cbed1:evas/validation/baselines/regression-v1.json"))
comparison=gate.compare_report(report,baseline)
admission=load(A/"python-regression-admission/regression-admission.json")
assert admission["trusted_comparison"]==comparison and comparison["merge_allowed"] is False
assert comparison["differences"]==["expected exactly one matching trusted baseline context"]
out=dict(run=40384473617,candidate=H,tree=TREE,actual_checkout=before["source_commit"],artifact_archive_hashes_verified=load(R/"artifact-download-receipt.json"),actual_assets=len(rows),unchanged_assets_reused=reused,changed_assets_verified=changed_assets,full_input_count=len(entries),shards=shards,merged_exact=True,raw_sha256=sha(rawpath.read_bytes()),methods=len(b),conditions=sum(len(t["conditions"]) for t in b.values()),method_outcomes=dict(collections.Counter(t["outcome"] for t in b.values())),unittest_condition_counters={k:report[k] for k in ("failures","errors","skipped","expected_failures")},raw_successful=report["successful"],method_ids_preserved=True,method_outcome_changes=[r["id"] for r in method_deltas if r["old_outcome"]!=r["new_outcome"]],condition_delta_methods=[r["id"] for r in method_deltas],criteria_changed_paths=criteria_diff,D0_and_kernel_unchanged=True,other_context_profiles_unchanged=True,admission=comparison,semantic_qualification=False,E1_acceptance="pending independent review and precise source-bound condition delta mapping",whole_CI_accepted=False)
write("raw-verification.json",out)
print(json.dumps({k:out[k] for k in ("actual_assets","unchanged_assets_reused","full_input_count","methods","conditions","method_outcomes","method_outcome_changes","condition_delta_methods","criteria_changed_paths","D0_and_kernel_unchanged","semantic_qualification")}))

