from pathlib import Path
import subprocess,hashlib,re,json
base='4448253a15ea8cf566d88e62be54c3819060648a'
p=Path('evas/docs/COMPARISON.md');old=subprocess.check_output(['git','show',base+':'+str(p)],text=True);new=p.read_text()
# Historical result rows are immutable; the old open-work summary is deliberately updated.
rows=[x for x in old.split('### EVAS 还缺什么')[0].splitlines() if x.startswith('|')]
missing=[x for x in rows if x not in new]
print('old result/settings rows:',len(rows),'not retained:',missing)
paths=['evas/docs/COMPARISON.md','evas/docs/COMPARISON-METHODOLOGY.md','evas/validation/README.md','evas/validation/paper/README.md','experiments/backends/support/README.md']
missing_links=[]
for name in paths:
 p=Path(name)
 for target in re.findall(r'\]\(([^\s)]+)\)',p.read_text()):
  if ':' in target or target.startswith('#'):continue
  ref=target.split('#')[0]
  if ref and not (p.parent/ref).exists():missing_links.append((name,target))
print('missing local targets:',missing_links)
assert not missing and not missing_links
r=Path('runs/evas-overnight-20261012');d=json.loads(Path('experiments/backends/support/20261012-breadth.json').read_text())
assert d['selected_slots']==852 and d['collected_slots']==852
print('final slots',len(d['slots']),'groups',len(d['groups']))
for f in ['20261012-breadth-baseline.json','20261012-breadth.json','20261012-breadth-diagnostics.json']:
 q=Path('experiments/backends/support')/f;print(f,hashlib.sha256(q.read_bytes()).hexdigest(),q.stat().st_size)
legacy=subprocess.check_output(['git','diff','--name-only',base,'--','evas/validation/paper/core-v1.json','evas/validation/paper/inventory-v1.json','evas/validation/paper/precision-v2.json','evas/validation/paper/precision-bindings-v1.json','evas/validation/paper/precision_v2.py','evas/validation/paper/precision_checker.py'],text=True)
assert not legacy
print('six legacy cards/checker/binding paths unchanged; old open-work summary updated, not treated as frozen scores')
