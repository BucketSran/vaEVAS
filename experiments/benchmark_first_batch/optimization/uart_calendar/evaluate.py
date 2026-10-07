"""Independent UART contract: start qualification, serial samples, stop and reset."""
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
    for signal in ('rx','reset'):
        for t,d in input_edges(case['controls'][signal]):heapq.heappush(queue,(t,signal,d,None))
    active=False;token=0;partial=0;events=[];good=0;framing=0;bits=0;false_starts=0;cancelled=0
    def event(t,signal,value):events.append((t,signal,value))
    while queue:
        t,kind,index,data=heapq.heappop(queue)
        if t>case['stop']:break
        if kind=='reset' and index>0:
            cancelled+=active;active=False;token+=1;partial=0
            for signal in ('busy','valid','error','data','shift'):event(t,signal,0.)
        elif kind=='rx' and index<0 and not active and pwl(case['controls']['reset'],t)<.5:
            active=True;token+=1;partial=0
            event(t,'busy',1.)
            for signal in ('valid','error','shift'):event(t,signal,0.)
            heapq.heappush(queue,(t+.5*case['bit_period'],'sample',-1,token))
        elif kind=='sample' and active and data==token:
            level=pwl(case['controls']['rx'],t)>=.5
            if index==-1:
                if level:
                    active=False;false_starts+=1;event(t,'busy',0.)
                else:heapq.heappush(queue,(t+case['bit_period'],'sample',0,token))
            elif index<8:
                bits+=1
                # Serial transfer reads the prescribed wire at bit centers.
                partial|=int(level)<<index;event(t,'shift',partial/255)
                heapq.heappush(queue,(t+case['bit_period'],'sample',index+1,token))
            else:
                active=False;event(t,'busy',0.)
                if level:
                    good+=1;event(t,'data',partial/255);event(t,'valid',1.)
                else:framing+=1;event(t,'error',1.)
    return sorted(events),dict(valid_frames=good,framing_errors=framing,bit_samples=bits,
                               false_starts=false_starts,cancelled_frames=cancelled)


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
    for signal in ('rx','reset'):
        expected=input_edges(case['controls'][signal]);observed=[]
        for a,b in zip(rows,rows[1:]):
            va,vb=a[signal],b[signal]
            if va<.5<=vb or va>=.5>vb:
                observed.append((a['time']+(.5-va)*(b['time']-a['time'])/(vb-va),1 if vb>va else -1))
        if len(expected)!=len(observed) or any(ed!=od or abs(et-ot)>1e-12 for (et,ed),(ot,od) in zip(expected,observed)):
            failures.append(f'{signal} stimulus edge count or timing mismatch')
    events,counts=timeline(case);max_error=0.;max_transition_error=0.;max_edge_error=0.;input_error=0.
    for signal in ('busy','valid','error','data','shift'):
        changes=[];previous=0.
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
            center=found[0];max_edge_error=max(max_edge_error,abs(center-(t+case['rise']/2)))
            for fraction in (.25,.75):
                probe=center+(fraction-.5)*case['rise']
                max_transition_error=max(max_transition_error,abs(interpolate(rows,times,signal,probe)-(old+fraction*(new-old))))
        changes_times=[t for t,_,_ in changes]
        for row in rows:
            t=row['time'];index=bisect.bisect_right(changes_times,t)-1
            near=any(abs(t-changes_times[j])<case['exclusion'] for j in (index,index+1) if 0<=j<len(changes_times))
            if near:continue
            value=0. if index<0 else changes[index][2]
            max_error=max(max_error,abs(row[signal]-value))
    if max_edge_error>case['edge_atol']:failures.append('serial sample calendar or output timing mismatch')
    if max_transition_error>case['voltage_atol']:failures.append('finite output transition mismatch')
    if max_error>case['voltage_atol']:failures.append('serial data, shift history, framing, busy, valid or reset plateau mismatch')
    return dict(passed=not failures,failures=failures[:20],max_output_error_v=max_error,
                max_transition_error_v=max_transition_error,max_edge_error_s=max_edge_error,
                max_stimulus_error_v=input_error,saved_waveform_points=len(rows),**counts)
