"""Independent analytic answers for paper-a1-core-v1, in normalized time x=t/T."""
import math


def pwl(points, x):
    if x <= points[0][0]: return points[0][1]
    if x >= points[-1][0]: return points[-1][1]
    for (a, va), (b, vb) in zip(points, points[1:]):
        if a <= x <= b: return va+(vb-va)*(x-a)/(b-a)
    raise ValueError(x)


def vco_phase(x):
    knots=[0,1.2,2,3.2,4,4.8,6,6.8,8]
    rates=[.2,.2,.4,1,1,1,.4,.2,.2]
    phase=.125
    for a,b,fa,fb in zip(knots,knots[1:],rates,rates[1:]):
        z=max(0,min(x,b)-a)
        phase+=fa*z+(fb-fa)*z*z/(2*(b-a))
    return phase


def clip(x):return min(1,max(0,x))


def values(card, x, events, counters):
    """One shared inferred event history drives every port; no backend traces used."""
    case=card['id']
    result={k:(s['value_V'] if s['kind']=='dc' else pwl(s['points_T_V'],x)) for k,s in card['stimulus'].items()}
    if case=='VR-01': result['out']=result['ref']+1.5*(result['ip']-result['im'])-.125
    elif case in ('EX-01','CO-VCO-01'):
        result['freq']=min(1,max(.2,.4+.5*result['ctl']))
        if case=='CO-VCO-01':
            p=vco_phase(x);result.update(phase=p%1,out=math.sin(2*math.pi*p))
    elif case=='CP-01':
        p=.125+.3*x if x<=2 else .725+.3*(x-2)+.15*(x-2)**2 if x<=4 else 1.925+.9*(x-4)
        result['phase']=p
    elif case=='CP-02':
        p=.125+.75*x;result.update(phase=p%1,out=math.sin(2*math.pi*p))
    elif case in ('EV-HC-01','EV-HC-02','CO-HC-01'):
        n=counters['count']; q=(1-n%2) if case=='EV-HC-02' else n%2
        result['out']=.1+.8*q
        if case=='CO-HC-01':
            e=events['count'];result.update(state=q,out=.1+.8*(clip((x-e[0]-.125)/.25)-clip((x-e[1]-.125)/.5)))
    elif case=='EV-SH-01':
        n=counters['count'];result['out']=-.25 if n==0 else pwl(card['stimulus']['in']['points_T_V'],events['count'][n-1])
    elif case=='TM-01':
        e=events['count'];result.update(state=counters['count']%2,out=clip((x-e[0]-.25)/.5)-clip(x-e[1]-.25))
    elif case=='SI-01':
        na,nb=counters['na'],counters['nb']
        result.update(oa=-.25 if na==0 else .1*events['na'][na-1],ob=.75 if nb==0 else 1-.1*events['nb'][nb-1])
    elif case=='CO-SH-01':
        n=counters['count'];e=events['count'];levels=[-.25,pwl(card['stimulus']['in']['points_T_V'],e[0]),-.25,-.25,pwl(card['stimulus']['in']['points_T_V'],e[3]),pwl(card['stimulus']['in']['points_T_V'],e[4])]
        y=levels[0]
        for j,t in enumerate(e): y+=(levels[j+1]-levels[j])*clip((x-t)/.1)
        result.update(state=levels[n],out=y)
    return result


def error_bound(card, port, x, time_error_T, event_error_T, input_error):
    """Conservative Lipschitz bounds, including initial/input integration uncertainty."""
    case=card['id']; e=event_error_T
    if port in card['stimulus']:
        s=card['stimulus'][port]
        slope=0 if s['kind']=='dc' else max(abs((vb-va)/(b-a)) for (a,va),(b,vb) in zip(s['points_T_V'],s['points_T_V'][1:]))
        return slope*time_error_T
    if case=='VR-01':return 1.225*time_error_T+4*input_error
    if case=='EX-01':return .5*time_error_T+.5*input_error
    if case=='EV-SH-01':return .3*e+input_error
    if case in ('EV-HC-01','EV-HC-02'):return 0
    if case=='TM-01':return 2*(e+time_error_T)
    if case=='SI-01':return .1*e+input_error
    if case=='CO-SH-01':return .2*e+input_error+(0 if port=='state' else 10.5*(e+time_error_T))
    if case=='CO-HC-01':return 0 if port=='state' else 3.2*(e+time_error_T)
    if case=='CP-01':return .9*time_error_T+max(0,x)*input_error
    if case=='CP-02':return .75*time_error_T*(2*math.pi if port=='out' else 1)
    if case=='CO-VCO-01':
        phase_error=time_error_T+.5*max(0,x)*input_error
        if port=='freq':return .5*time_error_T+.5*input_error
        return phase_error*(2*math.pi if port=='out' else 1)
    raise ValueError((case,port))
