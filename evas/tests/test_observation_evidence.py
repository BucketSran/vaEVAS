"""Actual kernel observation evidence; transport validation does not grant qualification."""
import copy
import math
import unittest
from evas import KernelError, transient
from evas.protocol import validate_response
from test_affine import KERNEL, instance, model
from evas import compile_sources


class ObservationEvidence(unittest.TestCase):
    def test_stateless_reports_actual_controls_and_working_point_origin(self):
        program=compile_sources({'test.va':model('V(y,r)<+2*V(u,r);')},[instance()])
        result=transient(program,{'u':[[0,0],[1,1]]},[0,0.5,1],stop=1,max_step=0.25,
                         vabstol=2e-7,reltol=3e-6,kernel=KERNEL)
        evidence=result['observation_evidence']
        self.assertEqual(evidence['schema_version'],1)
        self.assertEqual(evidence['nodes'],result['nodes'])
        self.assertEqual(evidence['effective_controls'],dict(absolute_V=2e-7,relative=3e-6,stop_s=1,max_step_s=0.25,max_step_applied=False))
        self.assertEqual(evidence['sample_origins'],['stateless_working_point']*3)
        self.assertTrue(evidence['initial_settled'])
        self.assertEqual([r['voltages'][result['nodes'].index('y')] for r in result['solutions']],[0,1,2])
        bounds=evidence['voltage_bounds_V']
        self.assertEqual(len(bounds),3)
        for expected,row in zip([0,1,2],bounds):
            lo,hi=row[result['nodes'].index('y')]
            self.assertLessEqual(lo,expected);self.assertGreaterEqual(hi,expected)

    def test_optional_response_validation_preserves_old_and_rejects_invalid_bounds(self):
        program=compile_sources({'test.va':model('V(y,r)<+2*V(u,r);')},[instance()])
        result=transient(program,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=0.25,kernel=KERNEL)
        old=copy.deepcopy(result);old.pop('observation_evidence')
        self.assertEqual(validate_response(old,program,2,[0,1]),old)
        mutants=[]
        for change in (lambda e:e.update(schema_version=2), lambda e:e.update(nodes=list(reversed(result['nodes']))),
                       lambda e:e.update(sample_origins=['accepted_controller_frame']),
                       lambda e:e.update(initial_settled='true'),
                       lambda e:e['effective_controls'].update(max_step_applied=1),
                       lambda e:e['effective_controls'].update(absolute_V=-1)):
            bad=copy.deepcopy(result);change(bad['observation_evidence']);mutants.append(bad)
        for interval in ([1,-1],[float('inf'),2],[0],[-2,-1]):
            bad=copy.deepcopy(result);bad['observation_evidence']['voltage_bounds_V'][0][result['nodes'].index('y')]=interval
            mutants.append(bad)
        for bad in mutants:
            with self.subTest(evidence=bad['observation_evidence']),self.assertRaisesRegex(KernelError,'invalid_response'):
                validate_response(bad,program,2,[0,1])
        # A broad genuine enclosure is valid transport, but cannot certify a
        # 50 uV observation. The protocol must not silently tighten it.
        broad=copy.deepcopy(result)
        broad['observation_evidence']['voltage_bounds_V'][0][result['nodes'].index('y')]=[-0.01,0.01]
        self.assertEqual(validate_response(broad,program,2,[0,1]),broad)
        missing=copy.deepcopy(result)
        missing['observation_evidence']['voltage_bounds_V'][0]=None
        self.assertEqual(validate_response(missing,program,2,[0,1]),missing)

    def test_event_sample_exposes_history_error_after_amplification(self):
        program=compile_sources({'test.va':model(
            '@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-6,1e-5)) q=V(u,r); '
            'V(y,r)<+1e6*q;', 'real q;')},[instance()])
        result=transient(program,{'u':[[0,0],[2,2]]},[0,1,1.75,2],stop=2,max_step=0.5,
                         vabstol=10,reltol=0,kernel=KERNEL)
        evidence=result['observation_evidence']
        self.assertTrue(evidence['effective_controls']['max_step_applied'])
        self.assertTrue(evidence['initial_settled'])
        self.assertEqual(evidence['sample_origins'],['accepted_controller_frame']*4)
        lo,hi=evidence['voltage_bounds_V'][-1][result['nodes'].index('y')]
        self.assertGreater(hi,lo)
        self.assertLessEqual(lo,1e6*math.sqrt(2));self.assertGreaterEqual(hi,1e6*math.sqrt(2))
        # This uncertainty is real history/input uncertainty. A perfect residual
        # cannot be used to replace it with a fabricated zero-width enclosure.
        self.assertEqual(result['solutions'][-1]['max_residual_v'],0)

    def test_causal_frame_keeps_distinct_physical_timer_phases(self):
        # binary64 0.3 precedes the exact binary64 sum 0.1+0.2. The controller
        # publishes both requested phases after closing the overlapping cluster.
        program=compile_sources({'test.va':model(
            '@(initial_step) begin a=0; b=0; end @(timer(0.3,0,1e-6)) a=1; '
            '@(timer(0.1,0.2,1e-6)) b=b+1; V(y,r)<+a+10*b;', 'integer a,b;')},[instance()])
        times=[0,0.3,0.30000000000000004,1]
        result=transient(program,{'u':[[0,0],[1,0]]},times,stop=1,max_step=1,kernel=KERNEL)
        evidence=result['observation_evidence']
        self.assertEqual(evidence['sample_origins'][1:3],['certified_causal_frame']*2)
        column=result['nodes'].index('y')
        self.assertEqual([row['voltages'][column] for row in result['solutions']],[0,11,21,51])
        for expected,row in zip([0,11,21,51],evidence['voltage_bounds_V']):
            self.assertLessEqual(row[column][0],expected);self.assertGreaterEqual(row[column][1],expected)
        sparse=transient(program,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['events'],sparse['transient']['events'])
        self.assertEqual(result['solutions'][-1],sparse['solutions'][-1])

    def test_implicit_history_returns_existing_enclosure_without_claiming_max_step(self):
        # y+y^2=z, z'=1+2y, z(0)=0 implies y=t on the initial y=0 branch.
        program=compile_sources({'test.va':model('V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);')},[instance()])
        times=[0,0.125,0.5,1]
        result=transient(program,{'u':[[0,0],[1,0]]},times,stop=1,max_step=0.125,
                         vabstol=1e-9,reltol=0,kernel=KERNEL)
        evidence=result['observation_evidence']
        self.assertEqual(evidence['sample_origins'],['implicit_history_evaluation']*4)
        self.assertFalse(evidence['effective_controls']['max_step_applied'])
        for expected,row in zip(times,evidence['voltage_bounds_V']):
            lo,hi=row[result['nodes'].index('y')]
            self.assertLessEqual(lo,expected);self.assertGreaterEqual(hi,expected)

    def test_near_zero_output_keeps_the_actual_absolute_error_enclosure(self):
        program=compile_sources({'test.va':model('V(y,r)<+1e6*(V(u,r)-0.5);')},[instance()])
        result=transient(program,{'u':[[0,0.2],[1,0.8]]},[0,0.5,1],stop=1,max_step=1,
                         vabstol=1e-7,reltol=1e-5,kernel=KERNEL)
        evidence=result['observation_evidence'];column=result['nodes'].index('y')
        lo,hi=evidence['voltage_bounds_V'][1][column]
        # Exact binary64 endpoint PWL at 0.5 is not exactly 0.5. Compute its
        # mathematical midpoint independently as a rational, including gain.
        from fractions import Fraction as F
        exact=10**6*((F(0.2)+F(0.8))/2-F(0.5))
        self.assertLessEqual(F(lo),exact);self.assertGreaterEqual(F(hi),exact)
        self.assertLess(hi-lo,1e-7)

    def test_unexported_nonlinear_certificate_stays_missing(self):
        program=compile_sources({'test.va':model('V(y,r)<+pow(V(u,r),2);')},[instance()])
        result=transient(program,{'u':[[0,0],[1,1]]},[0,0.5,1],stop=1,max_step=0.25,kernel=KERNEL)
        evidence=result['observation_evidence']
        self.assertEqual(evidence['voltage_bounds_V'],[None,None,None])
        self.assertEqual(evidence['sample_origins'],['stateless_working_point']*3)
        self.assertEqual(result['solutions'][1]['voltages'][result['nodes'].index('y')],0.25)
        without_zero=transient(program,{'u':[[0,0],[1,1]]},[0.5,1],stop=1,max_step=0.25,kernel=KERNEL)
        self.assertNotIn('initial_settled',without_zero['observation_evidence'])

    def test_phase_and_sine_bounds_remain_aligned_after_internal_node_lowering(self):
        source=model('p=idtmod(V(u,r),0.25,1,0); V(phase,r)<+p; V(y,r)<+sin(6.283185307179586*p);',
                     'real p;',ports='u,y,phase,r',directions='input u; output y,phase; inout r;')
        program=compile_sources({'test.va':source},[instance(connections=dict(u='u',y='y',phase='phase',r='0'))])
        result=transient(program,{'u':[[0,1],[1,1]]},[0,0.125,0.5,1],stop=1,max_step=0.25,kernel=KERNEL)
        evidence=result['observation_evidence']
        self.assertEqual(evidence['nodes'],list(program.nodes))
        phase=result['nodes'].index('phase');out=result['nodes'].index('y')
        for expected,row in zip([0.25,0.375,0.75,0.25],evidence['voltage_bounds_V']):
            self.assertEqual(len(row),len(program.nodes))
            self.assertLessEqual(row[phase][0],expected);self.assertGreaterEqual(row[phase][1],expected)
            sine=math.sin(2*math.pi*expected)
            self.assertLessEqual(row[out][0],sine);self.assertGreaterEqual(row[out][1],sine)

if __name__=='__main__':unittest.main()
