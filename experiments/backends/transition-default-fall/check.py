"""Independent affine-segment checks on preserved native observations; no resampling."""
import argparse,hashlib,json,math,re,sys
from fractions import Fraction as F
from pathlib import Path
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE.parents[2]))
from experiments.backends.evidence.psf import normalize
from experiments.backends.evidence.archive import verify_archive_members
ARCHIVES={
 'original':('b7e7f4d0e7525489697c02240a4cca74aafb438d5bf56a71b3d3781015bac5eb',['three-arg--sparse','three-arg--dense','four-arg--sparse']),
 'timer-controls':('e9f2759b2e8126f4fcaebb1cf19d0531961361b7c39cc679cf4327bdfc981223',['zero-period--1e-12','positive-period--1e-18','positive-period--1e-12'])}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
TABLE=json.loads((BASE/'independent-segments.json').read_text())
SEGMENTS={n:[[F(v) for v in row] for row in seg] for n,seg in TABLE['segments'].items()}
SIGNALS=[i+'_'+n for i in ['a','b'] for n in ['simple','reverse','extend','mirror','qs','qr','qe','qm']]
def expected(n,t):
 t=F(t)
 for a,b,v,m in SEGMENTS[n]:
  if a<=t<=b:return v+m*(t-a)
 if t<SEGMENTS[n][0][0]:return F(0)
 raise ValueError('query outside frozen segment domain')
def coverage(times,required):
 if len(set(times))!=len(times) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('duplicate/nonincreasing native times')
 return [t for t in required if t not in set(times)]
def waveform(rows):
 maxima={};failures=[]
 for row in rows:
  for n in SEGMENTS:
   value=row['voltages'][n]
   if not math.isfinite(value):raise ValueError('nonfinite waveform')
   e=float(expected(n,row['time']));diff=abs(value-e);item=dict(time=row['time'],observed=value,expected=e,difference=diff,budget=1e-8)
   if n not in maxima or diff>maxima[n]['difference']:maxima[n]=item
   if diff>1e-8:failures.append(dict(signal=n,**item))
 return dict(maxima=maxima,failures=failures)
def state_observations(rows):
 # Observed state jumps bracket a callback, not certify hidden event time/count.
 expected_values={'qs':[(.25,1),(1.5,0)],'qr':[(.25,1),(.5,0)],'qe':[(.25,1),(.5,2)],'qm':[(.25,-1),(.5,0)]}
 out={};failures=[]
 for i in ['a','b']:
  for n,changes in expected_values.items():
   key=i+'_'+n;jumps=[];previous=rows[0]
   if previous['voltages'][key]!=0:failures.append(dict(signal=key,reason='nonzero initial target'))
   for r in rows[1:]:
    if r['voltages'][key]!=previous['voltages'][key]:jumps.append(dict(previous_observation=previous['time'],first_new_observation=r['time'],before=previous['voltages'][key],after=r['voltages'][key]))
    previous=r
   if len(jumps)!=len(changes) or [j['after'] for j in jumps]!=[v for _,v in changes]:failures.append(dict(signal=key,reason='observed target sequence differs'))
   out[key]=jumps
 return dict(jumps=out,failures=failures,timer_window_verdict='I: native observations do not certify every callback within 1e-18; repeated unchanged-target callback is unobservable',callback_count_verdict='I: held targets cannot count the repeated .875 callback')
def analyze(runs,manifest_path=None,mode='original'):
 if runs!=runs.parent.parent/'spectre-output/runs':raise ValueError('must read canonical spectre-output/runs bound to archive')
 fixed_sha,required_cases=ARCHIVES[mode]
 required=['spectre-output/FILE_MANIFEST.json']+[f'spectre-output/runs/{case}/{file}' for case in required_cases for file in ['dut.va','tb.scs','psf/tran.tran.tran','spectre.log','RESULT.json']]
 archive_members=verify_archive_members(runs.parent.parent,fixed_sha,required)
 manifest=json.loads((manifest_path or BASE/('timer-controls/MANIFEST.json' if mode=='timer-controls' else 'MANIFEST.json')).read_text())
 if [c['id'] for c in manifest['cases']]!=required_cases:raise ValueError('unexpected frozen case set')
 cases={};raw={}
 for c in manifest['cases']:
  p=runs/c['id']
  for f,h in c['files'].items():
   if sha(p/f)!=h:raise ValueError('source/deck hash mismatch: '+str(p/f))
  o=normalize(p/'psf/tran.tran.tran',{'voltage_nodes':SIGNALS});rows=o['rows'];raw[c['id']]=rows
  required=c.get('requested_times',manifest.get('required_times'));times=[r['time'] for r in rows];missing=coverage(times,required);log=(p/'spectre.log').read_text();sec=log.split('Important parameter values:')[-1].split('Output and IC/nodeset summary:')[0];effective=dict(re.findall(r'^\s*(reltol|abstol\(V\)|abstol\(I\)|maxstep|method|errpreset)\s*=\s*(.+)$',sec,re.M));index={r['time']:r for r in rows}
  cases[c['id']]=dict(source_sha256=sha(p/'dut.va'),deck_sha256=sha(p/'tb.scs'),psf_sha256=o['psf_sha256'],log_sha256=sha(p/'spectre.log'),spectre_version=log.splitlines()[2],effective_settings=effective,native_rows=len(rows),time_domain=[times[0],times[-1]],required_points=len(required),present_points=len(required)-len(missing),missing=missing,native_waveform=waveform(rows),required_waveform=waveform([index[t] for t in required if t in index]),states=state_observations(rows))
 pairs={}
 primary=manifest['cases'][0]['id']
 for other in [c['id'] for c in manifest['cases'][1:]]:
  a=raw[primary];b=raw[other];ia={r['time']:r['voltages'] for r in a};ib={r['time']:r['voltages'] for r in b};common=ia.keys()&ib.keys()
  pairs[other]=dict(common_native_rows=len(common),sparse_only=len(ia.keys()-ib.keys()),other_only=len(ib.keys()-ia.keys()),same_native_time_sequence=list(ia)==list(ib),max_signal_difference={n:max(abs(ia[t][n]-ib[t][n]) for t in common) for n in SIGNALS})
 return dict(schema='transition-default-fall-v1',archive_sha256=fixed_sha,verified_regular_files=len(archive_members),primary_case=primary,qualification='bounded waveform diagnostics; coverage/timer/count limitations remain',cases=cases,pairs=pairs),raw
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runs',type=Path);p.add_argument('output',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--mode',choices=list(ARCHIVES),default='original');a=p.parse_args();r,_=analyze(a.runs,a.manifest,a.mode);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
