"""Development-informed foundation cards and simulator-independent bounds.

Fractions describe the actual binary64 tokens. Returned ranges include callback
and 16*ULP(stop) time serialization uncertainty. They are not DUT error allowances.
"""
from fractions import Fraction as F
import math
from decimal import Decimal, localcontext
from itertools import product

T = 1e-6


def _outward(value, up):
    number = float(value)
    if (F(number) < value) if up else (F(number) > value):
        number = math.nextafter(number, math.inf if up else -math.inf)
    return number


def _pwl(points, time):
    for (a,u),(b,v) in zip(points,points[1:]):
        if time <= F(a):
            return F(u)
        if time <= F(b):
            return F(u)+(F(v)-F(u))*(time-F(a))/(F(b)-F(a))
    return F(points[-1][1])


def _card(group, body, outputs, declarations='', inputs=None, stop=5*T):
    if inputs is None:
        inputs={'u':[[0,-.5],[2*T,.5],[4*T,-.5],[stop,-.5]],
                'r':[[0,.25],[2*T,.375],[4*T,.25],[stop,.25]]}
    ports=list(inputs)+outputs
    source='`include "disciplines.vams"\nmodule probe('+','.join(ports)+');\n'
    source+='input '+','.join(inputs)+';\n' if inputs else ''
    source+='output '+','.join(outputs)+';\nelectrical '+','.join(ports)+';\n'
    source+=declarations+'\nanalog begin\n'+body+'\nend\nendmodule\n'
    return dict(id=group+'-base',group_id=group,family='foundation',title=group,
                source=source,top='probe',ports=ports,parameters={},inputs=inputs,
                outputs=outputs,scale_V=1.,unit_s=T,stop_s=stop,
                critical_times_s=sorted({0.,stop,*[p[0] for ps in inputs.values() for p in ps]}),
                events=[],counter_channels={},input_gain_bound=6.,
                output_slope_bound_V_s=6/T,reference_kind=group,
                reference_parameters={})


def cards():
    result=[]
    def add(group,body,outputs,declarations='',**kw):
        c=_card(group,body,outputs,declarations,**kw);result.append(c);return c
    c=add('F01','leaf a(u,yA,r); leaf #(.G(-0.5)) b(u,yB,r);',['yA','yB'])
    # Instances are declarations, not procedural statements.
    c['source']=c['source'].replace('analog begin\nleaf a(u,yA,r); leaf #(.G(-0.5)) b(u,yB,r);\nend',
                                  'leaf a(u,yA,r); leaf #(.G(-0.5)) b(u,yB,r);')
    c['source']='`define SCALE(z) ((z)*G)\n'+c['source']+"module leaf(u,y,r); input u; output y; inout r; electrical u,y,r; parameter real G=3; analog begin V(y,r)<+`SCALE(V(u,r))+0.125; end endmodule\n"
    add('F02','a=V(u,r); V(y,r)<+a; a=2*a+0.125; V(y,r)<+a; V(z,r)<+a;',
        ['y','z'],'real a;')
    body='V(lt)<+(V(u)<0.5); V(le)<+(V(u)<=0.5); V(gt)<+(V(u)>0.5); V(ge)<+(V(u)>=0.5); V(logic)<+(V(a)||V(b)&&V(c)); V(tern)<+(V(a)?1:V(b)?2:3);'
    dc_rows=[(.5,0,0,0),(math.nextafter(.5,-math.inf),-1,0,0),
             (math.nextafter(.5,math.inf),0,-1,1),(-.25,0,1,0)]
    dc_rows += [(.5,a,b,c) for a in (0,1) for b in (0,1) for c in (0,1)]
    for i,row in enumerate(dc_rows):
        inputs={n:[[0,v],[T,v]] for n,v in zip(('u','a','b','c'),row)}
        c=add('F03',body,['lt','le','gt','ge','logic','tern'],inputs=inputs,stop=T)
        c['id']=f'F03-dc-{i}'; c['output_slope_bound_V_s']=0
    for i,u in enumerate((0,1,2,-1,.5)):
        c=add('F04','a=9; case(V(u)) 0,1:a=3; 1:a=99; 2:a=7; default:a=9; endcase V(y)<+a;',
              ['y'],'real a;',inputs={'u':[[0,u],[T,u]]},stop=T)
        c['id']=f'F04-dc-{i}';c['output_slope_bound_V_s']=0
    functions="""analog function real clip; input x; real x;
 begin if(x<0) clip=0; else if(x>0.75) clip=0.75; else clip=x; end endfunction
 analog function real seq; input x; real x,t;
 begin t=x; seq=0; if(t>0.5) begin t=-t; seq=1; end seq=seq+t; end endfunction"""
    c=add('F05','V(y)<+clip(V(u)); V(z)<+seq(V(u));',['y','z'],functions,
          inputs={'u':[[0,-.25],[2*T,.75],[4*T,-.25]]},stop=4*T)
    c['critical_times_s']+= [T/2,1.5*T,2.5*T,3.5*T]
    for i,u in enumerate((0,.5,.75)):
        c=add('F05','V(y)<+clip(V(u)); V(z)<+seq(V(u));',['y','z'],functions,
              inputs={'u':[[0,u],[T,u]]},stop=T)
        c['id']=f'F05-dc-{i}';c['output_slope_bound_V_s']=0
    add('F06','for(i=0;i<3;i=i+1) q[i]=(i+1)*V(u,r); for(i=0;i<3;i=i+1) V(y,r)<+q[i]; V(first,r)<+q[0]; V(last,r)<+q[2];',
        ['y','first','last'],'real q[0:2]; genvar i;')
    c=add('F08','V(b[0],r)<+V(u,r); V(b[1],r)<+-2*V(u,r); V(b0)<+V(b[0]); V(b1)<+V(b[1]); V(y,r)<+V(b[0],r)+V(b[1],r);',
          ['y','b0','b1'],'electrical [1:0] b;')
    c=add('F09','',['z','y'],'child #(.G(2)) a(u,z,r); child #(.G(-0.5)) b(z,y,r);')
    c['source']+='module child(u,y,r); input u; output y; inout r; electrical u,y,r; parameter real G=1; analog begin V(y,r)<+G*V(u,r)+0.125; end endmodule\n'
    c=add('F10','V(y,r)<+2*V(u,r); V(y,r)<+0.125;',['y'])
    import copy
    shifted=copy.deepcopy(c);shifted['id']='F10-common-mode'
    for ps in shifted['inputs'].values():
        for point in ps:point[1]+=.125
    result.append(shifted)
    add('F11','V(y,r)<+0.25*V(y,r)+0.5*V(u,r)+0.125;',['y'])
    add('F12','V(y,r)<+V(u,r)-0.5*pow(V(y,r),3);',['y'])
    for i,v in enumerate((-1.5,0,1.5)):
        c=add('F12','V(y,r)<+V(u,r)-0.5*pow(V(y,r),3);',['y'],
              inputs={'u':[[0,v],[T,v]],'r':[[0,0],[T,0]]},stop=T)
        c['id']=f'F12-dc-{i}';c['output_slope_bound_V_s']=0
    c=add('F07',f"@(initial_step) begin n=0; for(i=0;i<2;i=i+1) q[i]=i; end @(timer({T/4:.17g},0,1e-10)) begin n=n+1; for(i=0;i<2;i=i+1) q[i]=10*q[i]+i+1; end @(cross(V(u)-0.5,1,1e-10,1e-4)) begin n=n+1; for(i=0;i<2;i=i+1) q[i]=10*q[i]+i+1; end V(first)<+q[0]; V(last)<+q[1]; V(y)<+q[0]+q[1]; V(count)<+n;",
          ['first','last','y','count'],'real q[0:1],n; genvar i;',inputs={'u':[[0,0],[T,1]]},stop=T)
    c['events']=[_event('array-timer',T/4,1,'timer'),_event('array-cross',T/2,2,'cross')]
    c['events'][1].update(input='u',slope_V_s=1/T,expression_tolerance_V=1e-4)
    c['counter_channels']={'count':{'initial':0,'final':2}}
    c['critical_times_s']+= [T/4,T/2]
    c['output_slope_bound_V_s']=0
    integral_inputs={'u':[[0,0],[T,.5],[2*T,-.5],[3*T,0]]}
    c=add('F13','V(y)<+idt(1000000*V(u),0.125);',['y'],inputs=integral_inputs,stop=3*T)
    c['reference_parameters']={'integrand_gain':1e6};c['output_slope_bound_V_s']=.5e6
    c=add('F14',f'V(y)<+{T:.17g}*ddt(V(u));',['y'],
          inputs={'u':[[0,0],[T,.5],[2*T,-.5],[3*T,-.5]]},stop=3*T)
    c['reference_parameters']={'derivative_scale':T}
    c['undefined_point_obligations']={'y':[T,2*T]}
    tau=2**-20
    filt_inputs={'u':[[0,.25],[tau,.75],[2*tau,-.25],[3*tau,-.25]]}
    for group,body in [('F15',f"V(y)<+laplace_nd(V(u),'{{1}},'{{1,{tau:.17g}}});"),
                       ('F16',"V(y)<+laplace_np(V(u),'{1},'{-1048576,0});")]:
        c=add(group,body,['y'],inputs=filt_inputs,stop=3*tau)
        c['unit_s']=tau;c['reference_parameters']={'tau_s':tau}
        c['qualification_note']='Dyadic tau/pole establishes identical represented ODE; no general NP claim.'
    ramp={'u':[[0,-.25],[T,.75],[2*T,-.25],[3*T,-.25]]}
    delay=.75*T
    c=add('F17',f'V(y)<+absdelay(V(u),{delay:.17g});',['y'],inputs=ramp,stop=3*T)
    c['reference_parameters']={'delay_s':delay}
    c['critical_times_s'] += [delay,T+delay,2*T+delay]
    c=add('F18','V(y)<+slew(V(u),250000,-500000);',['y'],
          inputs={'u':[[0,0],[T,.5],[2*T,-.5],[3*T,-.5]]},stop=3*T)
    c['reference_parameters']={'rise_V_s':250000.,'fall_V_s':-500000.}
    c['critical_times_s'] += [float(_slew_catches(c)[0]),float(_slew_catches(c)[1])]
    c=add('F19',f"@(initial_step) begin q=0; n=0; end @(timer({T:.17g},0,1e-10)) begin q=0.5; n=n+1; end @(timer({3*T:.17g},0,1e-10)) begin q=0; n=n+1; end V(y)<+transition(q,{T/4:.17g},{T/2:.17g},{T:.17g}); V(state)<+q; V(count)<+n;",
          ['y','state','count'],'real q,n;',inputs={},stop=5*T)
    c['events']=[_event('edge-rise',T,1,'timer'),_event('edge-fall',3*T,2,'timer')]
    c['counter_channels']={'count':{'initial':0,'final':2}}
    c['reference_parameters']={'delay_s':T/4,'rise_s':T/2,'fall_s':T}
    c['critical_times_s'] += [T,1.25*T,1.75*T,3*T,3.25*T,4.25*T]
    c['output_slope_bound_V_s']=1/T
    c=add('F20','p=idtmod(750000,0.125,1,0); V(phase)<+p; V(y)<+sin(6.2831853071795862*p);',
          ['phase','y'],'real p;',inputs={},stop=5*T)
    c['reference_parameters']={'frequency_Hz':750000.,'initial_phase':.125,'sine_gain':float('6.2831853071795862')}
    c['critical_times_s']=sorted([0.,5*T,*[float(F(8*k-1,8)/750000) for k in (1,2,3)]])
    c['wrap_times_s']=c['critical_times_s'][1:-1]
    c['qualification_note']='Raw phase uses ordinary voltage error; circular phase is diagnostic only. Full wrap-side observations required.'
    c['output_slope_bound_V_s']=2*math.pi*750000
    gains={'F01':5.,'F02':5.,'F03':1.,'F04':1.,'F05':1.,'F06':11.,'F07':0.,'F08':5.,'F09':3.,'F10':3.,'F11':1.,'F12':1.,'F13':3.,'F14':2.,'F15':1.,'F16':1.,'F17':1.,'F18':1.,'F19':0.,'F20':0.}
    for c in result:
        c['input_gain_bound']=gains[c['group_id']]
        c['title']={'F01':'Macro and instance parameters','F02':'Sequential locals and contribution snapshots','F03':'Comparisons, logic and ternary DC boundaries','F04':'Scalar case first match and default','F05':'Pure function branches and locals','F06':'Static loop and local array','F07':'Non-idempotent persistent array events','F08':'Static electrical vector','F09':'Two-level hierarchy parameters','F10':'Reference and additive contributions','F11':'Unique affine implicit relation','F12':'Monotone cubic implicit relation','F13':'Integral with nonzero initial state','F14':'PWL derivative one-sided values','F15':'Dyadic laplace_nd DC initialization','F16':'Dyadic laplace_np equivalent encoding','F17':'Fixed delay startup history','F18':'Asymmetric slew reverse catch-up','F19':'Timer and complete asymmetric transition','F20':'Half-open wrapped phase and sine'}[c['group_id']]
        if c['group_id']=='F14':
            c['phase_obligations']={'initial':'DC operating point derivative 0; transient phase must be distinguished','requires_actual_phase_evidence':True}
            c['qualification_note']='time=0 alone is not evidence of DC phase; derivative corners require native one-sided rows.'
        if c['group_id'] in ('F03','F04'):
            c['input_exact_evidence_required']=True
            c['qualification_note']='DC equality and adjacent binary64 rows require enough input export precision to establish the represented value.'
        c['critical_times_s']=sorted(set(c['critical_times_s']))
        c['timing_evidence_required']=bool(c['events'])
        if c['group_id']=='F07':c['event_sensitivity_bound_V_s']=0.
        if c['group_id']=='F19':c['event_sensitivity_bound_V_s']=1e6
        if c['events']:
            for e in c['events']:c['critical_times_s'] += [e['early_s'],e['late_s']]
        c['critical_times_s']=sorted(set(c['critical_times_s']))
    return sorted(result,key=lambda c:(c['group_id'],c['id']))


def _event(name,nominal,index,kind):
    early=nominal-1e-10 if kind=='timer' else nominal
    return dict(id=name,counter='count',index=index,nominal_s=nominal,
                early_s=early,late_s=nominal+1e-10,kind=kind)


def _pure(card,t):
    inputs={n:_pwl(ps,t) for n,ps in card['inputs'].items()}
    u=inputs.get('u',F(0));r=inputs.get('r',F(0));v=u-r;g=card['group_id']
    if g=='F01':return {'yA':r+3*v+F(1,8),'yB':r-v/2+F(1,8)}
    if g=='F02':return {'y':r+3*v+F(1,8),'z':r+2*v+F(1,8)}
    if g=='F03':
        a,b,c=(bool(inputs[n]) for n in ('a','b','c'))
        return dict(lt=F(u<F(1,2)),le=F(u<=F(1,2)),gt=F(u>F(1,2)),ge=F(u>=F(1,2)),
                    logic=F(a or b and c),tern=F(1 if a else 2 if b else 3))
    if g=='F04':return {'y':F(3 if u in (0,1) else 7 if u==2 else 9)}
    if g=='F05':return {'y':min(F(3,4),max(F(0),u)), 'z':u if u<=F(1,2) else 1-u}
    if g=='F06':return {'y':r+6*v,'first':r+v,'last':r+3*v}
    if g=='F08':return {'y':r-v,'b0':r+v,'b1':r-2*v}
    if g=='F09':return {'z':r+2*v+F(1,8),'y':r-v+F(1,16)}
    if g=='F10':return {'y':r+2*v+F(1,8)}
    if g=='F11':return {'y':r+(F(1,2)*v+F(1,8))/F(3,4)}
    if g=='F12':
        lo,hi=F(-4),F(4)
        for _ in range(120):
            mid=(lo+hi)/2
            if mid+mid**3/2 < v:lo=mid
            else:hi=mid
        return {'y':(r+lo,r+hi)}
    raise NotImplementedError(g)


def _exp(value):
    """Decimal.exp correct rounding plus one decimal ULP contains exp(Fraction)."""
    with localcontext() as ctx:
        ctx.prec=90
        # Enclose conversion as well; monotonic exp then expands rounded values.
        ctx.rounding='ROUND_FLOOR';lo=Decimal(value.numerator)/Decimal(value.denominator)
        ctx.rounding='ROUND_CEILING';hi=Decimal(value.numerator)/Decimal(value.denominator)
        a=lo.exp();b=hi.exp()
        return F(a.next_minus()),F(b.next_plus())


def _mul(a,b):
    vals=[x*y for x in a for y in b];return min(vals),max(vals)


def _filter(card,t):
    points=card['inputs']['u'];tau=F(card['reference_parameters']['tau_s'])
    y=(F(points[0][1]),F(points[0][1]))
    if t<=0:return y
    for (a,u),(b,v) in zip(points,points[1:]):
        a,b,u,v=map(F,(a,b,u,v));h=min(t,b)-a
        if h<=0:break
        slope=(v-u)/(b-a);m=slope*tau;x=h/tau
        term=_mul((y[0]-u+m,y[1]-u+m),_exp(-x))
        base=u+slope*h-m;y=(base+term[0],base+term[1])
        if t<=b:break
    return y


def _integral(card,t):
    total=F(1,8);gain=F(card['reference_parameters']['integrand_gain'])
    for (a,u),(b,v) in zip(card['inputs']['u'],card['inputs']['u'][1:]):
        a,b,u,v=map(F,(a,b,u,v));h=min(t,b)-a
        if h<=0:break
        total+=gain*(u*h+(v-u)*h*h/(2*(b-a)))
        if t<=b:break
    return total


def _slew_segments(card):
    y=F(card['inputs']['u'][0][1]);segments=[]
    rise=F(card['reference_parameters']['rise_V_s']);fall=F(card['reference_parameters']['fall_V_s'])
    for (a,u),(b,v) in zip(card['inputs']['u'],card['inputs']['u'][1:]):
        a,b,u,v=map(F,(a,b,u,v));m=(v-u)/(b-a)
        rate=rise if y<u else fall if y>u else min(rise,max(fall,m))
        catch=(u-y)/(rate-m) if rate!=m else F(-1)
        if 0<catch<b-a:
            segments.append((a,a+catch,y,rate));y+=rate*catch
            track=min(rise,max(fall,m));segments.append((a+catch,b,y,track));y+=track*(b-a-catch)
        else:
            segments.append((a,b,y,rate));y+=rate*(b-a)
    return segments


def _slew_catches(card):
    segments=_slew_segments(card)
    original={F(p[0]) for p in card['inputs']['u']}
    return [a for a,b,y,r in segments if a not in original]


def _clip(x):return min(F(1),max(F(0),x))


def _sin_phase(phase, gain=F(float('6.2831853071795862'))):
    # The source angle coefficient is the represented binary64 token, not an
    # ideal 2*pi. Taylor's Lagrange remainder needs no library transcendental.
    phase=phase-math.floor(phase)
    x=gain*phase
    s=sum(((-1)**k*x**(2*k+1)/math.factorial(2*k+1) for k in range(40)),F(0))
    error=abs(x)**81/math.factorial(81)
    return max(F(-1),s-error),min(F(1),s+error)


def _callback_ranges(card,event_bounds):
    known={e['id'] for e in card['events']}
    if set(event_bounds)-known:raise ValueError('unknown event id')
    ranges=[]
    for e in card['events']:
        pair=event_bounds.get(e['id'],[e['early_s'],e['late_s']])
        if len(pair)!=2 or not all(math.isfinite(x) for x in pair) or pair[0]>pair[1]:
            raise ValueError('invalid callback interval')
        # Never clip a caller's interval to the legal window. Shared grader checks legality.
        ranges.append(tuple(map(F,pair)))
    if any(a[1]>=b[0] for a,b in zip(ranges,ranges[1:])):
        raise ValueError('callback intervals do not establish required order')
    return ranges


def _dynamic(card,t,callback_ranges):
    g=card['group_id'];p=card['reference_parameters']
    if g=='F07':
        lower=sum(t>=hi for lo,hi in callback_ranges);upper=sum(t>=lo for lo,hi in callback_ranges)
        states=[(0,1),(1,12),(11,122)]
        return {name:(min(vals),max(vals)) for name,vals in
                [('first',[states[n][0] for n in range(lower,upper+1)]),
                 ('last',[states[n][1] for n in range(lower,upper+1)]),
                 ('y',[sum(states[n]) for n in range(lower,upper+1)]),
                 ('count',list(range(lower,upper+1)))]}
    if g=='F13':return {'y':_integral(card,t)}
    if g in ('F15','F16'):return {'y':_filter(card,t)}
    if g=='F17':return {'y':_pwl(card['inputs']['u'],max(F(0),t-F(p['delay_s'])))}
    if g=='F18':
        for a,b,y,rate in _slew_segments(card):
            if t<=b:return {'y':y+rate*max(F(0),t-a)}
        a,b,y,rate=_slew_segments(card)[-1];return {'y':y+rate*(b-a)}
    if g=='F19':
        candidates=[]
        for e1,e2 in product(*[(lo,hi) for lo,hi in callback_ranges]):
            y=F(1,2)*_clip((t-e1-F(p['delay_s']))/F(p['rise_s']))
            y-=F(1,2)*_clip((t-e2-F(p['delay_s']))/F(p['fall_s']))
            n=int(t>=e1)+int(t>=e2);q=F(1,2) if e1<=t<e2 else F(0)
            candidates.append({'y':y,'state':q,'count':F(n)})
        return {n:(min(v[n] for v in candidates),max(v[n] for v in candidates)) for n in candidates[0]}
    if g=='F20':
        phi=F(p['initial_phase'])+F(p['frequency_Hz'])*max(t,F(0))
        return {'phase':phi-math.floor(phi),'y':_sin_phase(phi,F(p['sine_gain']))}
    raise NotImplementedError(g)


def reference(card, time_s, event_bounds):
    if not isinstance(time_s,(int,float)) or not math.isfinite(time_s):raise ValueError('nonfinite time')
    if time_s<0 or time_s>card['stop_s']:raise ValueError('time outside card extent')
    ut=card.get('reference_time_uncertainty_s',16*math.ulp(card['stop_s']))
    if not math.isfinite(ut) or ut<0:raise ValueError('invalid time serialization uncertainty')
    time=F(time_s);half=F(ut)
    low=max(F(0),time-half);high=min(F(card['stop_s']),time+half)
    times=[low,high]
    times += [F(t) for t in card['critical_times_s'] if low<=F(t)<=high]
    callback_ranges=_callback_ranges(card,event_bounds)
    g=card['group_id'];undefined={}
    if g=='F14':
        if time_s==0:values=[{'y':F(0)}]
        elif any(low<=F(t)<=high for t in card['undefined_point_obligations']['y']):
            values=[{}];undefined={'y':'PWL derivative undefined at corner; both one-sided critical observations required'}
        else:
            values=[]
            for t in times:
                for (a,u),(b,v) in zip(card['inputs']['u'],card['inputs']['u'][1:]):
                    if F(a)<t<=F(b):
                        values.append({'y':F(card['reference_parameters']['derivative_scale'])*(F(v)-F(u))/(F(b)-F(a))});break
    else:
        values=[_dynamic(card,t,callback_ranges) if g in ('F07','F13','F15','F16','F17','F18','F19','F20') else _pure(card,t) for t in times]
    ranges={n:[_outward(min((a[n][0] if isinstance(a[n],tuple) else a[n]) for a in values),False),
               _outward(max((a[n][1] if isinstance(a[n],tuple) else a[n]) for a in values),True)] for n in values[0]}
    if g=='F20':
        p=card['reference_parameters'];a=F(p['initial_phase'])+F(p['frequency_Hz'])*low;b=F(p['initial_phase'])+F(p['frequency_Hz'])*high
        if math.floor(a)!=math.floor(b):ranges['phase']=[0.,1.]
        # A Lipschitz enclosure includes sine extrema missed by endpoint sampling.
        gain=F(p['sine_gain']);mid=(a+b)/2;slo,shi=_sin_phase(mid,gain);radius=(b-a)*gain/2
        if math.floor(a)!=math.floor(b):
            # sin at raw phase 1 and 0 differ by coefficient rounding.
            endlo,endhi=_sin_phase(F(1)-F(1,10**100),gain)
            slo=min(slo,endlo,F(0));shi=max(shi,endhi,F(0))
        ranges['y']=[_outward(max(F(-1),min(F(ranges['y'][0]),slo-radius)),False),
                     _outward(min(F(1),max(F(ranges['y'][1]),shi+radius)),True)]
    # Bound any extrema inside the serialized time cell, including a clamp cusp
    # or ODE stationary point that endpoint-only sampling could miss.
    if g not in ('F03','F04','F07','F14','F19','F20') and half:
        center=_dynamic(card,time,callback_ranges) if g in ('F13','F15','F16','F17','F18') else _pure(card,time)
        radius=F(card['output_slope_bound_V_s'])*half
        for n,v in center.items():
            lo,hi=v if isinstance(v,tuple) else (v,v)
            ranges[n]=[_outward(min(F(ranges[n][0]),lo-radius),False),
                       _outward(max(F(ranges[n][1]),hi+radius),True)]
    # 120 bisections, 90-digit exp, and the rational Taylor tail contribute
    # less than 1e-30 V here; four binary64 ULPs bound outward export conversion.
    arithmetic=max((4*math.ulp(max(abs(lo),abs(hi))) for lo,hi in ranges.values()),default=0.)+1e-30
    return dict(outputs=ranges,numerical_uncertainty_V=arithmetic,undefined=undefined,
                time_uncertainty_included=True)
