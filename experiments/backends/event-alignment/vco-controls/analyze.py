"""Bounded constant VCO diagnostic. Native rows only; independent idt is not idtmod state."""
import argparse, hashlib, importlib.util, json, math, re
from fractions import Fraction as F
from pathlib import Path
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('normalize_psf',BASE.parent/'normalize_psf.py')
normalizer=importlib.util.module_from_spec(spec);spec.loader.exec_module(normalizer)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def exact(t):
    q=F(1,8)+524288*F(t);p=q-q.numerator//q.denominator
    return q,p

def compare(rows):
    maxima={};failures=[]
    for r in rows:
        q,p=exact(r['time']);v=r['voltages']
        expected={'freq':.5,'phase':float(p),'out':math.sin(2*math.pi*float(p))}
        if 'raw' in v:expected['raw']=float(q)
        for n,e in expected.items():
            diff=abs(v[n]-e);budget=.003 if n=='out' else .001
            item=dict(time=r['time'],observed=v[n],expected=e,difference=diff,budget=budget)
            if n not in maxima or diff>maxima[n]['difference']:maxima[n]=item
            if diff>budget:failures.append(dict(signal=n,**item))
        diff=abs(v['phase']-float(p))%1;diff=min(diff,1-diff)
        if 'phase_circular' not in maxima or diff>maxima['phase_circular']['difference']:maxima['phase_circular']=dict(time=r['time'],difference=diff,budget=.001)
    return dict(maxima=maxima,ordinary_failures=failures)

def native_index(rows):
    times=[r['time'] for r in rows];index={r['time']:r for r in rows}
    if len(times)!=len(index) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('duplicate/nonincreasing native time records')
    return index

def analyze(root):
    manifest=json.loads((BASE/'MANIFEST.json').read_text());results={};native={}
    for c in manifest['cases']:
        folder=root/c['id'];nodes=['ctl','freq','phase','out']+(['raw'] if c['observer']=='raw-observer' else [])
        for f,h in c['files'].items():
            if sha(folder/f)!=h:raise ValueError('frozen input hash mismatch: '+str(folder/f))
        obs=normalizer.normalize(folder/'psf/tran.tran.tran',{'voltage_nodes':nodes});rows=obs['rows'];native[c['id']]=rows
        index=native_index(rows)
        log=(folder/'spectre.log').read_text();section=log.split('Important parameter values:')[-1].split('Output and IC/nodeset summary:')[0]
        effective=dict(re.findall(r'^\s*(reltol|abstol\(V\)|abstol\(I\)|maxstep|method|errpreset)\s*=\s*(.+)$',section,re.M))
        anchors=[]
        for t in manifest['required_times']:
            q,p=exact(t);entry=dict(time=t,time_hex=t.hex(),present=t in index,exact_q=str(q),exact_phase=str(p))
            if t in index:
                v=index[t]['voltages'];entry['observed']=v
                if 'raw' in v:
                    raw=v['raw'];ulp=F(math.ulp(raw));entry.update(raw_hex=raw.hex(),raw_error_ULP=str((F(raw)-q)/ulp),raw_minus_nearest_integer_ULP=str((F(raw)-round(raw))/ulp),exported_raw_modulo=raw-math.floor(raw))
            anchors.append(entry)
        result=dict(source_sha256=sha(folder/'dut.va'),deck_sha256=sha(folder/'tb.scs'),psf_sha256=obs['psf_sha256'],log_sha256=sha(folder/'spectre.log'),spectre_version=log.splitlines()[2],effective_settings=effective,native_rows=len(rows),required_count=len(anchors),present_count=sum(a['present'] for a in anchors),missing=[a['time'] for a in anchors if not a['present']],anchors=anchors,**compare(rows))
        results[c['id']]=result
    pairs={}
    for setting in ['baseline','tight']:
        a=native['original--'+setting];b=native['raw-observer--'+setting];ia={r['time']:r['voltages'] for r in a};ib={r['time']:r['voltages'] for r in b};common=ia.keys()&ib.keys()
        pairs[setting]=dict(same_native_time_sequence=[r['time'] for r in a]==[r['time'] for r in b],common_rows=len(common),original_only=len(ia.keys()-ib.keys()),observer_only=len(ib.keys()-ia.keys()),max_signal_difference={n:max(abs(ia[t][n]-ib[t][n]) for t in common) for n in ['ctl','freq','phase','out']})
    return dict(schema='vco-controls-diagnostic-v1',status='ordinary-phase-and-required-coverage-failures-retained',scope='constant exact-dyadic VCO only; raw is independent idt, not internal idtmod state',budgets=manifest['comparison_budgets'],cases=results,observer_effect=pairs),native
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runs',type=Path);p.add_argument('output',type=Path);a=p.parse_args();result,_=analyze(a.runs);a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
