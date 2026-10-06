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
def run(times,step=2e-10):
    p=compile_sources({'dut.va':SOURCE},[Instance('dut','paper_vco',{n:n for n in ('ctl','freq','phase','out')},{})])
    return transient(p,{'ctl':[[0,-1],[2e-6,0],[4e-6,2],[6e-6,0],[8e-6,-1]]},[t*1e-6 for t in times],stop=8e-6,max_step=step,kernel=KERNEL,vabstol=1e-7,reltol=1e-5)
class InputClamp(unittest.TestCase):
    def test_original_vco_source_independent_phase_and_sine(self):
        times=[0,.6,1.2,1.6,2,2.6,3.2,3.7,4,4.8,5.2,6,6.4,6.8,7.4,8]
        result=run(times)
        self.assertEqual(set(result['nodes']),{'0','ctl','freq','phase','out'})
        for t,r in zip(times,result['solutions']):
            row=dict(zip(result['nodes'],r['voltages']))
            for n,want in zip(('freq','phase','out'),oracle(t)):self.assertAlmostEqual(row[n],want,delta=2e-8,msg=(t,n,row[n],want))
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
