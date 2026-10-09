"""Independent rational references for new finite layered alignment cases."""
from fractions import Fraction as F
import math,hashlib,json

BUDGETS={'samplevalue':1e-3,'count':0.,'x':1e-5,'ctl':1e-5,'freq':1e-3,'accum':1e-3,'phase_ordinary':1e-3,'phase_circular':1e-3,'sine':3e-3}

def reference(card,t):
    t=F.from_float(t);q=F(card['ic']);freq=None
    for s in card['segments']:
        l,r,a,b=(F(s[k]) for k in ['left','right','frequency_left_cycles_per_s','slope_cycles_per_s2'])
        d=max(F(0),min(t,r)-l);q+=a*d+b*d*d/2
        if l<=t<=r:freq=(a+b*(t-l))/2**20
    phase=q%1
    ctl=F(0)
    if card['layer']!='constant':
        points=[(F.from_float(x),F.from_float(v)) for x,v in card['pwl']]
        for (l,v),(r,w) in zip(points,points[1:]):
            if l<=t<=r:ctl=v+(w-v)*(t-l)/(r-l);break
    return dict(ctl=float(ctl),freq=float(freq),accum=float(q),phase=float(phase),out=math.sin(2*math.pi*float(phase)),exact_phase=str(phase),exact_accum=str(q))

def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def valid(rows):
    return bool(rows) and all(finite(r.get('time')) for r in rows) and all(b['time']>a['time'] for a,b in zip(rows,rows[1:]))

def check_layer(rows,card,required_times):
    failures=[];maxima={};wraps=[];outside=[]
    if not valid(rows):return dict(pass_=False,failures=[dict(kind='invalid_times')])
    times={r['time'] for r in rows};missing=[t for t in required_times if t not in times]
    if missing:failures.append(dict(kind='missing_anchors',times=missing))
    stop=float(F(card['segments'][-1]['right']))
    for i,row in enumerate(rows):
        t=row['time']
        if not 0<=t<=stop:outside.append(row);failures.append(dict(kind='outside_stop',index=i,time=t));continue
        wanted=reference(card,t)
        for signal in ['ctl','freq','phase_ordinary','phase_circular','sine']+(['accum'] if card['observer'] else []):
            port='phase' if signal.startswith('phase') else 'out' if signal=='sine' else signal
            v=row.get(port)
            if not finite(v):failures.append(dict(kind='invalid_signal',index=i,signal=signal));continue
            error=abs(v-wanted[port]);error=abs((v-wanted[port]+.5)%1-.5) if signal=='phase_circular' else error
            record=dict(error=error,budget=BUDGETS[signal],time=t,actual=v,reference=wanted[port],exact_accum=wanted['exact_accum'],exact_phase=wanted['exact_phase'])
            if signal not in maxima or error>maxima[signal]['error']:maxima[signal]=record
            if error>BUDGETS[signal]:failures.append(dict(kind='waveform_error',index=i,signal=signal,**record))
        if not isinstance(row.get('phase'),(int,float)):continue
        if not 0<=row['phase']<1:failures.append(dict(kind='phase_range',index=i,actual=row['phase']))
        if i and isinstance(rows[i-1].get('phase'),(int,float)) and row['phase']-rows[i-1]['phase']<-.5:wraps.append(dict(left=rows[i-1]['time'],right=t,left_phase=rows[i-1]['phase'],right_phase=row['phase']))
    if len(wraps)!=len(card['roots_decimal']):failures.append(dict(kind='wrap_count',actual=len(wraps),expected=len(card['roots_decimal'])))
    for w,root in zip(wraps,card['roots_decimal']):
        nominal=float(root);w.update(root_decimal=root,time_budget_s=1e-10)
        if not nominal-1e-10<=w['left']<=w['right']<=nominal+1e-10:failures.append(dict(kind='wrap_bracket',**w))
    return dict(pass_=not failures,failures=failures,maxima=maxima,wraps=wraps,missing_anchors=missing,outside_stop_rows=outside,original_denominator=len(rows))

def observer_compare(off,on,required_times,signals):
    failures=[];maximum={};side_changes=[]
    for label,rows in [('off',off),('on',on)]:
        if not valid(rows):failures.append(dict(kind='invalid_times',side=label))
        for i,row in enumerate(rows):
            for signal in signals:
                if not finite(row.get(signal)):failures.append(dict(kind='invalid_signal',side=label,index=i,signal=signal))
    if failures:return dict(pass_=False,maxima=maximum,failures=failures,ordinary_side_changes=side_changes,native_grid_equal=False,off_rows=len(off),on_rows=len(on))
    if not all(finite(t) for t in required_times):return dict(pass_=False,maxima={},failures=[dict(kind='invalid_required_times')],ordinary_side_changes=[],native_grid_equal=False,off_rows=len(off),on_rows=len(on))
    a={r['time']:r for r in off};b={r['time']:r for r in on};missing=[]
    for t in required_times:
        if t not in a or t not in b:missing.append(t);continue
        for signal in signals:
            error=abs(a[t][signal]-b[t][signal]);budget=BUDGETS['phase_ordinary' if signal=='phase' else 'sine' if signal=='out' else signal]
            if signal not in maximum or error>maximum[signal]['error']:maximum[signal]=dict(time=t,error=error,budget=budget,off=a[t][signal],on=b[t][signal])
            if error>budget:failures.append(dict(kind='observer_effect',time=t,signal=signal,error=error,budget=budget))
            if signal=='phase' and (a[t][signal]<.5)!=(b[t][signal]<.5):side_changes.append(dict(time=t,off=a[t][signal],on=b[t][signal]))
    if missing:failures.append(dict(kind='missing_common_anchors',times=missing))
    grid_equal=[r['time'] for r in off]==[r['time'] for r in on]
    if not grid_equal:failures.append(dict(kind='native_grid_changed'))
    return dict(pass_=not failures,maxima=maximum,failures=failures,ordinary_side_changes=side_changes,native_grid_equal=grid_equal,off_rows=len(off),on_rows=len(on),required_time_count=len(required_times),compared_time_count=sum(t in a and t in b for t in required_times),compared_signal_count=len(signals),compared_times_sha256=hashlib.sha256(json.dumps([t for t in required_times if t in a and t in b],separators=(',',':')).encode()).hexdigest(),claim='independent idt observer is not modulo internal state')

def check_event(rows,card,required_times,native_events=None,*,projection=False):
    failures=[];jumps=[];latched=[]
    # This checker accepts only an explicit observation contract, never inferred columns.
    if not isinstance(card,dict):return dict(pass_=False,failures=[dict(kind='invalid_event_contract',fields=['card'])])
    ports=card.get('ports');bad=[]
    if not isinstance(ports,list) or not all(isinstance(p,str) for p in ports) or len(ports)!=len(set(ports)) or not {'x','samplevalue','count'}<=set(ports) or not set(ports)<={'x','samplevalue','count','firedtime'}:bad.append('ports')
    for key in ['math_root_s','allowed_delay_s','ramp_slope_V_per_s']:
        if not finite(card.get(key)):bad.append(key)
    if not bad and (card['ramp_slope_V_per_s']<=0 or card['allowed_delay_s']<0 or not 0<=card['math_root_s']<=1/card['ramp_slope_V_per_s']):bad.append('event_domain')
    if bad:return dict(pass_=False,failures=[dict(kind='invalid_event_contract',fields=bad)])
    root=card['math_root_s'];allowed=card['allowed_delay_s'];slope=card['ramp_slope_V_per_s'];stop=1/slope
    if not valid(rows):return dict(pass_=False,failures=[dict(kind='invalid_times')])
    times=[r['time'] for r in rows];missing=[t for t in required_times if t not in times]
    if missing:failures.append(dict(kind='missing_anchors',times=missing))
    expects_time=not projection and 'firedtime' in ports
    required=['x','samplevalue','count']+(['firedtime'] if expects_time else [])
    for i,r in enumerate(rows):
        invalid=[signal for signal in required if not finite(r.get(signal))]
        for signal in invalid:failures.append(dict(kind='invalid_signal',index=i,signal=signal))
        if not 0<=r['time']<=stop:failures.append(dict(kind='outside_stop',index=i,time=r['time']))
        if finite(r.get('x')) and abs(r['x']-slope*r['time'])>1e-5:failures.append(dict(kind='ramp_error',index=i,actual=r['x'],reference=slope*r['time'],budget=1e-5))
        count=r.get('count')
        if not finite(count) or count not in [0,1]:failures.append(dict(kind='count_value',index=i,actual=count));continue
        if i and count!=rows[i-1].get('count'):jumps.append(dict(left=rows[i-1]['time'],right=r['time'],before=rows[i-1].get('count'),after=count))
        if count==1 and r['time']<root-1e-15:failures.append(dict(kind='early_event_read',index=i,time=r['time'],root=root))
        if count==0 and r['time']>root+min(allowed,1e-10)+1e-15:failures.append(dict(kind='late_event_read',index=i,time=r['time'],root=root,time_budget_s=1e-10,allowed_delay_s=allowed))
        sample=r.get('samplevalue');sample_target=-1. if count==0 else .375
        if finite(sample) and abs(sample-sample_target)>1e-3:failures.append(dict(kind='physical_samplevalue',index=i,actual=sample,root_sample=sample_target,budget=1e-3))
        if expects_time and finite(r.get('firedtime')):
            fired=r['firedtime']
            if count==0:
                if abs(fired+1)>1e-10:failures.append(dict(kind='initial_firedtime',index=i,actual=fired,reference=-1.,budget=1e-10))
            else:
                if fired>r['time']+1e-15:failures.append(dict(kind='future_callback_at_read',index=i,read_time=r['time'],stored_callback_abstime=fired))
                latched.append(dict(read_time=r['time'],stored_callback_abstime=fired,math_root=root,delay=fired-root,samplevalue=sample,math_root_sample=.375,callback_time_sample=fired*slope))
                if abs(fired-root)>1e-10:failures.append(dict(kind='physical_event_time',index=i,actual=fired,root=root,budget=1e-10))
                if not root-1e-15<=fired<=root+allowed+1e-15:failures.append(dict(kind='allowed_event_window',index=i,actual=fired,root=root,allowed_delay=allowed))
                if finite(sample) and abs(sample-fired*slope)>1e-5:failures.append(dict(kind='callback_time_sample_inconsistent',index=i,actual=sample))
        elif expects_time:failures.append(dict(kind='invalid_signal',index=i,signal='firedtime'))
    if rows[0].get('count')!=0:failures.append(dict(kind='initial_count',actual=rows[0].get('count')))
    if len(jumps)!=1 or jumps[0]['before']!=0 or jumps[0]['after']!=1:failures.append(dict(kind='event_count',jumps=jumps))
    if rows[-1].get('count')!=1:failures.append(dict(kind='missing_event'))
    if native_events is not None:
        if len(native_events)!=1:failures.append(dict(kind='native_event_count',actual=len(native_events)))
        for e in native_events:
            if not finite(e.get('time')):failures.append(dict(kind='invalid_native_event_time'));continue
            if abs(e['time']-root)>1e-10:failures.append(dict(kind='native_nominal_event_time',actual=e['time'],root=root))
            if 'observation_time_bounds' in e:
                bounds=e['observation_time_bounds']
                if not isinstance(bounds,list) or len(bounds)!=2 or not all(finite(t) for t in bounds) or bounds[1]<bounds[0]:failures.append(dict(kind='invalid_observation_time_bounds'))
    return dict(pass_=not failures,failures=failures,latched_observations=latched,count_jumps=jumps,native_events=native_events,missing_anchors=missing,original_denominator=len(rows),required_signals=required,projection=projection,native_event_semantics='EVAS nominal/representative event point and mathematical-root read; not Spectre callback abstime',claim='math root, stored callback abstime and read sample remain separate; projection lacks actual $abstime field')
