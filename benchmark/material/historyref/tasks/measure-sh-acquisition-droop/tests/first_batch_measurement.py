"""Independent electrical observations and metric definitions, not reference outputs."""
import bisect
import math


def value(rows,node,t):
    ts=[r['time'] for r in rows]
    j=max(0,min(bisect.bisect_right(ts,t)-1,len(rows)-2))
    a,b=rows[j:j+2]
    f=(t-a['time'])/(b['time']-a['time']) if b['time']>a['time'] else 0
    return a[node]+f*(b[node]-a[node])


def edges(rows,node,level=.5,rising=True):
    result=[]
    for a,b in zip(rows,rows[1:]):
        if (a[node]<level<=b[node]) if rising else (a[node]>level>=b[node]):
            result.append(a['time']+(b['time']-a['time'])*(level-a[node])/(b[node]-a[node]))
    return result


def spectrum(samples,tone):
    if len(samples)!=64:raise ValueError('64 ADC observations required')
    power={}
    for k in range(1,33):
        re=sum(x*math.cos(2*math.pi*k*n/64) for n,x in enumerate(samples))
        im=sum(x*math.sin(2*math.pi*k*n/64) for n,x in enumerate(samples))
        power[k]=(1 if k==32 else 2)*(re*re+im*im)/4096
    residual=[v for k,v in power.items() if k!=tone]
    return {'sndr':10*math.log10(power[tone]/sum(residual)),
            'sfdr':10*math.log10(power[tone]/max(residual)),
            'dc':sum(samples)/64}


def result(rows,case,expected,tolerances,failures):
    observed={k:value(rows,k,case['stop']-5e-9) for k in expected}
    for k,want in expected.items():
        if abs(observed[k]-want)>tolerances[k]:failures.append(k+' metric mismatch')
    completed={'measure-adc-spectrum':6.45e-6,'measure-comparator-delay-hysteresis':1.4e-6,'measure-sh-acquisition-droop':1.991e-6,'measure-pll-relock-jitter':4.4e-6}[case['task']]
    for r in rows:
        if r['time']>=completed and any(abs(r[k]-want)>tolerances[k] for k,want in expected.items()):
            failures.append('result not completed and held throughout final window');break
    return {'passed':not failures,'failures':failures,'expected_metrics':expected,'observed_metrics':observed}


def adc(rows,case):
    failures=[]
    rises=edges(rows,'clk')
    if len(rises)!=66:failures.append('ADC stimulus clock coverage')
    rises=rises[:64]
    if len(rises)!=64:return {'passed':False,'failures':failures+['missing ADC samples']}
    samples=[]
    for n,t in enumerate(rises):
        if abs(t-(n*100e-9+10.05e-9))>.2e-9:failures.append('ADC clock cadence')
        q=value(rows,'code',t+1e-9)
        if abs(q-round(q))>.01 or not 0<=q<=4095:failures.append('invalid raw ADC code')
        samples.append(q)
        phase=2*math.pi*case['tone_bin']*n/64
        analog=2048+case['amp']*(math.sin(phase)+case['h2']*math.sin(2*phase)+case['h3']*math.cos(3*phase))
        # The code must actually come from the published sampled circuit input.
        # At exact integer boundaries, floating arithmetic may round either way.
        if abs(q-math.floor(analog))>1.01:failures.append('ADC raw observations differ from synthetic circuit')
        if abs(value(rows,'vin',n*100e-9)-analog/4096)>.0003:failures.append('ADC analog stimulus differs from coherent tone')
    # Invalid raw observations must be rejected before entering the DFT metric domain.
    if failures:return {'passed':False,'failures':failures}
    expected=spectrum(samples,case['tone_bin'])
    return result(rows,case,expected,{'sndr':.05,'sfdr':.05,'dc':.01},failures)


def comparator(rows,case):
    failures=[]
    qr=edges(rows,'q');qf=edges(rows,'q',rising=False)
    vr=[t for t in edges(rows,'vin',0) if t>=900e-9]
    vf=[t for t in edges(rows,'vin',0,rising=False) if t>=900e-9]
    if len(qr)!=2 or len(qf)!=2 or len(vr)!=1 or len(vf)!=1:
        return {'passed':False,'failures':['comparator experiment edge coverage']}
    for t,want in [(0,-.02),(200e-9,0),(400e-9,.02),(600e-9,0),(850e-9,-.02),(1.05e-6,.02),(1.3e-6,-.02)]:
        if abs(value(rows,'vin',t)-want)>.0001:failures.append('comparator sweep/step stimulus')
    dr=qr[1]-vr[0];df=qf[1]-vf[0]
    expected={'high_mv':1000*(value(rows,'vin',qr[0])-1e5*dr),
              'low_mv':1000*(value(rows,'vin',qf[0])+1e5*df),
              'rise_ns':dr/1e-9,'fall_ns':df/1e-9}
    # Independent engineering sanity checks guard against corrupted device support.
    if abs(expected['high_mv']-case['hysteresis']*500)>.1 or abs(expected['low_mv']+case['hysteresis']*500)>.1:
        failures.append('raw comparator thresholds inconsistent with circuit')
    if abs(dr-case['delay'])>.3e-9 or abs(df-case['delay'])>.3e-9:failures.append('raw propagation delay inconsistent with circuit')
    return result(rows,case,expected,{'high_mv':.05,'low_mv':.05,'rise_ns':.15,'fall_ns':.15},failures)


def acquisition(rows,case):
    failures=[];settling=[];drooping=[]
    for k in range(4):
        base=k*500e-9;target=.8 if k%2==0 else .2
        window=[r for r in rows if base<=r['time']<=base+250e-9]
        first=None
        for a,b in zip(window,window[1:]):
            ea=abs(a['y']-a['vin'])-.003;eb=abs(b['y']-b['vin'])-.003
            if ea>0>=eb:
                first=a['time']+(b['time']-a['time'])*ea/(ea-eb);break
        if first is None:return {'passed':False,'failures':['S/H never established in acquisition']}
        if any(abs(r['y']-r['vin'])>.00301 for r in window if r['time']>=first+.5e-9):failures.append('S/H rebound after first crossing')
        settling.append((first-base)/1e-9)
        drooping.append(1000*(value(rows,'y',base+260e-9)-value(rows,'y',base+490e-9))/.23)
        for dt,tr in [(50,1),(200,1),(300,0),(450,0)]:
            if abs(value(rows,'vin',base+dt*1e-9)-target)>.001 or abs(value(rows,'track',base+dt*1e-9)-tr)>.01:failures.append('S/H input/track experiment')
    expected={'settle_ns':sum(settling)/4,'droop_mvus':sum(drooping)/4}
    if abs(expected['settle_ns']-math.log(100)*case['tau']/1e-9)>.6:failures.append('raw S/H acquisition differs from circuit')
    if abs(expected['droop_mvus']-case['droop']*.001)>.2:failures.append('raw S/H droop differs from circuit')
    return result(rows,case,expected,{'settle_ns':.5,'droop_mvus':.2},failures)


def pll(rows,case):
    failures=[]
    refs=edges(rows,'ref');clks=edges(rows,'clk')
    if not refs:return {'passed':False,'failures':['PLL reference edge coverage']}
    acquisition=[t for t in clks if 1e-6<=t<2.2e-6]
    run=[];locked=None
    for t in acquisition:
        if min(abs(t-r) for r in refs)<=3e-9:
            run.append(t)
            if len(run)==4:locked=run[0]-1e-6;break
        else:run=[]
    stable=[t for t in clks if 2.2e-6<=t<4.2e-6]
    if locked is None or len(stable)!=20:return {'passed':False,'failures':['PLL acquisition/stable edge coverage']}
    periods=[(b-a)/1e-9 for a,b in zip(stable,stable[1:])]
    mean=sum(periods)/len(periods)
    deviation=math.sqrt(sum((p-mean)**2 for p in periods)/len(periods))
    expected={'relock_ns':locked/1e-9,'jitter_ns':deviation}
    if abs(locked-case['settle_cycles']*100e-9)>.3e-9:failures.append('raw PLL relock inconsistent with circuit')
    if any(abs(abs(p-100)-2*case['jitter']/1e-9)>.3 for p in periods):failures.append('raw period jitter inconsistent with circuit')
    return result(rows,case,expected,{'relock_ns':.3,'jitter_ns':.02},failures)


def evaluate(rows,case,work=None):
    if len(rows)<2 or any(not math.isfinite(v) for r in rows for v in r.values()):return {'passed':False,'failures':['invalid waveform']}
    functions={'measure-adc-spectrum':adc,'measure-comparator-delay-hysteresis':comparator,
               'measure-sh-acquisition-droop':acquisition,'measure-pll-relock-jitter':pll}
    return functions[case['task']](rows,case)
