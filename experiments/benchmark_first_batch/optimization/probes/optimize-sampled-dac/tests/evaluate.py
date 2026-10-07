"""DAC oracle from binary counter stimulus and sampled voltage reconstruction."""
import bisect
import math


def interpolate(rows,times,key,t):
    j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
    a,b=rows[j],rows[j+1]
    return a[key]+(b[key]-a[key])*(t-a['time'])/(b['time']-a['time'])


def evaluate(rows,case,work=None):
    keys=case['signals']+['time']
    if len(rows)<2 or any(not math.isfinite(row[key]) for row in rows for key in keys):
        return dict(passed=False,failures=['incomplete or nonfinite waveform'])
    times=[r['time'] for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])):
        return dict(passed=False,failures=['unordered time'])
    failures=[]
    if times[0]>1e-15 or times[-1]<case['stop']*(1-1e-8):
        failures.append('incomplete time coverage')
    observed_edges=[]
    for a,b in zip(rows,rows[1:]):
        if a['clock']<.5<=b['clock']:
            observed_edges.append(a['time']+(.5-a['clock'])*(b['time']-a['time'])/(b['clock']-a['clock']))
    expected_edges=[];t=case['first_cross']
    while t<case['stop']:
        expected_edges.append(t);t+=case['period']
    if len(observed_edges)!=len(expected_edges) or any(abs(a-b)>1e-12 for a,b in zip(observed_edges,expected_edges)):
        failures.append('clock edge count or timing mismatch')
    max_error=abs(interpolate(rows,times,'out',.5e-9)-case['offset'])
    bus_errors=0
    previous=case['offset']
    for sample_index,t in enumerate(expected_edges):
        integer=sample_index%4096
        for bit in range(12):
            actual=interpolate(rows,times,'b'+str(bit),t)>.5
            bus_errors+=actual!=bool(integer & (1<<bit))
        value=case['offset']+case['vref']*integer/4095
        for dt in (2e-9,8e-9):
            if t+dt<=case['stop']:
                max_error=max(max_error,abs(interpolate(rows,times,'out',t+dt)-value))
        if t>.5e-9:
            max_error=max(max_error,abs(interpolate(rows,times,'out',t-.5e-9)-previous))
        previous=value
    if bus_errors:
        failures.append('actual stimulus did not exercise expected binary codes')
    if max_error>case['atol']:
        failures.append('sampled weighted reconstruction, endpoint scale or hold mismatch')
    return dict(passed=not failures,failures=failures,max_output_error_v=max_error,
                expected_samples=len(expected_edges),bus_bit_errors=bus_errors,
                observed_clock_edges=len(observed_edges),saved_waveform_points=len(rows))
