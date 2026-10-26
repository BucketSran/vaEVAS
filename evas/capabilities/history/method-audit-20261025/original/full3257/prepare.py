import ast, collections, csv, hashlib, inspect, json, sys, unittest
from pathlib import Path

ROOT = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
OUT = Path(__file__).resolve().parent
BASE = OUT.parent
sys.path[:0] = [str(ROOT/'evas/src'), str(ROOT/'evas/tests')]
summary = json.loads((BASE/'delivery-phase2-final/summary.json').read_text())
prior = {r['id']:r for r in json.loads((ROOT/'experiments/backends/support/ir33-recovery/capability-audit/audit.json').read_text())['rows']}
mapping = {r['test_id']:r for r in csv.DictReader((ROOT/'experiments/backends/support/ir33-recovery/capability-audit/methods.tsv').open(), delimiter='\t')}
def cases(s):
    for t in s:
        if isinstance(t, unittest.TestSuite): yield from cases(t)
        else: yield t
rows = []
for case in cases(unittest.defaultTestLoader.discover(str(ROOT/'evas/tests'))):
    assert not isinstance(case, unittest.loader._FailedTest), case
    ident = case.id()
    fun = getattr(case,case._testMethodName)
    source, start = inspect.getsourcelines(fun)
    source_path = Path(inspect.getsourcefile(fun)).resolve()
    module_path = ROOT/'evas/tests'/(case.__class__.__module__+'.py')
    body = ''.join(source)
    rows.append(dict(id=ident, outcome=summary['methods'][ident], module=case.__class__.__module__,
        source_file=str(source_path.relative_to(ROOT)), module_file=str(module_path.relative_to(ROOT)),
        start_line=start, end_line=start+len(source)-1, method_sha256=hashlib.sha256(body.encode()).hexdigest(),
        module_sha256=hashlib.sha256(module_path.read_bytes()).hexdigest(), source=body,
        generated=fun.__name__!=case._testMethodName, expected_failure=bool(getattr(fun,'__unittest_expecting_failure__',False)),
        prior_failure_audit=prior.get(ident), prior_mapping=mapping.get(ident)))
assert len(rows)==len({r['id'] for r in rows})==3257
assert {r['id'] for r in rows}==summary['methods'].keys()
rows.sort(key=lambda r:r['id'])
modules=collections.defaultdict(list)
for r in rows: modules[r['module_file']].append(r)
loads=[0]*6; lanes=[[] for _ in loads]
for name in sorted(modules,key=lambda x:(-len((ROOT/x).read_text()),x)):
    i=min(range(6),key=lambda i:(loads[i],i));lanes[i].extend(modules[name]);loads[i]+=len((ROOT/name).read_text())
scope=dict(source_root=str(ROOT), main_commit='15eb7216f7071edb7eda7a9b0c56b7e8933c4c79',
    source_commit='566c36a9366419c970ec008ef27f7bdd3d82e9f6', ci_head=summary['head'],ci_run=summary['run_id'],
    source_identity='production and test files identical between main, checkout and CI candidate; full tree main equals checkout',
    method_count=3257, counts=summary['counts'], module_count=len(modules),
    purpose='Audit every method contract, oracle and assertion, including passed and expected-failure methods; no implementation/test changes; no new simulation qualification',
    spectre='pending by user instruction', source_modules={m:hashlib.sha256((ROOT/m).read_bytes()).hexdigest() for m in sorted(modules)},
    lanes=[dict(lane=i+1,methods=len(l),modules=len({r['module_file'] for r in l}),source_chars=loads[i]) for i,l in enumerate(lanes)])
(OUT/'scope.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2)+'\n')
(OUT/'inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
for i,lane in enumerate(lanes):
    (OUT/f'input-{i+1}.json').write_text(json.dumps(dict(scope=scope,methods=sorted(lane,key=lambda r:r['id'])),ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:scope[k] for k in ('method_count','counts','module_count','lanes')},ensure_ascii=False))
