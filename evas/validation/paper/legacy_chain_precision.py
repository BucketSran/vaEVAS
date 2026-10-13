"""Independent finite Q checks for the twelve original chain observations.

Actual callback times select one common history for every native output row.
Trace values are DUT observations only. References use frozen input operands,
interrupted transition polygons and analytical first-order convolution.
"""
from decimal import Decimal as D, localcontext
import math
from pathlib import Path
import re
import sys

VALIDATION = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(VALIDATION/'sample_edge_filter'), str(VALIDATION/'strobe')]
import contract as sef
import timer_composition as st
import near_timer as nt
import legacy_chain_bounds as interval_math

TIERS = {'Q1':10.1e-6, 'Q2':1.01e-6, 'Q3':101e-9}
ANALYSIS_ID = 'legacy-chain-Q-v2'
PROFILE_BINDING = {'Q1':'base', 'Q2':'both', 'Q3':'deep'}


def dec(x):
    """Exact binary64 operands, rather than a rounded decimal intent."""
    return D.from_float(x) if type(x) is float else D(x)


def pwl(points, t):
    t=dec(t)
    if t<=dec(points[0][0]):return dec(points[0][1])
    for (a,u),(b,v) in zip(points,points[1:]):
        a,b,u,v=map(dec,(a,b,u,v))
        if t<=b:return u+(v-u)*(t-a)/(b-a)
    return dec(points[-1][1])


class Polygon:
    """Replay transition interruption using prior origin/destination semantics."""
    def __init__(self, initial, callbacks, delay, rise, fall, stop):
        value=origin=target=dec(initial); slope=D(0); start=D(0)
        self.knots=[(start,value,slope)]
        for event,new in callbacks:
            activation=dec(event)+dec(delay);new=dec(new)
            if new==target:continue
            if slope:
                end=start+(target-value)/slope
                if end<=activation:
                    self.knots.append((end,target,D(0)));value=target;slope=D(0);start=end
            current=value+slope*(activation-start)
            new_origin=(origin if (new-current)*slope>0 else target) if slope else current
            new_slope=(new-new_origin)/dec(rise if new>current else fall) if new!=current else D(0)
            value=current;start=activation;origin=new_origin;target=new;slope=new_slope
            self.knots.append((start,value,slope))
        if slope:
            end=start+(target-value)/slope
            if end<dec(stop):self.knots.append((end,target,D(0)))
        self.initial=dec(initial)

    def value(self,t):
        t=dec(t)
        a,u,m=next(k for k in reversed(self.knots) if k[0]<=t)
        return u+m*(t-a)

    def filtered(self,t,tau):
        t=dec(t);tau=dec(tau);out=self.initial;old=D(0)
        for a,u,m in self.knots:
            h=t-a
            if h<0:break
            out+=(m-old)*(h-tau*(1-(-h/tau).exp()));old=m
        return out


def filtered_pwl(points,t,tau,initial=0):
    """Piecewise variation-of-constants, independent of solver histories."""
    t=dec(t);tau=dec(tau);y=dec(initial)
    for (a,u),(b,v) in zip(points,points[1:]):
        a,b,u,v=map(dec,(a,b,u,v))
        if t<=a:return y
        h=min(t,b)-a;m=(v-u)/(b-a)
        y=u+m*(h-tau)+(y-u+m*tau)*(-h/tau).exp()
        if t<=b:return y
    h=t-dec(points[-1][0]);u=dec(points[-1][1])
    return u+(y-u)*(-h/tau).exp()


def rectangles(t,initial,callbacks,scale=1,offset=0):
    t=dec(t);start=D(0);previous=dec(initial);out=dec(offset)
    for end,value in callbacks:
        end=dec(end)
        out+=previous*max(D(0),min(t,end)-start)/dec(scale)
        if t<end:return out
        start=end;previous=dec(value)
    return out+previous*max(D(0),t-start)/dec(scale)


def callback_specs(card):
    if card['kind']=='sef':
        return {p['name']:[float(t)*sef.T for t,_ in sef.callbacks(p)] for p in card['instances']}
    if card['kind']=='integral':return {'sample':card['events_s']}
    if card['kind']=='c2':return {'sample':[1.5e-6,2.5e-6,3.5e-6]}
    return {'a':[.3], 'b':[float(dec(.1)+k*dec(.2)) for k in range(5)]}


def sample_reference(card,label,t,index):
    if card['kind']=='sef':
        p=next(p for p in card['instances'] if p['name']==label)
        if p['cross'] and pwl(card['inputs']['rst'],t)>dec(.25):return dec(.25)
        return dec(p['gain'])*pwl(card['inputs']['u'],t)+dec(p['bias'])
    if card['kind']=='integral':return pwl(card['inputs']['u'],t)
    if card['kind']=='c2':return filtered_pwl(card['inputs']['vin'],t,.5e-6)
    return dec(1 if label=='a' else index)


def trace_source(card):
    """Only add read-only strobes in existing executed event bodies."""
    source=card['source']
    if card['kind']=='sef':
        for p in card['instances']:
            marker='count=count+1; end'
            log=f'count=count+1; $strobe("LEGACY_Q {p["name"]} %0d %.17g %.17g",count,$abstime,q); end'
            source=source.replace(marker,log,1)
    elif card['kind']=='integral':
        source=source.replace('n=n+1; end','n=n+1; $strobe("LEGACY_Q sample %0d %.17g %.17g",n,$abstime,q); end')
    elif card['kind']=='c2':
        # No state/counter is introduced. Index is assigned by parser in order.
        source=source.replace('else held = V(vin, vref);','else held = V(vin, vref);\n            $strobe("LEGACY_Q sample 0 %.17g %.17g",$abstime,held);')
    else:
        source=source.replace(')) a=1;', ')) begin a=1; $strobe("LEGACY_Q a 1 %.17g %.17g",$abstime,a); end')
        source=source.replace(')) b=b+1;', ')) begin b=b+1; $strobe("LEGACY_Q b %0d %.17g %.17g",b,$abstime,b); end')
    if source==card['source']:raise ValueError('trace instrumentation found no event body')
    return source


def parse_trace(text):
    records=[];counts={}
    for m in re.finditer(r'LEGACY_Q\s+(\w+)\s+(\d+)\s+(\S+)\s+(\S+)',text):
        label,index,t,value=m.groups();counts[label]=counts.get(label,0)+1
        records.append(dict(label=label,index=int(index) or counts[label],time_s=float(t),sample_V=float(value),
                            time_bounds_s=[math.nextafter(float(t),-math.inf),math.nextafter(float(t),math.inf)],origin='spectre_readonly_event_strobe'))
    return records


def evas_callbacks(card,response):
    """Read committed state changes, retaining actual observation-time boxes.

    No independent read-value trace is invented. State readback is a DUT value;
    it is checked against the frozen-input oracle below.
    """
    tr=response.get('transient',{});names=tr.get('state_names',[]);out=[];counts={}
    wanted={}
    if card['kind']=='sef':
        wanted={p['name']:(p['name']+':q',p['name']+':count') for p in card['instances']}
    elif card['kind']=='integral':wanted={'sample':('dut:q','dut:n')}
    elif card['kind']=='c2':wanted={'sample':('sampler:held',None)}
    else:wanted={'a':('dut:a',None),'b':('dut:b',None)}
    for event in tr.get('events',[]):
        before=event.get('before',[]);after=event.get('after',[])
        if len(after)!=len(names) or len(before)!=len(names):continue
        for label,(state,counter) in wanted.items():
            matching=[n for n in names if n==state or n.endswith('.'+state) or n.endswith('/'+state)]
            if len(matching)!=1:continue
            state=matching[0]
            i=names.index(state)
            changed=before[i]!=after[i]
            matching_counter=[n for n in names if counter and (n==counter or n.endswith('.'+counter) or n.endswith('/'+counter))]
            if len(matching_counter)==1:
                j=names.index(matching_counter[0]);changed=before[j]!=after[j]
            if not changed:continue
            counts[label]=counts.get(label,0)+1
            bounds=event.get('observation_time_bounds')
            if bounds is None and event.get('kind') in ('timer','held_timer'):
                # Audited schema19 event producer stores fixed timer [time,time]
                # internally and omits that point box on serialization. Adjacent
                # floats conservatively cover serialization only. Cross roots
                # require their actual supplied box; nonpoint timer boxes stay intact.
                bounds=[math.nextafter(event['time'],-math.inf),math.nextafter(event['time'],math.inf)]
            out.append(dict(label=label,index=counts[label],time_s=event['time'],sample_V=after[i],
                            time_bounds_s=bounds,origin='evas_committed_event_state',
                            event_identity=event.get('event')))
    return out


def references(card,callbacks):
    histories={label:[(c['time_s'],sample_reference(card,label,c['time_s'],c['index'])) for c in callbacks if c['label']==label]
               for label in callback_specs(card)}
    polys={}
    if card['kind']=='sef':
        polys={p['name']:Polygon(float(sef.initial(p)),histories[p['name']],p['delay']*sef.T,p['rise']*sef.T,p['fall']*sef.T,card['stop_s']) for p in card['instances']}
    elif card['kind']=='c2':polys={'sample':Polygon(.1,histories['sample'],0,25e-9,25e-9,card['stop_s'])}
    elif card['kind']=='nt' and card['chain']:
        # Stable sort retains actual log/event order for equal callback times.
        sequence=sorted(((c['time_s'],c['label'],c['index']) for c in callbacks),key=lambda r:r[0])
        a=b=0;held=[]
        for t,label,index in sequence:
            if label=='a':a=1
            else:b=index
            held.append((t,dec(.01)*a+dec(.1)*b))
        histories['chain']=held;polys={'chain':Polygon(0,held,0,.05,.05,card['stop_s'])}
    def value(t):
        out={}
        def held(label,initial):
            return next((v for s,v in reversed(histories[label]) if dec(s)<=dec(t)),dec(initial))
        def count(label):return sum(dec(s)<=dec(t) for s,v in histories[label])
        if card['kind']=='sef':
            for p in card['instances']:
                n=p['name'];out.update({n+'h':held(n,float(sef.initial(p))),n+'n':dec(count(n)),n+'e':polys[n].value(t),n+'f':polys[n].filtered(t,p['tau']*sef.T)})
        elif card['kind']=='integral':out.update(y=held('sample',.25),count=dec(count('sample')),i=rectangles(t,.25,histories['sample'],sef.T,.05))
        elif card['kind']=='c2':out.update(z=filtered_pwl(card['inputs']['vin'],t,.5e-6),vout=polys['sample'].value(t))
        else:
            a=count('a');b=count('b');out['y']=dec(a+10*b)
            if card['chain']:out.update(h=held('chain',0),e=polys['chain'].value(t),f=polys['chain'].filtered(t,.05),i=rectangles(t,0,histories['chain']))
        return out
    return value,polys


def sample_box(card,callback):
    """Independent range over one full observation box; DUT log is not reference."""
    return interval_math.sample_envelope(card,callback['label'],callback,callback['index'])


def history_bound(card,callbacks):
    """Certified integral bound, or an explicit unsupported enclosure.

    Integral difference is bounded by moving each holding discontinuity over
    its full callback width plus sampled-value uncertainty over every remaining
    rectangle. The maximum includes both held output and the integral output.
    Transition interruption topology requires a separate interval proof.
    """
    if card['kind']=='nt' and not card['chain']:
        return D(0),dict(status='proved_discrete_prefix',reason='no continuous consumer; all observations constrained by recorded callback prefixes')
    if card['kind']!='integral':
        if any(c['time_bounds_s'][1]>c['time_bounds_s'][0] for c in callbacks):
            return None,dict(status='pending',reason='transition/phase callback-box enclosure not proved',
                kind=card['kind'],no_assumed_lipschitz_constant=True)
        return D(0),dict(status='exact_callback_history',reason='all callback boxes are points')
    error=D(0);previous_low=previous_high=dec(.25);terms=[]
    for c in sorted(callbacks,key=lambda r:r['index']):
        lo,hi=map(dec,c['time_bounds_s']);width=hi-lo
        low,high=sample_box(card,c);reference=sample_reference(card,c['label'],c['time_s'],c['index'])
        variation=max(abs(reference-low),abs(high-reference))
        jump=max(abs(previous_low-low),abs(previous_low-high),abs(previous_high-low),abs(previous_high-high))
        tail=max(D(0),dec(card['stop_s'])-lo)/dec(sef.T)
        timing=jump*width/dec(sef.T);sampling=variation*max(D(1),tail)
        error+=timing+sampling
        terms.append(dict(index=c['index'],width_s=float(width),jump_upper_V=float(jump),
            remaining_area_factor=float(tail),timing_integral_bound_V=float(timing),sample_propagation_bound_V=float(sampling)))
        previous_low,previous_high=low,high
    return error,dict(status='proved_integral_rectangles',formula='sum(jump_upper*width/T + sample_range_radius*max(1,(stop-lo)/T))',terms=terms)


def nt_phase_reference(row, answers, ordered_events, minimum_prefix, discrete, ut):
    """Choose one monotone prefix of the common history, or leave it unproved."""
    candidates=[];prefixes=[];a=b=0
    for prefix in range(len(ordered_events)+1):
        done=ordered_events[:prefix];future=ordered_events[prefix:]
        if prefix>=minimum_prefix and all(c['time_bounds_s'][0]-ut<=row['time'] for c in done) and all(row['time']<=c['time_bounds_s'][1]+ut for c in future):
            candidates.append(dict(answers,y=dec(a+10*b),**({'h':dec(.01)*a+dec(.1)*b} if 'h' in discrete else {})));prefixes.append(prefix)
        if prefix<len(ordered_events):
            c=ordered_events[prefix]
            if c['label']=='a':a=1
            else:b=c['index']
    if not candidates:
        raise interval_math.BoundsPending('no monotone callback prefix at observation')
    selected=min(range(len(candidates)),key=lambda i:max(abs(dec(row[n])-candidates[i][n]) for n in discrete))
    return candidates[selected],prefixes[selected]


def _assess(card,rows,callbacks,tier):
    budget=TIERS[tier];limit=budget/100
    delta=[]
    if card['kind']=='c2' and card['event_late_s']!=4e-11:
        delta=[dict(field='event_late_s',frozen=card['event_late_s'],analysis=4e-11,reason='restore original c2 40ps contract')];card={**card,'event_late_s':4e-11}
    result=dict(status='evidence_insufficient',analysis_identity=ANALYSIS_ID,contract_delta=delta,failure_owner='protocol_fail',tier=tier,budget_V=budget,input_budget_V=limit,
                reference_budget_V=limit,callback_uncertainty_budget_V=budget/10,
                claim='finite native rows and prescribed boundaries of this source only; no whole-trajectory proof',
                source_variant=card.get('variant','original'),row_count=len(rows))
    with localcontext() as ctx:
        ctx.prec=80
        if not rows:return {**result,'reason':'missing waveform'}
        required=['time',*card['inputs'],*card['outputs']]
        if any(type(r.get(k)) not in (float,int) or not math.isfinite(r[k]) for r in rows for k in required):return {**result,'reason':'missing/nonfinite scientific observation'}
        times=[r['time'] for r in rows];ut=16*math.ulp(card['stop_s'])
        if any(b<=a for a,b in zip(times,times[1:])) or abs(times[0])>ut or abs(times[-1]-card['stop_s'])>ut:return {**result,'reason':'incomplete/unordered waveform'}
        if max((b-a for a,b in zip(times,times[1:])),default=math.inf)>card['max_gap_s']+ut:return {**result,'reason':'native observation gap'}
        errors={n:max(abs(dec(r[n])-pwl(pts,r['time'])) for r in rows) for n,pts in card['inputs'].items()}
        result['input_error_V']={n:float(e) for n,e in errors.items()}
        if any(e>dec(min(limit,card['original_input_budget_V'])) for e in errors.values()):return {**result,'status':'input_mismatch','reason':'input exceeds shared or original rule'}
        specs=callback_specs(card);ordered=[];sample_lower=sample_upper=holding_radius=D(0)
        if any(c.get('label') not in specs for c in callbacks):return {**result,'reason':'unknown callback label'}
        for label,nominals in specs.items():
            records=[c for c in callbacks if c.get('label')==label]
            if [c.get('index') for c in records]!=list(range(1,len(nominals)+1)):return {**result,'reason':'missing/duplicate callback inventory','label':label}
            for c,nominal in zip(records,nominals):
                t=c.get('time_s');bounds=c.get('time_bounds_s');sample=c.get('sample_V')
                if type(t) not in (float,int) or not math.isfinite(t) or type(sample) not in (float,int) or not math.isfinite(sample):return {**result,'reason':'invalid callback observation'}
                if bounds is None:return {**result,'reason':'callback observation-time uncertainty missing'}
                if len(bounds)!=2 or not all(type(x) in (float,int) and math.isfinite(x) for x in bounds) or not bounds[0]<=t<=bounds[1]:return {**result,'reason':'invalid callback time bounds'}
                # Original acceptance windows are independent of Q voltage tiers.
                if not nominal-card['event_early_s']-ut<=bounds[0]<=bounds[1]<=nominal+card['event_late_s']+ut:return {**result,'status':'behavior_error','reason':'callback outside original acceptance window','callback':c}
                try:low,high=sample_box(card,c)
                except interval_math.BoundsPending as exc:return {**result,'reason':'sample enclosure pending: '+str(exc)}
                sample_center=sample_reference(card,label,t,c['index'])
                holding_radius=max(holding_radius,abs(low-sample_center),abs(high-sample_center))
                value=dec(sample);rounding=dec(8*math.ulp(max(1.,abs(sample))))
                lower=max(D(0),low-value,value-high)-rounding
                upper=max(abs(value-low),abs(value-high))+rounding
                sample_lower=max(sample_lower,max(D(0),lower));sample_upper=max(sample_upper,upper)
                if sample_lower>dec(budget):return {**result,'status':'numerical_error','reason':'callback sampled value differs from independent reference','sample_error_lower_V':float(sample_lower),'sample_error_upper_V':float(sample_upper),'callback':c}
                ordered.append(c)
        # Re-establish one history in actual callback record order, including ties.
        ordered=[c for c in callbacks if c in ordered]
        uncertainty,proof=history_bound(card,ordered)
        # Continuous consumers use the independent directed enclosure below.
        # Retain the integral area derivation as an additional auditable bound.
        area_uncertainty=uncertainty if card['kind']=='integral' else None
        uncertainty=holding_radius
        result['history_enclosure']={'status':'pending','method':'independent directed Decimal80 callback replay','integral_area_proof':proof if area_uncertainty is not None else None}
        ref,polys=references(card,ordered)
        discrete=set()
        if card['kind']=='sef':discrete={p['name']+x for p in card['instances'] for x in 'hn'}
        elif card['kind']=='integral':discrete={'y','count'}
        elif card['kind']=='nt':discrete={'y','h'} if card['chain'] else {'y'}
        # Pre/post at a native callback timestamp is a single joint phase.
        # NT permits phases only in actual boxes plus original serialization ULPs.
        minimum_prefix=0
        def phase_errors(row,answers):
            nonlocal minimum_prefix
            candidates=[answers]
            if card['kind']=='nt':
                # Actual callback boxes and serialization alone govern phases.
                # Each candidate is one prefix of the common recorded history.
                ordered_events=sorted(ordered,key=lambda c:c['time_s'])
                answer,minimum_prefix=nt_phase_reference(row,answers,ordered_events,minimum_prefix,discrete,ut)
                return answer
            elif any(c['time_bounds_s'][0]-ut<=row['time']<=c['time_bounds_s'][1]+ut for c in ordered):
                previous=ref(math.nextafter(row['time'],-math.inf))
                candidates.append({**answers,**{n:previous[n] for n in discrete}})
            return min(candidates,key=lambda a:max((abs(dec(row[n])-a[n]) for n in discrete),default=D(0)))
        boundaries={0.,card['stop_s'],*[t for pts in card['inputs'].values() for t,v in pts],*[c['time_s'] for c in ordered],*[float(k[0]) for p in polys.values() for k in p.knots]}
        missing=[t for t in boundaries if 0<=t<=card['stop_s'] and min(abs(q-t) for q in times)>card['boundary_distance_s']+ut]
        if missing:return {**result,'reason':'missing key boundary neighborhood','missing_s':missing}
        missing_sides=[t for t in boundaries if ut<t<card['stop_s']-ut and (not any(0<t-q<=card['boundary_distance_s']+ut for q in times) or not any(0<q-t<=card['boundary_distance_s']+ut for q in times))]
        if missing_sides:return {**result,'reason':'missing key boundary left/right observations','missing_s':missing_sides}
        bound_reference=interval_math.prepare(card,ordered)
        maxima={};worst=None;maximum=sample_upper;minimum=sample_lower;reference_error=D(0)
        for row in rows:
            try:answers=phase_errors(row,ref(row['time']))
            except interval_math.BoundsPending as exc:
                return {**result,'reason':'callback phase enclosure pending: '+str(exc),'time_s':row['time']}
            enclosure=bound_reference(row['time'])
            if enclosure['status']!='proved':return {**result,'reason':'callback history enclosure pending: '+enclosure['reason'],'time_s':row['time']}
            reference_error=max(reference_error,enclosure['reference_error_V'])
            for node,answer in answers.items():
                actual=dec(row[node]);conversion=abs(dec(float(answer))-answer)+dec(8*math.ulp(max(1.,abs(float(answer)))))
                reference_error=max(reference_error,conversion)
                if node in enclosure['outputs']:
                    lo,hi=enclosure['outputs'][node]
                    influence=max(abs(answer-lo),abs(hi-answer))
                    uncertainty=max(uncertainty,influence)
                    error=max(abs(actual-lo),abs(actual-hi))+conversion
                    lower=max(D(0),lo-actual,actual-hi)-conversion
                else:
                    holding=(card['kind']=='sef' and node.endswith('h')) or (card['kind']=='integral' and node=='y')
                    radius=holding_radius if holding else D(0)
                    error=abs(actual-answer)+conversion+radius
                    lower=abs(actual-answer)-conversion-radius
                minimum=max(minimum,max(D(0),lower))
                maxima[node]=max(maxima.get(node,D(0)),error)
                if error>maximum:maximum=error;worst=dict(time_s=row['time'],node=node,actual_V=row[node],reference_V=float(answer))
        result['history_enclosure']['status']='proved_finite_intervals'
        if uncertainty>dec(budget/10):return {**result,'reason':'unresolved callback history influence exceeds tier bound','callback_history_uncertainty_V':float(uncertainty)}
        if reference_error>dec(limit):return {**result,'reason':'reference conversion exceeds budget'}
        result.update(status='pass' if maximum<=dec(budget) else 'numerical_error' if minimum>dec(budget) else 'evidence_insufficient',error_upper_V=float(maximum),error_lower_V=float(minimum),sample_error_upper_V=float(sample_upper),sample_error_lower_V=float(sample_lower),
                      maximum_errors_V={n:float(e) for n,e in maxima.items()},worst=worst,
                      callback_history_uncertainty_V=float(uncertainty),reference_error_V=float(reference_error),callbacks=ordered)
        return result


def assess(card,rows,callbacks,tier):
    result=_assess(card,rows,callbacks,tier)
    # This classification names the failed check, not the responsible simulator.
    # Configuration-versus-simulator attribution requires separate experiments.
    result['failure_owner']={'pass':'none','numerical_error':'numerical_error',
        'behavior_error':'behavior_error','input_mismatch':'input_mismatch',
        'evidence_insufficient':'protocol_fail'}.get(result['status'],'unresolved')
    if result['status']=='evidence_insufficient' and (not result.get('reason') or any(
            word in result['reason'] for word in ('enclosure pending','unresolved callback','reference conversion'))):
        result['failure_owner']='unresolved'
    return result


def scientific_identity(original,trace,columns):
    """Bit equality only qualifies complete matching time/column sets."""
    import struct
    pack=lambda x:struct.pack('>d',x)
    old={pack(r['time']):r for r in original};new={pack(r['time']):r for r in trace}
    common=old.keys() & new.keys();differences=[]
    for t in common:
        for n in columns:
            if n not in old[t] or n not in new[t] or pack(old[t][n])!=pack(new[t][n]):differences.append(dict(time_s=old[t]['time'],node=n))
    complete=(len(old)==len(original) and len(new)==len(trace) and old.keys()==new.keys())
    return dict(status='identical_complete_scientific_waveform' if complete and not differences else 'different' if differences else 'common_points_identical',
                complete_time_set=complete,common_points=len(common),original_points=len(original),trace_points=len(trace),differences=differences[:20],difference_count=len(differences))
