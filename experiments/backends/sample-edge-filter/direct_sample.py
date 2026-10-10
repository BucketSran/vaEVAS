"""Freeze and check a finite, same-source nonlinear-root sampling comparison.

Reuse the engineering budget/profile values from an explicitly supplied contract.
The oracle uses Decimal sqrt and PWL values, not EVAS root/certificate code.
Spectre execution uses callback_probe.py's existing bounded serial runner.
"""
import argparse
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'experiments/backends/paper'))
from inputs import save, sha

CONDITIONS = [('positive', 1.), ('negative', -1.), ('small', .001)]


def reference(scale, t=None):
    with localcontext() as ctx:
        ctx.prec = 80
        return float(Decimal(str(scale)) * (Decimal(2).sqrt() if t is None else Decimal(str(t))))


def freeze(output, contract):
    data = json.loads(contract.read_text())
    output.mkdir(parents=True, exist_ok=False)
    save(output/'CONTRACT.json', dict(id=data['id'], budgets=data['budgets'], profiles=data['profiles'],
         source_contract_sha256=sha(contract), source_contract_availability='local-only adjacent snapshot',
         checker_sha256=sha(Path(__file__))))
    root = reference(1)
    times = sorted({i/32 for i in range(97)} | {root-1e-12, root+1e-12})
    for name, scale in CONDITIONS:
        source = ('`include "disciplines.vams"\n'
            'module dut(clk,u,y,count); input clk,u; output y,count; electrical clk,u,y,count;\n'
            'real q; integer n; analog begin\n'
            '@(initial_step) begin q=0; n=0; end\n'
            '@(cross(pow(V(clk),2)-2,1,1e-3,1e-3)) begin q=V(u); n=n+1; end\n'
            'V(y)<+q; V(count)<+n; end endmodule\n')
        for profile in data['profiles']:
            work = output/(name+'--'+profile['id']); work.mkdir()
            settings = dict(stop_s=3., maxstep_s=profile['step_units'], reltol=profile['reltol'],
                            vabstol_V=profile['vabstol_V'], iabstol_A=profile['iabstol_A'])
            wave = f'0 0 3 {3*scale:.17g}'
            tb = ('simulator lang=spectre\nahdl_include "dut.va"\n'
                  'Vclk (clk 0) vsource type=pwl wave=[0 0 3 3]\n'
                  f'Vu (u 0) vsource type=pwl wave=[{wave}]\ndut (clk u y count) dut\n'
                  f'simulatorOptions options precision="%.17g" reltol={settings["reltol"]:.17g} '
                  f'vabstol={settings["vabstol_V"]:.17g} iabstol={settings["iabstol_A"]:.17g}\n'
                  f'tran tran stop=3 maxstep={settings["maxstep_s"]:.17g} errpreset=conservative method=traponly '
                  'strobetimes=['+' '.join(f'{t:.17g}' for t in times)+'] '
                  'strobeoutput=all compression=no skipcount=1\nsave clk u y count\n')
            (work/'dut.va').write_text(source); (work/'tb.scs').write_text(tb)
            save(work/'requested_settings.json', settings)
            save(work/'case.json', dict(id=name, profile=profile['id'], scale=scale, scale_V=2*abs(scale),
                 inputs={'clk':[[0,0],[3,3]], 'u':[[0,0],[3,3*scale]]}, times=times, stop=3,
                 initial_V=0, expected_events=1, root=root, ttol_s=1e-3, expr_tol=1e-3))
    save(output/'MANIFEST.json', {str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def assess(case, rows, budgets):
    """All native rows, one shared callback bracket, original fixed budgets."""
    B = budgets['absolute_V']+budgets['relative']*case['scale_V']
    ut = budgets['time_serialization_ulps']*math.ulp(case['stop'])
    uv = budgets['voltage_serialization_ulps']*math.ulp(max(1.,case['scale_V']))
    out = dict(status='evidence_insufficient', voltage_budget_V=B, row_count=len(rows))
    def fail(reason, status='evidence_insufficient'):
        return dict(out, status=status, reason=reason)
    if len(rows)<3 or any(any(k not in r or not math.isfinite(r[k]) for k in ('time','clk','u','y','count')) for r in rows):
        return fail('missing or nonfinite data')
    times = [r['time'] for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])) or abs(times[0])>ut or abs(times[-1]-3)>ut:
        return fail('nonmonotone or incomplete time coverage')
    if max(b-a for a,b in zip(times,times[1:]))>budgets['global_gap_units']+2*ut:
        return fail('observation gap')
    t = case['root']; distance = budgets['boundary_distance_s']+ut
    if not any(ut<t-x<=distance for x in times) or not any(ut<x-t<=distance for x in times):
        return fail('missing root left/right observation')
    for name,scale in [('clk',1.),('u',case['scale'])]:
        err = max(abs(r[name]-reference(scale,r['time']))+uv+abs(scale)*ut for r in rows)
        limit = budgets['input_absolute_V']+budgets['input_relative']*(1. if name=='clk' else case['scale_V'])
        if err>limit:return fail('input mismatch: '+name,'input_mismatch')
    counts = [round(r['count']) for r in rows]
    if any(abs(r['count']-n)>budgets['count_V'] for r,n in zip(rows,counts)) or counts[0]!=0 or counts[-1]!=1 or any(b-a not in (0,1) for a,b in zip(counts,counts[1:])):
        return fail('missing, repeated, reversed or fractional event','behavior_error')
    index = counts.index(1); bracket = [times[index-1]-ut,times[index]+ut]
    # Exact polynomial guard gives the allowed late bound. No linear-clock
    # approximation is used for clk(t)^2-2.
    late = min(case['ttol_s'], math.sqrt(2+case['expr_tol'])-t)
    lo,hi = max(bracket[0],t-ut), min(bracket[1],t+late+ut)
    if lo>hi:return fail('event outside original cross window','behavior_error')
    if hi-lo>2*budgets['boundary_distance_s']+2*ut:
        return fail('callback bracket too wide to certify sampling')
    qlo,qhi = sorted(reference(case['scale'],x) for x in (lo,hi))
    initial = max(abs(r['y'])+uv for r in rows[:index])
    held = rows[index:]
    sampled = max(max(abs(r['y']-qlo),abs(r['y']-qhi))+uv for r in held)
    drift = max(r['y'] for r in held)-min(r['y'] for r in held)+2*uv
    # The original direct-sample regression also requires its ideal-root answer.
    ideal = max(abs(r['y']-reference(case['scale']))+uv for r in held)
    out.update(initial_error_V=initial, sample_error_upper_V=sampled, hold_drift_upper_V=drift,
               ideal_root_error_upper_V=ideal, event_bracket_s=bracket, legal_callback_s=[lo,hi],
               status='pass' if max(initial,sampled,drift,ideal)<=B else 'numerical_error')
    return out


def check_events(case, events, budgets):
    """Check the explicit representative separately from observed jump sides."""
    slack = budgets['time_serialization_ulps']*math.ulp(case['stop'])
    root = case['root']
    late = min(case['ttol_s'], math.sqrt(2+case['expr_tol'])-root)
    if (len(events)!=1 or events[0].get('kind')!='cross'
            or not math.isfinite(events[0]['time'])
            or not root-slack<=events[0]['time']<=root+late+slack):
        raise ValueError('explicit event outside original cross contract')


def native_rows(work, ref):
    """Bind numerical evidence to successful execution, source and native data."""
    from observations import read_native
    from runner import effective_settings, stage_failure
    result = json.loads((ref/'RESULT.json').read_text())
    if (stage_failure(result['execution']) or result.get('analysis_failure')
            or not result['execution'].get('cleanup',{}).get('complete')):
        raise ValueError('unsuccessful reference execution: '+work.name)
    for name,field in [('dut.va','source_sha256'),('tb.scs','deck_sha256')]:
        if sha(work/name)!=sha(ref/name) or sha(ref/name)!=result[field]:
            raise ValueError('changed reference source/deck: '+work.name)
    raw = ref/'psf/tran.tran.tran'
    rows = json.loads((ref/'rows.json').read_text())
    if sha(raw)!=result['raw_sha256'] or read_native(raw,'spectre')!=rows:
        raise ValueError('reference rows do not match native data: '+work.name)
    if effective_settings(ref,'spectre')!=result['effective_settings']:
        raise ValueError('reference settings do not match native readback: '+work.name)
    return rows


def compare(inputs, spectre, output, kernel):
    for rel,digest in json.loads((inputs/'MANIFEST.json').read_text()).items():
        if sha(inputs/rel)!=digest:raise ValueError('changed frozen input: '+rel)
    for rel,digest in json.loads((spectre/'MANIFEST.json').read_text()).items():
        if sha(spectre/rel)!=digest:raise ValueError('changed actual reference: '+rel)
    output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import Instance, compile_sources
    from evas.runtime import _invoke
    data = json.loads((inputs/'CONTRACT.json').read_text()); records=[]
    expected = {name+'--'+profile['id'] for name,_ in CONDITIONS for profile in data['profiles']}
    if not expected or {p.name for p in inputs.iterdir() if p.is_dir()}!=expected:
        raise ValueError('incomplete frozen comparison denominator')
    if {p.name for p in spectre.iterdir() if p.is_dir()}!=expected:
        raise ValueError('incomplete reference comparison denominator')
    for work in sorted(p for p in inputs.iterdir() if p.is_dir()):
        ref = spectre/work.name; case=json.loads((work/'case.json').read_text())
        dest=output/work.name;dest.mkdir()
        native=native_rows(work,ref)
        record=dict(case=work.name, source_sha256=sha(work/'dut.va'), spectre=assess(case,native,data['budgets']))
        try:
            program=compile_sources({'dut.va':(work/'dut.va').read_text()},[Instance('dut','dut',{p:p for p in ('clk','u','y','count')})])
            request=dict(program=program.to_dict(), driven=list(case['inputs']), samples=[],
                transient=dict(pwl=list(case['inputs'].values()),output_times=case['times'],stop=3,max_step=3),
                tolerances=dict(absolute=record['spectre']['voltage_budget_V'],relative=0))
            save(dest/'request.json',request)
            response=_invoke(request,kernel,timeout=90,diagnostics_path=dest/'diagnostics.json')
            save(dest/'response.json',response)
            if response['transient']['times']!=case['times']:
                raise ValueError('response observation times differ from request')
            rows=[dict(time=t,**dict(zip(response['nodes'],r['voltages']))) for t,r in zip(case['times'],response['solutions'],strict=True)]
            save(dest/'rows.json',rows);record['evas']=assess(case,rows,data['budgets'])
            check_events(case,response['transient']['events'],data['budgets'])
            record['evas_event_representative_s']=response['transient']['events'][0]['time']
            pairs=[]; phase=[]
            for row in rows:
                match=[r for r in native if r['time']==row['time']]
                if len(match)!=1:raise ValueError('missing unique native common time')
                other=match[0]
                if round(row['count'])!=round(other['count']):
                    phase.append(row['time'])
                else:pairs.append(abs(row['y']-other['y']))
            record.update(paired_voltage_error_V=max(pairs),phase_differences_s=phase,
                paired_points=len(pairs), total_requested_points=len(rows))
            # A phase difference is allowed only inside the union of the two
            # independently accepted event brackets, never silently discarded.
            brackets=[record[k].get('event_bracket_s',[]) for k in ('evas','spectre')]
            phase_ok=all(len(b)==2 for b in brackets) and all(min(b[0] for b in brackets)<=t<=max(b[1] for b in brackets) for t in phase)
            record['pass']=all(record[k]['status']=='pass' for k in ('evas','spectre')) and phase_ok and max(pairs)<=record['spectre']['voltage_budget_V']
        except Exception as error:
            record.update(evas={'status':'execution_or_comparison_failure','reason':str(error)})
            record['pass']=False
        save(dest/'RESULT.json',record); records.append(record)
        print(work.name,record['spectre']['status'],record['evas']['status'],record['pass'],flush=True)
    save(output/'RESULTS.json',records)
    save(output/'IDENTITY.json',dict(kernel_sha256=sha(kernel),checker_sha256=sha(Path(__file__)),
         input_manifest_sha256=sha(inputs/'MANIFEST.json'),spectre_manifest_sha256=sha(spectre/'MANIFEST.json')))
    if not all(r['pass'] for r in records):raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path);f.add_argument('contract',type=Path)
    c=s.add_parser('compare');c.add_argument('inputs',type=Path);c.add_argument('spectre',type=Path);c.add_argument('output',type=Path);c.add_argument('kernel',type=Path)
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output,a.contract)
    else:compare(a.inputs,a.spectre,a.output,a.kernel)
