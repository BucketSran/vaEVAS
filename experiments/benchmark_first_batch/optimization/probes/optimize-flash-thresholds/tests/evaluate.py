"""Flash ADC oracle: independently integrate the public sampling contract."""
import bisect
import math


def interpolate(rows, times, key, t):
    j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
    a,b=rows[j],rows[j+1]
    return a[key]+(b[key]-a[key])*(t-a['time'])/(b['time']-a['time'])


def expected_code(t, case):
    vin=case['vref']*(.5+.63*math.sin(2*math.pi*1370000*t))
    thresholds=[case['vref']*(k/256+case['skew']*(k/256)*(1-k/256)) for k in range(1,256)]
    return sum(vin >= threshold for threshold in thresholds)


def evaluate(rows, case, work=None):
    if len(rows)<2 or any(not math.isfinite(row[k]) for row in rows for k in ('time','clock','vin','code')):
        return dict(passed=False,failures=['incomplete or nonfinite waveform'])
    times=[row['time'] for row in rows]
    if any(b<=a for a,b in zip(times,times[1:])):
        return dict(passed=False,failures=['unordered time'])
    failures=[]
    if times[0]>1e-15 or times[-1]<case['stop']*(1-1e-8):
        failures.append('incomplete time coverage')
    edges=[]
    for a,b in zip(rows,rows[1:]):
        if a['clock']<.5<=b['clock']:
            edges.append(a['time']+(.5-a['clock'])*(b['time']-a['time'])/(b['clock']-a['clock']))
    expected_edges=[]
    t=case['clock_first_cross']
    while t<case['stop']:
        expected_edges.append(t)
        t+=case['clock_period']
    if len(edges)!=len(expected_edges) or any(abs(a-b)>1e-12 for a,b in zip(edges,expected_edges)):
        failures.append('clock edge count or timing mismatch')
    max_error=0.0
    previous=0.0
    for t in expected_edges:
        value=expected_code(t,case)/255
        # Preserve public delay and finite linear transition, including edges.
        for fraction in (.25,.5,.75):
            probe=t+case['delay']+fraction*case['rise']
            if probe<=case['stop']:
                wanted=previous+fraction*(value-previous)
                max_error=max(max_error,abs(interpolate(rows,times,'code',probe)-wanted))
        if case['delay']>0:
            probe=t+case['delay']/2
            max_error=max(max_error,abs(interpolate(rows,times,'code',probe)-previous))
        for dt in (2e-9,8e-9):
            if t+dt<=case['stop']:
                max_error=max(max_error,abs(interpolate(rows,times,'code',t+dt)-value))
        previous=value
    if abs(interpolate(rows,times,'code',5e-10))>case['atol']:
        failures.append('incorrect reset code')
    if max_error>case['atol']:
        failures.append('sampled threshold count or hold mismatch')
    return dict(passed=not failures,failures=failures,max_code_voltage_error=max_error,
                expected_samples=len(expected_edges),observed_clock_edges=len(edges),saved_waveform_points=len(rows))
