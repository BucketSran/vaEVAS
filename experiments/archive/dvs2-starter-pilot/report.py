"""Export sanitized finite-observation results and diagnostic waveform plots."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from analyze import read_waveform
from suite import conditions, reference

BACKENDS=['spectre','evas','openvaf_ngspice','gnucap']
LABELS={'spectre':'Spectre 21.1','evas':'EVAS 0.8.7',
        'openvaf_ngspice':'OpenVAF-R + ngspice 46','gnucap':'Gnucap + modelgen'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--plot',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    records=json.loads((args.root/'ANALYSIS.json').read_text())
    public=[];csvrows=[]
    for r in records:
        a=r.get('analysis',{})
        work=args.root/'runs'/r['backend']/r['condition']/r['profile']
        item={k:r[k] for k in ['backend','condition','card','profile','source_sha256','status']}
        item['analysis']=a
        item['waveform_sha256']=r.get('waveform_sha256')
        item['netlist_sha256']=hashlib.sha256((work/('tb.scs' if r['backend'] in ['evas','spectre'] else 'tb.gc' if r['backend']=='gnucap' else 'tb.cir')).read_bytes()).hexdigest()
        public.append(item)
        csvrows.append(dict(condition=r['condition'],card=r['card'],backend=r['backend'],profile=r['profile'],
            execution_status=r['status'],observation_status=a.get('status','unavailable'),
            sample_count=a.get('sample_count',''),max_gap_s=a.get('max_gap_s',''),
            max_observed_error_v=max((v['error_v'] for v in a.get('max_observed_error',{}).values()),default=''),
            plateau_error_v=a.get('plateau_error_v',''),formal_dvs_qualification='I'))
    (args.output/'results.json').write_text(json.dumps(public,indent=2)+'\n')
    with (args.output/'results.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(csvrows[0]));writer.writeheader();writer.writerows(csvrows)
    counts={b:{p:dict(Counter(r.get('analysis',{}).get('status',r['status']) for r in records if r['backend']==b and r['profile']==p)) for p in ['base','fine']} for b in BACKENDS}
    (args.output/'counts.json').write_text(json.dumps(counts,indent=2)+'\n')
    print(json.dumps(counts,indent=2))
    if not args.plot:return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases={c['id']:c for c in conditions()}
    selected=['v1-main','v2-main','v3-main','v4-c1','v5-main','v6-main','v7-linear-main','v7-nonlinear-2.0']
    colors={'spectre':'#1b9e77','evas':'#d95f02','openvaf_ngspice':'#7570b3','gnucap':'#1f78b4'}
    fig,axes=plt.subplots(4,2,figsize=(14,14))
    fig.subplots_adjust(left=.065,right=.985,bottom=.045,top=.905,hspace=.40,wspace=.20)
    for name,ax in zip(selected,axes.flat):
        case=cases[name];node=case['outputs'][0]
        ts=[i*1e-9 for i in range(4001)]
        ax.plot([t*1e6 for t in ts],[reference(case,t)[node] for t in ts],color='black',ls='--',lw=1.8,label='Analytic nominal',zorder=8)
        unavailable=[]
        for backend in BACKENDS:
            match=next(r for r in records if r['backend']==backend and r['condition']==name and r['profile']=='fine')
            if match['status']!='waveform_available':
                unavailable.append(LABELS[backend]+': '+match['status']);continue
            path=args.root/'runs'/backend/name/'fine'/match['waveform']
            rows=read_waveform(path,backend)
            ax.plot([r['time']*1e6 for r in rows],[r[node] for r in rows],lw=1.1,alpha=.85,color=colors[backend],label=LABELS[backend])
        ax.set(title=name+' / '+node,xlabel='Time (us)',ylabel='Voltage (V)',xlim=(0,4))
        ax.grid(alpha=.2)
        if unavailable:ax.text(.02,.02,'\n'.join(unavailable),transform=ax.transAxes,fontsize=7,va='bottom',bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
    handles={}
    for ax in axes.flat:
        for handle,label in zip(*ax.get_legend_handles_labels()):handles[label]=handle
    fig.legend(handles.values(),handles.keys(),loc='upper center',bbox_to_anchor=(.5,.955),ncol=5,fontsize=9)
    fig.suptitle('DVS-2 starter pilot: fine settings, exported waveforms\nMissing curves are execution/compile outcomes; plots do not certify unsampled behavior',fontsize=14,y=.993)
    fig.savefig(args.output/'waveforms-fine.png',dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,constrained_layout=True)
    case=cases['v4-c1']
    for ax,profile in zip(axes,['base','fine']):
        ts=[i*1e-9 for i in range(4001)]
        ax.plot([t*1e6 for t in ts],[reference(case,t)['vout'] for t in ts],'k--',lw=1.8,label='Analytic nominal')
        for backend in ['spectre','evas','gnucap']:
            match=next(r for r in records if r['backend']==backend and r['condition']=='v4-c1' and r['profile']==profile)
            if match['status']!='waveform_available':continue
            rows=read_waveform(args.root/'runs'/backend/'v4-c1'/profile/match['waveform'],backend)
            ax.plot([r['time']*1e6 for r in rows],[r['vout'] for r in rows],color=colors[backend],label=LABELS[backend],lw=1.2)
        ax.axvspan(1.15,1.85,color='#999999',alpha=.12,label='Reset high')
        ax.set(title='V4 C1 / '+profile, ylabel='Output (V)', xlim=(0,4),ylim=(.05,.8));ax.grid(alpha=.2);ax.legend(ncol=5,fontsize=8)
    axes[-1].set_xlabel('Time (us)')
    fig.savefig(args.output/'v4-refinement.png',dpi=160)
    plt.close(fig)


if __name__=='__main__':
    main()
