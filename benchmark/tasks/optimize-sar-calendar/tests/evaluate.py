"""Independent SAR contract: held input, twelve bit intervals, busy/reset/valid."""
import bisect
import heapq
import math


def pwl(points,t):
    times=[p[0] for p in points]
    j=max(0,min(len(points)-2,bisect.bisect_right(times,t)-1))
    a,va=points[j];b,vb=points[j+1]
    return va+(vb-va)*(t-a)/(b-a)


def input_edges(points):
    return [(a+(.5-va)*(b-a)/(vb-va),1 if vb>va else -1)
            for (a,va),(b,vb) in zip(points,points[1:])
            if va<.5<=vb or va>=.5>vb]


def timeline(case):
    queue=[]
    for signal in ('start','reset'):
        for t,d in input_edges(case['controls'][signal]):heapq.heappush(queue,(t,signal,d,None))
    active=False;token=0;code=0;events=[];conversions=0;bits=0;cancelled=0;ignored=0
    def event(t,signal,value):events.append((t,signal,value))
    while queue:
        t,kind,d,data=heapq.heappop(queue)
        if t>case['stop']:break
        if kind=='reset' and d>0:
            cancelled+=active;active=False;token+=1;code=0
            for signal in ('busy','valid','code','dac'):event(t,signal,0.)
        elif kind=='start' and d>0:
            if active or pwl(case['controls']['reset'],t)>=.5:
                ignored+=1;continue
            active=True;token+=1
            sampled=pwl(case['controls']['vin'],t)
            # Independent ideal transfer; trace prefixes come from code bits,
            # not a copy of the implementation's trial comparison loop.
            code=min(4095,max(0,math.floor(sampled/case['vref']*4096)))
            event(t,'busy',1.);event(t,'valid',0.);event(t,'dac',.5)
            for bit in range(1,13):heapq.heappush(queue,(t+bit*case['bit_period'],'bit',bit,(token,code)))
        elif kind=='bit' and active and data[0]==token:
            bits+=1;code=data[1]
            if d<12:
                prefix=(code>>(12-d))<<(12-d)
                event(t,'dac',(prefix+(1<<(11-d)))/4096)
            else:
                active=False;conversions+=1
                event(t,'busy',0.);event(t,'valid',1.)
                event(t,'code',code/4095);event(t,'dac',code/4096)
    return sorted(events),dict(completed_conversions=conversions,bit_decisions=bits,
                               cancelled_conversions=cancelled,ignored_starts=ignored)


def interpolate(rows,times,key,t):
    j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
    a,b=rows[j],rows[j+1]
    return a[key]+(b[key]-a[key])*(t-a['time'])/(b['time']-a['time'])


def evaluate(rows,case,work=None):
    keys=['time']+case['signals']
    if len(rows)<2 or any(not math.isfinite(row[key]) for row in rows for key in keys):
        return dict(passed=False,failures=['incomplete or nonfinite waveform'])
    times=[row['time'] for row in rows]
    if any(b<=a for a,b in zip(times,times[1:])):return dict(passed=False,failures=['unordered time'])
    failures=[]
    if times[0]>1e-15 or times[-1]<case['stop']*(1-1e-8):failures.append('incomplete time coverage')
    for signal in ('start','reset'):
        expected=input_edges(case['controls'][signal]);observed=[]
        for a,b in zip(rows,rows[1:]):
            va,vb=a[signal],b[signal]
            if va<.5<=vb or va>=.5>vb:
                observed.append((a['time']+(.5-va)*(b['time']-a['time'])/(vb-va),1 if vb>va else -1))
        if len(expected)!=len(observed) or any(ed!=od or abs(et-ot)>1e-12 for (et,ed),(ot,od) in zip(expected,observed)):
            failures.append(f'{signal} stimulus edge count or timing mismatch')
    events,counts=timeline(case);max_error=0.;max_transition_error=0.;max_edge_error=0.;input_error=0.
    for t,signal,value in events:
        if signal=='busy' and value==1.:
            input_error=max(input_error,abs(interpolate(rows,times,'vin',t)-pwl(case['controls']['vin'],t)))
    for signal in ('busy','valid','code','dac'):
        changes=[];previous=0.;centers=[]
        for t,s,value in events:
            if s==signal and value!=previous:
                changes.append((t,previous,value));previous=value
        # Every prescribed transition must exist near its independent deadline;
        # midpoint-relative probes retain finite rise while permitting 1 ns polls.
        for t,old,new in changes:
            middle=(old+new)/2;left=bisect.bisect_left(times,max(0.,t-case['edge_atol']));right=bisect.bisect_right(times,t+case['edge_atol']+case['rise'])
            found=[]
            for a,b in zip(rows[left:right],rows[left+1:right+1]):
                va,vb=a[signal],b[signal]
                if (va<middle<=vb) if new>old else (va>middle>=vb):
                    found.append(a['time']+(middle-va)*(b['time']-a['time'])/(vb-va))
            if len(found)!=1:
                failures.append(f'{signal} missing/extra transition near {t:.12g}');continue
            center=found[0];centers.append((center,old,new));max_edge_error=max(max_edge_error,abs(center-(t+case['rise']/2)))
            for fraction in (.25,.75):
                probe=center+(fraction-.5)*case['rise']
                max_transition_error=max(max_transition_error,abs(interpolate(rows,times,signal,probe)-(old+fraction*(new-old))))
        # Count/deadline/direction were prescribed independently; only the
        # bounded event-time displacement is inferred from the midpoint. Rebuild
        # public fixed-width ramps from independent old/new targets, never a
        # fitted observed shape, and check every original saved point.
        center_times=[center for center,old,new in centers]
        for row in rows:
            index=bisect.bisect_right(center_times,row['time']+case['rise']/2)-1
            if index<0:
                wanted=0.
            else:
                center,old,new=centers[index]
                fraction=min(1.,max(0.,(row['time']-center+case['rise']/2)/case['rise']))
                wanted=old+(new-old)*fraction
            max_transition_error=max(max_transition_error,abs(row[signal]-wanted))
        changes_times=[t for t,_,_ in changes]
        for row in rows:
            t=row['time'];index=bisect.bisect_right(changes_times,t)-1
            near=any(abs(t-changes_times[j])<3e-9 for j in (index,index+1) if 0<=j<len(changes_times))
            if near:continue
            value=0. if index<0 else changes[index][2]
            max_error=max(max_error,abs(row[signal]-value))
    if input_error>5e-6:failures.append('sampled input stimulus mismatch')
    if max_edge_error>case['edge_atol']:failures.append('conversion bit calendar or output timing mismatch')
    if max_transition_error>case['voltage_atol']:failures.append('finite output transition mismatch')
    if max_error>case['voltage_atol']:failures.append('sample/hold, SAR trial, busy, valid or reset plateau mismatch')
    return dict(passed=not failures,failures=failures[:20],max_output_error_v=max_error,
                max_transition_error_v=max_transition_error,max_edge_error_s=max_edge_error,
                max_stimulus_error_v=input_error,saved_waveform_points=len(rows),**counts)
