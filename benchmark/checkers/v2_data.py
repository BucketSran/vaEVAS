"""Grade free-running VA predictions against held-out transistor observations."""
import bisect, math

def evaluate(rows,case,work):
    try:
        limits=case['limits'];truth=case['truth']
        if not rows or len(rows)<2:raise ValueError('missing waveform')
        if not truth or len(truth)<2:raise ValueError('missing truth')
        if any(len(r)!=2 or not all(math.isfinite(float(x)) for x in r) for r in truth):raise ValueError('invalid truth')
        if any(b[0]<=a[0] for a,b in zip(truth,truth[1:])):raise ValueError('nonmonotonic truth')
        if not math.isfinite(case['stop']) or case['stop']<=0:raise ValueError('invalid stop')
        if any(not math.isfinite(v) or v<=0 for v in limits.values()):raise ValueError('invalid limits')
        times=[float(r['time']) for r in rows];volts=[float(r['vhold']) for r in rows]
        if any(not math.isfinite(x) for x in times+volts):raise ValueError('nonfinite waveform')
        if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('nonmonotonic waveform')
        if times[0]>truth[0][0]+1e-15 or times[-1]<case['stop']-1e-15:raise ValueError('incomplete waveform')
        def at(t):
            i=bisect.bisect_left(times,t)
            if i==0:return volts[0]
            if i==len(times):return volts[-1]
            return volts[i-1]+(volts[i]-volts[i-1])*(t-times[i-1])/(times[i]-times[i-1])
        # Observe source-fixed timestamps, with no candidate-dependent realignment.
        errors=[(t,abs(at(t)-v)) for t,v in truth]
        def window(a,b):return [e for t,e in errors if a-1e-15<=t<=b+1e-15]
        track=[]
        for a,b in case['tracks']:
            values=window(a,b)
            if not values:raise ValueError('empty acquisition window')
            track.append(math.sqrt(sum(e*e for e in values)/len(values)))
        hold=[]
        for a,b in case['holds']:
            values=window(a,b)
            if not values:raise ValueError('empty hold window')
            hold.append(max(values))
        samples=[]
        tt=[t for t,v in truth]
        for t in case['samples']:
            insertion=bisect.bisect_left(tt,t)
            choices=[i for i in [insertion-1,insertion] if 0<=i<len(tt)]
            i=min(choices,key=lambda i:abs(tt[i]-t))
            if abs(tt[i]-t)>1e-15:raise ValueError('sample missing from frozen truth')
            samples.append(abs(at(t)-truth[i][1]))
        metrics={'track_rms':max(track),'sample_max':max(samples),'hold_max':max(hold)}
        return {'passed':all(metrics[k]<=limits[k] for k in metrics),'metrics_V':metrics,'per_track_rms_V':track,'per_sample_abs_V':samples,'per_hold_max_V':hold,'limits_V':limits}
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as exc:return {'passed':False,'status':'checker_error','reason':str(exc)}
