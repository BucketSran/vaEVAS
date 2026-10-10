"""Grade free-running VA predictions against held-out transistor observations."""
import bisect, hashlib, math, struct

# Predeclared source export identities, independently reviewed at ebd314e3.
# JKU source: 892272208df28b6c7620101e129a9d8dd95ebab7
# SKY130 PDK: f62031a1be9aefe902d6d54cddd6f59b57627436
# Grid hashes bind every compressed public / 50 ps hidden observation and
# full [0, stop] extent. Observation hashes also bind the original voltages.
# Runtime never derives the expected identity from the case being evaluated.
FROZEN_OBSERVATIONS = {
    "selftest-0": {
        "count": 422,
        "stop": 1.6e-07,
        "grid_sha256": "863d39c6c933874bc26c649f6e6d09322332f3e39af1c0db325991cd3731727d",
        "observations_sha256": "e68ac25b41f48701bf6c57944d45b3852b95abc2c7ee891ba70404e8f7de9bec"
    },
    "selftest-1": {
        "count": 380,
        "stop": 1.6e-07,
        "grid_sha256": "81c571b89a930950ca406ccbdaa0cb9d0ce4a8ada85f81325ead7eb84a7cb9b1",
        "observations_sha256": "e312779e9ee9336d65f98560d28d4ad10fb2209cda87fbc801e72cfaa2f0b57f"
    },
    "heldout-0": {
        "count": 3201,
        "stop": 1.6e-07,
        "grid_sha256": "ec0fea6b898b396adff825bb265cf435cb364d9191522df93359e6522e77c1d1",
        "observations_sha256": "f86ffbc729e71189c9210dffdfc916c8909e473a8a432ae07c7692aeecced808"
    },
    "heldout-1": {
        "count": 3201,
        "stop": 1.6e-07,
        "grid_sha256": "ec0fea6b898b396adff825bb265cf435cb364d9191522df93359e6522e77c1d1",
        "observations_sha256": "7d23786cabd83823f2fccfd2b6b7b54a18c5c36d6337d52f842bd857e48794be"
    },
    "heldout-2": {
        "count": 4401,
        "stop": 2.2e-07,
        "grid_sha256": "81abb1803ba00676ea6e0c13866a449901d00d6b39e9e244e6d8d7ec681e7e38",
        "observations_sha256": "fb76cf075714b236b98d394e1b89396dfdcb55dd5035b16947b3b7539339cdb3"
    },
    "heldout-3": {
        "count": 4401,
        "stop": 2.2e-07,
        "grid_sha256": "81abb1803ba00676ea6e0c13866a449901d00d6b39e9e244e6d8d7ec681e7e38",
        "observations_sha256": "2e26555d3b4a8ac446f7744cef30e89e3cb03c4a2343c7d286a25d692a6d12be"
    }
}

def evaluate(rows,case,work):
    try:
        limits=case['limits'];truth=case['truth']
        if not rows or len(rows)<2:raise ValueError('missing waveform')
        if not truth or len(truth)<2:raise ValueError('missing truth')
        if any(len(r)!=2 or not all(math.isfinite(float(x)) for x in r) for r in truth):raise ValueError('invalid truth')
        if any(b[0]<=a[0] for a,b in zip(truth,truth[1:])):raise ValueError('nonmonotonic truth')
        if not math.isfinite(case['stop']) or case['stop']<=0:raise ValueError('invalid stop')
        expected=FROZEN_OBSERVATIONS[case['name']]
        if len(truth)!=expected['count'] or truth[0][0]!=0 or truth[-1][0]!=expected['stop'] or case['stop']!=expected['stop']:
            raise ValueError('incomplete frozen truth extent')
        grid=hashlib.sha256(b''.join(struct.pack('>d',float(t)) for t,v in truth)).hexdigest()
        if grid!=expected['grid_sha256']:raise ValueError('frozen truth observation grid mismatch')
        observations=hashlib.sha256(b''.join(struct.pack('>dd',float(t),float(v)) for t,v in truth)).hexdigest()
        if observations!=expected['observations_sha256']:raise ValueError('frozen source observation identity mismatch')
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
