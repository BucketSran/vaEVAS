"""Small EVAS/Spectre cross comparison, separate from the frozen 31 conditions.

The identical DUT samples a linear clock voltage at each event. Held voltages
provide observable event-time witnesses, not privileged simulator timestamps.
Checks are conditional on the declared voltage observation allowance, not formal
continuous-time qualification. Spectre must pass the same independent oracle.
"""
import argparse
from fractions import Fraction as Q
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evas/src'))
from evas import Instance, compile_sources, transient
sys.path.insert(0, str(ROOT / 'experiments/dvs2-starter-pilot'))
from analyze import read_waveform
from remote import digest, dump, execute

STOP = 3e-6
V_ALLOWANCE = 1e-8
PROFILES = {'coarse': 100e-9, 'fine': 7e-9}


def cases():
    ramp = [[0,.4],[1e-6,.6],[2e-6,.4],[STOP,.6]]
    shift = 37e-12
    specifications = [
        ('both-directions', ramp, [0,1,2], 0, 1e-10, 1e-5),
        ('rising-only', ramp, [0,2], 1, 1e-10, 1e-5),
        ('shifted', [[0,.4],[shift,.4],[1e-6+shift,.6],
                     [2e-6+shift,.4],[STOP+shift,.6]], [1,2,3], 0, 1e-10, 1e-5),
        ('knot-and-touch', [[0,.4],[.5e-6,.5],[1e-6,.6],
                            [1.5e-6,.5],[2e-6,.6],[STOP,.4]], [0,4], 0, 1e-10, 1e-5),
        ('initial-high', [[0,.6],[1e-6,.6],[2e-6,.4],[STOP,.6]], [1,2], 0, 1e-10, 1e-5),
        ('internal-feedback', ramp, [0,1,2], 0, 1e-10, 1e-5),
        ('time-tight', ramp, [0,1,2], 0, 1e-12, 1e-3),
        ('expression-tight', ramp, [0,1,2], 0, 1e-8, 1e-7),
    ]
    result = []
    for name, points, segments, direction, ttol, etol in specifications:
        gain = 2 if name == 'internal-feedback' else 1
        # Independently declared crossing segments; no EVAS event/root code.
        roots = []
        for segment in segments:
            (t0, a), (t1, b) = points[segment:segment+2]
            slope = gain * (Q(b)-Q(a)) / (Q(t1)-Q(t0))
            root = Q(t0) + (Q(.5)-Q(a)) * (Q(t1)-Q(t0)) / (Q(b)-Q(a))
            roots.append(dict(time=str(root), slope=str(slope),
                              width=str(min(Q(ttol), Q(etol)/abs(slope)))))
        source = f'''`include "disciplines.vams"
module cross_probe(u,clock,y,stamp,r);
input u,clock; output y,stamp; inout r;
electrical u,clock,y,stamp,r,z;
integer n; real held;
analog begin
  @(initial_step) begin n=0; held=0; end
  V(z,r)<+V(u,r)+{0.5 if gain == 2 else 0}*V(z,r);
  @(cross(V(z,r)-{gain*.5}, {direction}, {ttol!r}, {etol!r})) begin
    n=n+1; held=V(clock,r);
  end
  V(y,r)<+n;
  V(stamp,r)<+held;
end
endmodule
'''
        result.append(dict(id=name, source=source, inputs={'u':points,'clock':[[0,0],[STOP,3]]},
                           roots=roots, stop=STOP, ttol=ttol, etol=etol,
                           output_times=[0,.25e-6,.75e-6,1.25e-6,1.75e-6,2.25e-6,2.75e-6,STOP]))
    return result


def pwl(points, time):
    for (t0,a),(t1,b) in zip(points, points[1:]):
        if Q(t0) <= time <= Q(t1):
            return Q(a)+(Q(b)-Q(a))*(time-Q(t0))/(Q(t1)-Q(t0))
    raise ValueError('time outside input domain')


def check(rows, case):
    required = {'time','u','clock','y','stamp'}
    if not rows or any(not required <= row.keys() for row in rows):
        raise ValueError('missing observations')
    if any(not math.isfinite(row[k]) for row in rows for k in required):
        raise ValueError('nonfinite observations')
    if rows[0]['time'] != 0 or abs(rows[-1]['time']-case['stop']) > 1e-18:
        raise ValueError('incomplete observations')
    if any(not 0 < b['time']-a['time'] <= .501e-6 for a,b in zip(rows,rows[1:])):
        raise ValueError('invalid observation order or gap')
    rate = Q(3)/Q(case['stop'])
    reserve = Q(V_ALLOWANCE)/rate
    roots = [(Q(r['time']),Q(r['width'])) for r in case['roots']]
    seen, held = set(), {}
    previous = 0
    for row in rows:
        t = Q(row['time'])
        for name in ['u','clock']:
            if abs(Q(row[name])-pwl(case['inputs'][name],t)) > Q(V_ALLOWANCE):
                raise ValueError('input mismatch')
        n = round(row['y'])
        if abs(row['y']-n) > V_ALLOWANCE or not previous <= n <= len(roots):
            raise ValueError('invalid event count')
        earliest = sum(t > r+w+reserve for r,w in roots)
        latest = sum(t >= r-reserve for r,w in roots)
        if not earliest <= n <= latest:
            raise ValueError('event history violates analytic windows')
        if n == 0:
            if abs(row['stamp']) > V_ALLOWANCE:
                raise ValueError('initial held state changed')
        else:
            r,w = roots[n-1]
            witness = Q(row['stamp'])/rate
            if not r-reserve <= witness <= r+w+reserve:
                raise ValueError('held event time violates cross tolerances')
            lo,hi = witness-reserve,witness+reserve
            old_lo,old_hi = held.get(n,(r,r+w))
            held[n] = max(lo,old_lo),min(hi,old_hi)
            if held[n][0] > held[n][1]:
                raise ValueError('held samples have no common event-time witness')
        previous=n
        seen.add(n)
    if seen != set(range(len(roots)+1)):
        raise ValueError('not every expected count plateau was observed')
    return dict(status='finite_observation_pass', points=len(rows), events=len(roots),
                observation_allowance_v=V_ALLOWANCE, formal_qualification=False,
                witnessed_event_intervals_s=[[float(a),float(b)] for a,b in held.values()])


def build(root):
    root.mkdir(parents=True, exist_ok=False)
    specs=cases()
    dump(root/'conditions.json',specs)
    for case in specs:
        for profile,step in PROFILES.items():
            work=root/case['id']/profile
            work.mkdir(parents=True)
            (work/'dut.va').write_text(case['source'])
            lines=['simulator lang=spectre','ahdl_include "dut.va"']
            for name,points in case['inputs'].items():
                wave=' '.join(f'{t:.17g} {v:.17g}' for t,v in points)
                lines.append(f'V{name} ({name} 0) vsource type=pwl wave=[{wave}]')
            lines += ['dut (u clock y stamp 0) cross_probe',
                      'simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                      f'tran tran stop={STOP:.17g} step={step:.17g} maxstep={step:.17g} method=traponly',
                      'save u clock y stamp']
            (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    # Preserve all runner/checker dependencies before any backend execution.
    dependencies=[Path(__file__),Path(__file__).with_name('remote.py'),
                  Path(__file__).with_name('test_cross_reference.py'),
                  ROOT/'experiments/dvs2-starter-pilot/analyze.py',
                  ROOT/'experiments/dvs2-starter-pilot/suite.py']
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in dependencies})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p)
         for p in sorted(root.rglob('*')) if p.is_file()})


def verify(root):
    root=root.resolve()
    for rel,expected in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        path=root/rel
        if not path.resolve().is_relative_to(root) or digest(path) != expected:
            raise ValueError('input drift: '+rel)
    for rel,expected in json.loads((root/'checker_identity.json').read_text()).items():
        if digest(ROOT/rel) != expected:
            raise ValueError('checker drift: '+rel)


def run_evas(root, kernel):
    verify(root)
    dump(root/'EVAS_STARTED.json',dict(kernel_sha256=digest(kernel),
         source_sha256={str(p.relative_to(ROOT)):digest(p) for directory,pattern in
                       [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')]
                       for p in directory.rglob(pattern)}))
    for case in json.loads((root/'conditions.json').read_text()):
        instance=Instance('dut','cross_probe',dict(u='u',clock='clock',y='y',stamp='stamp',r='0'),{})
        program=compile_sources({'dut.va':case['source']},[instance])
        for profile,step in PROFILES.items():
            result=transient(program,case['inputs'],case['output_times'],stop=STOP,
                             max_step=step,kernel=kernel,vabstol=1e-10,reltol=1e-8)
            dump(root/case['id']/profile/'evas.json',result)


def run_spectre(root, profile):
    verify(root)
    config=json.loads(profile.read_text())
    binary,scripts=config['spectre'],config['setup_scripts']
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*scripts]):
        raise ValueError('unsupported tool path')
    setup='\n'.join('source '+s for s in scripts)+'\n'
    cpu=min(os.sched_getaffinity(0))
    dump(root/'SPECTRE_STARTED.json',dict(max_attempts=16,timeout_s=90,license_wait_s=30,cpu=cpu,
         input_manifest_sha256=digest(root/'INPUT_MANIFEST.json'),binary_sha256=digest(Path(binary)),
         setup_sha256=[digest(Path(s)) for s in scripts]))
    (root/'version.csh').write_text(setup+binary+' -W\nexit $status\n')
    identity=execute(['/bin/csh','-f','version.csh'],root,'version.log',30)
    dump(root/'version.json',identity)
    if identity['returncode'] or identity['timeout']:
        raise RuntimeError('Spectre version preflight failed')
    for case in json.loads((root/'conditions.json').read_text()):
        for name in PROFILES:
            work=root/case['id']/name
            (work/'run.csh').write_text(setup+binary+
                ' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
            result=execute(['taskset','-c',str(cpu),'/bin/csh','-f','run.csh'],work,'stdout.log',90)
            dump(work/'spectre-execution.json',result)
            print(case['id'],name,result['returncode'],flush=True)


def analyze(root, output):
    verify(root)
    report=[]
    for case in json.loads((root/'conditions.json').read_text()):
        for profile in PROFILES:
            work=root/case['id']/profile
            for backend in ['evas','spectre']:
                path=work/('evas.json' if backend == 'evas' else 'psf/tran.tran.tran')
                record=dict(condition=case['id'],profile=profile,backend=backend)
                try:
                    if backend == 'evas':
                        result=json.loads(path.read_text())
                        rows=[dict(zip(result['nodes'],s['voltages']),time=t) for t,s in
                              zip(result['transient']['times'],result['solutions'])]
                    else:
                        execution=json.loads((work/'spectre-execution.json').read_text())
                        if execution['returncode'] or execution['timeout']:
                            raise ValueError('Spectre execution failed or timed out')
                        rows=read_waveform(path,'spectre')
                    record.update(check(rows,case),waveform_sha256=digest(path))
                except FileNotFoundError:
                    record['status']='not_executed_or_missing_artifact'
                except (ValueError,KeyError) as error:
                    record.update(status='failed',reason=str(error))
                report.append(record)
    dump(output,report)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','evas','spectre','check'])
    parser.add_argument('root',type=Path)
    parser.add_argument('--kernel',type=Path)
    parser.add_argument('--spectre-profile',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action == 'build': build(args.root)
    elif args.action == 'evas': run_evas(args.root,args.kernel)
    elif args.action == 'spectre': run_spectre(args.root,args.spectre_profile)
    else: analyze(args.root,args.output)
