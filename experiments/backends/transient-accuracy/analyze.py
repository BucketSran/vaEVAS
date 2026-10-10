from pathlib import Path
import argparse,hashlib,importlib.util,json
from check import check_dynamic,check_vco
p=argparse.ArgumentParser();p.add_argument('observation',type=Path);p.add_argument('--model',choices=['nonlinear','event-continuation','vco'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--qualify-reference',action='store_true');a=p.parse_args()
if a.qualify_reference and a.model=='vco':p.error('reference qualification is scoped to the two rational trajectories')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads(a.observation.read_text())['rows']
if a.model=='vco':
 v=Path(__file__).resolve().parent/'retained-vco';card=json.loads((v/'condition.json').read_text());spec=importlib.util.spec_from_file_location('maintained_paper_oracle',v/'oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
 report=check_vco(rows,card,oracle)
elif a.qualify_reference:
 from qualify import qualify_dynamic
 report=qualify_dynamic(rows,a.model=='event-continuation')
else:report=check_dynamic(rows,a.model=='event-continuation')
report['identity']={'observation_sha256':sha(a.observation),'checker_sha256':sha(Path(__file__).with_name('check.py')),'analysis_sha256':sha(Path(__file__)),'availability':'local-only'}
if a.qualify_reference:report['identity']['qualification_checker_sha256']=sha(Path(__file__).with_name('qualify.py'))
with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
summary={'legacy_pass':report['legacy']['pass'],'qualified_finite_observations':report['qualified_finite_observations']} if a.qualify_reference else {'pass':report['pass'],'failures':len(report['failures'])}
print(json.dumps({**summary,'output':str(a.output)}))
