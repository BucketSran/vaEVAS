"""Same-source check of the sampled-amplitude filter path under the frozen budgets.

One physical case, all four original precision profiles. Execution is provided
by callback_probe.py; comparison checks native points without interpolation.
"""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'evas/src'), str(ROOT/'experiments/backends/paper')]
from inputs import save, sha
from direct_sample import native_rows
from root_compare import oracle

SOURCE = '''`include "disciplines.vams"
module dut(u,e,y); input u; output e,y; electrical u,e,y; real q;
analog begin @(initial_step) q=0;
@(cross(pow(V(u),2)-2,1,1e-3,1e-3)) q=V(u);
V(e)<+transition(q,0.125,0.5,0.5);
V(y)<+laplace_nd(V(e),'{1},'{1,0.25}); end endmodule
'''


OBSERVATION_TIME = math.sqrt(2) + .625 + 2e-12
OBSERVATION_SOURCE = f'''`include "disciplines.vams"
module native_observation(sense); input sense; electrical sense;
analog begin
@(timer({OBSERVATION_TIME:.17g},0,1e-15))
    $strobe("FILTER_OBSERVATION %.17g",$abstime);
end endmodule
'''


def check_observation_control(work, reference):
    """The extra testbench module only requests a native point and logs it."""
    for folder in (work, reference):
        if (folder/'observation.va').read_text() != OBSERVATION_SOURCE:
            raise ValueError('changed observation-only source')
    callbacks = re.findall(r'FILTER_OBSERVATION (\S+)',
                           (reference/'spectre.log').read_text())
    if (len(callbacks) != 1 or not math.isfinite(float(callbacks[0]))
            or abs(float(callbacks[0])-OBSERVATION_TIME) > 16*math.ulp(3.)):
        raise ValueError('missing or displaced native observation callback')
    return dict(kind='observation_only_timer', requested_s=OBSERVATION_TIME,
                actual_s=float(callbacks[0]))


def freeze(output, contract):
    data = json.loads(contract.read_text())
    output.mkdir(parents=True, exist_ok=False)
    save(output/'CONTRACT.json', dict(id=data['id'], budgets=data['budgets'],
         profiles=data['profiles'], profile_selection=data['profile_selection'], source_contract_sha256=sha(contract),
         signal_scale_V=2., delay_s=.125, strict_evas_budget_V=1e-10,
         spectre_observation_control='observation_only_timer'))
    root = math.sqrt(2)
    times = sorted({i/32 for i in range(97)} | {root-2e-12, root+2e-12,
                    root+.125-2e-12, root+.125+2e-12, root+.625-2e-12, root+.625+2e-12})
    for profile in data['profiles']:
        work = output/profile['id']; work.mkdir()
        settings = dict(stop_s=3., maxstep_s=profile['step_units'], reltol=profile['reltol'],
                        vabstol_V=profile['vabstol_V'], iabstol_A=profile['iabstol_A'])
        deck = ('simulator lang=spectre\nahdl_include "dut.va"\nahdl_include "observation.va"\n'
                'Vu (u 0) vsource type=pwl wave=[0 0 3 3]\ndut (u e y) dut\n'
                'observation (u) native_observation\n'
                f'simulatorOptions options precision="%.17g" reltol={settings["reltol"]:.17g} '
                f'vabstol={settings["vabstol_V"]:.17g} iabstol={settings["iabstol_A"]:.17g}\n'
                f'tran tran stop=3 maxstep={settings["maxstep_s"]:.17g} errpreset=conservative method=traponly '
                'strobetimes=['+' '.join(f'{t:.17g}' for t in times)+'] '
                'strobeoutput=all compression=no skipcount=1\nsave u e y\n')
        (work/'dut.va').write_text(SOURCE); (work/'tb.scs').write_text(deck)
        (work/'observation.va').write_text(OBSERVATION_SOURCE)
        save(work/'requested_settings.json', settings)
    save(output/'MANIFEST.json', {str(p.relative_to(output)):sha(p)
         for p in sorted(output.rglob('*')) if p.is_file()})


def assess(rows, data, budget):
    b = data['budgets']; scale = data['signal_scale_V']; stop = 3.
    ut = b['time_serialization_ulps']*math.ulp(stop)
    uv = b['voltage_serialization_ulps']*math.ulp(scale)
    if len(rows)<3 or any(any(k not in r or not math.isfinite(r[k]) for k in ('time','u','e','y')) for r in rows):
        return dict(status='evidence_insufficient', reason='missing or nonfinite rows')
    times = [r['time'] for r in rows]
    if (abs(times[0])>ut or abs(times[-1]-stop)>ut
            or any(y<=x or y-x>b['global_gap_units']+2*ut for x,y in zip(times,times[1:]))):
        return dict(status='evidence_insufficient', reason='time coverage')
    for t in (math.sqrt(2), math.sqrt(2)+.125, math.sqrt(2)+.625):
        distance = b['boundary_distance_s']+ut
        if not any(ut<t-x<=distance for x in times) or not any(ut<x-t<=distance for x in times):
            return dict(status='evidence_insufficient', reason='boundary coverage')
    input_error = max(abs(r['u']-r['time']) for r in rows)+uv+ut
    root = math.sqrt(2)
    errors = dict(
        e=max(abs(r['e']-root*min(1.,max(0.,(r['time']-root-.125)/.5))) for r in rows),
        y=max(abs(r['y']-root*oracle(r['time'],.125)) for r in rows))
    # Both continuous outputs have slope no greater than sqrt(2)/0.5.
    errors = {k:v+uv+root/.5*ut for k,v in errors.items()}
    input_budget = b['input_absolute_V']+b['input_relative']*scale
    return dict(status='pass' if input_error<=input_budget and max(errors.values())<=budget else 'numerical_error',
                errors_upper_V=errors, input_error_upper_V=input_error, budget_V=budget,
                rows=len(rows))


def compare(inputs, spectre, output, kernel):
    from evas import Instance, compile_sources
    from evas.runtime import _invoke
    for directory in (inputs, spectre):
        for rel,digest in json.loads((directory/'MANIFEST.json').read_text()).items():
            if sha(directory/rel)!=digest: raise ValueError('changed evidence: '+rel)
    data=json.loads((inputs/'CONTRACT.json').read_text())
    profiles={p['id'] for p in data['profiles']}
    if any({p.name for p in d.iterdir() if p.is_dir()}!=profiles for d in (inputs,spectre)):
        raise ValueError('incomplete profile denominator')
    output.mkdir(parents=True, exist_ok=False)
    save(output/'IDENTITY.json', dict(kernel_sha256=sha(kernel), checker_sha256=sha(Path(__file__)),
         kernel_identity=json.loads(subprocess.check_output([str(kernel.resolve()),'--version','--json'])),
         input_manifest_sha256=sha(inputs/'MANIFEST.json'), reference_manifest_sha256=sha(spectre/'MANIFEST.json')))
    records=[]
    B=data['budgets']['absolute_V']+data['budgets']['relative']*data['signal_scale_V']
    for profile in sorted(profiles):
        source=inputs/profile; ref=spectre/profile
        if (source/'dut.va').read_text()!=SOURCE: raise ValueError('unexpected model source')
        rows=native_rows(source,ref)
        work=output/profile; work.mkdir()
        program=compile_sources({'dut.va':(source/'dut.va').read_text()},[Instance('dut','dut',{n:n for n in ('u','e','y')})])
        record=dict(profile=profile, spectre=assess(rows,data,B), evas=[])
        if data.get('spectre_observation_control') == 'observation_only_timer':
            record['native_observation'] = check_observation_control(source, ref)
        for budget in (B,data['strict_evas_budget_V']):
            path=work/str(budget); path.mkdir()
            request=dict(program=program.to_dict(),driven=['u'],samples=[],tolerances=dict(absolute=budget,relative=0),
                 transient=dict(pwl=[[[0,0],[3,3]]],stop=3,max_step=1,output_times=[r['time'] for r in rows]))
            save(path/'request.json',request)
            try:
                result=_invoke(request,kernel,diagnostics_path=path/'diagnostics.json')
                save(path/'response.json',result)
                actual=[dict(time=r['time'],**dict(zip(result['nodes'],v['voltages']))) for r,v in zip(rows,result['solutions'],strict=True)]
                verdict=assess(actual,data,budget)
                events=result['transient']['events']; root=math.sqrt(2)
                if len(events)!=1 or not root-16*math.ulp(3)<=events[0]['time']<=root+min(1e-3,math.sqrt(2+1e-3)-root):
                    verdict['status']='event_error'
                verdict['same_time_difference_V']={k:max(abs(a[k]-r[k]) for a,r in zip(actual,rows,strict=True)) for k in ('e','y')}
                verdict['pair_status']='pass' if max(verdict['same_time_difference_V'].values())+2*data['budgets']['voltage_serialization_ulps']*math.ulp(2.)<=B else 'numerical_error'
                verdict['root_iterations']=json.loads((path/'diagnostics.json').read_text())['counters'].get('root_refinement_iterations',0)
            except Exception as error:
                verdict=dict(status='execution_error',reason=str(error),budget_V=budget)
            record['evas'].append(verdict)
        records.append(record)
    save(output/'RESULTS.json',records)
    print(json.dumps(records,indent=2))
    selected=next((p['id'] for p in data['profiles'] for r in records if r['profile']==p['id']
        and r['spectre']['status']=='pass' and all(e['status']=='pass' and e.get('pair_status')=='pass' for e in r['evas'])), None)
    save(output/'SUMMARY.json', dict(selected_profile=selected, reference_configurations=len(records),
         evas_requests=sum(len(r['evas']) for r in records), all_attempts_retained=True))
    if selected is None: raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='mode',required=True)
    f=sub.add_parser('freeze'); f.add_argument('output',type=Path); f.add_argument('contract',type=Path)
    c=sub.add_parser('compare')
    for name in ('inputs','spectre','output','kernel'): c.add_argument(name,type=Path)
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output,a.contract)
    else:compare(a.inputs,a.spectre,a.output,a.kernel)
