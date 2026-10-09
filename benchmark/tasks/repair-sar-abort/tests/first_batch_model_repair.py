"""Independent event/trajectory contracts for first-batch model and repair tasks.

No reference Verilog-A is imported or executed to compute expected behavior.
"""
import bisect
import math


def interpolate(rows,node,t):
    ts=[r['time'] for r in rows]
    j=max(0,min(len(rows)-2,bisect.bisect_right(ts,t)-1))
    a,b=rows[j],rows[j+1]
    return a[node] if a['time']==b['time'] else a[node]+(b[node]-a[node])*(t-a['time'])/(b['time']-a['time'])


def crossings(rows,node,threshold=.5):
    found=[]
    for a,b in zip(rows,rows[1:]):
        if a[node]<threshold<=b[node] or a[node]>=threshold>b[node]:
            if b[node]!=a[node]:found.append(a['time']+(b['time']-a['time'])*(threshold-a[node])/(b[node]-a[node]))
    return found


def comparator_targets(case):
    targets={n:[(0.,0.)] for n in ['outp','outn','ready']}
    resets=case['resets']
    for e in case['events']:
        delay=case['tbase']+case['tau']*math.log1p(case['vscale']/(abs(e['differential'])+case['vfloor']))
        # Reset release cannot rearm the sampled decision. The first reset
        # assertion after the sampling edge either cancels it or clears it.
        clear_at=min([e['fall']]+[t for t,v in resets if v and e['rise']<t<e['fall']])
        if level_at(0,resets,e['rise'])<.5 and e['differential']!=0 and e['rise']+delay<clear_at:
            for n,value in [('outp',float(e['differential']>0)),('outn',float(e['differential']<0)),('ready',1.)]:
                if value:targets[n]+=[(e['rise']+delay,value),(clear_at,0.)]
    return targets


def evaluate_logic(rows,case,targets):
    failures=[];total=0;worst=0.;counts={}
    for node,events in targets.items():
        clean=[events[0]]
        for t,v in sorted(events[1:]):
            if v!=clean[-1][1]:clean.append((t,v))
        times=[t for t,v in clean];edge_expected=[t+case['tr']/2 for t,v in clean[1:]]
        observed=crossings(rows,node);counts[node]={'expected':len(edge_expected),'observed':len(observed)}
        if node in case.get('analog_nodes',[]):pass
        elif len(observed)!=len(edge_expected):failures.append({'kind':'edge_count','node':node,**counts[node]})
        elif node not in case.get('analog_nodes',[]):
            for index,(a,b) in enumerate(zip(observed,edge_expected)):
                if abs(a-b)>case['edge_atol']:failures.append({'kind':'edge_time','node':node,'index':index,'expected':b,'observed':a})
        # Full waveform stable samples exclude only declared output transition windows.
        for r in rows:
            t=r['time']
            if any(abs(t-x)<=case['tr']+case['edge_atol'] for x in times[1:]):continue
            expected=clean[max(0,bisect.bisect_right(times,t)-1)][1]
            error=abs(r[node]-expected);worst=max(worst,error);total+=1
            if error>case['atol'] and len(failures)<30:failures.append({'kind':'stable_voltage','node':node,'time':t,'expected':expected,'observed':r[node]})
    return {'passed':not failures,'failures':failures,'stable_samples':total,'worst_voltage_error':worst,'edges':counts}



def level_at(initial,events,t):
    value=initial
    for et,v in events:
        if et>t:break
        value=v
    return value


def bbpd_targets(case):
    targets={n:[(0.,0.)] for n in ['up','down']}
    for t,tag in sorted([(t,'clock') for t,v in case['clock']]+[(t,'data') for t,v in case['data']]):
        u=d=0.
        if tag=='data':
            clk=level_at(0,case['clock'],t);ret=level_at(0,case['retimed'],t)
            u=float(clk>.5 and ret<.5);d=float(clk<.5 and ret>.5)
        targets['up'].append((t,u));targets['down'].append((t,d))
    return targets


def sigma_targets(case):
    from fractions import Fraction
    incoming=Fraction(0);old_bit=0;events=[(0.,0.)]
    for i in range(case['block_cycles']*len(case['levels'])):
        incoming+=Fraction(case['levels'][i//case['block_cycles']])-old_bit
        new_bit=int(incoming>=0)
        if new_bit!=old_bit:events.append(((i+1)*case['period'],float(new_bit)))
        old_bit=new_bit
    return {'bitout':events}


def hold_value(case,t):
    y=case['vinit'];done=0.
    actions=sorted([(a,'start',b,u) for a,b,u in case['windows']]+[(a,'reset',b,0) for a,b in case['resets']])
    for start,kind,end,u in actions:
        if t<start:break
        if kind=='reset':y=case['vinit'];done=end
        else:
            duration=max(0.,min(t,end)-start)
            y=u+(y-u)*math.exp(-duration/case['tau']);done=end
        if t<=end:break
    return y


def evaluate_hold(rows,case):
    failures=[];worst=0;count=0
    for r in rows:
        if any(abs(r['time']-a)<80e-12 for a,b in case['resets']):continue
        expected=hold_value(case,r['time']);error=abs(r['vout']-expected);worst=max(worst,error);count+=1
        if error>case['atol'] and len(failures)<25:failures.append({'kind':'acquisition_hold_reset','time':r['time'],'expected':expected,'observed':r['vout']})
    return {'passed':not failures,'failures':failures,'worst_voltage_error':worst,'samples':count}


def pwl_value(points,t):
    if t<=points[0][0]:return points[0][1]
    for (a,va),(b,vb) in zip(points,points[1:]):
        if t<=b:return va+(vb-va)*(t-a)/(b-a)
    return points[-1][1]


def uvlo_targets(case):
    import heapq
    queue=[];token=0;up_token=down_token=None;good=0;reset=0
    targets={'pgood':[(0.,0.)],'fault':[(0.,1.)]}
    for threshold,label in [(case['upper'],'upper'),(case['lower'],'lower')]:
        for (a,va),(b,vb) in zip(case['supply'],case['supply'][1:]):
            if va<threshold<=vb or va>=threshold>vb:
                t=a+(b-a)*(threshold-va)/(vb-va)
                heapq.heappush(queue,(t,label+'_rise' if vb>va else label+'_fall',0))
    for t,v in case['resets']:heapq.heappush(queue,(t,'reset_rise' if v else 'reset_fall',0))
    def arm(t,direction):
        nonlocal token,up_token,down_token
        token+=1
        if direction=='up':up_token=token;deadline=t+case['tgood']
        else:down_token=token;deadline=t+case['tbad']
        heapq.heappush(queue,(deadline,direction,token))
    if case['supply'][0][1]>case['upper']:arm(0,'up')
    while queue:
        t,tag,identity=heapq.heappop(queue)
        if t>case['stop']:break
        previous=good
        if tag=='reset_rise':reset=1;good=0;up_token=down_token=None
        elif tag=='reset_fall':
            reset=0
            if pwl_value(case['supply'],t)>case['upper']:arm(t,'up')
        elif tag=='upper_rise' and not reset and not good:arm(t,'up')
        elif tag=='upper_fall':up_token=None
        elif tag=='lower_fall' and not reset and good:arm(t,'down')
        elif tag=='lower_rise':down_token=None
        elif tag=='up' and identity==up_token and not reset:good=1;up_token=None
        elif tag=='down' and identity==down_token and not reset:good=0;down_token=None
        if good!=previous:targets['pgood'].append((t,float(good)));targets['fault'].append((t,float(1-good)))
    return targets


def sar_targets(case):
    import heapq
    queue=[(t,'clk') for t,v in case['clock'] if v]+[(t,'start') for t,v in case['starts'] if v]+[(t,'reset') for t,v in case['resets'] if v]
    heapq.heapify(queue);generation=0;active=False;pending=False;working=result=0;position=3;trial=0.
    targets={n:[(0.,0.)] for n in ['d3','d2','d1','d0','trial','busy','valid']}
    def emit(t,node,value):
        if targets[node][-1][1]!=value:targets[node].append((t,float(value)))
    while queue:
        t,tag=heapq.heappop(queue)
        reset=level_at(0,case['resets'],t)>.5
        if tag=='reset':
            generation+=1;active=False;pending=False;working=result=0;trial=0.
            for node in targets:emit(t,node,0)
        elif tag=='start' and not reset and not active:
            generation+=1;active=True;pending=False;working=result=0;position=3;trial=.5
            for node in ['d3','d2','d1','d0','valid']:emit(t,node,0)
            emit(t,'busy',1);emit(t,'trial',trial)
        elif tag=='clk' and active and not pending and not reset:
            # Independent SAR decisions use the specified physical comparator truth.
            vin=pwl_value(case['vin'],t)
            weight=2**position
            if vin>=trial:working+=weight
            if position==0:
                pending=True;trial=working/16
                heapq.heappush(queue,(t+case['tvalid'],'publish:'+str(generation)))
            else:position-=1;trial=(working+2**position)/16
            emit(t,'trial',trial)
        elif tag.startswith('publish:') and int(tag.split(':')[1])==generation and active and pending and not reset:
            result=working;active=False;pending=False
            emit(t,'busy',0);emit(t,'valid',1)
            for bit in range(4):emit(t,'d'+str(bit),(result>>bit)&1)
    return targets


def zoom_targets(case):
    targets={n:[(0.,float(n=='rst'))] for n in case['signals']}
    finish=2.4e-9+case['nbits']*case['step']
    windows={'rst':[(0,.6e-9)],'sample':[(1e-9,2e-9)],'sar':[(2.4e-9,finish)],'residue':[(finish+.2e-9,finish+.7e-9)],'integrate':[(finish+1e-9,finish+2e-9)],'rst_zoom':[(finish+2.1e-9,finish+2.3e-9)],'zoom':[(finish+2.5e-9,finish+5.5e-9)],'clk_sar':[(2.4e-9+j*case['step'],2.7e-9+j*case['step']) for j in range(case['nbits'])],'clk_zoom':[(finish+2.5e-9+j*case['step'],finish+2.8e-9+j*case['step']) for j in range(3)]}
    for cycle in range(math.ceil(case['stop']/case['frame'])):
        base=cycle*case['frame']
        for node,spans in windows.items():
            for start,end in spans:
                for t,value in [(base+start,1.),(base+end,0.)]:
                    if 0<t<=case['stop']:targets[node].append((t,value))
    return targets


def evaluate(rows,case,work=None):
    if len(rows)<2 or any(not math.isfinite(v) for r in rows for v in r.values()):
        return {'passed':False,'failures':['invalid_waveform']}
    kind=case['kind']
    if kind=='sample_hold':return evaluate_hold(rows,case)
    independent_targets={'latched_comparator':comparator_targets,'bbpd':bbpd_targets,'sigma_delta':sigma_targets,'uvlo':uvlo_targets,'sar':sar_targets,'zoom':zoom_targets}
    if kind not in independent_targets:raise ValueError('unsupported model/repair contract: '+kind)
    return evaluate_logic(rows,case,independent_targets[kind](case))
