"""Voltage-supervisor oracle, derived from PWL threshold crossing intervals."""
import bisect
import heapq
import math


def expected_edges(case):
    queue=[]
    controls=case['controls']
    on=case['on_voltage'];off=case['off_voltage'];qualify=case['qualification']
    for (a,va),(b,vb) in zip(controls,controls[1:]):
        if va==vb:
            continue
        for threshold,kind in ((on,'on_up' if vb>va else 'on_down'),(off,'off_down')):
            if kind=='off_down' and vb>va:
                continue
            if min(va,vb)<threshold<max(va,vb):
                t=a+(threshold-va)*(b-a)/(vb-va)
                heapq.heappush(queue,(t,kind))
    enabled=False;deadline=None;edges=[]
    if controls[0][1]>=on:
        deadline=qualify
        heapq.heappush(queue,(deadline,'due'))
    while queue:
        t,kind=heapq.heappop(queue)
        if t>case['stop']:
            break
        if kind=='on_up' and not enabled:
            deadline=t+qualify
            heapq.heappush(queue,(deadline,'due'))
        elif kind=='on_down' and not enabled:
            deadline=None
        elif kind=='off_down':
            if enabled:
                edges.append((t,-1))
            enabled=False;deadline=None
        elif kind=='due' and deadline==t:
            enabled=True;deadline=None;edges.append((t,+1))
    return edges


def evaluate(rows, case, work=None):
    if len(rows)<2 or any(not math.isfinite(row[k]) for row in rows for k in ('time','supply','enable')):
        return dict(passed=False,failures=['incomplete or nonfinite waveform'])
    times=[r['time'] for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])):
        return dict(passed=False,failures=['unordered time'])
    failures=[]
    if times[0]>1e-15 or times[-1]<case['stop']*(1-1e-8):
        failures.append('incomplete time coverage')
    observed=[]
    for a,b in zip(rows,rows[1:]):
        va=a['enable'];vb=b['enable']
        if va<.5<=vb or va>=.5>vb:
            t=a['time']+(.5-va)*(b['time']-a['time'])/(vb-va)
            observed.append((t,1 if vb>va else -1))
    expected=expected_edges(case)
    if len(observed)!=len(expected):
        failures.append('wrong enable edge count')
    elif any(d!=ed or abs(t-et)>case['edge_atol'] for (t,d),(et,ed) in zip(observed,expected)):
        failures.append('qualification delay, hysteresis or disable timing mismatch')
    # Check every saved point outside a 3 ns edge neighborhood. The tolerance
    # covers the baseline 1 ns poll quantization and the public output transition.
    max_error=0.
    for row in rows:
        t=row['time']
        if any(abs(t-et)<3e-9 for et,_ in expected):
            continue
        value=0
        for et,d in expected:
            if et<t:
                value=1 if d>0 else 0
        max_error=max(max_error,abs(row['enable']-value))
    if max_error>case['voltage_atol']:
        failures.append('incorrect enable plateau')
    return dict(passed=not failures,failures=failures,expected_edges=expected,
                observed_edges=observed,max_plateau_error_v=max_error,saved_waveform_points=len(rows))
