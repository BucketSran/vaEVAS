"""Bounded engineering comparison, independent of EVAS implementation.

Times in the handwritten cases are microseconds. Oracle uses exact rational
linear-edge segments and the analytical convolution of a first-order filter.
"""
from fractions import Fraction as F
import math

T = 1e-6
STOP = 8.5*T
VOLTAGE_BUDGET = 1e-4
TIME_BUDGET = 5e-12
INPUT_BUDGET = 1e-8
INPUT = [[0,.25],[1,.75],[2,.1],[3,.9],[4,-.25],[5,.6],[6,.25],[7,-.1],[8.5,.2]]
CLOCK = [[0,0]]
for t in (1,3,5,7):
    CLOCK.extend([[t-.125,0],[t+.125,1],[t+.5,1],[t+.75,0]])
CLOCK.append([8.5,0])
RESET = [[0,0],[2.125,0],[2.375,1],[4.125,1],[4.375,0],[8.5,0]]


def frac(x):
    return F(str(x))


def pwl(points, t):
    t=frac(t)
    for (a,u),(b,v) in zip(points,points[1:]):
        a,b,u,v=map(frac,(a,b,u,v))
        if a<=t<=b:
            return u+(v-u)*(t-a)/(b-a)
    raise ValueError('outside input history')


def instance(name='a', phase=1, period=2, delay=.125, rise=.5, fall=.75, tau=.5, gain=1, bias=0, cross=False):
    return dict(name=name,phase=phase,period=period,delay=delay,rise=rise,fall=fall,tau=tau,gain=gain,bias=bias,cross=cross)


CASES = [
    dict(id='SEF-TIMER', instances=[instance()]),
    dict(id='SEF-RESET', instances=[instance(cross=True)]),
    dict(id='SEF-INTERRUPT', instances=[instance(period=1,rise=1.5,fall=1.25)]),
    dict(id='SEF-ISOLATION', instances=[instance(),instance('b',phase=1.5,period=3,delay=.25,rise=.75,fall=.5,tau=.25,gain=-.5,bias=.1)]),
]


def callbacks(config):
    times=[frac(t) for t in (1,3,5,7)] if config['cross'] else []
    if not config['cross']:
        t=frac(config['phase'])
        while t<frac(8.5):
            times.append(t); t+=frac(config['period'])
    if config['cross']:
        times.append(frac(2.25));times.sort()
    out=[]
    for t in times:
        reset=config['cross'] and pwl(RESET,t)>frac(.25)
        value=frac(.25) if reset else frac(config['gain'])*pwl(INPUT,t)+frac(config['bias'])
        out.append((t,value))
    return out


def initial(config):
    return frac(config['gain'])*frac(.25)+frac(config['bias'])


def segments(config):
    """Manual transition rules expressed as exact slope-change construction.

    Same-direction interruption retains the old origin; reversal uses the old
    destination. This defines an affine polygon, not simulated golden values.
    """
    value=initial(config); origin=value; target=value; slope=F(0); start=F(0)
    knots=[(F(0),value,F(0))]
    for event,new in callbacks(config):
        activation=event+frac(config['delay'])
        if new==target:
            continue
        if slope:
            end=start+(target-value)/slope
            if end<=activation:
                knots.append((end,target,F(0)));value=target;slope=F(0);start=end
        current=value+slope*(activation-start)
        if slope:
            same=(new-current)*slope>0
            new_origin=origin if same else target
        else:
            new_origin=current
        new_slope=(new-new_origin)/frac(config['rise'] if new>current else config['fall']) if new!=current else F(0)
        value=current;start=activation;origin=new_origin;target=new;slope=new_slope
        knots.append((start,value,slope))
    if slope:
        end=start+(target-value)/slope
        if end<frac(8.5):knots.append((end,target,F(0)))
    return knots


def edge_value(config, t):
    t=frac(t)
    a,y,m=next(k for k in reversed(segments(config)) if k[0]<=t)
    return float(y+m*(t-a))


def filter_value(config,t):
    # Convolution: each slope jump d at a contributes
    # d*((t-a)-tau*(1-exp(-(t-a)/tau))) for t>=a.
    tau=float(config['tau']);result=float(initial(config));old=F(0)
    for a,_,slope in segments(config):
        h=t-float(a)
        if h<0:break
        result+=float(slope-old)*(h+tau*math.expm1(-h/tau));old=slope
    return result


def source(case):
    modules=[]
    for p in case['instances']:
        name=p['name'];g=p['gain'];b=p['bias']
        event=('cross(V(clk)-0.5,1,1e-12,1e-9) or cross(V(rst)-0.5,1,1e-12,1e-9)' if p['cross'] else f'timer({p["phase"]*T:.17g},{p["period"]*T:.17g},1e-12)')
        assignment=f'q={g}*V(u)+({b});'
        if p['cross']:assignment='if(V(rst)>0.25) q=0.25; else '+assignment
        modules.append(f'''module cell_{name}(u,clk,rst,h,e,f,n);
input u,clk,rst; output h,e,f,n; electrical u,clk,rst,h,e,f,n;
real q; integer count;
analog begin
@(initial_step) begin q={float(initial(p)):.17g}; count=0; end
@({event}) begin {assignment} count=count+1; end
V(h)<+q; V(n)<+count;
V(e)<+transition(q,{p['delay']*T:.17g},{p['rise']*T:.17g},{p['fall']*T:.17g});
V(f)<+laplace_nd(V(e),'{{1}},'{{1,{p['tau']*T:.17g}}});
end endmodule''')
    outputs=[p['name']+x for p in case['instances'] for x in 'hefn']
    ports=['u','clk','rst',*outputs]
    wrappers=[f"cell_{p['name']} {p['name']}(u,clk,rst,"+','.join(p['name']+x for x in 'hefn')+');' for p in case['instances']]
    return '`include "disciplines.vams"\n'+'\n'.join(modules)+f'\nmodule dut({",".join(ports)});\ninput u,clk,rst; output {",".join(outputs)}; electrical {",".join(ports)};\n'+'\n'.join(wrappers)+'\nendmodule\n'


def times(case,dense=False):
    result={i*T/(64 if dense else 16) for i in range(round(8.5*(64 if dense else 16))+1)}
    for p in case['instances']:
        for t,_ in callbacks(p):
            result.update([float(t)*T+d for d in (-1e-11,-2e-12,0,2e-12,1e-11)])
        for t,_,_ in segments(p):result.add(float(t)*T)
    return sorted(result)


def assess(case,rows):
    failures=[];errors={}; event_brackets=[]
    def fail(reason):
        if reason not in failures:failures.append(reason)
    if not rows:return dict(status='FAIL',failures=['no rows'])
    required=['time','u','clk','rst',*[p['name']+x for p in case['instances'] for x in 'hefn']]
    if any(any(not isinstance(r.get(key),(int,float)) or not math.isfinite(r[key]) for key in required) for r in rows):
        return dict(status='FAIL',failures=['missing or nonfinite observation'])
    ts=[r['time'] for r in rows]
    if any(not math.isfinite(t) for t in ts) or any(a>=b for a,b in zip(ts,ts[1:])):fail('invalid time order')
    if ts[0]!=0 or abs(ts[-1]-STOP)>TIME_BUDGET:fail('missing start/stop coverage')
    if max((b-a for a,b in zip(ts,ts[1:])),default=math.inf)>T/16+1e-15:fail('insufficient native coverage')
    for port,points in [('u',INPUT),('clk',CLOCK),('rst',RESET)]:
        e=max(abs(r.get(port,math.inf)-float(pwl(points,min(8.5,max(0,r['time']/T))))) for r in rows)
        errors[port]=e
        if e>INPUT_BUDGET:fail('input '+port)
    for p in case['instances']:
        events=callbacks(p);name=p['name'];prev=0;last_t=0
        for port in 'hef':errors[name+port]=0.
        for r in rows:
            t=r['time']/T
            count=r.get(name+'n',math.inf)
            if not math.isfinite(count) or abs(count-round(count))>1e-10:fail('noninteger counter '+name);continue
            count=round(count)
            legal=[i for i in range(len(events)+1) if (i==0 or float(events[i-1][0])*T<=r['time']+TIME_BUDGET) and (i==len(events) or float(events[i][0])*T>=r['time']-TIME_BUDGET)]
            if count not in legal:fail('callback count/time '+name)
            if count<prev or count>prev+1:fail('counter order '+name)
            if count==prev+1:
                target=float(events[count-1][0])*T if count<=len(events) else math.inf
                event_brackets.append(dict(instance=name,index=count,lo_s=last_t,hi_s=r['time'],nominal_s=target))
                if last_t<target-TIME_BUDGET or r['time']>target+TIME_BUDGET:fail('callback bracket '+name)
            prev=count;last_t=r['time']
            held=float(initial(p) if count==0 else events[count-1][1]) if 0<=count<=len(events) else math.inf
            for port,answer in [('h',held),('e',edge_value(p,t)),('f',filter_value(p,t))]:
                actual=r.get(name+port,math.inf)
                if not math.isfinite(actual):fail('nonfinite '+name+port);continue
                error=abs(actual-answer);errors[name+port]=max(errors[name+port],error)
                if error>VOLTAGE_BUDGET:fail('voltage '+name+port)
        if prev!=len(events):fail('final count '+name)
    return dict(status='PASS' if not failures else 'FAIL',failures=failures,maximum_errors_V=errors,event_brackets=event_brackets,rows=len(rows),scope='finite native observations and observed counter brackets; no exact-boundary or continuous-time qualification')
