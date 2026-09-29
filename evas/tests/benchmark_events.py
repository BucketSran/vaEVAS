"""Bounded release-kernel event scaling check, including transport and trace cost.

Not a simulator ranking. Freeze requests/limits before invoking either binary.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import statistics
import subprocess
import time

from evas import compile_sources, Instance


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=args.output; root.mkdir(parents=True,exist_ok=False)
    header='module {name}(u,y,r); input u; output y; inout r; electrical u,y,r; '
    producer=header.format(name='producer')+'''integer n; analog begin
        @(initial_step) n=0; @(timer(0.5,0.5,0.001)) n=n+1; V(y,r)<+n; end endmodule'''
    reader=header.format(name='reader')+'''real s; analog begin
        @(initial_step) s=0; @(timer(0.5,0.5,0.001)) s=V(u,r); V(y,r)<+s; end endmodule'''
    cases=[]
    for size in [1,8,32]:
        instances=[Instance(f'x{k:02}', 'producer' if k==0 else 'reader',
            dict(u='u' if k==0 else f'y{k-1}',y=f'y{k}',r='0')) for k in range(size)]
        program=compile_sources({'p.va':producer,'r.va':reader},instances)
        for count in [10,100]:
            name=f'n{size}-events{count}'; stop=count*.5
            request=dict(program=program.to_dict(),driven=['u'],samples=[],
                transient=dict(pwl=[[[0,0],[stop,0]]],output_times=[0,stop],stop=stop,max_step=stop),
                tolerances=dict(vabstol=1e-10,reltol=1e-8))
            dump(root/(name+'.json'),request)
            cases.append(dict(id=name,nodes=size,events=count,request_sha256=digest(root/(name+'.json'))))
    contract=dict(cases=cases,repetitions=3,timeout_s=30,wall_budget_s=5,rss_budget_bytes=256*1024**2,
        platform=platform.platform(),baseline_sha256=digest(args.baseline),candidate_sha256=digest(args.candidate),
        script_sha256=digest(Path(__file__)),limits='Wall time includes process/transport; RSS includes the time wrapper. Same local host, alternating order; six development cases, no asymptotic or cross-simulator claim.')
    dump(root/'contract.json',contract)
    records=[]
    for c in cases:
        request=(root/(c['id']+'.json')).read_text()
        for repeat in range(3):
            order=[('baseline',args.baseline),('candidate',args.candidate)]
            if repeat%2:order.reverse()
            for backend,kernel in order:
                command=[str(kernel.resolve())]
                if platform.system()=='Darwin': command=['/usr/bin/time','-l',*command]
                start=time.perf_counter()
                completed=subprocess.run(command,input=request,text=True,capture_output=True,timeout=30)
                elapsed=time.perf_counter()-start
                key=f'{c["id"]}-{repeat}-{backend}'
                (root/(key+'.stdout')).write_text(completed.stdout)
                (root/(key+'.stderr')).write_text(completed.stderr)
                assert completed.returncode==0,(key,completed.stderr)
                result=json.loads(completed.stdout)
                assert 'error' not in result,(key,result)
                assert result['transient']['states'][-1]==[float(c['events'])]*c['nodes'],key
                assert len(result['transient']['events'])==c['nodes']*c['events'],key
                for e in result['transient']['events']:
                    count=round(e['time']/.5)
                    assert e['after']==[float(count)]*c['nodes'],key
                found=re.search(r'(\d+)\s+maximum resident set size',completed.stderr)
                rss=int(found.group(1)) if found else None
                records.append(dict(configuration=c['id'],backend=backend,repeat=repeat,wall_s=elapsed,rss_bytes=rss,
                    counts_and_states_correct=True,stdout_sha256=digest(root/(key+'.stdout'))))
    summary=[]
    for c in cases:
        row=dict(configuration=c['id'])
        for backend in ['baseline','candidate']:
            group=[r for r in records if r['configuration']==c['id'] and r['backend']==backend]
            row[backend]=dict(median_s=statistics.median(r['wall_s'] for r in group),
                max_s=max(r['wall_s'] for r in group),max_rss_bytes=max((r['rss_bytes'] or 0) for r in group))
        row['candidate_budget_met']=row['candidate']['max_s']<=contract['wall_budget_s'] and row['candidate']['max_rss_bytes']<=contract['rss_budget_bytes']
        summary.append(row)
    dump(root/'results.json',dict(contract=contract,records=records,summary=summary))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
