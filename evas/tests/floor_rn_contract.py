"""Independent source formulas for the eleven IR33 Floor migration cases.

This is a test checker, not an IR evaluator. It derives answers from the saved
VA text and exact PWL inputs. Every real source operation rounds separately;
physical interpolation and true crossing roots remain exact rationals.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'CROSS', 'COMPOSE']
from contextlib import contextmanager
from fractions import Fraction as Q
from pathlib import Path
from unittest.mock import patch
import json
import math
import re
import sys
from initial_record_contract import check_initial_record_batch

CAPTURE = None  # Optional read-only evidence callback used by the isolated runner.

class SourceFault(Exception):
    pass

def rn(value):
    try:
        answer = float(value)
    except OverflowError as error:
        raise SourceFault('executed real overflow') from error
    if not math.isfinite(answer):
        raise SourceFault('executed nonfinite real')
    return Q(answer)

def divide_floor(value):
    quotient = rn(rn(Q(value)) / Q(.9))
    product = rn(quotient * 15)
    shifted = rn(product + Q(.5))
    return shifted.numerator // shifted.denominator

def mul_floor(value, coefficient):
    product = rn(Q(coefficient) * rn(Q(value)))
    return product.numerator // product.denominator

def pwl(row, time):
    if time <= Q(row[0][0]):
        return Q(row[0][1])
    for (a, x), (b, y) in zip(row, row[1:]):
        if time <= Q(b):
            return Q(x) + (time-Q(a))*(Q(y)-Q(x))/(Q(b)-Q(a))
    return Q(row[-1][1])

def crossing_roots(row, level):
    roots = []
    for (a, x), (b, y) in zip(row, row[1:]):
        a,x,b,y = map(Q, (a,x,b,y))
        if x < level <= y:
            root = a+(level-x)*(b-a)/(y-x)
            if root not in roots:
                roots.append(root)
    return roots

def label(event):
    o = event['origin']
    return f"{o['source']}:{o['line']}:{o['column']} ({o['instance']})"

def finite_number(value):
    if type(value) not in (int,float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False

def check_physical_node(nominal, box, truth, source_error, controls):
    # Four independent duties: a finite, ordered full enclosure; complete
    # source truth inside it; the returned finite representative inside it;
    # and the original point/continuous-accuracy obligation. A wide box does
    # not make an unrelated representative a solution.
    assert finite_number(nominal), 'finite native voltage'
    assert len(box)==2 and all(finite_number(v) for v in box), 'finite fullbox'
    lo,hi=map(Q,box)
    assert lo<=hi, 'ordered fullbox'
    assert source_error>=0
    assert lo<=truth-source_error and truth+source_error<=hi, 'complete physical R enclosure'
    native=Q(nominal)
    assert lo<=native<=hi, 'native representative inside fullbox'
    if source_error==0 and Q(float(truth))==truth:
        # Every original held output and every exact PWL query point in the
        # eleven fixtures already has an exact binary64 point oracle.
        assert native==truth, 'original exact source/output point'
    else:
        absolute=controls.get('absolute',1e-9)
        relative=controls.get('relative',1e-6)
        assert finite_number(absolute) and absolute>0
        assert finite_number(relative) and relative>=0
        allowed=source_error+Q(absolute)+Q(relative)*max(abs(truth),abs(native))
        assert abs(native-truth)<=allowed, 'original continuous source tolerance'

class Expected:
    def __init__(self, case, source, request):
        self.case, self.source, self.request = case, source, request
        self.wire = json.loads(json.dumps(request['program']))
        self.text = ''.join(source.split())
        self.names = [s['name'] for s in self.wire['states']]
        self.owner = {s['instance'] for s in self.wire['states']}
        assert len(self.owner) == 1
        self.owner = next(iter(self.owner))
        self.seeds = [0] * len(self.names)
        assert [s['initial'] for s in self.wire['states']] == self.seeds
        assert self.wire['schema_version'] == 33
        self.held = dict.fromkeys(self.names, Q(0))
        self.fault = None
        errors = request['transient'].get('pwl_errors_v') or [0]*len(request['driven'])
        self.errors = dict(zip(request['driven'],map(Q,errors),strict=True))
        self.trace = []
        self._source_shape()
        assert self.owner == ('ring' if case=='ring' else 'dut')
        for state in self.wire['states']:
            expected_kind = ('integer' if state['name'] in ('n','j','code') else 'real') if case=='ring' else ('real' if case=='right' or state['name']=='lsb' or 'realq;' in self.text else 'integer')
            assert state['kind']==expected_kind, 'source declaration type'
        declared = self.wire['events']
        initial = [(i,e) for i,e in enumerate(declared) if e['trigger']['kind']=='initial_step']
        runtime = [(i,e) for i,e in enumerate(declared) if e['trigger']['kind']!='initial_step']
        assert len(initial) == len(runtime) == 1
        for _,event in initial + runtime:
            o = event['origin']
            assert o['instance'] == self.owner and not o.get('expansion')
            lines = source.splitlines()
            assert lines[o['line']-1][o['column']-1] == '@', 'original source event position'
        index,event = initial[0]
        if case == 'lsb':
            self.held['lsb'] = rn(Q(.9)/8)
        if case == 'ring':
            self.held['j'] = Q(self.width)
        self.trace.append((Q(0), index, self.seeds[:], self.vector()))
        self.initial_after = self.vector()
        index,event = runtime[0]
        if case in ('right', 'ring', 'phase') or '8*(V(u,r)-0.625)' in self.text:
            name = 'clk' if case == 'ring' else 'u'
            assert event['trigger']['kind'] == 'cross'
            self.roots = crossing_roots(self.input_row(name), Q(1,3) if case=='phase' else Q(.5))
        else:
            assert event['trigger']['kind'] == 'timer'
            assert Q(event['trigger']['start']) == Q(1,4)
            self.roots = [Q(1,4)]
        assert self.roots
        try:
            # A real source band is not a point proof, even when its nominal
            # happens to be at the same exact root as a positive case.
            for root in self.roots:
                if any(self.errors.values()):
                    if case != 'right' or self.errors.get('u',0) != 0:
                        raise SourceFault('true input band has no isolated source occurrence proof in these fixtures')
                    value=self.input_value('w',root);error=self.errors['w']
                    coefficient=3 if 'q=floor(3*V(w,r));' in self.text else 2
                    if mul_floor(value-error,coefficient)!=mul_floor(value+error,coefficient):
                        raise SourceFault('true input band crosses two Floor bins after complete source RN')
                before = self.vector()
                self._step(root)
                self.trace.append((root,index,before,self.vector()))
        except SourceFault as error:
            self.fault = str(error)

    def _source_shape(self):
        text = self.text
        if self.case == 'ring':
            found = re.search(r'reallevel\[0:(\d+)\]',text)
            assert found
            self.width = int(found.group(1))+1
            assert self.width == 32 and 'parameterrealrail=1;' in text
            assert 'code=floor(V(data)+0.5);' in text
            assert 'n=(n+1)%16;' in text
            assert 'level[j]=((n-j+32)%16<3)?rail:0;' in text
            assert set(self.names) == {'n','j','code',*(f'level[{i}]' for i in range(self.width))}
        elif self.case == 'right':
            assert set(self.names) == {'q','p'}
            assert 'q=floor(2*V(w,r));' in text or 'q=floor(3*V(w,r));' in text
            assert 'cross(V(u,r)-0.5,1)' in text
        elif self.case == 'phase':
            assert set(self.names)=={'q'}
            assert 'q=floor(-0.1*V(w,r));' in text and 'cross(3*V(u,r)-1,1)' in text
            assert self.input_row('u')==[[0,0],[1,1]] and self.input_row('w')==[[0,0],[1,30]]
        elif self.case == 'lsb':
            assert set(self.names) == {'lsb','q'}
            assert 'lsb=0.9/8.0;' in text and 'q=floor(V(u,r)/lsb);' in text
        else:
            assert set(self.names) == {'q'}
            if self.case == 'native':
                assert 'floor(8*V(u,r))' in text or 'floor(8*(V(u,r)-0.625))' in text
            elif self.case == 'source':
                assert any(s in text for s in ('floor((V(u,r)/0.9)*15+0.5)', 'floor(0.1*V(u,r))', 'floor(V(u,r)/3)'))
            else:
                raise AssertionError(self.case)

    def input_row(self, name):
        return self.request['transient']['pwl'][self.request['driven'].index(name)]

    def input_value(self, name, root):
        return pwl(self.input_row(name),root)

    def vector(self):
        return [float(self.held[n]) for n in self.names]

    def store(self, name, value):
        value = rn(Q(value))
        state = self.wire['states'][self.names.index(name)]
        if state['kind'] == 'integer' and (value.denominator != 1 or not -2**31 <= value < 2**31):
            raise SourceFault('first executed typed store exceeds signed32')
        self.held[name] = value

    def _step(self, root):
        t = self.text
        if self.case == 'ring':
            k = rn(rn(self.input_value('data',root))+Q(.5))
            self.store('code',k.numerator//k.denominator)
            self.store('code',min(15,max(0,self.held['code'])))
            self.store('n',(int(self.held['n'])+1)%16)
            for j in range(self.width):
                self.store(f'level[{j}]',int((int(self.held['n'])-j+32)%16<3))
            self.store('j',self.width)
            return
        if self.case == 'right':
            coefficient = 3 if 'q=floor(3*V(w,r));' in t else 2
            self.store('q',mul_floor(self.input_value('w',root),coefficient))
            match = re.search(r'if\(q(<=|>=|<|>)1\)p=2;elsep=3;',t)
            assert match
            q = self.held['q']
            yes = {'<':q<1,'<=':q<=1,'>':q>1,'>=':q>=1}[match.group(1)]
            self.store('p',2 if yes else 3)
            return
        if self.case == 'phase':
            self.store('q',mul_floor(self.input_value('w',root),-.1))
            return
        value = self.input_value('u',root)
        if self.case == 'native':
            if '8*(V(u,r)-0.625)' in t:
                k = rn(8*rn(rn(value)-Q(.625)))
                k = k.numerator//k.denominator
            else:
                k = mul_floor(value,8)
            if 'floor(8*V(u,r))/2' in t:
                k = rn(Q(k)/2)
        elif self.case == 'lsb':
            self.store('lsb',rn(Q(.9)/8))
            k = rn(rn(value)/self.held['lsb'])
            k = k.numerator//k.denominator
        elif 'floor(V(u,r)/3)' in t:
            k = rn(rn(value)/3)
            k = k.numerator//k.denominator
            if 'floor(V(u,r)/3)/2' in t:
                k = rn(Q(k)/2)
        elif 'floor(0.1*V(u,r))' in t:
            k = mul_floor(value,.1)
        else:
            k = divide_floor(value)
            if 'pow(floor(' in t:
                k = rn(Q(k)*k)
            if 'if(floor(' in t:
                k = 7 if k<1 else 8
        self.store('q',k)  # Must fail here before a later clamp can erase it.
        if 'if(q<0)q=0;' in t:
            self.store('q',max(0,self.held['q']))
        if 'if(q>7)q=7;' in t:
            self.store('q',min(7,self.held['q']))

    def values_at(self, time):
        held = dict(zip(self.names,self.seeds))
        last = None
        for root,_,_,after in self.trace:
            if root <= time:
                held = dict(zip(self.names,map(Q,after)))
                last = root
        values = {'0':Q(0)}
        values.update({n:pwl(row,time) for n,row in zip(self.request['driven'],self.request['transient']['pwl'])})
        if self.case == 'ring':
            assert time == 0 or last is not None and time >= last+Q(.01), 'these original queries are after the complete ramp'
            values['bit0'] = Q(int(held['code']) & 1)
            values.update({f'y{i}':held[f'level[{i}]'] for i in range(self.width)})
        else:
            out = held['p'] if self.case=='right' else held['q']
            if 'V(y,r)<+(q<2?0:1);' in self.text:
                out = Q(0 if out<2 else 1)
            values['y'] = Q(out)
        return held,values

    def check(self, result):
        assert self.fault is None, ('runtime accepted a source-domain fault',self.fault)
        assert result['schema_version'] == 33
        assert result['nodes'] == self.wire['nodes']
        tr = result['transient']
        assert tr['times'] == self.request['transient']['output_times']
        assert tr['state_names'] == [f"{s['instance']}:{s['name']}" for s in self.wire['states']]
        # Reuse the independently reviewed initial checker, retaining raw
        # records for all numerical/source checks below. Never filter t0.
        check_initial_record_batch(result,self.wire,self.seeds,self.initial_after,1)
        actual = tr['events']
        assert len(actual) == len(self.trace)
        for rec,(root,index,before,after) in zip(actual,self.trace,strict=True):
            event = self.wire['events'][index]
            assert type(rec['event']) is int and rec['event']==index
            assert rec['kind']==event['trigger']['kind'] and rec['origin']==label(event)
            lo,hi=map(Q,rec.get('observation_time_bounds',[rec['time'],rec['time']]))
            assert lo<=root<=hi and lo<=Q(rec['time'])<=hi, 'actual source occurrence must be enclosed'
            if event['trigger']['kind']=='cross':
                assert abs(Q(rec['time'])-root)<=Q(event['trigger']['time_tolerance'])
                name='clk' if self.case=='ring' else 'u'
                scale,level=(3,Q(1)) if self.case=='phase' else (1,Q(.5))
                guard_lo=scale*self.input_value(name,lo)-level
                guard_hi=scale*self.input_value(name,hi)-level
                assert guard_lo<=Q(rec['guard_value'])<=guard_hi, 'guard uses the original physical root window'
                for fired in rec.get('fired_triggers',[]):
                    assert fired['trigger']==0 and fired.get('kind','cross')=='cross'
                    a,b=map(Q,fired.get('time_bounds',[lo,hi]))
                    assert a<=root<=b
                    assert scale*self.input_value(name,a)-level<=Q(fired['guard_value'])<=scale*self.input_value(name,b)-level
            elif event['trigger']['kind']=='timer':
                assert Q(rec['time'])==root and 'guard_value' not in rec
                assert not rec.get('fired_triggers')
            assert rec['before']==before and rec['after']==after
            assert not rec.get('display_records') and not rec.get('displays'), 'these original VA cases have no display'
        for time,states,sol,box in zip(tr['times'],tr['states'],result['solutions'],result['observation_evidence']['voltage_bounds_V'],strict=True):
            held,values=self.values_at(Q(time))
            assert states==[float(held[n]) for n in self.names]
            assert set(values)==set(result['nodes'])
            assert len(box)==len(sol['voltages'])==len(result['nodes'])
            for i,name in enumerate(result['nodes']):
                error=self.errors.get(name,Q(0))
                check_physical_node(sol['voltages'][i],box[i],values[name],error,self.request.get('tolerances',{}))
            assert sol['max_residual_ratio']<=1
        return result

    def evidence(self):
        return {'case':self.case,'source_fault':self.fault,'seeds':self.seeds,'trace':[{'exact_time':str(t),'event':i,'before':b,'after':a} for t,i,b,a in self.trace],
                'root_vs_output_box':'Exact rational occurrence roots certify source answers; outward f64 output boxes need only enclose the corresponding physical truth, not prove uniqueness over their entire hull.'}

@contextmanager
def floor_contract(test, case):
    """Check raw public responses without materializing the Program twice."""
    module = sys.modules[test.__class__.__module__]
    original_compile = module.compile_sources
    import evas.runtime as runtime
    original_invoke = runtime._invoke
    sources = {}
    def compile_capture(source,*args,**kwargs):
        result=original_compile(source,*args,**kwargs)
        sources.update(source)
        return result
    def invoke(request,kernel,*args,**kwargs):
        origins={event['origin']['source'] for event in request['program']['events']}
        assert len(origins)==1
        name=next(iter(origins));assert name in sources
        expected=Expected(case,sources[name],request)
        if CAPTURE is not None:CAPTURE('expected',expected,request,None)
        try:answer=original_invoke(request,Path(kernel).resolve(),*args,**kwargs)
        except Exception as error:
            if CAPTURE is not None:CAPTURE('diagnostic',expected,request,error)
            raise
        expected.check(answer)
        if CAPTURE is not None:CAPTURE('response',expected,request,answer)
        return answer
    with patch.object(module,'compile_sources',compile_capture),patch.object(runtime,'_invoke',invoke):
        yield
