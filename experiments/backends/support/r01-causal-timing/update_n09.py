"""Import explicitly completed latest N09 finite receipts; no simulations."""
from pathlib import Path
import json,hashlib,argparse,shutil
import build_extracts as base
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def update(R):
 a=R/'reference-preparation/paired-analysis-final-c5-v5';d=R/'reference-preparation/dut-final-c5-v5';summary=load(a/'SUMMARY.json');identity=load(d/'IDENTITY.json');after=load(d/'AFTER.json');execution=load(d/'EXECUTION.json');assert after['source_kernel_unchanged'] and summary['finite_pair_pass']==summary['denominator']==6 and summary['voltage_pairs']==169 and summary['query_points']==44
 assert sha(d/'IDENTITY.json')==summary['dut_identity_sha256'] and sha(d/'AFTER.json')==summary['after_sha256'] and sha(d/'EXECUTION.json')==summary['execution_manifest_sha256']
 origins=load(P/'ORIGINS.json')
 for f in a.glob('*.json'):
  rel='n09-final/'+f.name;base.dump(rel,load(f));origins[rel]={'original_sha256':sha(f),'local_receipt':str(f.relative_to(R))}
  if f.name!='SUMMARY.json':
   case=load(f);label=case['label'];pr=d/label/'program.json';assert sha(pr)==case['compiled_program_sha256'];dest=P/'n09-final'/label;dest.mkdir(parents=True,exist_ok=True)
   text=pr.read_text();assert not any(s in text for s in ['/'+part+'/' for part in ['Users','home','edamgr']]);shutil.copyfile(pr,dest/'program.json');base.dump('n09-final/'+label+'/RECEIPT.json',load(d/label/'RECEIPT.json'))
   assert sha(d/label/'RECEIPT.json')==case['receipt_sha256']
 base.dump('n09-final/IDENTITY.json',{'kernel_sha256':identity['kernel_sha256'],'source':identity['source'],'source_compilation':identity['source_compilation'],'source_kernel_unchanged_after':after['source_kernel_unchanged'],'original_identity_sha256':sha(d/'IDENTITY.json'),'original_after_sha256':sha(d/'AFTER.json'),'original_execution_sha256':sha(d/'EXECUTION.json'),'execution':execution})
 base.dump('ORIGINS.json',origins);status=load(P/'STATUS.json');assert status['fixed_kernel_sha256']==summary['kernel_sha256'];status.update(n09_final_current_status='passed',n09_final_current_kernel_sha256=summary['kernel_sha256'],n09_final_current_controls_pass=6,n09_final_current_query_points=44,n09_final_current_voltage_pairs=169);base.dump('STATUS.json',status)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('run_root',type=Path);update(ap.parse_args().run_root)
