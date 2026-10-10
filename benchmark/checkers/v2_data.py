"""Grade free-running VA predictions against held-out transistor observations."""
import bisect, math

def evaluate(rows,case,work):
    limits=case['limits'];truth=case['truth']
    if not rows or len(rows)<2:return {'passed':False,'reason':'missing waveform'}
    try:
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
            i=bisect.bisect_left(tt,t)
            if i==len(tt) or abs(tt[i]-t)>1e-15:raise ValueError('sample missing from frozen truth')
            samples.append(abs(at(t)-truth[i][1]))
        metrics={'track_rms':max(track),'sample_max':max(samples),'hold_max':max(hold)}
        return {'passed':all(metrics[k]<=limits[k] for k in metrics),'metrics_V':metrics,'per_track_rms_V':track,'per_sample_abs_V':samples,'per_hold_max_V':hold,'limits_V':limits}
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as exc:return {'passed':False,'reason':str(exc)}
