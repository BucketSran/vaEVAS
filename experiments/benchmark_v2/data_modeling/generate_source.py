"""Generate real JKU SKY130 sampler records with a pinned, unmodified PDK."""
import argparse, csv, hashlib, json, subprocess
from pathlib import Path

PDK_REV='f62031a1be9aefe902d6d54cddd6f59b57627436'
SOURCE_REV='892272208df28b6c7620101e129a9d8dd95ebab7'
TASK=Path(__file__).resolve().parents[3]/'benchmark/tasks/v2-data-sampling-identification'

def flatten(path):
    text=[]
    for line in path.read_text().splitlines():
        if line.lower().startswith('.include '): text.append(flatten(path.parent/line.split('"')[1]))
        else: text.append(line)
    return '\n'.join(text)

def models(pdk):
    files=['models/parameters/lod.spice']
    for typ in ['n','p']:
        for kind in ['tt','mismatch']:
            files.append(f'cells/{typ}fet_01v8/sky130_fd_pr__{typ}fet_01v8__{kind}.corner.spice')
    return '.option scale=1u wnflag=1\n.param sky130_fd_pr__nfet_01v8__dlc_rotweak=0 sky130_fd_pr__pfet_01v8__dlc_rotweak=0\n'+'\n'.join(flatten(pdk/f) for f in files)

def circuit():
    s='* Copyright 2022 Manuel Moser; Apache-2.0. Manual schematic transcription.\n'
    for name,d,g,src,b,typ,w,l,nf in [('p','vin','clock','out','vdd','p',7.6,.22,4),('n','vin','sample','out','0','n',7.6,.22,4),('pd','out','sample','out','vdd','p',3.8,.22,2),('nd','out','clock','out','0','n',3.8,.22,2),('ip','sample','clock','vdd','vdd','p',.84,.15,2),('in','sample','clock','0','0','n',.42,.15,1)]:
        a=int((nf+1)/2)*w/nf*.29; ass=int((nf+2)/2)*w/nf*.29
        s+=f'X{name} {d} {g} {src} {b} sky130_fd_pr__{typ}fet_01v8 w={w} l={l} nf={nf} ad={a} as={ass} pd={2*int((nf+1)/2)*(w/nf+.29)} ps={2*int((nf+2)/2)*(w/nf+.29)} nrd={.29/w} nrs={.29/w} mult=1 m=1\n'
    return s+'C1 out 0 2.44p\nVDD vdd 0 1.8\n.temp 25\n'

def experiment(name,initial,levels,durations,phase=0):
    # Active-low track; complete history starts at t=0 with track asserted.
    vin=[[0,initial]]; clk=[[0,0],[30e-9,0],[30.02e-9,1.8]]; tracks=[]; holds=[]
    for i,(level,duration) in enumerate(zip(levels,durations)):
        start=(40+30*i)*1e-9; end=start+duration*1e-9
        change=start-3e-9+phase*1e-9
        vin += [[change,vin[-1][1]],[change+.02e-9,level]]
        clk += [[start,1.8],[start+.02e-9,0],[end,0],[end+.02e-9,1.8]]
        tracks.append([start+.3e-9,end-.05e-9]);holds.append([end+.4e-9,(70+30*i)*1e-9-1e-9])
    stop=(40+30*len(levels))*1e-9
    vin.append([stop,vin[-1][1]]);clk.append([stop,1.8])
    return dict(name=name,initial=initial,vin=vin,clock=clk,tracks=tracks,holds=holds,samples=[b+.4e-9 for a,b in tracks],stop=stop)

def experiments():
    train=[]
    for i,(init,levels) in enumerate([(.2,[1.6,.2,1.2,.5]),(1.6,[.2,1.6,.5,1.2]),(.5,[1.2,.5,1.6,.2]),(1.2,[.5,1.2,.2,1.6])]):
        for j,durs in enumerate([[.8,1.5,3,6],[6,3,1.5,.8]]): train.append(experiment(f'train-{i}-{j}',init,levels,durs))
    train += [experiment('train-mid-0',.3,[1.5,.6,1.1,.9],[1,2,4,5]), experiment('train-mid-1',1.5,[.3,1.4,.9,.6],[5,4,2,1],4), experiment('train-mid-2',.9,[1.4,.3,1.5,1.1],[.9,5.5,1.2,4.5],3.5),experiment('train-mid-3',1.1,[.6,1.4,.3,.9],[4.5,1.2,5.5,.9])]
    for i,u in enumerate([.2,.3,.5,.6,.9,1.1,1.2,1.4,1.5,1.6]):
        for j,init in enumerate([.2,1.6]):train.append(experiment(f'train-sweep-{i}-{j}',init,[u],[6]))
    public=[experiment('selftest-0',.3,[1.4,.4,1.1,.7],[1,2,4,5]),experiment('selftest-1',1.5,[.6,1.3,.3,1.0],[5,4,2,1],4)]
    hidden=[experiment('heldout-0',.35,[1.45,.65,1.25,.4],[1.2,2.5,4.5,.9]),experiment('heldout-1',1.45,[.35,1.05,.55,1.5],[.9,4.5,2.5,1.2],4),experiment('heldout-2',.8,[1.5,.3,1.3,.6,.9,1.4],[1.1,5.5,2.2,3.5,.85,4.2]),experiment('heldout-3',1.0,[.4,1.4,.7,1.2,.3,.8],[4.2,.85,3.5,2.2,5.5,1.1],3.5)]
    return {'train':train,'selftest':public,'heldout':hidden}

def pwl(points):return 'PWL('+ ' '.join(f'{t:.12g} {v:.12g}' for t,v in points)+')'

def run(exp,work,ngspice,maxstep=10e-12,reltol=1e-4,method='gear',uic=False):
    work.mkdir(parents=True,exist_ok=True)
    deck='JKU sampler actual transistor data\n.include models.spice\n'+circuit()+f'Vin vin 0 {pwl(exp["vin"])}\nVclock clock 0 {pwl(exp["clock"])}\n'
    if uic:deck+=f'.ic V(out)={exp["initial"]} V(sample)=1.8\n'
    deck+=f'.options reltol={reltol} abstol=1e-15 vntol=1e-6 chgtol=1e-18 trtol=1 method={method}\n.tran {maxstep} {exp["stop"]} 0 {maxstep}'+(' uic' if uic else '')+'\n.control\nrun\nset wr_vecnames\nset wr_singlescale\nwrdata waveform.txt v(vin) v(clock) v(sample) v(out)\nquit\n.endc\n.end\n'
    (work/'source.cir').write_text(deck)
    p=subprocess.run([ngspice,'-n','-b','source.cir'],cwd=work,capture_output=True,text=True)
    (work/'source.log').write_text(p.stdout+p.stderr)
    if p.returncode or not (work/'waveform.txt').exists() or 'aborted' in p.stdout+p.stderr:raise RuntimeError(f'Source run failed: {work}')
    rows=[list(map(float,l.split())) for l in (work/'waveform.txt').read_text().splitlines()[1:]]
    return rows

def interp(rows,t,k):
    import bisect
    i=bisect.bisect_left(rows,t,key=lambda r:r[0])
    if i==0:return rows[0][k]
    if i==len(rows):return rows[-1][k]
    a,b=rows[i-1],rows[i];return a[k]+(b[k]-a[k])*(t-a[0])/(b[0]-a[0])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pdk',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--ngspice',default='ngspice');args=ap.parse_args()
    rev=subprocess.check_output(['git','-C',str(args.pdk),'rev-parse','HEAD'],text=True).strip()
    if rev!=PDK_REV:raise ValueError('PDK revision mismatch')
    args.work.mkdir(parents=True,exist_ok=True);model=models(args.pdk);groups=experiments();manifest={'pdk_revision':rev,'source_revision':SOURCE_REV,'ngspice_version':subprocess.check_output([args.ngspice,'--version'],text=True),'models_sha256':hashlib.sha256(model.encode()).hexdigest(),'groups':groups,'records':{}}
    for group,exps in groups.items():
        dest=TASK/('environment/public/data' if group!='heldout' else 'tests/truth');dest.mkdir(parents=True,exist_ok=True)
        for exp in exps:
            work=args.work/exp['name'];work.mkdir(exist_ok=True);(work/'models.spice').write_text(model)
            rows=run(exp,work,args.ngspice)
            times=[i*50e-12 for i in range(round(exp['stop']/50e-12)+1)]
            if group!='heldout':
                times=[t for t in times if round(t/50e-12)%40==0 or any(a-.35e-9<=t<=b+.55e-9 for a,b in exp['tracks']) or any(abs(t-x)<.25e-9 for x,v in exp['vin'])]
                times += [t for t,v in exp['vin']+exp['clock']]
            times=sorted(set(round(t,15) for t in times+exp['samples']+[exp['stop']]))
            path=dest/(exp['name']+'.csv')
            with path.open('w') as f:
                writer=csv.writer(f,lineterminator='\n');writer.writerow(['time_s','vin_V','clock_V','vhold_V'])
                for t in times:writer.writerow([f'{t:.12g}',f'{interp(rows,t,1):.10g}',f'{interp(rows,t,2):.10g}',f'{interp(rows,t,4):.10g}'])
            manifest['records'][exp['name']]={'group':group,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'deck_sha256':hashlib.sha256((work/'source.cir').read_bytes()).hexdigest()}
    (Path(__file__).parent/'dataset-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (TASK/'environment/public/experiments.json').write_text(json.dumps({k:v for k,v in groups.items() if k!='heldout'},indent=2)+'\n')
    (args.work/'models.spice').write_text(model)
if __name__=='__main__':main()
