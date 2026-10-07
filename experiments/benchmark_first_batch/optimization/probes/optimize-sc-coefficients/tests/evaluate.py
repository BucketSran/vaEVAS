"""Clocked filter oracle from the public simultaneous stage recurrence."""
import bisect
import math


def interpolate(rows,times,key,t):
    j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
    a,b=rows[j],rows[j+1]
    return a[key]+(b[key]-a[key])*(t-a['time'])/(b['time']-a['time'])


def recurrence_samples(case):
    t=case['first_cross'];previous_time=0.;states=[0.]*4;samples=[]
    while t<case['stop']:
        elapsed=t-previous_time
        sample=.5+.45*math.sin(2*math.pi*case['sine_frequency']*t)
        # Simultaneous section updates use the old upstream capacitor voltage.
        old=states[:]
        for i,tau in enumerate(case['taus']):
            upstream=sample if i==0 else old[i-1]
            states[i]=old[i]*math.exp(-elapsed/tau)+upstream*(-math.expm1(-elapsed/tau))
        samples.append((t,states[3],sample))
        previous_time=t;t+=case['period']
    return samples


def raw_transition_error(rows, key, samples, initial, delay, rise):
    """Check every saved point against the prescribed sample times and linear ramps."""
    starts=[t+delay for t,value in samples]
    maximum=0.0
    for row in rows:
        index=bisect.bisect_right(starts,row['time'])-1
        if index<0:
            wanted=initial
        else:
            previous=initial if index==0 else samples[index-1][1]
            fraction=min(1.0,max(0.0,(row['time']-starts[index])/rise))
            wanted=previous+fraction*(samples[index][1]-previous)
        maximum=max(maximum,abs(row[key]-wanted))
    return maximum


def evaluate(rows,case,work=None):
    if len(rows)<2 or any(not math.isfinite(row[key]) for row in rows for key in ('time','clock','vin','out')):
        return dict(passed=False,failures=['incomplete or nonfinite waveform'])
    times=[r['time'] for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])):
        return dict(passed=False,failures=['unordered time'])
    failures=[]
    if times[0]>1e-15 or times[-1]<case['stop']*(1-1e-8):
        failures.append('incomplete time coverage')
    observed=[]
    for a,b in zip(rows,rows[1:]):
        if a['clock']<.5<=b['clock']:
            observed.append(a['time']+(.5-a['clock'])*(b['time']-a['time'])/(b['clock']-a['clock']))
    samples=recurrence_samples(case)
    if len(observed)!=len(samples) or any(abs(actual-expect[0])>1e-12 for actual,expect in zip(observed,samples)):
        failures.append('wrong actual clock sample count or phase')
    max_error=abs(interpolate(rows,times,'out',.5e-9));previous=0.;stimulus_error=0.
    for t,value,vin in samples:
        stimulus_error=max(stimulus_error,abs(interpolate(rows,times,'vin',t)-vin))
        # Preserve public delay and finite linear transition, including edges.
        for fraction in (.25,.5,.75):
            probe=t+case['delay']+fraction*case['rise']
            if probe<=case['stop']:
                wanted=previous+fraction*(value-previous)
                max_error=max(max_error,abs(interpolate(rows,times,'out',probe)-wanted))
        if case['delay']>0:
            probe=t+case['delay']/2
            max_error=max(max_error,abs(interpolate(rows,times,'out',probe)-previous))
        for dt in (2e-9,case['period']-2e-9):
            if t+dt<=case['stop']:
                max_error=max(max_error,abs(interpolate(rows,times,'out',t+dt)-value))
        max_error=max(max_error,abs(interpolate(rows,times,'out',t-.5e-9)-previous))
        previous=value
    raw_error=raw_transition_error(rows,'out',[(t,value) for t,value,vin in samples],0.,case['delay'],case['rise'])
    max_error=max(max_error,raw_error)
    if stimulus_error>5e-6:
        failures.append('actual input stimulus mismatches prescribed sine')
    if max_error>case['atol']:
        failures.append('settling coefficients, stage update ordering or hold mismatch')
    return dict(passed=not failures,failures=failures,max_output_error_v=max_error,max_raw_transition_error_v=raw_error,
                max_stimulus_error_v=stimulus_error,expected_samples=len(samples),
                observed_clock_edges=len(observed),saved_waveform_points=len(rows))
