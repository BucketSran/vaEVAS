"""Independent terminal-waveform contracts for diagnosis and repair tasks."""
from bisect import bisect_right
import math

def value(rows, signal, t):
    times=[r['time'] for r in rows]
    i=max(0,min(len(rows)-2,bisect_right(times,t)-1))
    a,b=rows[i],rows[i+1]
    f=0 if b['time']==a['time'] else (t-a['time'])/(b['time']-a['time'])
    return a[signal]+f*(b[signal]-a[signal])

def crossings(rows, signal, threshold=.45, direction=0):
    result=[]
    for a,b in zip(rows,rows[1:]):
        x,y=a[signal]-threshold,b[signal]-threshold
        sign=1 if x<=0<y else -1 if x>=0>y else 0
        if sign and (not direction or direction==sign):
            result.append((a['time']+(b['time']-a['time'])*(-x)/(y-x),sign))
    return result

def expected(rows,case):
    kind=case['kind']; out=[]
    if kind in ('sequencer','uvlo'):
        q=0; out=[(0,{'stage1':0,'stage2':0,'ready':0,'progress':0} if kind=='sequencer' else {'out':0,'metric':.9})]
        for t,_ in crossings(rows,'clk',direction=1):
            if kind=='sequencer':
                q=0 if value(rows,'rst',t)>.45 or value(rows,'supply_ok',t)<=.45 or value(rows,'bias_ok',t)<=.45 else min(q+1,case.get('final_stage',3))
                n=case.get('final_stage',3)
                outputs={'stage1':.9*(q>=1),'stage2':.9*(q>=2),'ready':.9*(q>=n),'progress':.9*q/n}
            else:
                if value(rows,'rst',t)>.45: q=0
                elif value(rows,'vin',t)>.65: q=1
                elif value(rows,'vin',t)<.55: q=0
                outputs={'out':.9*q,'metric':.1 if q else .9}
            out.append((t,outputs))
    elif kind=='debounce':
        out=[(0,{'out':0})]
        # A qualifying rise has a complete uninterrupted high interval and no reset.
        rises=crossings(rows,'sig',direction=1)
        falls=crossings(rows,'sig',direction=-1)
        resets=crossings(rows,'rst_n',direction=-1)
        for t,_ in falls+resets: out.append((t,{'out':0}))
        for t,_ in rises:
            end=t+case.get('stable',12e-9)
            if value(rows,'rst_n',t)>.45 and not any(t<=f<=end for f,_ in falls+resets) and end<=case['stop']:
                out.append((end,{'out':.9}))
        out.sort(key=lambda x:x[0])
    elif kind=='pfd':
        out=[(0,{'up':0,'down':0})]; q={'up':0,'down':0}; pending=None
        ev=[(t,'reset') for t,_ in crossings(rows,'rstb',direction=-1)]
        ev += [(t,n) for n,s in [('up','ref'),('down','fb')] for t,_ in crossings(rows,s,direction=1)]
        for t,n in sorted(ev):
            if pending is not None and pending<t:
                q={'up':0,'down':0}; out.append((pending,q.copy())); pending=None
            if n=='reset': q={'up':0,'down':0}; pending=None
            elif value(rows,'rstb',t)>.45:
                q[n]=.9
                if q['up'] and q['down']: pending=t+case.get('reset_delay',80e-12)
            out.append((t,q.copy()))
        if pending is not None: out.append((pending,{'up':0,'down':0}))
    elif kind=='chain':
        # First derive supply-valid intervals solely from measured external vin.
        edges=[(t,'on') for t,_ in crossings(rows,'vin',.65,1)]
        edges += [(t,'off') for t,_ in crossings(rows,'vin',.55,-1)]
        qualified=[]; start=None
        for t,n in sorted(edges):
            if n=='on' and start is None: start=t
            elif n=='off' and start is not None:
                qualified.append((start,t)); start=None
        if start is not None: qualified.append((start,case['stop']+1))
        ev=[]
        for a,b in qualified:
            ev.extend([(a,'good'),(b,'invalid')])
            if a+case.get('release_delay',10e-9)<b: ev.append((a+case.get('release_delay',10e-9),'release'))
        ev.extend((t,'clock') for t,_ in crossings(rows,'clk',direction=1))
        state={'pgood':0,'resetb':0,'enable':0,'activity':0}; count=0
        out=[(0,state.copy())]
        for t,n in sorted(ev):
            if n=='good': state['pgood']=.9
            elif n=='invalid': state={k:0 for k in state};count=0
            elif n=='release': state['resetb']=state['enable']=.9
            elif n=='clock':
                count=count+1 if state['enable']>.45 and state['resetb']>.45 else 0
                state['activity']=.1*count
            out.append((t,state.copy()))
    else: raise ValueError('unknown repair kind: '+kind)
    return out

def evaluate(rows,case,work=None):
    if len(rows)<3 or rows[0]['time']!=0 or abs(rows[-1]['time']-case['stop'])>1e-15: raise ValueError('incomplete waveform interval')
    required={'sequencer':{'clk','rst','supply_ok','bias_ok','stage1','stage2','ready','progress'},'uvlo':{'clk','rst','vin','out','metric'},'debounce':{'sig','rst_n','out'},'pfd':{'ref','fb','rstb','up','down'},'chain':{'vin','clk','pgood','resetb','enable','activity'}}[case['kind']]
    if any(not required <= r.keys() for r in rows): raise ValueError('missing required signal')
    if any(not math.isfinite(v) for r in rows for v in r.values()): raise ValueError('nonfinite waveform')
    if case.get('maxstep') and any(b['time']-a['time']>case['maxstep']*1.001 for a,b in zip(rows,rows[1:])): raise ValueError('sparse waveform')
    if any(b['time']<=a['time'] for a,b in zip(rows,rows[1:])): raise ValueError('nonmonotone time')
    events=expected(rows,case); times=[t for t,_ in events]; guard=case.get('guard',.15e-9); errors=[]; checked=0
    for r in rows:
        t=r['time']
        if any(abs(t-e)<=guard for e in times): continue
        want=events[max(0,bisect_right(times,t)-1)][1]
        checked+=1
        for name,v in want.items():
            if name not in r: raise ValueError('missing output '+name)
            if abs(r[name]-v)>case.get('voltage_atol',.025):
                if len(errors)<12: errors.append({'time':t,'signal':name,'expected':v,'observed':r[name]})
    if checked<10: raise ValueError('insufficient settled observations')
    return {'passed':not errors,'checked_rows':checked,'violations':errors,'expected_events':len(events)}

if __name__=='__main__':
    from circuit_task import main
    main(evaluate)
