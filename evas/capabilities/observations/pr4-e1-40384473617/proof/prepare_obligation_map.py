"""Draft complete source-bound obligation pairs, without asserting independent approval."""
from pathlib import Path
import copy,difflib,hashlib,json,os,re,subprocess,sys
R=Path(__file__).resolve().parent
B=R.parent.parents[1]
sys.path.insert(0,str(R.parent/"source/scripts"))
import regression_gate as gate, regression_context_registration as reg
OLD=B/"pr4/bootstrap-integration-20261026/local-only-fix/ci-40358433992/artifacts/python-regression-timings/python-regression.json"
old=json.loads(OLD.read_text());new=json.loads((R/"e1-bundle-preview/report.json").read_text())
a={t["id"]:t for t in old["tests"]};b={t["id"]:t for t in new["tests"]};assert a.keys()==b.keys()
cmd=["/usr/bin/git","--no-lazy-fetch","--git-dir=/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night","--work-tree=/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night"]
env={k:v for k,v in os.environ.items() if not k.startswith("GIT_")}
info={}
for module in ("test_bound_step","test_deferred_rdist","test_source_math"):
    raws=[subprocess.check_output(cmd+["show",rev+":evas/tests/"+module+".py"],env=env) for rev in ("842bde7101164330fa03e7aee58b45d1789cbed1","168a9d7a4305e7ce21d1577b4ca1dda65beae4ce")]
    lines=[r.decode().splitlines() for r in raws]
    pairs={x+1:y+1 for aa,bb,size in difflib.SequenceMatcher(a=lines[0],b=lines[1],autojunk=False).get_matching_blocks() for x,y in zip(range(aa,aa+size),range(bb,bb+size))}
    info[module]={"old_sha":hashlib.sha256(raws[0]).hexdigest(),"new_sha":hashlib.sha256(raws[1]).hexdigest(),"lines":pairs}
def transform(value,module):
    i=info[module]
    if isinstance(value,list):return [transform(x,module) for x in value]
    if not isinstance(value,dict):return value
    out={k:transform(v,module) for k,v in value.items()}
    if "source_sha256" in out and out["source_sha256"]==i["old_sha"]:
        out["source_sha256"]=i["new_sha"]
        if "line" in out:out["line"]=i["lines"][out["line"]]
    elif "function" in out and "line" in out and "values" in out:
        out["line"]=i["lines"][out["line"]]
    if "python_code" in out:
        pairs=out["python_code"]["mapping_items"]
        old_pairs=dict(value["python_code"]["mapping_items"])
        if old_pairs.get("source_sha256")==i["old_sha"]:
            out["python_code"]["mapping_items"]=[[k,i["new_sha"] if k=="source_sha256" else i["lines"][v] if k=="line" else v] for k,v in pairs]
    if "traceback" in out:
        pattern=r'(evas/tests/'+re.escape(module)+r'\.py", line )(\d+)'
        out["traceback"]=re.sub(pattern,lambda m:m[1]+str(i["lines"][int(m[2])]),out["traceback"])
    return out
def condition_id(owner,c):
    if c.get("kind")=="subtest":
        identity={"method":owner,**{k:c[k] for k in ("phase","params","message","site","context")}}
    elif c.get("kind") in ("method_completion","method_status"):
        identity={"method":owner,**{k:c[k] for k in ("phase","kind","site")}}
    else:
        identity={"method":owner,**{k:c[k] for k in ("phase","site")},"context":c["reason"]["context"]}
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
mapping=[];proofs=[];mechanical=exact=manual=0
for owner in sorted(a):
    ac=a[owner]["conditions"];bc=b[owner]["conditions"]
    assert a[owner]["outcome"]==b[owner]["outcome"] and len(ac)==len(bc)
    for before,after in zip(ac,bc):
        assert before["outcome"]==after["outcome"]
        if gate._retention_condition(before)==gate._retention_condition(after):
            kind="identical-source-bound-condition";exact+=1
        else:
            module=owner.split(".")[0];assert module in info
            assert condition_id(owner,before)==before["id"] and condition_id(owner,after)==after["id"]
            if owner=="test_deferred_rdist.DeferredRdist.test_bad_raw_leaf_seed_and_signature_are_rejected":
                fields=dict(dict(before["params"]["bad"]["state"]["mapping_items"])["fields"]["mapping_items"])
                variant=("function" if fields["function"]=="rdist_uniform" else "seed" if fields["seed"]==0 else "arity" if len(fields["args"]["tuple"])==1 else None)
                assert variant and after["params"]=={"field":variant}
                expected_reason="system function seed requires same-instance integer state" if variant=="seed" else "invalid deferred system function signature"
                assert after["context"][0]["values"]["reason"]==expected_reason and after["context"][0]["values"]["name"]==variant
                kind="corrected-negative-control-preserves-function-seed-arity-variant";manual+=1
                proofs.append({"owner":owner,"old_condition":before["id"],"new_condition":after["id"],"variant":variant,"new_expected_diagnostic":expected_reason,"classification":"pending independent exact mapping approval","proof":"fixed Git diff replaces the actual selected event and adds unchanged-leaf control; original malformed leaf variant preserved; per-case detector calibration and CI pass retained"})
            else:
                normalized=transform(before,module)
                normalized["id"]=condition_id(owner,normalized)
                assert normalized==after,(owner,before["id"])
                kind="exact-unchanged-line-and-module-hash-remap";mechanical+=1
        mapping.append(dict(old_owner=owner,old_condition=before["id"],old_signature_sha256=reg.digest(gate._retention_condition(before)),new_owner=owner,new_condition=after["id"],new_signature_sha256=reg.digest(gate._retention_condition(after)),classification="preserved",review_reference="DRAFT primary source-bound mapping; independent Astra exact-context decision PENDING; see condition-mapping-proof.json",attribution=None))
# No setup/module fixtures existed in either original raw; no omitted fixture obligations.
assert old["fixtures"]==new["fixtures"]==[]
reg.mapped_obligations({"obligation_mapping":mapping},gate,old,new)
(R/"obligation-map-draft.json").write_text(json.dumps(mapping,indent=2)+"\n")
proof=dict(total_old_obligations=len(mapping),identical=exact,mechanical_source_location_remaps=mechanical,corrected_negative_controls=manual,corrected_variants=proofs,source_bound_draft_structurally_complete=True,independent_review_approved=False,E1_accepted=False,semantic_qualification=False,notes="All outcomes and counts preserved. Mechanical mapping uses exact unchanged source lines, hashes and encoded Python code location only; original/new condition IDs recomputed from unchanged collector. Five changed method bodies separately require the existing detector calibration and independent review.")
(R/"condition-mapping-proof.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps({k:v for k,v in proof.items() if k not in ("corrected_variants","notes")}))

