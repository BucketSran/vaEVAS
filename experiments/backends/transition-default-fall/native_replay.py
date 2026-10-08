from pathlib import Path
from fractions import Fraction as F
import sys,importlib.util,json,subprocess,hashlib,math
import argparse
from response import observations
parser=argparse.ArgumentParser();parser.add_argument('runs',type=Path);parser.add_argument('manifest',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--select',nargs='*');parser.add_argument('--mode',choices=['original','timer-controls'],default='original');args=parser.parse_args()
R=Path(__file__).resolve().parents[3];O=args.output;O.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'evas/src'))
from evas import Instance,compile_sources
spec=importlib.util.spec_from_file_location('check',R/'experiments/backends/transition-default-fall/check.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
runs=args.runs;analysis,raw=a.analyze(runs,args.manifest,args.mode);k=args.kernel;manifest=json.loads(args.manifest.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inst=[Instance(i,'transition_default',{'r':'0'}|{n:i+'_'+n for n in ['simple','reverse','extend','mirror','qs','qr','qe','qm']},{'edge':tr,'delay':d}) for i,tr,d in [('a',.5,0),('b',1,.125)]]
report=dict(source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),kernel_sha256=sha(k),kernel_identity=json.loads(subprocess.check_output([str(k),'--version','--json'],text=True)),local_numerical_calls=0,remote_calls=0,cases={})
for name,rows in raw.items():
 if args.select and name not in args.select:continue
 src=runs/name/'dut.va';p=compile_sources({str(src):src.read_text()},inst);times=[r['time'] for r in rows];rq=dict(program=p.to_dict(),driven=[],samples=[],transient=dict(pwl=[],output_times=times,stop=3,max_step=.015625),tolerances=dict(absolute=1e-11,relative=1e-10));folder=O/('native-'+name);folder.mkdir(exist_ok=True);(folder/'request.json').write_text(json.dumps(rq,indent=2)+'\n');process=subprocess.run([str(k)],input=json.dumps(rq),capture_output=True,text=True,timeout=90);report['local_numerical_calls']+=1;(folder/'stdout.json').write_text(process.stdout);(folder/'stderr.txt').write_text(process.stderr)
 rec=dict(returncode=process.returncode,request_sha256=sha(folder/'request.json'),stdout_sha256=sha(folder/'stdout.json'),source_sha256=sha(src),native_requested_count=len(times))
 if process.returncode==0:
  response=json.loads(process.stdout);erows=observations(response,times,sorted(['0']+a.SIGNALS));assert all(math.isfinite(v) for r in erows for v in r['voltages'].values());rec['evas_independent']=a.waveform(erows);failures=[];maxima={}
  for e,s in zip(erows,rows,strict=True):
   for n in a.SIGNALS:
    diff=abs(e['voltages'][n]-s['voltages'][n]);item=dict(time=s['time'],evas=e['voltages'][n],spectre=s['voltages'][n],difference=diff,budget=1e-8)
    if n not in maxima or diff>maxima[n]['difference']:maxima[n]=item
    if diff>1e-8:failures.append(dict(signal=n,**item))
  (folder/'paired-failures.json').write_text(json.dumps(failures,indent=2)+'\n');tol=next(c.get('timer_tolerance',1e-18) for c in manifest['cases'] if c['id']==name)
  state_failures=[f for f in failures if f['signal'] not in a.SEGMENTS];inside=sum(any(abs(F(f['time'])-F(t))<=F(tol) for t in ([.25,1.5] if f['signal'].endswith('qs') else [.25,.5])) for f in state_failures)
  rec['state_difference_classification']=dict(explicit_timer_window=tol,inside_timer_window=inside,outside_timer_window=len(state_failures)-inside,ordinary_failures_retained=True,limits='Saved q values do not certify hidden callback time/count')
  rec.update(paired_failure_count=len(failures),paired_waveform_failure_count=sum(f['signal'] in a.SEGMENTS for f in failures),paired_state_failure_count=sum(f['signal'] not in a.SEGMENTS for f in failures),paired_maxima=maxima,paired_failures_sha256=sha(folder/'paired-failures.json'))
 else:rec['diagnostic']=process.stdout+process.stderr
 report['cases'][name]=rec
(O/'native-pair-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({n:{'waveform_F':c.get('paired_waveform_failure_count'),'state_F':c.get('paired_state_failure_count'),'state_window':c.get('state_difference_classification')} for n,c in report['cases'].items()},indent=2))
