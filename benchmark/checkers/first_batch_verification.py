"""Independent waveform checks for first-batch verification-tool submissions."""
import bisect
import math


def value(rows,node,t):
    ts=[r['time'] for r in rows]
    j=max(0,min(bisect.bisect_right(ts,t)-1,len(rows)-2))
    a,b=rows[j:j+2]
    f=(t-a['time'])/(b['time']-a['time']) if b['time']>a['time'] else 0
    return a[node]+f*(b[node]-a[node])


def edges(rows,node,level=.5,rising=True):
    result=[]
    for a,b in zip(rows,rows[1:]):
        if (a[node]<level<=b[node]) if rising else (a[node]>level>=b[node]):
            result.append(a['time']+(b['time']-a['time'])*(level-a[node])/(b[node]-a[node]))
    return result


def sar(rows,case):
    failures=[]
    for k in range(6):
        base=k*200e-9
        for dt in [25,35,45,55,68,80,95,130,180]:
            t=base+dt*1e-9
            expected={'vin':(2*k+1.25)/16,'start':float(31<=dt<42 or 51<=dt<62),
                      'rst':float(not(k==2 and 65<=dt<76))}
            for node,want in expected.items():
                if abs(value(rows,node,t)-want)>.015:failures.append(f'stimulus {node} at {t:g}')
    if value(rows,'rst',10e-9)>.1:failures.append('initial reset missing')
    starts=edges(rows,'start');dones=edges(rows,'done');raw_bad=False
    # Fixed published experiment creates 5 completed conversions and one abort.
    expected_done=[k*200e-9+40e-9+case['latency']*10e-9+.05e-9 for k in [0,1,3,4,5]]
    if len(dones)!=len(expected_done):raw_bad=True
    else:
        for k,t,want in zip([0,1,3,4,5],dones,expected_done):
            if abs(t-want)>1.1e-9 or abs(value(rows,'code',t+1e-9)-(2*k+1))>.1:raw_bad=True
    if len(starts)!=12:failures.append('start edge coverage')
    for t in [482e-9,490e-9,500e-9]:
        if abs(value(rows,'code',t))>.1 or value(rows,'done',t)>.1:raw_bad=True
    expected_bad=case['fault']!=0
    if raw_bad!=expected_bad:failures.append('device observation disagrees with independently specified fault')
    observed=value(rows,'verdict',case['stop']-10e-9)
    if abs(observed-float(raw_bad))>.1:failures.append('verdict disagrees with raw handshake/code')
    return {'passed':not failures,'failures':failures,'raw_device_bad':raw_bad,'done_edges_s':dones,'verdict':observed}


def evaluate(rows,case,work=None):
    if len(rows)<2 or any(not math.isfinite(v) for r in rows for v in r.values()):
        return {'passed':False,'failures':['invalid waveform']}
    verdict_failures=[]
    if 'verdict' in rows[0]:
        if abs(rows[0]['verdict'])>.1:verdict_failures.append('verdict initial value')
        if any(r['verdict']<-.01 or r['verdict']>1.01 for r in rows):verdict_failures.append('verdict outside logical levels')
        if any(b['verdict']<a['verdict']-.01 for a,b in zip(rows,rows[1:])):verdict_failures.append('verdict did not latch')
    if case['task']=='verify-sar-flow':
        answer=sar(rows,case);answer['failures'].extend(verdict_failures);answer['passed']=not answer['failures'];return answer
    failures=list(verdict_failures)
    task=case['task']
    if task=='verify-nonoverlap-stimulus':
        p,d=case['period'],case['dead']
        for node,offset in [('p1',d),('p2',p/2+d)]:
            actual=edges(rows,node)
            wanted=[k*p+offset+.05e-9 for k in range(12)]
            if len(actual)!=12 or any(abs(a-b)>.3e-9 for a,b in zip(actual,wanted)):
                failures.append(node+' rise timing/count')
            falls=[t for t in edges(rows,node,rising=False) if t<case['stop']-.3e-9]
            wanted_falls=[k*p+(p/2 if node=='p1' else p)+.05e-9 for k in range(12)]
            wanted_falls=[t for t in wanted_falls if t<=case['stop']]
            if len(falls)!=len(wanted_falls) or any(abs(a-b)>.3e-9 for a,b in zip(falls,wanted_falls)):
                failures.append(node+' fall timing/count')
        if any(r['p1']>.5 and r['p2']>.5 for r in rows):failures.append('overlap')
        # Threshold crossings alone cannot establish valid electrical rails.
        # Test every raw point outside the published edge timing/transition guard.
        bad_rail=False
        for r in rows:
            phase=r['time']%p
            boundaries=[0,d,p/2,p/2+d,p]
            if min(abs(phase-b) for b in boundaries)<=.5e-9:continue
            wanted={'p1':float(d<=phase<p/2),'p2':float(p/2+d<=phase<p)}
            if any(abs(r[node]-level)>.01 for node,level in wanted.items()):
                bad_rail=True;break
        if bad_rail:failures.append('phase stable electrical level')

        for k in range(12):
            capture=k*p+d+.05e-9
            observed=value(rows,'z',k*p+p/2+d+1e-9)
            expected=.5+.3*math.sin(2*math.pi*capture/700e-9)
            if abs(observed-expected)>.002:failures.append('downstream sampled transfer')
    elif task=='verify-comparator-overdrive':
        qedges=edges(rows,'q');expected_edges=[]
        for rising,offset in [(True,20e-9),(False,70e-9)]:
            actual=edges(rows,'clk',rising=rising)
            wanted=[k*100e-9+offset+.05e-9 for k in range(12)]
            if len(actual)!=12 or any(abs(a-b)>.3e-9 for a,b in zip(actual,wanted)):failures.append('comparator clock edges')
        for k in range(12):
            d=[.01,.025,.05][k%3];sign=1 if k%2==0 else -1
            for dt in [5,25,60,80,95]:
                t=k*100e-9+dt*1e-9
                if abs(value(rows,'vp',t)-case['cm']-sign*d/2)>.001 or abs(value(rows,'vn',t)-case['cm']+sign*d/2)>.001:
                    failures.append('differential/commonmode coverage')
                if abs(value(rows,'clk',t)-float(20<=dt<70))>.01:failures.append('clock/reset coverage')
                if k%2 and abs(value(rows,'q',t))>.01:failures.append('negative decision/reset')
            if k%2==0:expected_edges.append(k*100e-9+20e-9+.05e-9+1e-9+.1e-9/d+.05e-9)
        if len(qedges)!=6 or any(abs(a-b)>.35e-9 for a,b in zip(qedges,expected_edges)):
            failures.append('overdrive delay observations')
    elif task=='verify-pll-lock-checker':
        refs=edges(rows,'ref');clks=[t for t in edges(rows,'clk') if t>=1e-6]
        refs=[t for t in refs if t>=1e-6]
        raw_bad=len(clks)!=len(refs)
        raw_bad=raw_bad or any(min(abs(t-r) for r in refs)>2e-9 for t in clks)
        raw_bad=raw_bad or any(abs(b-a-100e-9)>2e-9 for a,b in zip(clks,clks[1:]))
        raw_bad=raw_bad or not clks or case['stop']-clks[-1]>102e-9
        if raw_bad!=(case['fault']!=0):failures.append('device differs from specified fault')
        if abs(value(rows,'verdict',case['stop']-10e-9)-int(raw_bad))>.1:failures.append('PLL verdict disagrees with raw edges')
    elif task=='verify-sh-settling-checker':
        raw_bad=False
        for r in rows:
            phase=r['time']%500e-9
            if (120e-9<=phase<249e-9 or 255e-9<=phase<490e-9) and abs(r['y']-r['vin'])>.005:
                raw_bad=True
        if raw_bad!=(case['fault']!=0):failures.append('device differs from specified fault')
        if abs(value(rows,'verdict',case['stop']-10e-9)-int(raw_bad))>.1:failures.append('S/H verdict disagrees with complete windows')
    else:raise ValueError('unknown verification task '+task)
    return {'passed':not failures,'failures':failures}
