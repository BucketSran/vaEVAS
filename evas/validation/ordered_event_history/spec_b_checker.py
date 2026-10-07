"""Frozen independent Spec B finite checker. Exact Fraction formulas; no DUT imports."""
from fractions import Fraction as F
import argparse, hashlib, json, math, re
from pathlib import Path
V=F(1,10**6); T=F(1,5_000_000)
SIGNALS=('u','z','history','sample','count','edit')
def rat(x):
    if isinstance(x,F): return x
    if isinstance(x,float):
        if not math.isfinite(x): raise ValueError('nonfinite value')
        return F.from_float(x)
    return F(str(x))
def events(case):
    if case=='E5': return [('count',F(1,3),'cross')]
    return [('edit',F(1,4),'timer'),('count',F(3,4) if case=='E4' else F(1,2),'cross' if case in ('E2','E3','E4') else 'timer')]
def formula(case,t):
    t=rat(t); zero=F(0)
    z=zero
    if case=='E3': z=t if t<=F(1,4) else F(1,4)+2*(t-F(1,4))
    if case=='E4': z=t*t/2
    if case=='E5': z=3*t if t<=F(1,3) else 1+t-F(1,3)
    if case=='E6': z=1/(1-t) if t<=F(1,2) else 1/t
    return {'u':t,'z':z,'history':t*t/2 if case in ('E1','E2') else 2*t if case=='E5' else zero,'sample':F(t>F(1,3)) if case=='E5' else zero,'count':F(t>(F(1,3) if case=='E5' else F(3,4) if case=='E4' else F(1,2))),'edit':zero if case=='E5' else F(t>F(1,4))}
def read_psf(path):
    lines=[s.strip() for s in Path(path).read_text().splitlines()]; start=lines.index('VALUE')+1
    if lines[-1]!='END': raise ValueError('truncated PSF')
    rows=[]; row=None
    for line in lines[start:-1]:
        m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line)
        if not m: raise ValueError('unexpected PSF row')
        if m[1]=='time':
            if row is not None: rows.append(row)
            row={'time':m[2]}
        elif row is None or m[1] in row: raise ValueError('duplicate signal or missing time')
        else: row[m[1]]=m[2]
    if row is not None: rows.append(row)
    return rows

def inspect(rows,case,stop,maxstep,records=None,origin='unqualified_decimal_export'):
    r={'case':case,'rows':len(rows),'origin':origin,'numeric_status':'I','event_status':'I','exact_boundaries':[],'qualification_status':'I','failures':[]}
    if len(rows)<3: r['failures'].append('insufficient waveform');return r
    try:
        rows=[{k:rat(row[k]) for k in ('time',*SIGNALS)} for row in rows]
    except (ValueError,KeyError,ZeroDivisionError,OverflowError) as e:
        r['numeric_status']='F';r['event_status']='F';r['failures'].append(str(e));return r
    if any(b['time']<a['time'] for a,b in zip(rows,rows[1:])):
        r['numeric_status']='F';r['event_status']='F';r['failures'].append('unordered time');return r
    expected=events(case); centers=[e[1] for e in expected]
    domain=rows[0]['time']==0 and rows[-1]['time']==rat(stop)
    if not domain: r['failures'].append('missing exact domain endpoint')
    gap=max(b['time']-a['time'] for a,b in zip(rows,rows[1:]))
    dense=gap<=rat(maxstep)*(1+F(1,10**8))
    if not dense:r['failures'].append('global observation gap exceeds maxstep')
    errors={k:F(0) for k in ('u','z','history','sample')}
    for row in rows:
        ref=formula(case,row['time'])
        for k in errors:
            # Sample is a discrete jump; compare stored sample outside its uncertainty window.
            if k=='sample' and case=='E5' and abs(row['time']-F(1,3))<=T:continue
            errors[k]=max(errors[k],abs(row[k]-ref[k]))
    r['max_errors_V']={k:float(v) for k,v in errors.items()}
    r['numeric_status']='F' if any(e>V for e in errors.values()) else 'P' if domain and dense else 'I'
    brackets=[]; bad=False; insufficient=False
    for signal in ('edit','count'):
        desired=[e for e in expected if e[0]==signal]; changes=[]; old=F(0); previous=None
        for row in rows:
            val=row[signal]
            # Counts/order are exact obligations, no analog-voltage allowance.
            if val.denominator!=1 or val<0: bad=True;r['failures'].append('noninteger '+signal);break
            if val!=old:
                if val!=old+1:bad=True;r['failures'].append('nonunit/reversed '+signal)
                changes.append((previous['time'] if previous else row['time'],row['time']));old=val
            previous=row
            if desired and abs(row['time']-desired[0][1])>T and val!=F(row['time']>desired[0][1]):bad=True
            if not desired and val!=0:bad=True
        if len(changes)!=len(desired):bad=True;r['failures'].append('wrong total '+signal)
        for (lo,hi),(_,nominal,kind) in zip(changes,desired):
            bracket={'signal':signal,'kind':kind,'nominal':str(nominal),'lower':str(lo),'upper':str(hi),'width_s':float(hi-lo)};brackets.append(bracket)
            if lo>nominal+T or hi<nominal-T:bad=True;r['failures'].append('event bracket outside time budget')
            elif hi-lo>T or lo<nominal-T or hi>nominal+T:insufficient=True
    brackets.sort(key=lambda b:rat(b['lower']));r['event_brackets']=brackets
    if [b['signal'] for b in brackets]!=[e[0] for e in expected]:bad=True;r['failures'].append('event order mismatch')
    if records is not None:
        r['event_records']=records
        if len(records)!=len(expected):bad=True;r['failures'].append('event record count mismatch')
        else:
            for record,(_,nominal,kind) in zip(records,expected):
                if record['kind']!=kind or abs(rat(record['time'])-nominal)>T:bad=True;r['failures'].append('event record kind/time mismatch')
    r['event_status']='F' if bad else 'I' if insufficient or not domain else 'P'
    for _,center,kind in expected:
        at=[row for row in rows if row['time']==center]
        r['exact_boundaries'].append({'desired_rational':str(center),'kind':kind,'exact_rational_records':len(at),'values':[{k:str(row[k]) for k in SIGNALS} for row in at], 'status':'observed' if at and origin in ('synthetic_exact','evas_binary64_native') else 'I','note':'Exact rational equality only; nearest or rounded records do not prove callback convention.'})
    r['qualification_status']='F' if 'F' in (r['numeric_status'],r['event_status']) else 'P' if origin=='synthetic_exact' and r['numeric_status']==r['event_status']=='P' else 'I'
    r['limits']='Finite-record numeric agreement only. Export origin, continuous-time bounds and exact callback semantics are separate.'
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('waveform',type=Path);p.add_argument('--backend',choices=['evas','spectre'],required=True);p.add_argument('--stop',required=True);p.add_argument('--maxstep',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.backend=='evas':
        v=json.loads(a.waveform.read_text());rows=[dict(zip(v['nodes'],s['voltages']),time=t) for t,s in zip(v['transient']['times'],v['solutions'])];records=v['transient']['events'];origin='evas_binary64_native'
    else: rows=read_psf(a.waveform);records=None;origin='unqualified_decimal_export'
    result=inspect(rows,a.case,a.stop,a.maxstep,records,origin);result['waveform_sha256']=hashlib.sha256(a.waveform.read_bytes()).hexdigest();result['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
