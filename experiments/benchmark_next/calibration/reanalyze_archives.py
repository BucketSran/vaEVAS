"""Recheck unchanged analog circuits on archived real waveforms, without simulation."""
import argparse,hashlib,json,sys,tarfile,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'benchmark/checkers'))
sys.path.insert(0,str(ROOT/'benchmark/tasks/v3-calibration-continuous-offset/tests'))
from adc_linearity import read_psf
from v2_runtime import validate_rows
from v2_next_calibration import evaluate

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path,required=True);parser.add_argument('--baseline-report',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 baseline=json.loads(args.baseline_report.read_text());records=[];unchanged={}
 for name,expected in baseline['material_assets'].items():
  if ('continuous-offset' in name or 'common-mode-servo' in name) and not name.endswith('/v2_next_calibration.py'):
   actual=sha((ROOT/name).read_bytes())
   if actual!=expected:raise ValueError('analog material changed: '+name)
   unchanged[name]=actual
 for request in json.loads((args.prepared/'requests.json').read_text()):
  task_id=Path(request['task']).name
  if task_id=='v3-calibration-fractional-pll':continue
  prepared=Path(request['prepared']);task=ROOT/'benchmark/tasks'/task_id;tests=task/'tests';plan=json.loads((prepared/'preparation.json').read_text())
  cases={case['name']:case for case in json.loads((tests/'cases.json').read_text())}
  analysis_sources={name:sha((tests/name).read_bytes()) for name in ('v2_next_calibration.py','adc_linearity.py','v2_runtime.py','cases.json','contract.json')}
  analysis_sources['instruction.md']=sha((task/'instruction.md').read_bytes())
  for item in json.loads((prepared/'results.json').read_text()):
   archive=prepared/'remote'/item['job_id']/'archive/job.tar.gz'
   with tarfile.open(archive) as stream:
    raw_report=stream.extractfile('run/work/verifier/report.json').read()
    if sha(raw_report)!=item['result']['artifacts']['work/verifier/report.json']['sha256']:raise ValueError('execution report changed')
    old=json.loads(raw_report);outputs=[]
    candidate=ROOT/request['candidate_directory']/'dut.va'
    if sha(candidate.read_bytes())!=old['candidate_files']['dut.va']:raise ValueError('current candidate differs from actual execution')
    for execution_case in old['cases']:
     if execution_case['status']!='graded' or execution_case['returncode']!=0:raise ValueError('cannot reuse ungraded circuit execution')
     name=execution_case['name'];wave=stream.extractfile(f'run/work/verifier/{name}/psf/tran.tran.tran').read()
     if sha(wave)!=execution_case['waveform_sha256']:raise ValueError('waveform identity mismatch')
     with tempfile.TemporaryDirectory(prefix='calibration-reanalysis-') as directory:
      work=Path(directory);path=work/'waveform.psf';path.write_bytes(wave);rows=read_psf(path);validate_rows(rows,cases[name]);verdict=evaluate(rows,cases[name],work)
     if verdict['checks']!=execution_case['checks'] or verdict['passed']!=execution_case['passed']:raise ValueError('analog result changed under shared checker')
     outputs.append(dict(name=name,waveform_sha256=sha(wave),waveform_rows=len(rows),netlist_sha256=execution_case['netlist_sha256'],support_sha256=execution_case['support_sha256'],**verdict))
   record=dict(task_id=task_id,variant=request['variant'],condition_id=item['condition_id'],job_id=item['job_id'],execution_candidate_sha256=plan['candidate']['candidate_sha256'],execution_criteria_sha256=plan['criteria_sha256'],execution_report_sha256=sha(raw_report),archive_sha256=sha(archive.read_bytes()),analysis_sources=analysis_sources,score=int(all(c['passed'] for c in outputs)),cases=outputs)
   record['analysis_identity_sha256']=sha(json.dumps(record,sort_keys=True,separators=(',',':')).encode());records.append(record)
 report=dict(kind='archived-real-waveform-reanalysis',analysis_tool_sha256=sha(Path(__file__).read_bytes()),new_simulations=0,reanalyzed_conditions=len(records),baseline_report_sha256=sha(args.baseline_report.read_bytes()),unchanged_material_assets=unchanged,reason='Only shared checker source changed in D2/D3; circuits, stimuli, candidate, parser and physical acceptance contracts unchanged. Preserve execution identity and add a new analysis identity.',conditions=records)
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'reanalyzed_conditions':len(records),'new_simulations':0}))
if __name__=='__main__':main()
