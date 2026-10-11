"""Independent LDO sampled metrics and response-driven experiment oracle."""
import bisect
import math

class Wave:
    def __init__(self,rows):
        self.rows=rows; self.ts=[r['time'] for r in rows]
    def value(self,t,node):
        i=max(0,min(len(self.ts)-2,bisect.bisect_right(self.ts,t)-1))
        a,b=self.rows[i:i+2]
        return a[node]+(b[node]-a[node])*(t-a['time'])/(b['time']-a['time'])

def startup_metrics(values,c):
    dt,target=c['tick'],c['target']
    last90=max((i for i,x in enumerate(values) if x<.9*target),default=-1)
    reach=last90+1<len(values)
    first=round(c['ramp_end']/dt)
    bad=[i for i in range(first,len(values)) if abs(values[i]-target)>.02*target]
    stable=max(first,bad[-1]+1 if bad else first)
    settled=stable<=len(values)-c['tail']
    bounds=any(x<-.1 or x>2.2 for x in values)
    return dict(t90_us=((last90+1)*dt-c['ramp_start'])*1e6 if reach else -1.,
                overshoot_mv=max(0.,max(values)-target)*1e3,
                settle_us=(stable*dt-c['ramp_end'])*1e6 if settled else -1.,
                reached=float(reach),settled=float(settled),
                status=float(4 if bounds else 2 if not reach else 3 if not settled else 1),done=1.)

def compare(w,t,expected,c,failures):
    for node,value in expected.items():
        actual=w.value(t,node)
        tolerance=c.get('tolerances',{}).get(node,.002)
        if abs(actual-value)>tolerance and len(failures)<40:
            failures.append(dict(time=t,node=node,expected=value,actual=actual,tolerance=tolerance))

def startup(w,c):
    n=round(c['window']/c['tick'])
    values=[w.value(i*c['tick'],'vout') for i in range(n+1)]
    metrics=startup_metrics(values,c); failures=[]
    zero={k:0. for k in metrics}
    for row in w.rows:
        t=row['time']
        if t<c['window']-c['guard']:compare(w,t,zero,c,failures)
        elif t>c['window']+c['guard']:compare(w,t,metrics,c,failures)
    # The fixed input must be observed, never replaced by a candidate target.
    for t in w.ts:
        expected=c['vin_high']*min(1,max(0,(t-c['ramp_start'])/(c['ramp_end']-c['ramp_start'])))
        if abs(w.value(t,'vin')-expected)>.001 and len(failures)<40:
            failures.append(dict(kind='fixed-supply',time=t,expected=expected,actual=w.value(t,'vin')))
    return dict(status='graded',passed=not failures,failures=failures,metrics=metrics)

def bench(w,c):
    """Reconstruct every stage from actual observed output at fixed ticks."""
    dt=c['tick']; target=c['target']; failures=[]
    names=['startup','line_up','line_down','load_up','load_down']
    report={'done':0.,'stage':0.}
    for name in names:
        for suffix in ['peak_mv','offset_mv','recovery_us','status']:
            report[name+'_'+suffix]=0.
    stage=0;start=0.; good=[]; values=[]; times=[]; states=[(0.,report.copy())]
    commands=[(0.,0.,0.)];finished=None
    for i in range(round(c['stop']/dt)+1):
        t=i*dt
        if stage>=5:break
        y=w.value(t,'vout'); values.append(y);times.append(t)
        eligible=t>=c['ramp_end'] if stage==0 else True
        good.append(bool(eligible and abs(y-target)<=c['band']))
        qualified=len(good)>=c['qualification'] and all(good[-c['qualification']:])
        age=t-start
        minimum=c['ramp_end'] if stage==0 else c['min_window']
        timeout=c['startup_timeout'] if stage==0 else c['timeout']
        if (age>=minimum-1e-14 and qualified) or age>=timeout-1e-14:
            name=names[stage]
            bad=[j for j,x in enumerate(good) if not x]
            index=(bad[-1]+1) if bad else 0
            report.update({name+'_peak_mv':max(abs(x-target) for x in values)*1e3,
                           name+'_offset_mv':(y-target)*1e3,
                           name+'_recovery_us':(times[index]-start)*1e6 if qualified else -1.,
                           name+'_status':1. if qualified else 2.})
            stage+=1;report['stage']=float(stage)
            if stage==5:report['done']=1.;finished=t
            states.append((t,report.copy()))
            line=1.95 if stage==1 else 1.8
            load=1. if stage==3 else 0.
            commands.append((t,line,load))
            start=t;good=[];values=[];times=[]
    if finished is None:failures.append(dict(kind='missing-complete-experiment'))
    # Commands must change exactly when actual qualification or timeout allows.
    for row in w.rows:
        t=row['time']
        if any(abs(t-x[0])<=c['guard'] for x in states[1:]):continue
        si=bisect.bisect_right([s[0] for s in states],t)-1
        compare(w,t,states[max(0,si)][1],c,failures)
        ci=bisect.bisect_right([s[0] for s in commands],t-c['guard'])-1
        at,line,load=commands[max(0,ci)]
        if ci==0:line=1.8*min(1,max(0,(t-c['ramp_start'])/(c['ramp_end']-c['ramp_start'])))
        if any(abs(t-x[0])<c['guard'] for x in commands[1:]):continue
        compare(w,t,dict(line_cmd=line,load_cmd=load,vin=line,load_current=.01*load),c,failures)
    return dict(status='graded',passed=not failures,failures=failures,stages=states,commands=commands,finished=finished)

def evaluate(rows,case,work=None):
    try:
        if len(rows)<2 or any(not math.isfinite(v) for r in rows for v in r.values()):raise ValueError('nonfinite or missing waveform')
        w=Wave(rows)
        if any(a>=b for a,b in zip(w.ts,w.ts[1:])):raise ValueError('non-increasing times')
        if abs(w.ts[0])>1e-15 or abs(w.ts[-1]-case['stop'])>1e-12:raise ValueError('incomplete record')
        result=startup(w,case) if case['kind']=='startup' else bench(w,case)
        for node in case.get('observation_currents',[]):
            peak=max(abs(r[node]) for r in rows)
            if peak>case['observation_current_atol']:
                result['failures'].append(dict(kind='read-only-input-current',node=node,peak_a=peak,limit_a=case['observation_current_atol']))
                result['passed']=False
        result['observation_current_peaks']={n:max(abs(r[n]) for r in rows) for n in case.get('observation_currents',[])}
        return result
    except (ValueError,KeyError,IndexError) as e:
        return dict(status='environment_error',passed=False,reason=str(e))
