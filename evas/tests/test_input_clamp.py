"""Input-derived clipping: independent piecewise-area public Rust contracts."""
from fractions import Fraction as F
import math
import copy
import json
import subprocess
from pathlib import Path
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, model
GUARDS = ['DYNAMICS','COMPOSE']
SOURCE=Path(__file__).with_name('fixtures').joinpath('input_clamp_vco.va').read_text()
# Independent decimal piecewise oracle, not the lowering root calculation.
POINTS=[(F(0),F('0.2')),(F('1.2'),F('0.2')),(F(2),F('0.4')),
        (F('3.2'),F(1)),(F('4.8'),F(1)),(F(6),F('0.4')),
        (F('6.8'),F('0.2')),(F(8),F('0.2'))]
def oracle(t):
    t=F(str(t));area=F('0.125');freq=None
    for (a,u),(b,v) in zip(POINTS,POINTS[1:]):
        if t>=a:
            x=min(t,b)-a; slope=(v-u)/(b-a)
            area+=u*x+slope*x*x/2
            if t<=b:freq=u+slope*x;break
    phase=float(area%1)
    return float(freq),phase,math.sin(2*math.pi*phase)
def binary_phase_oracle(program,inputs,time):
    binary=lambda x:F.from_float(float(x))
    operator=next(o for o in program['operators'] if o['kind']=='idt_mod')
    sources={program['nodes'].index(n):[(binary(t),binary(v)) for t,v in points] for n,points in inputs.items()}
    def source(n,t):
        if n==0:return F(0)
        for (a,x),(b,y) in zip(sources[n],sources[n][1:]):
            if a<=t<=b:return x+(y-x)*(t-a)/(b-a)
        raise AssertionError('query outside source')
    def evaluate(e,t):
        if e['op']=='affine':return binary(e['constant'])+sum(binary(q['coefficient'])*source(q['node'],t) for q in e['terms'])
        a=evaluate(e['left'],t);b=evaluate(e['right'],t)
        if e['op']=='add':return a+b
        if e['op']=='multiply':return a*b
        raise AssertionError('unexpected affine expression')
    expr=operator['input'];scale=F(1)
    while expr['op']=='multiply':
        left,right=expr['left'],expr['right']
        if left['op']=='affine' and not left['terms']:scale*=binary(left['constant']);expr=right
        else:scale*=binary(right['constant']);expr=left
    lo=binary(expr['right']['constant']);hi=binary(expr['else_value']['right']['constant']);base=expr['left']
    t=binary(time);total=binary(operator['ic']);knots=sorted({t for points in sources.values() for t,v in points})
    for start,end in zip(knots,knots[1:]):
        if t<=start:break
        stop=min(t,end);a,b=evaluate(base,start),evaluate(base,end);cuts=[start,stop]
        if a!=b:
            for threshold in [lo,hi]:
                root=start+(threshold-a)*(end-start)/(b-a)
                if start<root<stop:cuts.append(root)
        cuts.sort()
        def clipped(t):return min(hi,max(lo,a+(b-a)*(t-start)/(end-start)))
        total+=scale*sum((clipped(a)+clipped(b))*(b-a)/2 for a,b in zip(cuts,cuts[1:]))
    offset=binary(operator['offset']);modulus=binary(operator['modulus'])
    return offset+(total-offset)%modulus

def run(times,step=2e-10):
    p=compile_sources({'dut.va':SOURCE},[Instance('dut','paper_vco',{n:n for n in ('ctl','freq','phase','out')},{})])
    return transient(p,{'ctl':[[0,-1],[2e-6,0],[4e-6,2],[6e-6,0],[8e-6,-1]]},[t*1e-6 for t in times],stop=8e-6,max_step=step,kernel=KERNEL,vabstol=1e-7,reltol=1e-5)
class InputClamp(unittest.TestCase):
    def test_cancelled_clamp_does_not_expand_direct_phase_certification(self):
        for extra in ['', '+0.0*f', '+(f-f)']:
            with self.subTest(extra=extra):
                source=model('f=V(u); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; '
                             'V(y,r)<+idtmod(V(u)/3'+extra+',0.125,1,0);',declarations='real f;')
                program=compile_sources({'cancel.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'},{})])
                with self.assertRaises(KernelError) as error:
                    transient(program,{'u':[[0,1.5],[2,1.5]]},[1.7499999999999998],
                              stop=2,max_step=.125,kernel=KERNEL,vabstol=1e-12,reltol=1e-12)
                self.assertIn('waveform_accuracy',str(error.exception))

    def test_two_instances_certify_distinct_sides_at_same_wrap_time(self):
        source=model('f=V(u); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; '
                     'V(y,r)<+idtmod(f,initial,1,0);',
                     declarations='parameter real initial=0.5; real f;')
        lower_ic=math.nextafter(.5,0)
        program=compile_sources({'instances.va':source},[
            Instance('A','m',{'u':'a','y':'pa','r':'0'},{'initial':.5}),
            Instance('B','m',{'u':'b','y':'pb','r':'0'},{'initial':lower_ic})])
        inputs={name:[[0,-.25],[1,1.25],[2,1.25]] for name in ('a','b')}
        # Symmetry makes the exact area 1/2 despite roots at 1/3 and 2/3.
        # A lands on the lower endpoint; B is strictly below the upper one.
        result=transient(program,inputs,[1],stop=2,max_step=.125,kernel=KERNEL,
                         vabstol=1e-12,reltol=1e-12)
        row=dict(zip(result['nodes'],result['solutions'][0]['voltages']))
        self.assertEqual(row['pa'],0)
        self.assertGreater(row['pb'],.99)
        self.assertLess(row['pb'],1)
        exact=F(1,2)+F.from_float(lower_ic)
        self.assertLessEqual(abs(F.from_float(row['pb'])-exact),F(1,2**53))

    def test_original_vco_source_independent_phase_and_sine(self):
        times=[0,.6,1.2,1.6,2,2.6,3.2,3.7,4,4.8,5.2,6,6.4,6.8,7.4,8]
        result=run(times)
        self.assertEqual(set(result['nodes']),{'0','ctl','freq','phase','out'})
        for t,r in zip(times,result['solutions']):
            row=dict(zip(result['nodes'],r['voltages']))
            for n,want in zip(('freq','phase','out'),oracle(t)):self.assertAlmostEqual(row[n],want,delta=2e-8,msg=(t,n,row[n],want))
    def test_original_four_wrap_centers_keep_exact_binary64_side(self):
        # Fraction oracle integrates original binary64 sources/IR before any
        # rounded clamp roots. Decimal engineering oracle remains separate.
        times=[2.689966442575134e-6,3.755e-6,4.754999999999999e-6,6.31937515251343e-6]
        program=compile_sources({'dut.va':SOURCE},[Instance('dut','paper_vco',{n:n for n in ('ctl','freq','phase','out')},{})])
        inputs={'ctl':[[0,-1],[2e-6,0],[4e-6,2],[6e-6,0],[8e-6,-1]]}
        expected=[binary_phase_oracle(program.to_dict(),inputs,t) for t in times]
        self.assertEqual([x<F(1,2) for x in expected],[True,True,False,True])
        for time,want in zip(times,expected):
            result=transient(program,inputs,[time],stop=8e-6,max_step=1e-6,kernel=KERNEL,vabstol=1e-7,reltol=1e-5)
            row=result['solutions'][0]
            value=row['voltages'][result['nodes'].index('phase')]
            self.assertAlmostEqual(value,float(want),delta=2e-15)
            self.assertAlmostEqual(row['voltages'][result['nodes'].index('out')],
                                   math.sin(2*math.pi*float(want)),delta=2e-14)

    def test_rational_clamp_roots_equality_sides_negative_phase_and_offset(self):
        for ic,offset in [(.5,0),(0,-.5),(-.5,0)]:
            source=model(f'f=V(u); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; V(y,r)<+idtmod(f,{ic},1,{offset});',declarations='real f;')
            program=compile_sources({'rational.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'},{})])
            inputs={'u':[[0,-.25],[1,1.25],[2,1.25]]}
            times=[math.nextafter(1,0),1,math.nextafter(1,2)]
            sparse=transient(program,inputs,times,stop=2,max_step=.5,kernel=KERNEL,vabstol=1e-12,reltol=1e-12)
            dense=transient(program,inputs,[0,.2,.6]+times+[1.5,2],stop=2,max_step=.125,kernel=KERNEL,vabstol=1e-12,reltol=1e-12)
            for i,t in enumerate(times):
                exact=binary_phase_oracle(program.to_dict(),inputs,t)
                value=sparse['solutions'][i]['voltages'][sparse['nodes'].index('y')]
                self.assertAlmostEqual(value,float(exact),delta=2e-15)
                self.assertGreaterEqual(value,offset)
                self.assertLess(value,offset+1)
                self.assertEqual(value,dense['solutions'][i+3]['voltages'][dense['nodes'].index('y')])
            self.assertEqual(sparse['solutions'][1]['voltages'][sparse['nodes'].index('y')],offset)

    def test_unaligned_original_source_knots_preserve_affine_correlation(self):
        source=model('f=V(u)+0.5*V(x); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; V(y,r)<+idtmod(f,0.5,1,0);',declarations='real f;')
        source=source.replace('module m(u,y,r);','module m(u,x,y,r);').replace('electrical u,y,r;','electrical u,x,y,r;').replace('input u;','input u,x;')
        program=compile_sources({'unaligned.va':source},[Instance('dut','m',{'u':'u','x':'x','y':'y','r':'0'},{})])
        inputs={'u':[[0,-.25],[1,1.25],[2,1.25]],'x':[[0,-.125],[.3,.25],[.7,-.25],[1,.125],[2,.125]]}
        times=[math.nextafter(1,0),1,math.nextafter(1,2)]
        result=transient(program,inputs,times,stop=2,max_step=.125,kernel=KERNEL,vabstol=1e-12,reltol=1e-12)
        for row,t in zip(result['solutions'],times):
            want=binary_phase_oracle(program.to_dict(),inputs,t)
            self.assertAlmostEqual(row['voltages'][result['nodes'].index('y')],float(want),delta=2e-15)

    def test_observation_grid_and_step_do_not_reintegrate(self):
        sparse=run([0,2,4,6,8],1e-6);dense=run([i/10 for i in range(81)],2e-7)
        for a,b in zip(sparse['solutions'],dense['solutions'][::20]):
            for x,y in zip(a['voltages'],b['voltages']):self.assertAlmostEqual(x,y,delta=2e-9)
    def test_discontinuous_select_remains_rejected(self):
        s=model('f=V(u); if(f<0.5) f=0; else f=1; V(y,r)<+idtmod(f,0,1,0);',declarations='real f;')
        p=compile_sources({'bad.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'},{})])
        with self.assertRaises(KernelError):transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=.1,kernel=KERNEL)

    def test_two_instances_keep_independent_input_histories_and_ties(self):
        source=model('f=V(u); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; V(y,r)<+idtmod(f,0,10,0);',declarations='real f;')
        p=compile_sources({'clamp.va':source},[Instance('A','m',{'u':'a','y':'pa','r':'0'},{}),Instance('B','m',{'u':'b','y':'pb','r':'0'},{})])
        result=transient(p,{'a':[[0,0],[1,1]],'b':[[0,1],[1,0]]},[0,.25,.5,.75,1],stop=1,max_step=.125,kernel=KERNEL)
        want_a=[0,.0625,.15625,.3125,.5]
        want_b=[0,.1875,.34375,.4375,.5]
        for row,a,b in zip(result['solutions'],want_a,want_b):
            values=dict(zip(result['nodes'],row['voltages']))
            self.assertAlmostEqual(values['pa'],a,delta=2e-10)
            self.assertAlmostEqual(values['pb'],b,delta=2e-10)
        self.assertEqual(set(result['nodes']),{'0','a','b','pa','pb'})
    def test_hidden_internal_dependency_remains_rejected(self):
        source=model('f=V(u)+0*V(y,r); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; V(y,r)<+idtmod(f,0,10,0);',declarations='real f;',directions='input u; inout y,r;')
        p=compile_sources({'feedback.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'},{})])
        with self.assertRaises(KernelError):transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=.125,kernel=KERNEL)
    def test_event_composition_outside_scope_stays_rejected(self):
        source=model('@(initial_step) q=0; @(timer(0.5)) q=1; f=V(u); if(f<0.25) f=0.25; else if(f>0.75) f=0.75; V(y,r)<+idtmod(f,0,10,0)+q;',declarations='real f,q;')
        # This event composition is rejected by the existing frontend first.
        # The separate raw-IR Rust control covers persistent-state rejection
        # and unchanged inputs on failure; it is not an event raw-IR control.
        with self.assertRaises((CompileError,KernelError)):
            p=compile_sources({'event.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'},{})])
            transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=.125,kernel=KERNEL)

    def test_upper_first_and_inclusive_clamps_preserve_boundary_values(self):
        for conditions in (
            'if(f>0.75) f=0.75; else if(f<0.25) f=0.25;',
            'if(f<=0.25) f=0.25; else if(f>=0.75) f=0.75;',
        ):
            with self.subTest(conditions=conditions):
                source=model('f=V(u); '+conditions+' V(y,r)<+idtmod(f,0,10,0);',declarations='real f;')
                p=compile_sources({'ties.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'},{})])
                result=transient(p,{'u':[[0,0],[1,1]]},[0,.25,.5,.75,1],stop=1,max_step=.125,kernel=KERNEL)
                for row,want in zip(result['solutions'],[0,.0625,.15625,.3125,.5]):
                    self.assertAlmostEqual(row['voltages'][result['nodes'].index('y')],want,delta=2e-10)

    def test_original_invalid_branch_endpoint_cannot_become_hidden_node(self):
        program=compile_sources({'dut.va':SOURCE},[Instance('dut','paper_vco',{n:n for n in ('ctl','freq','phase','out')},{})]).to_dict()
        program=json.loads(json.dumps(program))
        malformed=copy.deepcopy(program['contributions'][0])
        malformed['branch']['local_negative']='ghost'
        malformed['negative']=len(program['nodes'])
        program['contributions'].append(malformed)
        request=dict(program=program,driven=['ctl'],samples=[],
                     transient=dict(pwl=[[[0,-1],[2e-6,0],[4e-6,2],[6e-6,0],[8e-6,-1]]],
                                    output_times=[0,8e-6],stop=8e-6,max_step=1e-6),
                     tolerances=dict(absolute=1e-7,relative=1e-5))
        # Raw public-kernel IR boundary: index n is invalid in the original
        # program even when clamp lowering subsequently appends node n.
        result=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,
                              capture_output=True,timeout=90)
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertEqual(json.loads(result.stderr)['kind'],'invalid_ir')
