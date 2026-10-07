"""Finite development checks. References do not use either simulator's outputs."""
import math

def dynamic_reference(t, event=False):
    denominator=1+t if not event or t<=.5 else 1.5+2*(t-.5)
    z=1/denominator
    return {'z':z,'low':z-.5,'amp':10000*(z-.5),'count':int(event and t>.5)}

def check_dynamic(rows,event=False,events=None):
    failures=[];maximum={}; required=[0.,.125,.25,.5,.75,1.]
    if event:required.append(.5+1e-8)
    times=[r.get('time') for r in rows]
    finite=bool(rows) and all(isinstance(t,(int,float)) and math.isfinite(t) for t in times)
    if not finite or any(b<=a for a,b in zip(times,times[1:])):
        return {'pass':False,'failures':[{'kind':'invalid_time_observation'}]}
    missing=[t for t in required if t not in times]
    if missing:failures.append({'kind':'missing_anchor','times':missing})
    for i,r in enumerate(rows):
        t=r['time']
        if t<0 or t>1:failures.append({'kind':'outside_stop','index':i,'time':t});continue
        want=dynamic_reference(t,event)
        for n,budget in [('z',1e-7),('low',1e-7),('amp',1e-3),('count',0.)]:
            value=r.get(n)
            if not isinstance(value,(int,float)) or not math.isfinite(value):
                failures.append({'kind':'invalid_signal','signal':n,'index':i});continue
            # Count at the exact timer time is a separate same-time diagnostic.
            if n=='count' and event and abs(t-.5)<=1e-10:continue
            error=abs(value-want[n])
            if n not in maximum or error>maximum[n]['error']:maximum[n]={'error':error,'time':t,'budget':budget}
            if error>budget:failures.append({'kind':'waveform_error','signal':n,'index':i,'time':t,'error':error,'budget':budget})
    # Dense raw count observations bracket the event; never infer it by interpolating.
    count_rows=[r for r in rows if isinstance(r.get('count'),(int,float)) and math.isfinite(r['count'])]
    jumps=[{'left':a['time'],'right':b['time'],'from':a['count'],'to':b['count']} for a,b in zip(count_rows,count_rows[1:]) if a['count']!=b['count']]
    if len(jumps)!=(1 if event else 0):failures.append({'kind':'event_count','observed':len(jumps),'expected':int(event)})
    if event:
        for j in jumps:
            if j['from']!=0 or j['to']!=1 or not .5-1e-10<=j['left']<=j['right']<=.5+1e-10:
                failures.append({'kind':'event_bracket','bracket':j,'target':.5,'budget':1e-10})
    if events is not None:
        actual=[e['time'] for e in events]
        if len(actual)!=int(event) or (event and abs(actual[0]-.5)>1e-10):failures.append({'kind':'native_event_time','times':actual})
    return {'pass':not failures,'failures':failures,'maxima':maximum,'raw_count_jumps':jumps,'native_events':events,'claim':'finite development alignment; source/export qualification separate'}

def check_vco(rows,card,oracle):
    """Reuse the maintained paper oracle, report ordinary and circular phase separately.

    No interpolation, endpoint rewriting, or masking ordinary phase at wrap windows.
    Accumulated phase below is inferred from native drops and is not a native state.
    """
    failures=[];maxima={};outside=[];paired=[];wraps=[];turns=0
    centers=[t*1e-6 for t in card['event_contract'][0]['nominal_T']]
    times=[r.get('time') for r in rows]
    if not rows or any(not isinstance(t,(int,float)) or not math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        return {'pass':False,'failures':[{'kind':'invalid_time_observation'}]}
    for i,r in enumerate(rows):
        if r['time']>8e-6:outside.append(r);continue
        if not all(isinstance(r.get(k),(int,float)) and math.isfinite(r[k]) for k in ['ctl','freq','phase','out']):
            failures.append({'kind':'invalid_signal','index':i});continue
        if paired and r['phase']-paired[-1]['phase']<-.5:
            a=paired[-1];wraps.append({'left_s':a['time'],'right_s':r['time'],'left_phase':a['phase'],'right_phase':r['phase']});turns+=1
        paired.append(r);x=r['time']/1e-6;want=oracle.values(card,x,{},{});accum=oracle.vco_phase(x)
        errs={'ctl':abs(r['ctl']-want['ctl']),'freq':abs(r['freq']-want['freq']),'phase_ordinary':abs(r['phase']-want['phase']),'phase_circular':abs((r['phase']-want['phase']+.5)%1-.5),'phase_accumulated_from_drops':abs(r['phase']+turns-accum),'sine':abs(r['out']-want['out'])}
        for n,e in errs.items():
            budget={'ctl':1e-5,'freq':1e-3,'phase_ordinary':1e-3,'phase_circular':1e-3,'phase_accumulated_from_drops':1e-3,'sine':3e-3}[n]
            if n not in maxima or e>maxima[n]['error']:maxima[n]={'error':e,'time_s':r['time'],'budget':budget}
            if e>budget:failures.append({'kind':'waveform_error','signal':n,'index':i,'time_s':r['time'],'error':e,'budget':budget,'within_wrap_window':any(abs(r['time']-t)<=1e-10 for t in centers)})
        if not 0<=r['phase']<1:failures.append({'kind':'phase_range','index':i,'value':r['phase']})
    if len(wraps)!=4:failures.append({'kind':'wrap_count','observed':len(wraps),'expected':4})
    for j,t in zip(wraps,centers):
        j['nominal_s']=t;j['budget_s']=1e-10
        if not t-1e-10<=j['left_s']<=j['right_s']<=t+1e-10:failures.append({'kind':'wrap_bracket','bracket':j})
    if not paired or paired[0]['time']!=0:failures.append({'kind':'missing_initial'})
    return {'pass':not failures,'failures':failures,'maxima':maxima,'raw_wrap_brackets':wraps,'outside_original_stop_rows':outside,'count_within_original_stop':len(paired),'claim':'development alignment; decimal-source oracle and compiled-binary64 exact certificate remain distinct; stop/export qualification separate'}
