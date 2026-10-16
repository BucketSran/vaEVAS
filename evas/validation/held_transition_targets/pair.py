"""Finite held-target comparison against native local PSF; never resamples."""
import argparse
from fractions import Fraction as Q
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/src'))
from evas import CompileError, Instance, compile_sources, transient
from evas.scs import load_scs

TIMES=[0,.5,1,1.000000001,1.125,1.25,1.5,2,2.000000001,2.125,2.25,2.5,3,3.000000001,3.125,3.25]
B=Q(1e-7)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(t):
    t=Q(t);clip=lambda x:max(Q(0),min(Q(1),4*x))
    return clip(t-1)-clip(t-2)+clip(t-3)
def print_cell_error(time_token,value_token):
    t=Decimal(time_token);v=Decimal(value_token)
    if not t.is_finite() or not v.is_finite():raise ValueError('non-finite PSF row')
    tr=Q(Decimal(1).scaleb(t.as_tuple().exponent))/2
    vr=Q(Decimal(1).scaleb(v.as_tuple().exponent))/2
    # The independent continuous waveform is globally 4-Lipschitz.
    return abs(Q(v)-exact(Q(t)))+vr+4*tr

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kernel',type=Path,required=True);ap.add_argument('--reference-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=False)
    def save(n,x):
        with(a.output_dir/n).open('x')as f:json.dump(x,f,indent=2);f.write('\n')
    raw=a.reference_dir;manifest=json.loads((raw/'OUTPUT_MANIFEST.json').read_text())
    assert all((raw/n).is_file()and sha(raw/n)==v for n,v in manifest.items())
    tool=json.loads((raw/'TOOL_IDENTITY.json').read_text());after=json.loads((raw/'TOOL_IDENTITY_AFTER.json').read_text());assert tool['file_sha256']==after['file_sha256']
    results=[]
    for case in ['held-nested-select','held-hidden-feedback']:
        inputs=Path(__file__).parent/'inputs'/case
        execution=json.loads((raw/case/'RESULT.json').read_text())
        assert execution['returncode']==0 and not execution['timeout'] and execution['status']=='completed'
        assert execution['source_files_sha256']=={n:sha(raw/case/n)for n in ['dut.va','tb.scs']}
        # VA must be byte-identical; SCS settings profiles remain distinct.
        assert sha(inputs/'dut.va')==sha(raw/case/'dut.va')
        text=(raw/case/'psf/tran.tran.tran').read_text();tokens=re.findall(r'"time"\s+(\S+)\s+"y"\s+(\S+)',text.split('VALUE\n',1)[1]);rows=[(float(t),float(v))for t,v in tokens]
        assert rows and all(math.isfinite(t)and math.isfinite(v)for t,v in rows)
        native=max(abs(Q(v)-exact(t))for t,v in rows);assert native<=B
        print_error=max(print_cell_error(t,v)for t,v in tokens);assert print_error<=B
        missing=[t for t in TIMES if t not in dict(rows)]
        item={'case':case,'reference_execution':{k:execution[k]for k in ['returncode','timeout','status','elapsed_seconds']},'same_VA_sha256':sha(inputs/'dut.va'),'public_original_SCS_sha256':sha(inputs/'tb.scs'),'reference_SCS_sha256':sha(raw/case/'tb.scs'),'reference_psf_sha256':sha(raw/case/'psf/tran.tran.tran'),'reference_native_count':len(rows),'reference_native_max_math_error_V':float(native),'reference_max_print_cell_error_V':float(print_error),'requested_forced':TIMES,'reference_missing_exact_forced':missing,'reference_effective_PSF_settings':{n:re.findall(r'^"'+re.escape(n)+r'" (.*)$',text,re.M)[0]for n in ['reltol','abstol(V)','method','maxstep','errpreset']}}
        try:load_scs(inputs/'tb.scs');raise AssertionError('original unsupported method unexpectedly accepted')
        except CompileError as e:
            assert 'traponly'in str(e)
            item['original_SCS_rejection']=str(e).replace(str(inputs),'inputs/'+case)
        try:
            p=compile_sources({'dut.va':(inputs/'dut.va').read_text()},[Instance('D','held',connections={'y':'y'})])
            assert p.to_dict()['schema_version']==22
            result=transient(p,{},TIMES,stop=3.25,max_step=.01,kernel=a.kernel,vabstol=1e-12,reltol=1e-10)
        except CompileError as e:
            if case!='held-hidden-feedback' or 'transition target values must be held states or constants'not in str(e):raise
            item['EVAS_structural_rejection']={'type':'CompileError','message':str(e)}
            item['finite_check_pass']=not missing
        else:
            assert case=='held-nested-select';save(case+'-Program.json',p.to_dict());save(case+'-EVAS.json',result)
            i=result['nodes'].index('y');values=[r['voltages'][i]for r in result['solutions']];native_e=max(abs(Q(v)-exact(t))for t,v in zip(TIMES,values));assert native_e<=B
            bounds=result['observation_evidence']['voltage_bounds_V']
            assert all(Q(bounds[j][i][0])<=exact(t)<=Q(bounds[j][i][1])for j,t in enumerate(TIMES))
            common=[t for t in TIMES if t in dict(rows)];pair=max(abs(Q(values[TIMES.index(t)])-Q(dict(rows)[t]))for t in common);assert pair<=B
            item.update(EVAS_all_forced_count=len(values),EVAS_max_math_error_V=float(native_e),exact_common_count=len(common),exact_pair_max_error_V=float(pair),EVAS_effective_controls=result['observation_evidence']['effective_controls'],finite_check_pass=not missing)
        results.append(item)
    save('summary.json',{'scope':'held-only arithmetic nested Select; not complete MUX','budget_V':float(B),'kernel_sha256':sha(a.kernel),'source_script_sha256':sha(Path(__file__)),'reference_tool':{'version':tool['version'],'spectre_binary_sha256':next(v for k,v in tool['file_sha256'].items()if k.endswith('/spectre'))},'reference_output_manifest_sha256':sha(raw/'OUTPUT_MANIFEST.json'),'raw_availability':'local-only, not included in repository','profiles':'Original traponly SCS is retained and rejected by EVAS. Same VA is compiled via public API with separate explicit EVAS controls; reference effective settings above are read from PSF.','cases':results,'pass':all(r['finite_check_pass']for r in results),'original_MUX_checker':'NOT_RUN'})
    print(json.dumps({'pass':all(r['finite_check_pass']for r in results),'cases':len(results)}))
if __name__=='__main__':main()
