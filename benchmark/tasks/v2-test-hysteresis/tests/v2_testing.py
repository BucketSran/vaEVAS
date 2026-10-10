"""Independent waveform oracles for v2 circuit measurement tasks (stdlib only)."""
import bisect
import math


class Wave:
    def __init__(self, rows):
        self.rows = rows
        self.ts = [r['time'] for r in rows]
        if len(rows) < 2 or any(not math.isfinite(v) for r in rows for v in r.values()):
            raise ValueError('missing or nonfinite waveform')
        if any(a >= b for a, b in zip(self.ts, self.ts[1:])):
            raise ValueError('non-increasing time')

    def value(self, t, node):
        i = max(0, min(len(self.rows)-2, bisect.bisect_right(self.ts, t)-1))
        a, b = self.rows[i:i+2]
        return a[node] + (b[node]-a[node])*(t-a['time'])/(b['time']-a['time'])

    def edges(self, node, direction=1, threshold=.5):
        found = []
        for a, b in zip(self.rows, self.rows[1:]):
            x, y = a[node]-threshold, b[node]-threshold
            if (x < 0 <= y) if direction > 0 else (x > 0 >= y):
                found.append(a['time']+(b['time']-a['time'])*(-x)/(y-x))
        return found


def hysteresis(w, case):
    events = [(t, 'reset') for t in w.edges('begin_round' if 'begin_round' in w.rows[0] else 'begin')]
    events += [(t, 'up') for t in w.edges('cmp_out')]
    events += [(t, 'down') for t in w.edges('cmp_out', -1)]
    events.sort()
    state = dict(up=0., down=0., width=0., valid=0.)
    saw = set()
    guard, atol = case.get('guard', 1e-10), case.get('atol', .002)
    failures = []
    points = [(w.ts[0], 'initial')] + events
    for i, (t, kind) in enumerate(points):
        if kind == 'reset':
            state = dict(up=0., down=0., width=0., valid=0.)
            saw.clear()
        elif kind in ('up', 'down'):
            state[kind] = w.value(t, 'vin')
            saw.add(kind)
            if len(saw) == 2:
                state['width'] = state['up']-state['down']
                state['valid'] = 1.
        end = points[i+1][0] if i+1 < len(points) else w.ts[-1]
        for row in w.rows:
            if t+guard < row['time'] < end-guard:
                for node, expected in state.items():
                    if abs(row[node]-expected) > atol and len(failures) < 20:
                        failures.append(dict(kind='capture', node=node, time=row['time'], expected=expected, actual=row[node]))
    return dict(passed=not failures, status='graded', failures=failures, edges=len(events))


def pieces(w, case, states):
    """Check every saved hold point and one interior sample in each expected state."""
    failures=[]
    guard=case.get('guard',1e-10)
    for i,(t,state) in enumerate(states):
        end=states[i+1][0] if i+1<len(states) else w.ts[-1]
        if end-t<=2*guard:
            continue
        lo,hi=t+guard,end-guard
        times=[(lo+hi)/2]+w.ts[bisect.bisect_right(w.ts,lo):bisect.bisect_left(w.ts,hi)]
        for at in times:
            for node,expected in state.items():
                tolerance=case.get('tolerances',{}).get(node,case.get('atol',.002))
                actual=w.value(at,node)
                if abs(actual-expected)>tolerance and len(failures)<20:
                    failures.append(dict(kind='report',node=node,time=at,expected=expected,actual=actual))
    return dict(passed=not failures,status='graded',failures=failures,states=len(states))


def delay(w,case):
    threshold=case.get('threshold',.5)
    high=case.get('vhigh',1.)
    events=[(t,'launch') for t in w.edges('clk',threshold=threshold)]
    events += [(t,'outp') for t in w.edges('outp',threshold=threshold)]
    events += [(t,'outn') for t in w.edges('outn',threshold=threshold)]
    events.sort()
    state=dict(delay_ps=0.,overdrive_mv=0.,polarity=0.,valid=0.)
    states=[(0.,state.copy())]
    launch=None
    for t,kind in events:
        if kind=='launch':
            launch=t
            state['overdrive_mv']=abs(w.value(t,'vinp')-w.value(t,'vinn'))*1e3
            state['valid']=0.
        elif launch is not None:
            state.update(delay_ps=(t-launch)*1e12,polarity=high*float(kind=='outp'),valid=high)
            launch=None
        states.append((t,state.copy()))
    return pieces(w,case,states)

def rms(w,case):
    th,high=case.get('threshold',.45),case.get('vhigh',.9)
    events=[(t,'reset') for t in w.edges('reset',threshold=th)]
    events += [(t,'sample') for t in w.edges('clk',threshold=th)]
    events.sort()
    samples=[]
    state=dict(rms_out=0.,valid=0.)
    states=[(0.,state.copy())]
    for t,kind in events:
        if kind=='reset' or w.value(t,'reset')>th:
            samples=[]
            state=dict(rms_out=0.,valid=0.)
        else:
            state['valid']=0.
            if w.value(t,'enable')>th:
                samples.append(w.value(t,'vinp')-w.value(t,'vinn'))
                if len(samples)==4:
                    state['rms_out']=math.sqrt(sum(x*x for x in samples)/4)
                    state['valid']=high
                    samples=[]
        states.append((t,state.copy()))
    return pieces(w,case,states)


def duty(w,case):
    th,high=case.get('threshold',.45),case.get('vhigh',.9)
    events=[(t,1) for t in w.edges('clk_in',threshold=th)]
    events += [(t,-1) for t in w.edges('clk_in',direction=-1,threshold=th)]
    events.sort()
    state=dict(codes=[0],valid=0.)
    states=[(0.,state.copy())]
    start=fall=None
    ambiguity=[]
    uncertainty=case.get('edge_time_uncertainty',0.)
    for t,direction in events:
        if direction==1:
            if start is not None and fall is not None:
                duration,period=fall-start,t-start
                lo=255*max(0.,duration-2*uncertainty)/(period+2*uncertainty)
                hi=255*(duration+2*uncertainty)/(period-2*uncertainty)
                codes=list(range(max(0,math.floor(lo+.5)),min(255,math.floor(hi+.5))+1))
                state=dict(codes=codes,valid=high)
                if len(codes)>1: ambiguity.append(dict(time=t,codes=codes,lower=lo,upper=hi))
            start,fall=t,None
        elif start is not None: fall=t
        states.append((t,state.copy()))
    failures=[]
    guard,atol=case.get('guard',1e-10),case.get('atol',.002)
    for i,(t,state) in enumerate(states):
        end=states[i+1][0] if i+1<len(states) else w.ts[-1]
        if end-t<=2*guard: continue
        lo,hi=t+guard,end-guard
        for at in [(lo+hi)/2]+w.ts[bisect.bisect_right(w.ts,lo):bisect.bisect_left(w.ts,hi)]:
            observed=[w.value(at,f'duty{j}') for j in range(8)]
            complete_match=any(all(abs(observed[j]-high*((code>>j)&1))<=atol for j in range(8)) for code in state['codes'])
            valid_ok=abs(w.value(at,'valid')-state['valid'])<=atol
            if (not complete_match or not valid_ok) and len(failures)<20:
                failures.append(dict(kind='duty-code',time=at,allowed_codes=state['codes'],actual_bits=observed,valid=w.value(at,'valid'),expected_valid=state['valid']))
    return dict(passed=not failures,status='graded',failures=failures,states=len(states),quantization_ambiguity=ambiguity)

def gain(w,case):
    period=case['sample_period']
    start=case.get('start_time',0.)
    events=[(i*period,'sample') for i in range(int(case['stop']/period)+1) if i*period>=start]
    events += [(t,'reset') for t in w.edges('begin_round')]
    events.sort()
    ins,outs=[],[]
    state=dict(gain_out=0.,valid=0.)
    states=[(0.,state.copy())]
    for t,kind in events:
        if kind=='reset':
            ins,outs=[],[]
            state=dict(gain_out=0.,valid=0.)
        else:
            ins.append(w.value(t,'vinp')-w.value(t,'vinn'))
            outs.append(w.value(t,'voutp')-w.value(t,'voutn'))
            span=max(ins)-min(ins)
            if span>case.get('min_input_span',.02):
                high=case.get('vhigh',.9)
                state=dict(gain_out=high*(max(outs)-min(outs))/span/case.get('gain_scale',10.),valid=high)
        states.append((t,state.copy()))
    return pieces(w,case,states)

def frequency(w,case):
    th=case.get('threshold',.45)
    events=[(t,'dco') for t in w.edges('dco_clk',threshold=th)]
    events += [(t,'div') for t in w.edges('div_clk',threshold=th)]
    events += [(t,'reset') for t in w.edges('reset',threshold=th)]
    events += [(t,'reset') for t in w.edges('enable',direction=-1,threshold=th)]
    events.sort()
    last={}
    periods={}
    state=dict(freq_mhz=0.,divider_ratio=0.,valid=0.)
    states=[(0.,state.copy())]
    for t,kind in events:
        if kind=='reset' or w.value(t,'reset')>th or w.value(t,'enable')<=th:
            last,periods={},{}
            state=dict(freq_mhz=0.,divider_ratio=0.,valid=0.)
        else:
            if kind in last:
                periods[kind]=t-last[kind]
            last[kind]=t
            if 'dco' in periods:
                state['freq_mhz']=1e-6/periods['dco']
                if 'div' in periods:
                    state['divider_ratio']=periods['div']/periods['dco']
                    state['valid']=case.get('vhigh',1.)
        states.append((t,state.copy()))
    return pieces(w,case,states)

def search(w,case):
    requests=w.edges('request')
    ready=w.edges('ready')
    guard=case.get('guard',80e-12)
    states=[]
    state=dict(offset_est=0.,vinp=.5,vinn=.5,valid=0.,status=0.,request=0.)
    states.append((0.,state.copy()))
    failures=[]
    if not requests or abs(requests[0]-case['first_request'])>guard:
        failures.append(dict(kind='initial_request'))
    estimate=0.
    step=case.get('step_initial',.064)
    count=0
    for i,at in enumerate(requests):
        if i>=case['iterations']:
            failures.append(dict(kind='request_after_completion'))
            break
        state['request']=1.
        states.append((at,state.copy()))
        response=next((t for t in ready if t>at and (i+1==len(requests) or t<requests[i+1])),None)
        if response is None:
            timeout=at+case['timeout']
            if timeout>w.ts[-1]:
                failures.append(dict(kind='timeout_not_observed'))
            else:
                state.update(status=2.,request=0.,valid=0.)
                states.append((timeout,state.copy()))
            if i+1<len(requests):
                failures.append(dict(kind='advanced_without_response'))
            break
        if response-at>case['timeout']:
            failures.append(dict(kind='late_response_consumed'))
            break
        decision=w.value(response,'dcmpp')>.5
        estimate += -step if decision else step
        step *= .5
        count += 1
        state.update(offset_est=estimate,vinp=.5+.5*estimate,vinn=.5-.5*estimate,request=0.)
        if count==case['iterations']:
            state.update(status=1.,valid=1.)
        states.append((response,state.copy()))
        if count<case['iterations']:
            if i+1==len(requests):
                failures.append(dict(kind='missing_next_request'))
            elif abs(requests[i+1]-(response+case['gap']))>guard:
                failures.append(dict(kind='request_not_response_driven'))
    if len(requests)!=min(case['iterations'],count+int(count<case['iterations'])):
        failures.append(dict(kind='request_count'))
    result=pieces(w,case,states)
    result['failures']=(failures+result['failures'])[:20]
    result['passed']=not result['failures']
    result['updates']=count
    return result

def tdc(w,case):
    th=case.get('threshold',.5)
    high=case.get('vhigh',1.)
    events=[]
    for node in ['rst','start','stop','clk']:
        events.extend((t,node) for t in w.edges(node,threshold=th))
    order={'rst':0,'start':1,'stop':2,'clk':3}
    events.sort(key=lambda event:(event[0],order[event[1]]))
    count=0
    armed=False
    state={f'code_{i}':0. for i in range(8)}
    state.update(valid=0.,overflow=0.)
    states=[(0.,state.copy())]
    for at,kind in events:
        if kind=='rst' or w.value(at,'rst')>th:
            count=0
            armed=False
            state={f'code_{i}':0. for i in range(8)}
            state.update(valid=0.,overflow=0.)
        elif kind=='start':
            count=0
            armed=True
            state={f'code_{i}':0. for i in range(8)}
            state.update(valid=0.,overflow=0.)
        elif kind=='stop' and armed:
            state.update({f'code_{i}':high*((count>>i)&1) for i in range(8)})
            state['valid']=high
            armed=False
        elif kind=='clk' and armed:
            count+=1
            if count==256:
                state.update({f'code_{i}':high for i in range(8)})
                state.update(valid=high,overflow=high)
                armed=False
        states.append((at,state.copy()))
    return pieces(w,case,states)

def settling(w,case):
    state=dict(gain=0.,gain_valid=0.,settling_ns=0.,settled=0.,status=0.)
    states=[(0.,state.copy())]
    failures=[]
    launches=w.edges('launch')
    period=case['sample_period']
    count=case['samples']
    for i,start in enumerate(launches):
        end=start+count*period
        if end>w.ts[-1] or (i+1<len(launches) and launches[i+1]<end):
            failures.append(dict(kind='incomplete_window'))
            continue
        state=dict(gain=0.,gain_valid=0.,settling_ns=0.,settled=0.,status=0.)
        states.append((start,state.copy()))
        dx=w.value(end,'vin')-w.value(start,'vin')
        if abs(dx)<=case['min_input_span']:
            state['status']=2.
        else:
            static=w.value(end,'static_out')
            state['gain']=(static-w.value(start,'static_out'))/dx
            state['gain_valid']=1.
            observed=[w.value(start+j*period,'dynamic_out') for j in range(count+1)]
            bad=[j for j,x in enumerate(observed) if abs(x-static)>case['settle_tol']]
            last=bad[-1] if bad else -1
            if last<=count-case['tail_samples']:
                state.update(settled=1.,status=1.,settling_ns=(last+1)*period*case.get('time_scale',1e9))
            else:
                state.update(settled=0.,status=3.,settling_ns=0.)
        states.append((end,state.copy()))
    result=pieces(w,case,sorted(states))
    result['failures']=(failures+result['failures'])[:20]
    result['passed']=not result['failures']
    result['windows']=len(launches)
    return result

def por_digital(w,case):
    """Source-Verilog state oracle; digital boundary only, not POR acceptance."""
    events=[(t,'clock') for t in w.edges('clk',threshold=.9)]
    events += [(t,'reset') for t in w.edges('power',-1,threshold=.9)]
    for n in ['power','pdn','ena','dis','short','trip0','trip1','trip2']:
        events += [(t,'input') for t in w.edges(n,threshold=.9)]
        events += [(t,'input') for t in w.edges(n,-1,threshold=.9)]
    stage1=rsb=st=pc=0
    states=[]
    for t,kind in [(0.,'initial')]+sorted(events):
        if kind=='reset' or w.value(t,'power')<.9:
            stage1=rsb=st=pc=0
        elif kind=='clock':
            old_rsb,old_stage1,old_st,old_pc=rsb,stage1,st,pc
            stage1,rsb=1,old_stage1
            if not old_rsb: st=pc=0
            else:
                if old_st!=37: st=((old_st//8)*8+13)%64 if w.value(t,'short')>.9 else (old_st+1)%64
                if old_st==37 and old_pc!=1842:
                    pc=((old_pc//256)*256+306)%2048 if w.value(t,'short')>.9 else (old_pc+1)%2048
        trip=sum((1<<i)*int(w.value(t+1e-15,'trip'+str(i))>.9) for i in range(3))
        state={f'dec{i}':1.8*int(i==trip) for i in range(8)}
        state.update(pdnb=1.8*int(w.value(t+1e-15,'pdn')<.9),osc_ena=1.8*int(w.value(t+1e-15,'ena')>.9 or (w.value(t+1e-15,'dis')<.9 and w.value(t+1e-15,'power')>.9 and pc!=1842)),started=1.8*int(st==37),ended=1.8*int(pc==1842),por=1.8*int(st==37 and pc!=1842))
        states.append((t,state))
    return pieces(w,case,states)

def evaluate(rows, case, work=None):
    try:
        w = Wave(rows)
        if abs(w.ts[0]) > 1e-15 or abs(w.ts[-1]-case['stop']) > max(1e-15,case['stop']*1e-8):
            return dict(passed=False,status='environment_error',reason='incomplete transient')
        if case['kind'] == 'por_digital':
            return por_digital(w,case)
        if case['kind'] == 'settling':
            return settling(w,case)
        if case['kind'] == 'tdc':
            return tdc(w,case)
        if case['kind'] == 'search':
            return search(w,case)
        if case['kind'] == 'frequency':
            return frequency(w,case)
        if case['kind'] == 'gain':
            return gain(w,case)
        if case['kind'] == 'rms':
            return rms(w,case)
        if case['kind'] == 'duty':
            return duty(w,case)
        if case['kind'] == 'delay':
            return delay(w, case)
        if case['kind'] == 'hysteresis':
            return hysteresis(w, case)
        raise ValueError('unknown task kind')
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as exc:
        return dict(passed=False,status='environment_error',reason=str(exc))
