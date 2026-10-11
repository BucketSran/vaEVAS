"""Independent continuous OTA response and measured-experiment grading."""
import bisect,math,hashlib,struct

def propagate(y,target,dt,tau,positive,negative):
    error=target-y
    if not error:return y
    rate=positive if error>0 else negative
    distance=abs(error); threshold=rate*tau
    linear=max(0.,(distance-threshold)/rate)
    if dt<=linear:return y+math.copysign(rate*dt,error)
    return target-math.copysign(min(distance,threshold)*math.exp(-(dt-linear)/tau),error)

def interpolate(points,t):
    j=max(0,min(len(points)-2,bisect.bisect_right([p[0] for p in points],t)-1))
    a,b=points[j],points[j+1]
    return a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0])

def continuous_truth(case,dt=25e-12):
    # Exact constant-target propagator with midpoint reconstruction of public
    # linear ramps. Grid includes zero and stop and remains candidate-independent.
    n=math.ceil(case['stop']/dt);dt=case['stop']/n;y=0.;truth=[(0.,y)]
    for k in range(n):
        t=(k+.5)*dt;en=interpolate(case['enable'],t);vin=interpolate(case['input'],t)
        if en<.75:y=propagate(y,0.,dt,50e-9,math.inf,math.inf)
        else:y=propagate(y,min(1.4,max(.1,.75+.98*(vin-.75))),dt,20e-9,1e7,6e6)
        truth.append(((k+1)*dt,y))
    return truth

def evaluate(rows,case,work):
    times=[r['time'] for r in rows]
    if len(rows)<2 or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('invalid time grid')
    if times[0]>1e-15 or times[-1]<case['stop']-1e-15:raise ValueError('incomplete waveform')
    if max(b-a for a,b in zip(times,times[1:]))>case.get('resolution',.25e-9)*1.05:raise ValueError('insufficient numerical resolution')
    def at(t,n):
        j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1));a,b=rows[j],rows[j+1]
        return a[n]+(b[n]-a[n])*(t-a['time'])/(b['time']-a['time'])
    kind=case['kind']
    if kind=='continuous':
        truth=continuous_truth(case);errors=[abs(at(t,'vout')-v) for t,v in truth]
        input_error=max(abs(at(t,'vin')-interpolate(case['input'],t)) for t,v in truth)
        enable_error=max(abs(at(t,'enable')-interpolate(case['enable'],t)) for t,v in truth)
        return dict(passed=max(errors)<=case['atol'] and input_error<1e-6 and enable_error<1e-6,max_error_V=max(errors),input_error_V=input_error,enable_error_V=enable_error)
    if kind=='data':
        truth=case['truth']
        identity=hashlib.sha256(b''.join(struct.pack('>dd',float(t),float(v)) for t,v in truth)).hexdigest()
        if identity!=FROZEN_DATA[case['name']]:raise ValueError('source observation identity mismatch')
        errors=[(t,abs(at(t,'vout')-v)) for t,v in truth]
        metrics=[]
        for a,b,label,rms_limit,peak_limit in case['windows']:
            es=[e for t,e in errors if a<=t<=b]
            if not es:raise ValueError('empty source window')
            metrics.append(dict(window=label,rms_V=math.sqrt(sum(e*e for e in es)/len(es)),max_V=max(es),rms_limit_V=rms_limit,peak_limit_V=peak_limit))
        ok=all(m['rms_V']<=m['rms_limit_V'] and m['max_V']<=m['peak_limit_V'] for m in metrics)
        stimulus_error=max(max(abs(r['vin']-interpolate(case['input'],r['time'])),
                               abs(r['enable']-interpolate(case['enable'],r['time']))) for r in rows)
        return dict(passed=ok and stimulus_error<=1e-6,windows=metrics,stimulus_error_V=stimulus_error)
    if kind=='measurement':return measure_verdict(case,at,rows)
    raise ValueError('unknown OTA contract')

def measured(vin_before,vin_after,out_before,values):
    span=vin_after-vin_before
    final=sum(values[-20:])/20
    clipped=final<=.105 or final>=1.395
    last=max([i+1 for i,v in enumerate(values) if abs(v-final)>.003],default=0)
    settled=last<=160
    status=4 if abs(span)<.02 else 3 if clipped else 1 if settled else 2
    slew_metric=max(abs(b-a) for a,b in zip([out_before]+values,values))
    return dict(gain=(final-out_before)/span if abs(span)>=.02 else 0,slew_metric=slew_metric,settle=last+1 if settled else 180,valid=int(status==1),status=status,direction=1 if span>0 else -1)

def measure_verdict(case,at,rows):
    reports=[];ok=True
    # vout is read-only. Verify the fixed DUT response too, so a candidate cannot
    # replace the DUT waveform with a driven output and measure its own source.
    dut_error=0.
    if 'dut_parameters' in case:
        p=case['dut_parameters'];y=0.
        dut_error=abs(rows[0]['vout'])
        for a,b in zip(rows,rows[1:]):
            en=(a['enable']+b['enable'])/2;vin=(a['vin']+b['vin'])/2
            if en<.75:y=propagate(y,0.,b['time']-a['time'],50e-9,math.inf,math.inf)
            else:y=propagate(y,min(1.4,max(.1,.75+p['gain']*(vin-.75))),b['time']-a['time'],p['tau'],p['positive'],p['negative'])
            dut_error=max(dut_error,abs(b['vout']-y))

    steps=[200e-9,400e-9,600e-9,800e-9,1000e-9,1200e-9]
    levels=[.75,.8,.7,1.2,.3,1.6,.75]
    transitions=[10e-9]+steps+[t+180e-9 for t in steps]
    stimulus_failures=[]
    for row in rows:
        t=row['time']
        if any(0<=t-edge<=20e-12 for edge in transitions):continue
        ix=bisect.bisect_right(steps,t)
        expected_input=levels[ix]
        expected_enable=0. if t<10e-9 else 1.5
        active=ix>0 and t<steps[ix-1]+180e-9
        expected_launch=float(active)
        valid=abs(row['vin']-expected_input)<=1e-6 and abs(row['enable']-expected_enable)<=1e-6 and abs(row['launch']-expected_launch)<=1e-6
        if active:valid &= abs(row['valid'])<.01 and abs(row['status'])<.01
        if ix==0:valid &= all(abs(row[n])<.01 for n in ['gain','slew_metric','settle','valid','status','direction'])
        if not valid:stimulus_failures.append(t)
    ok=not stimulus_failures and dut_error<=.004
    for i,t in enumerate([200e-9,400e-9,600e-9,800e-9,1000e-9,1200e-9]):
        # Candidate owns stimulus. Verify the actual commanded experiment first.
        expected=[.8,.7,1.2,.3,1.6,.75][i]
        before=at(t-1e-9,'vin');after=at(t+1e-9,'vin')
        stimulation=abs(after-expected)<1e-6 and at(t+1e-9,'enable')>1.49 and at(t+1e-9,'launch')>.9
        values=[at(t+(j+1)*1e-9,'vout') for j in range(180)]
        metric=measured(before,after,at(t-1e-12,'vout'),values)
        obs={n:at(t+185e-9,n) for n in metric}
        errors={n:abs(obs[n]-v) for n,v in metric.items()}
        passed=stimulation and all(errors[n]<=({'gain':.003,'slew_metric':.001,'settle':2}.get(n,.01)) for n in errors)
        # New launch must invalidate old valid immediately, before completion.
        passed=passed and at(t+2e-9,'valid')<.01
        reports.append(dict(round=i,passed=passed,expected=metric,reported=obs,stimulus_valid=stimulation));ok &= passed
        # Reports must persist throughout each completed window, including the last.
    for i,report in enumerate(reports):
        start=steps[i]+180e-9+20e-12;end=steps[i+1] if i<5 else case['stop']
        for row in rows:
            if start<=row['time']<end:
                if any(abs(row[n]-report['expected'][n])>({'gain':.003,'slew_metric':.001,'settle':2}.get(n,.01)) for n in report['expected']):ok=False
    return dict(passed=ok,reports=reports,dut_error_V=dut_error,stimulus_failure_count=len(stimulus_failures),first_stimulus_failure_s=stimulus_failures[0] if stimulus_failures else None)

# Frozen independent JKU/ngspice observation identities, not derived from case input.
FROZEN_DATA={'train-1': 'bfcd3148af55fe35b1b9d1a13f2631a57a7b1bd4e4f9352a3e0b6a11cf21f34b', 'train-0': '40eb107e08199658fa3e20899db03b28770d2b95ea88a5798aced62f7267f37e', 'train-2': '73476366e99da6b1cf29d3ed4615f05a57931f002b1ab26fdd155f22557c5d3f', 'test-2': 'bffd998470741eca57e21f39f592a8938240afd16bdf21e8c66617fba56db54f', 'test-1': 'f372d8f1712b6c7004f845d9dc85080cd152d93df64c177d579988a883d996a5', 'test-0': 'b8274126a61ac3577fcbca5e17f0e9aaf90e2403f9607a3a677fee5631baf92b'}
