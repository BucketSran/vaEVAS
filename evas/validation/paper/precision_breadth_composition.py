"""Independent engineering-composition cards and mathematical enclosures.

No EVAS solver or runtime is imported. Event bounds belong to one run-wide
history. References use exact binary64 inputs, Decimal interval operations and
analytic solutions; unsupported/semantics-pending slots remain explicit probes.
"""
from __future__ import annotations
from decimal import Decimal, localcontext
import math
from fractions import Fraction

UNIT = 2.0 ** -20
TIME_TOL = 1e-10
D = Decimal
PI = D('3.141592653589793238462643383279502884197169399375105820974944592307816406286')


def _model(ports, body, declarations=''):
    return ('`include "disciplines.vams"\n`include "constants.vams"\n'
            f'module breadth({",".join(ports)});\ninout {",".join(ports)};\n'
            f'electrical {",".join(ports)};\nparameter real T=9.5367431640625e-7;\n'
            'parameter real TT=1e-10;\n' + declarations + '\nanalog begin\n' + body + '\nend\nendmodule\n')


def _event(card, name, x, index, *, counter='n', kind='timer', input=None, slope=None):
    t = float(x) * UNIT
    event = dict(id=f'{card["id"]}:{name}', counter=counter, index=index,
                 nominal_s=t, early_s=TIME_TOL, late_s=TIME_TOL, kind=kind)
    if input is not None:
        event.update(input=input, slope_V_s=slope, expression_tolerance_V=.0005)
        event['early_s']=0.
        event['late_s']=min(TIME_TOL,.0005/abs(slope))
    card['events'].append(event)
    card['critical_times_s'].append(t)
    card['counter_channels'][counter] = dict(initial=0, final=index)
    return event


def cards():
    """Return fresh JSON-serializable, complete ordinary-deck cards."""
    result = []
    for group in range(1,25):
        result.append(dict(id=f'EC{group:02d}-v1', group_id=f'EC{group:02d}',
            family='composition', title='', top='breadth', ports=[], parameters={},
            inputs={}, outputs=[], scale_V=1., unit_s=UNIT, stop_s=8*UNIT,
            critical_times_s=[0.,8*UNIT], events=[], counter_channels={},
            input_gain_bound=1., output_slope_bound_V_s=64/UNIT,
            reference_kind='independent-analytic-interval-v1', reference_parameters={}))

    def setcase(i, title, ports, body, decl='', *, inputs=None, stop=8, critical=()):
        c=result[i-1]
        c.update(title=title, ports=ports.split(), outputs=[p for p in ports.split() if p not in (inputs or {})],
                 source=_model(ports.split(),body,decl), stop_s=stop*UNIT,
                 inputs={k:[[x*UNIT,v] for x,v in pts] for k,pts in (inputs or {}).items()},
                 critical_times_s=sorted({0.,stop*UNIT,*(x*UNIT for x in critical)}))
        c['reference_parameters']={'contract': c['group_id'], 'unit_s': UNIT}
        return c

    c=setcase(1,'Sample/reset priority and transition','u clk rst q out n',
        '@(initial_step) begin h=-0.25; n0=0; end\n'
        '@(cross(V(clk)-0.5,1,TT,0.0005) or cross(V(rst)-0.5,1,TT,0.0005)) begin '
        'n0=n0+1; if(V(rst)>0.25) h=-0.25; else h=V(u); end\n'
        'V(q)<+h; V(out)<+transition(h,0,0.125*T,0.125*T); V(n)<+n0;',
        'real h; integer n0;', inputs={'u':[[0,-.4],[9,1.4]],
        'clk':[[0,0],[1.875,0],[2.125,1],[2.25,0],[3.875,0],[4.125,1],[4.25,0],
               [5.875,0],[6.125,1],[6.25,0],[7.875,0],[8.125,1],[8.25,0],[9,0]],
        'rst':[[0,0],[2.875,0],[3.125,1],[4.875,1],[5.125,0],[9,0]]},stop=9,
        critical=(2,3,4,5,6,8,2.125,3.125,6.125,8.125))
    for k,x in enumerate([2,3,4,6,8],1):
        _event(c,str(k),x,k,kind='cross',input='rst' if x==3 else 'clk',slope=4/UNIT)

    c=setcase(2,'Hysteresis, asymmetric edges and short-pulse reversal','u state out n',
        '@(initial_step) begin q=0; n0=0; end\n'
        '@(cross(V(u)-0.75,1,TT,0.0005)) begin q=1; n0=n0+1; end\n'
        '@(cross(V(u)-0.25,-1,TT,0.0005)) begin q=0; n0=n0+1; end\n'
        'V(state)<+q; V(out)<+transition(q,0.0625*T,0.25*T,0.5*T); V(n)<+n0;',
        'integer q,n0;',inputs={'u':[[0,0],[1,1],[2,1],[3,0],[4,0],[4.0625,1],[4.125,0],[5,0]]},stop=5,
        critical=(.75,2.75,4.046875,4.109375,1.0625,3.3125,0.8125,2.8125,4.171875,4.296875))
    for k,x in enumerate([.75,2.75,4.046875,4.109375],1):
        _event(c,str(k),x,k,kind='cross',input='u',slope=(1 if k==1 else -1 if k==2 else 16 if k==3 else -16)/UNIT)

    c=setcase(3,'Sampled integral nonzero IC including stop callback','u q y n',
        '@(initial_step) begin h=-0.25; n0=0; end\n'
        '@(timer(T,T,TT)) begin h=V(u); n0=n0+1; end\n'
        'V(q)<+h; V(y)<+idt(h/T,0.125); V(n)<+n0;',
        'real h; integer n0;',inputs={'u':[[0,0],[4,1]]},stop=4)
    for k in range(1,5): _event(c,str(k),k,k)

    c=setcase(4,'Ordered sampled assignment into nonlinear integral','u q y n',
        '@(initial_step) begin h=2; n0=0; end\n'
        '@(cross(V(u)*V(u)-2,1,TT,0.0005)) begin h=V(u); h=2*h+1; n0=n0+1; end\n'
        'V(q)<+h; V(y)<+idt(h*h/T,5); V(n)<+n0;',
        'real h; integer n0;',inputs={'u':[[0,0],[2.25,2.25]]},stop=2.25)
    _event(c,'sample',math.sqrt(2),1,kind='cross',input='u',slope=2*math.sqrt(2)/UNIT)

    c=setcase(5,'Interrupted transition into integral support probe','edge y n',
        '@(initial_step) begin q=0; n0=0; end\n'
        '@(timer(T,0,TT)) begin q=1; n0=n0+1; end\n'
        '@(timer(1.25*T,0,TT)) begin q=0; n0=n0+1; end\n'
        'V(edge)<+transition(q,0,0.5*T,T); V(y)<+idt(V(edge)/T,0.1); V(n)<+n0;',
        'integer q,n0;',stop=3,critical=(1,1.25,1.75))
    _event(c,'rise',1,1);_event(c,'reverse',1.25,2)

    c=setcase(6,'Two integrals with one reset and independent IC','a b sum n',
        '@(initial_step) begin r=0; n0=0; end\n'
        '@(timer(0.5*T,0,TT)) begin r=1; n0=n0+1; end\n'
        '@(timer(0.75*T,0,TT)) begin r=0; n0=n0+1; end\n'
        'V(a)<+idt(1/T,0.125,r); V(b)<+idt(1/T,-0.25); V(sum)<+V(a)+V(b); V(n)<+n0;',
        'integer r,n0;',stop=2,critical=(.5,.75))
    _event(c,'assert',.5,1);_event(c,'release',.75,2)
    reset_source=_model(['a','n'],
        '@(initial_step) begin r=0; n0=0; end\n'
        '@(timer(0.5*T,0,TT)) begin r=1; n0=n0+1; end\n'
        '@(timer(0.75*T,0,TT)) begin r=0; n0=n0+1; end\n'
        'V(a)<+idt(1/T,0.125,r); V(n)<+n0;',
        'integer r,n0;').replace('module breadth(', 'module reset_cell(')
    fixed_source=_model(['b'],'V(b)<+idt(1/T,-0.25);').replace('module breadth(', 'module fixed_cell(')
    c['source']=reset_source+fixed_source+_model(c['ports'],
        'V(sum)<+V(a)+V(b);','reset_cell acell(a,n); fixed_cell bcell(b);')

    c=setcase(7,'Reset upstream integral preserves downstream accumulated area','z y n',
        '@(initial_step) begin r=0; n0=0; end\n'
        '@(timer(0.5*T,0,TT)) begin r=1; n0=n0+1; end\n'
        '@(timer(0.75*T,0,TT)) begin r=0; n0=n0+1; end\n'
        'V(z)<+idt(1/T,0.25,r); V(y)<+idt(V(z)/T,0.125); V(n)<+n0;',
        'integer r,n0;',stop=2)
    _event(c,'assert',.5,1);_event(c,'release',.75,2)

    c=setcase(8,'Held-input linear feedback retains other state','y other n',
        '@(initial_step) begin q=0.5; n0=0; end\n'
        '@(timer(0.5*T,0,TT)) begin q=1.5; n0=n0+1; end\n'
        'V(y)<+idt((q-V(y))/T,0.25); V(other)<+idt(1/T,-0.125); V(n)<+n0;',
        'real q; integer n0;',stop=3)
    _event(c,'switch',.5,1)

    setcase(9,'Joint nonlinear integral and filter feedback','z y',
        "V(z)<+idt((1+V(y)-V(z)*V(z))/T,0);\n"
        "V(y)<+laplace_nd(V(z)*V(z)+2*V(z),'{1},'{1,T});",stop=2)

    c=setcase(10,'Event activates Riccati filter without new DC initialization','y n',
        '@(initial_step) begin q=0; n0=0; end\n'
        '@(timer(0.25*T,0,TT)) begin q=0.5; n0=n0+1; end\n'
        "V(y)<+laplace_nd((q*V(y))*(q*V(y))+1,'{1},'{1,T}); V(n)<+n0;",
        'real q; integer n0;',stop=3)
    _event(c,'switch',.25,1)

    setcase(11,'Second-order filter with internal derivative','u y d',
        "V(y)<+laplace_nd(V(u),'{1},'{1,2*T,T*T}); V(d)<+T*ddt(V(y));",
        inputs={'u':[[0,0],[4,4]]},stop=4)
    setcase(12,'Polynomial filter direct term with nonzero DC','u h',
        "V(h)<+laplace_nd(V(u)*V(u),'{1,T},'{2,T});",
        inputs={'u':[[0,.5],[4,4.5]]},stop=4)

    c=setcase(13,'Algebraic projection into delay and sampling','u z delayed q n',
        '@(initial_step) begin h=0.625; n0=0; end\n'
        '@(timer(T,T,TT)) begin h=V(delayed); n0=n0+1; end\n'
        'V(z)<+0.2*V(z)+V(u); V(delayed)<+absdelay(V(z),0.125*T); V(q)<+h; V(n)<+n0;',
        'real h; integer n0;',inputs={'u':[[0,.5],[4,1.5]]},stop=4,critical=(.125,))
    c['input_gain_bound']=1.2500001
    for k in range(1,5): _event(c,str(k),k,k)

    setcase(14,'Two fixed delays and independent parallel history','u a b other',
        'V(a)<+absdelay(V(u),0.125*T); V(b)<+absdelay(V(a),0.375*T); V(other)<+absdelay(V(u),0.25*T);',
        inputs={'u':[[0,.25],[1,1.25],[2,-.75],[3,-.75]]},stop=3,
        critical=(.125,.25,.5,1.125,1.25,1.5,2.125,2.25,2.5))
    setcase(15,'Two asymmetric slew stages and reversal catch-up','u a b',
        'V(a)<+slew(V(u),2/T,-1/T); V(b)<+slew(V(a),1/T,-0.5/T);',
        inputs={'u':[[0,0],[.5,2],[2,2],[3,0],[7,0]]},stop=7,
        critical=(.5,1,2,3,4,6))
    c=setcase(16,'DC derivative phase into filter direct term','u d y',
        "V(d)<+T*ddt(V(u)); V(y)<+laplace_nd(V(d),'{1,T},'{1,2*T});",
        inputs={'u':[[0,0],[4,4]]},stop=4)
    c['phase_obligations']={'dc':{'time_s':0.,'outputs':{'d':0.,'y':0.}},'transient_right':{'outputs':['d','y']}}

    for i, title, inp, freq, ic, offset, stop in [
        (17,'Positive chirp VCO coherent phase and sine',{'u':[[0,0],[4,4]]},'0.5+0.25*V(u)',.125,0,4),
        (18,'Negative frequency with nonzero modulo offset',{},'-0.25',.125,-.5,4)]:
        c=setcase(i,title,('u ' if inp else '')+'freq phase out',
            f'f={freq}; p=idtmod(f/T,{ic},1,{offset}); V(freq)<+f; V(phase)<+p; V(out)<+sin(2*`M_PI*p);',
            'real f,p;',inputs=inp,stop=stop)
        c['phase_channels']={'phase':{'modulus_V':1.,'offset_V':offset}}
        c['reference_parameters']['phase_rule']='raw half-open endpoint; circular diagnostics never replace scalar error'
        if i==17:
            c['critical_times_s'].extend(((-2+math.sqrt(4+8*(k-.125)))*UNIT) for k in range(1,5))
        else:c['critical_times_s'].append(2.5*UNIT)

    c=setcase(19,'Independent phase histories with different frequency and IC','phase_a out_a phase_b out_b sum diff',
        'pa=idtmod(0.5/T,0.125,1,0); pb=idtmod(0.75/T,-0.25,1,0); '
        'V(phase_a)<+pa; V(out_a)<+sin(2*`M_PI*pa); '
        'V(phase_b)<+pb; V(out_b)<+sin(2*`M_PI*pb); '
        'V(sum)<+V(out_a)+V(out_b); V(diff)<+V(out_a)-V(out_b);',
        'real pa,pb;',stop=4,critical=(1.75,3.75,1/3,5/3,3))
    c['phase_channels']={'phase_a':{'modulus_V':1.,'offset_V':0.},'phase_b':{'modulus_V':1.,'offset_V':0.}}
    phase_source=_model(['phase','out'],
        'p=idtmod(F/T,IC,1,0); V(phase)<+p; V(out)<+sin(2*`M_PI*p);',
        'parameter real F=0.5; parameter real IC=0.125; real p;').replace('module breadth(', 'module phase_cell(')
    c['source']=phase_source+_model(c['ports'],
        'V(sum)<+V(out_a)+V(out_b); V(diff)<+V(out_a)-V(out_b);',
        'phase_cell #(.F(0.5),.IC(0.125)) a(phase_a,out_a); '
        'phase_cell #(.F(0.75),.IC(-0.25)) b(phase_b,out_b);')

    c=setcase(20,'Binary64 nearby clocks and sampled integral area','q z sample na nb',
        '@(initial_step) begin q0=0; h=0; a=0; b=0; end\n'
        '@(timer(2e-6,2e-6,TT)) begin q0=q0+1; a=a+1; end\n'
        '@(timer(3e-6,3e-6,TT)) begin h=V(z); b=b+1; end\n'
        'V(q)<+q0; V(z)<+idt(q0/T,0); V(sample)<+h; V(na)<+a; V(nb)<+b;',
        'real q0,h; integer a,b;',stop=7e-6/UNIT)
    times=[]
    for kind,p,n in [('a',2e-6,3),('b',3e-6,2)]:
        for index in range(1,n+1):times.append((Fraction(p)*index,kind,index))
    for t,kind,index in sorted(times):
        event=_event(c,f'{kind}{index}',float(t)/UNIT,index,counter='na' if kind=='a' else 'nb')
        event['nominal_s']=float(t);event['early_s']=TIME_TOL;event['late_s']=TIME_TOL
        event['nominal_exact_fraction']=[t.numerator,t.denominator]
    c['event_order_exact']=[e['id'] for e in c['events']]
    c['order_evidence_required']=True

    c=setcase(21,'Advanced held calendar bounds nonlinear propagation','y n',
        '@(initial_step) begin next=0.625*T; q=1; n0=0; end\n'
        '@(timer(0.125*T,0,TT)) begin next=0.375*T; n0=n0+1; end\n'
        '@(timer(next,0,TT)) begin q=-1; n0=n0+1; end\n'
        'V(y)<+idt(q*V(y)*V(y)/T,0.75); V(n)<+n0;',
        'real next; integer q,n0;',stop=1,critical=(.125,.375,.625))
    _event(c,'advance',.125,1);_event(c,'switch',.375,2)

    c=setcase(22,'Same-time reset and clock semantic probe','u clk rst q out n',
        '@(initial_step) begin h=-0.25; n0=0; end\n'
        '@(cross(V(clk)-0.5,1,TT,0.0005) or cross(V(rst)-0.5,1,TT,0.0005)) begin '
        'n0=n0+1; if(V(rst)>0.25) h=-0.25; else h=V(u); end\n'
        'V(q)<+h; V(out)<+transition(h,0,0.125*T,0.125*T); V(n)<+n0;',
        'real h; integer n0;',inputs={'u':[[0,1],[2,1]],'clk':[[0,0],[.875,0],[1.125,1],[2,1]],
        'rst':[[0,0],[.875,0],[1.125,1],[2,1]]},stop=2,critical=(1,))
    c['timing_evidence_required']=True

    c=setcase(23,'Bidirectional self-commutation support probe','z q n',
        '@(initial_step) begin q0=1; n0=0; end\n'
        '@(cross(V(z)-1,1,TT,0.0005)) begin q0=-1; n0=n0+1; end\n'
        '@(cross(V(z),-1,TT,0.0005)) begin q0=1; n0=n0+1; end\n'
        'V(z)<+idt(q0/T,0); V(q)<+q0; V(n)<+n0;',
        'integer q0,n0;',stop=4,critical=(1,2,3,4))
    for k in range(1,5):_event(c,str(k),k,k,kind='cross',input='z',slope=(1 if k%2 else -1)/UNIT)

    c=setcase(24,'Index-one implicit DAE with reset support probe','u z y other n',
        '@(initial_step) begin r=0; n0=0; end\n'
        '@(timer(0.5*T,0,TT)) begin r=1; n0=n0+1; end\n'
        '@(timer(0.75*T,0,TT)) begin r=0; n0=n0+1; end\n'
        'V(z)<+idt((1+2*V(y))*(1-V(u))/T,0.3125,r); '
        'V(z)<+V(y)+V(y)*V(y)-V(z); V(other)<+idt(1/T,0.125); V(n)<+n0;',
        'integer r,n0;',inputs={'u':[[0,0],[1,1]]},stop=1)
    # Additive contributions above imply 2*z = idt + y+y^2. Use
    # separate zero constraint instead, preserving z = idt and z=y+y^2.
    c['source']=c['source'].replace('V(z)<+V(y)+V(y)*V(y)-V(z);', 'V(y)<+V(z)-V(y)*V(y);')
    _event(c,'assert',.5,1);_event(c,'release',.75,2)

    notes={5:'Current continuous network rejects transition as an integral dependency; no certified waveform expected.',
           22:'Same-time OR callback merging/count contract is unresolved; state priority alone cannot qualify the group.',
           23:'Issue #70 self-commuting cross history closure needs actual support and event-order evidence.',
           24:'Implicit DAE and event/reset combination is outside current documented acceptance.'}
    for i,note in notes.items():
        result[i-1].update(support_probe_only=True,qualification_note=note)
    sensitivities={1:12,2:12,3:5,4:12,6:1,7:2,8:2,10:1,13:2,20:12,21:20}
    for index,multiple in sensitivities.items():
        result[index-1]['event_sensitivity_bound_V_s']=multiple/UNIT
    for c in result:
        c['reference_time_uncertainty_s']=16*math.ulp(c['stop_s'])
        c['critical_times_s']=sorted(set(t for t in c['critical_times_s'] if 0<=t<=c['stop_s']))
    return result


class _I:
    """Decimal interval with outward rounding at every arithmetic operation."""
    def __init__(self, lo, hi=None):
        self.lo = _dec(lo)
        self.hi = self.lo if hi is None else _dec(hi)
        if self.lo > self.hi or not self.lo.is_finite() or not self.hi.is_finite():
            raise ValueError('finite ordered reference interval required')
    def __add__(self, b):
        b=_i(b); return _I((self.lo+b.lo).next_minus(),(self.hi+b.hi).next_plus())
    __radd__=__add__
    def __neg__(self):return _I(self.hi.copy_negate(),self.lo.copy_negate())
    def __sub__(self,b):return self+-_i(b)
    def __rsub__(self,b):return _i(b)+-self
    def __mul__(self,b):
        b=_i(b);v=[a*c for a in (self.lo,self.hi) for c in (b.lo,b.hi)]
        return _I(min(v).next_minus(),max(v).next_plus())
    __rmul__=__mul__
    def __truediv__(self,b):
        b=_i(b)
        if b.lo<=0<=b.hi:raise ValueError('reference denominator may be zero')
        return self*_I((1/b.hi).next_minus(),(1/b.lo).next_plus())
    def __rtruediv__(self,b):return _i(b)/self
    def __pow__(self,n):
        if n not in (2,3):raise ValueError('only quadratic/cubic reference powers')
        if n==2:
            v=[self.lo*self.lo,self.hi*self.hi]
            return _I(0 if self.lo<=0<=self.hi else min(v).next_minus(),max(v).next_plus())
        return _I((self.lo**3).next_minus(),(self.hi**3).next_plus())
    def exp(self):return _I(self.lo.exp().next_minus(),self.hi.exp().next_plus())
    def floats(self):return [math.nextafter(float(self.lo),-math.inf),math.nextafter(float(self.hi),math.inf)]


def _dec(x):
    return x if isinstance(x,D) else D.from_float(x) if isinstance(x,float) else D(x)


def _i(x):return x if isinstance(x,_I) else _I(x)


def _hull(*items):
    values=[_i(x) for x in items];return _I(min(x.lo for x in values),max(x.hi for x in values))


def _positive(x):
    x=_i(x);return _I(max(D(0),x.lo),max(D(0),x.hi))


def _min(a,b):
    a,b=_i(a),_i(b);return _I(min(a.lo,b.lo),min(a.hi,b.hi))


def _clip(x):
    x=_positive(x);return _I(min(D(1),x.lo),min(D(1),x.hi))


def _switch(t,event,before,after,occurred=None):
    """Hull all physical sides if an event window straddles a query."""
    if occurred is False:return before(t)
    if occurred is True:return after(t,event)
    if t.hi<event.lo:return before(t)
    if t.lo>=event.hi:return after(t,event)
    return _hull(before(t),after(t,event))


def _pwl(card,name,time):
    """Interval image of exact binary64 PWL, including all covered knots."""
    pts=card['inputs'][name]; pieces=[]
    if time.lo<=_dec(pts[0][0]):pieces.append(_I(pts[0][1]))
    for (ta,va),(tb,vb) in zip(pts,pts[1:]):
        a,b=_dec(ta),_dec(tb)
        if time.hi<a or time.lo>b:continue
        q=_I(max(time.lo,a),min(time.hi,b))
        pieces.append(_i(va)+(_i(vb)-va)*(q-a)/(b-a))
    if time.hi>=_dec(pts[-1][0]):pieces.append(_I(pts[-1][1]))
    return _hull(*pieces)


def _hold(t,events,values,initial,stages=None):
    value=_i(initial)
    for k,(e,q) in enumerate(zip(events,values)):
        if stages is not None:
            if stages[k]:value=q
            continue
        if t.lo>=e.hi:value=q
        elif t.hi>=e.lo:value=_hull(value,q)
    return value


def _held_area(t,events,values,initial,stages=None):
    """Rectangle areas with globally shared callback boxes, no point fitting."""
    if stages is not None:
        active=sum(stages)
        events,values=events[:active],values[:active]
    area=_i(0);starts=[_i(0),*events];qs=[_i(initial),*values]
    for k,(start,q) in enumerate(zip(starts,qs)):
        end=_min(t,events[k]) if k<len(events) else t
        area=area+q*_positive(end-start)
    return area


def _reset_value(t,a,b,ic,stages=None):
    return _switch(t,a,lambda x:ic+x,
        lambda x,e:_switch(x,b,lambda _: _i(ic),lambda y,f:ic+_positive(y-f),
                              None if stages is None else stages[1]),
        None if stages is None else stages[0])


def _reset_area(t,a,b,ic,stages=None):
    # Integral of ic+x before assert, ic while reset, ic+(x-b) after release.
    first=t if stages is not None and not stages[0] else _min(t,a)
    tail=_i(0) if stages is not None and not stages[1] else _positive(t-b)**2/2
    return ic*t+first**2/2+tail


def _transition(t,events,targets,initial,delay,rise,fall,stages=None):
    """Interval replay of original target/history-origin interruption geometry.

    Event order and direction are fixed in these cards. Even when queries share
    an event window, old/current targets remain in this same run-wide replay.
    Endpoint and clipping arithmetic intentionally over-enclose correlations.
    """
    initial=_i(initial); state=(initial,initial,initial,_i(0),_i(0))
    answer=initial
    def val(s,x):
        origin,start,target,slope,when=s
        progress=_positive(x-when)
        v=start+slope*progress
        return _I(max(min(start.lo,target.lo),min(max(start.hi,target.hi),v.lo)),
                  max(min(start.lo,target.lo),min(max(start.hi,target.hi),v.hi)))
    for k,(event,target) in enumerate(zip(events,targets)):
        if stages is not None and not stages[k]:return val(state,t)
        target=_i(target);when=event+delay
        current=val(state,when)
        oldorigin,oldstart,oldtarget,oldslope,oldwhen=state
        # Cards have alternating targets, except repeated reset/hold targets.
        if target.lo==oldtarget.lo and target.hi==oldtarget.hi:
            new=state
        elif target.lo>=current.hi:
            history=oldorigin if oldslope.lo>=0 else oldtarget
            new=(history,current,target,(target-history)/rise,when)
        elif target.hi<=current.lo:
            history=oldorigin if oldslope.hi<=0 else oldtarget
            new=(history,current,target,(target-history)/fall,when)
        else:
            raise ValueError('transition direction cannot be certified from common event history')
        if t.lo>=when.hi:answer=val(new,t)
        elif t.hi>=when.lo:answer=_hull(val(state,t),val(new,t))
        else:return val(state,t)
        state=new
    return answer


def _sin_scalar(x):
    # 80-digit independent Taylor sum after reduction; remainder <1e-74.
    period=2*PI
    x=x-(x/period).to_integral_value(rounding='ROUND_FLOOR')*period
    if x>PI:x-=period
    term=x;total=x;k=1
    while abs(term)>D('1e-76'):
        term=-term*x*x/D((2*k)*(2*k+1));total+=term;k+=1
        if k>160:raise ArithmeticError('independent sine failed to converge')
    return total


def _sin_cycles(a):
    if a.hi-a.lo>=1:return _I(-1,1)
    low,high=a.lo*2*PI,a.hi*2*PI
    vals=[_sin_scalar(low),_sin_scalar(high)]
    first=int(((low-PI/2)/PI).to_integral_value(rounding='ROUND_CEILING'))
    last=int(((high-PI/2)/PI).to_integral_value(rounding='ROUND_FLOOR'))
    for k in range(first,last+1):vals.append(D(1) if k%2==0 else D(-1))
    # Includes finite-precision PI/Taylor and the source's binary64 2*M_PI
    # vs mathematical 2*pi discrepancy on any wrapped phase in [-.5,1].
    error=D('1e-15')
    return _I(max(D(-1),min(vals)-error),min(D(1),max(vals)+error))


def _modulo(a,offset=0):
    o=_dec(offset);lo=a.lo-o;hi=a.hi-o
    kl=lo.to_integral_value(rounding='ROUND_FLOOR');kh=hi.to_integral_value(rounding='ROUND_FLOOR')
    if kl!=kh:return _I(o,o+1)
    return _I((lo-kl+o).next_minus(),(hi-kh+o).next_plus())


def _exact_phase(group,time_s,unit_s,offset):
    # With no sampled/event uncertainty these raw polynomial phases have an
    # exact rational value. Prove the half-open turn before Decimal conversion.
    x=Fraction(time_s)/Fraction(unit_s)
    if group==17:a=Fraction(1,8)+x/2+x*x/8
    elif group==18:a=Fraction(1,8)-x/4
    elif group==19:a=Fraction(1,8)+x/2
    elif group==190:a=Fraction(-1,4)+3*x/4
    else:raise ValueError('unknown phase formula')
    o=Fraction(offset); p=o+(a-o)%1
    value=D(p.numerator)/D(p.denominator)
    return _I(value.next_minus(),value.next_plus())


def _phase_serialization(group,time_s,unit_s,offset,radius):
    lo=max(0.,math.nextafter(time_s-radius,-math.inf))
    hi=math.nextafter(time_s+radius,math.inf)
    a=_exact_phase(group,lo,unit_s,offset)
    b=_exact_phase(group,hi,unit_s,offset)
    center=_exact_phase(group,time_s,unit_s,offset)
    # All three phase formulas are monotone over these tiny time windows.
    # A modulo turn is discontinuous. Prove the endpoint order before using
    # a narrow hull; otherwise retain the entire half-open range closure.
    decreasing=group==18
    crosses=(a.lo>b.hi) if not decreasing else (a.hi<b.lo)
    return _I(offset,offset+1) if crosses else _hull(a,b,center)


def _event_stages(card):
    supplied=card.get('reference_event_stages')
    counts=card.get('reference_counter_stages')
    if supplied is None and counts is None:return None
    if counts is not None:
        if set(counts)!=set(card['counter_channels']):raise ValueError('incomplete validated counter stages')
        for name,value in counts.items():
            limits=card['counter_channels'][name]
            if type(value) is not int or not limits['initial']<=value<=limits['final']:
                raise ValueError('invalid validated counter stage')
    if supplied is None:
        supplied={e['id']:counts[e['counter']]>=e['index'] for e in card['events']}
    if set(supplied)!={e['id'] for e in card['events']} or any(type(v) is not bool for v in supplied.values()):
        raise ValueError('invalid validated event stages')
    stages=[supplied[e['id']] for e in card['events']]
    for counter in card['counter_channels']:
        flags=[stages[k] for k,e in enumerate(card['events']) if e['counter']==counter]
        if any(not flags[k] and flags[k+1] for k in range(len(flags)-1)):
            raise ValueError('validated event stages contradict source sequence')
    if counts is not None:
        for event,flag in zip(card['events'],stages):
            if event['counter'] not in counts or flag!=(counts[event['counter']]>=event['index']):
                raise ValueError('validated counter and event stages disagree')
    return stages


def reference(card, time_s, event_bounds):
    """Enclose analytic answers for one globally consistent event history.

    Exact derivative/modulo values are retained where defined. Probe cards do
    not receive a fabricated waveform reference. Counts belong to shared logic.
    """
    if card.get('support_probe_only'):raise NotImplementedError(card['qualification_note'])
    if not math.isfinite(time_s) or not 0<=time_s<=card['stop_s']:
        raise ValueError('reference query outside finite simulation extent')
    if set(event_bounds)!={e['id'] for e in card['events']}:
        raise ValueError('one complete global event history is required')
    with localcontext() as ctx:
        ctx.prec=80
        radius=card.get('reference_time_uncertainty_s',16*math.ulp(card['stop_s']))
        if not math.isfinite(radius) or radius<0:raise ValueError('invalid time serialization bound')
        ts=_I(max(0.,math.nextafter(time_s-radius,-math.inf)),
              min(card['stop_s'],math.nextafter(time_s+radius,math.inf)))
        T=_I(card['unit_s']);x=ts/T
        history=[]
        for e in card['events']:
            bounds=event_bounds[e['id']]
            if len(bounds)!=2:raise ValueError('callback interval must have two endpoints')
            v=_I(*bounds)
            if v.lo<_dec(e['nominal_s']-e['early_s']) or v.hi>_dec(e['nominal_s']+e['late_s']):
                raise ValueError('callback bracket outside complete legal window')
            history.append(v/T)
        # Near clocks have overlapping serialization boxes but exact ordering
        # metadata. They are processed in that frozen order; uncertainty remains.
        if any(history[i].lo>history[i+1].hi for i in range(len(history)-1)):
            raise ValueError('callback history contradicts frozen event order')
        stages=_event_stages(card)
        if stages is not None:
            for e,flag in zip(history,stages):
                if (flag and x.hi<e.lo) or (not flag and x.lo>e.hi):
                    raise ValueError('validated event stage contradicts callback history and query')
        group=int(card['group_id'][2:]);out={};point_reference={}
        if group==1:
            values=[_pwl(card,'u',history[0]*T),_i(-.25),_i(-.25),
                    _pwl(card,'u',history[3]*T),_pwl(card,'u',history[4]*T)]
            out={'q':_hold(x,history,values,-.25,stages),
                 'out':_transition(x,history,values,-.25,0,_i(.125),_i(.125),stages)}
        elif group==2:
            targets=[_i(1),_i(0),_i(1),_i(0)]
            out={'state':_hold(x,history,targets,0,stages),
                 'out':_transition(x,history,targets,0,_i(.0625),_i(.25),_i(.5),stages)}
        elif group==3:
            values=[_pwl(card,'u',t*T) for t in history]
            out={'q':_hold(x,history,values,-.25,stages),'y':.125+_held_area(x,history,values,-.25,stages)}
        elif group==4:
            e=history[0];q=2*_pwl(card,'u',e*T)+1
            out={'q':_hold(x,[e],[q],2,stages),
                 'y':_switch(x,e,lambda t:5+4*t,lambda t,r:5+4*r+q**2*_positive(t-r),None if stages is None else stages[0])}
        elif group==6:
            a=_reset_value(x,*history,.125,stages=stages);b=-.25+x
            out={'a':a,'b':b,'sum':a+b}
        elif group==7:
            out={'z':_reset_value(x,*history,.25,stages=stages),'y':.125+_reset_area(x,*history,.25,stages=stages)}
        elif group==8:
            e=history[0]
            before=lambda t:.5-.25*(-t).exp()
            out={'y':_switch(x,e,before,lambda t,r:1.5+(before(r)-1.5)*(-_positive(t-r)).exp(),None if stages is None else stages[0]),
                 'other':-.125+x}
        elif group==9:out={'z':x,'y':x**2}
        elif group==10:
            out={'y':_switch(x,history[0],lambda t:_i(1),lambda t,r:2-4/(4+_positive(t-r)),None if stages is None else stages[0])}
        elif group==11:
            ex=(-x).exp();out={'y':x-2+(x+2)*ex,'d':1-(x+1)*ex}
        elif group==12:
            # w=(x+.5)^2; X'=w-2X, X0=.125. A polynomial
            # particular X=x²/2+1/8 leaves no linear coefficient.
            out={'h':(x+.5)**2-(x**2/2+.125)}
        elif group==13:
            gain=1/(_i(1)-.2);z=gain*_pwl(card,'u',ts)
            delayed=gain*_pwl(card,'u',_positive(ts-_i(.125)*T))
            vals=[gain*_pwl(card,'u',_positive(t*T-_i(.125)*T)) for t in history]
            out={'z':z,'delayed':delayed,'q':_hold(x,history,vals,.625,stages)}
        elif group==14:
            out={n:_pwl(card,'u',_positive(ts-d*T)) for n,d in [('a',.125),('b',.5),('other',.25)]}
        elif group==15:
            a=_min(2*x,2) if x.hi<=2 else _positive(4-x)
            b=_min(x,2) if x.hi<=2 else _positive(3-.5*x)
            if x.lo<2<x.hi:
                a=_hull(a,_min(2*x,2));b=_hull(b,_min(x,2))
            out={'a':a,'b':b}
        elif group==16:
            out={'d':_i(0),'y':_i(0)} if time_s==0 else {'d':_i(1),'y':1-.5*(-x/2).exp()}
        elif group in (17,18):
            if group==17:a=.125+.5*x+.125*x**2;freq=.5+.25*x;offset=0
            else:a=.125-.25*x;freq=_i(-.25);offset=-.5
            point_reference['phase']=sum(_exact_phase(group,time_s,card['unit_s'],offset).floats())/2
            out={'freq':freq,'phase':_phase_serialization(group,time_s,card['unit_s'],offset,radius),'out':_sin_cycles(a)}
        elif group==19:
            aa=.125+.5*x;bb=-.25+.75*x;sa=_sin_cycles(aa);sb=_sin_cycles(bb)
            point_reference={'phase_a':sum(_exact_phase(19,time_s,card['unit_s'],0).floats())/2,
                             'phase_b':sum(_exact_phase(190,time_s,card['unit_s'],0).floats())/2}
            out={'phase_a':_phase_serialization(19,time_s,card['unit_s'],0,radius),'out_a':sa,
                 'phase_b':_phase_serialization(190,time_s,card['unit_s'],0,radius),'out_b':sb,'sum':sa+sb,'diff':sa-sb}
        elif group==20:
            aes=[history[i] for i,e in enumerate(card['events']) if e['counter']=='na']
            bes=[history[i] for i,e in enumerate(card['events']) if e['counter']=='nb']
            astages=None if stages is None else [stages[i] for i,e in enumerate(card['events']) if e['counter']=='na']
            bstages=None if stages is None else [stages[i] for i,e in enumerate(card['events']) if e['counter']=='nb']
            qs=[_i(k) for k in range(1,len(aes)+1)]
            out={'q':_hold(x,aes,qs,0,astages),'z':_held_area(x,aes,qs,0,astages),
                 'sample':_hold(x,bes,[_held_area(t,aes,qs,0) for t in bes],0,bstages)}
        elif group==21:
            e=history[1]
            out={'y':_switch(x,e,lambda t:1/(_i(4)/3-t),lambda t,r:1/(_i(4)/3-2*r+t),None if stages is None else stages[1])}
        else:raise ValueError('unknown composition group')
        # Input channels are graded independently by the shared stimulus logic.
        expected=set(card['outputs'])-set(card['counter_channels'])
        if set(out)!=expected:raise ValueError('reference output contract mismatch')
        # Decimal arithmetic and full query-time uncertainty are already in
        # output intervals. This independent reserve covers export/constant
        # conversion of numerical reference values, not event/window width.
        numerical=max(1e-65,8*max(math.ulp(float(v.lo)) for v in out.values()),
                      8*max(math.ulp(float(v.hi)) for v in out.values()))
        return dict(outputs={k:v.floats() for k,v in out.items()},
                    numerical_uncertainty_V=numerical,undefined={},point_reference=point_reference,time_uncertainty_included=True)
