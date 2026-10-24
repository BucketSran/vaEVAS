"""Physical source RN observations retain exact membership and true error bands."""
GUARDS = ['LANG', 'ANALOG', 'EVENT-ORDER', 'TIMED-OPERATOR', 'COMPOSE']
from fractions import Fraction as F
import math
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

class SourceRNObservation(unittest.TestCase):
    def run_source(self, prefix='', *, gain=1, errors=None, times=None):
        source=model(prefix+f' c=V(u,r); V(y,r)<+{gain}*c;', 'real c; integer q;')
        program=compile_sources({'source-rn-observation.va':source},[instance()])
        return transient(program,{'u':[[0,1],[1,math.nextafter(1,math.inf)]]},
            times or [0,.25,.5,.75,1],stop=1,max_step=.125,
            vabstol=1e-12,reltol=0,source_errors=errors,kernel=KERNEL)

    def check_ties(self, result, times):
        y=result['nodes'].index('y');u=result['nodes'].index('u')
        self.assertEqual(result['transient']['times'],times)
        self.assertEqual(len(result['solutions']),len(times))
        self.assertEqual(len(result['observation_evidence']['voltage_bounds_V']),len(times))
        for t,row,box in zip(times,result['solutions'],result['observation_evidence']['voltage_bounds_V']):
            exact=F(1)+F(t)*F(1,2**52)
            expected=1.0 if t<=.5 else math.nextafter(1,math.inf)
            self.assertEqual(row['voltages'][y].hex(),expected.hex())
            self.assertLessEqual(F(box[y][0]),F(expected));self.assertGreaterEqual(F(box[y][1]),F(expected))
            self.assertLessEqual(F(box[u][0]),exact);self.assertGreaterEqual(F(box[u][1]),exact)
            self.assertLessEqual(box[y][1]-box[y][0],2e-12)

    def test_branchless_source_sample_has_unique_rn_at_tie_and_both_neighbors(self):
        self.check_ties(self.run_source(),[0,.25,.5,.75,1])

    def test_ordinary_refresh_after_timer_uses_query_source_and_preserves_history(self):
        prefix='@(timer(0.125)) q=1;'
        sparse=[0,.25,.5,.75,1];dense=[i/16 for i in range(17)]
        a=self.run_source(prefix,times=sparse);b=self.run_source(prefix,times=dense)
        self.check_ties(a,sparse);self.check_ties(b,dense)
        for i,t in enumerate(sparse):self.assertEqual(a['solutions'][i],b['solutions'][dense.index(t)])
        self.assertEqual(a['transient']['events'],b['transient']['events'])

    def test_true_source_band_crossing_rn_cells_is_not_a_nominal_point_certificate(self):
        with self.assertRaises(KernelError) as caught:
            self.run_source(gain=2**40,errors={'u':1e-6})
        self.assertEqual(caught.exception.diagnostic['kind'],'waveform_accuracy')

class ProcedureForcingRoles(unittest.TestCase):
    def test_discarded_and_inactive_zero_output_reads_cannot_hide_in_procedure_metadata(self):
        import copy
        import test_source_polynomial_forcing as support
        helper=support.SourcePolynomialForcing('test_same_output_source_quadratic_plus_held_transition')
        base=helper.marked()
        self.assertTrue(helper.raw(copy.deepcopy(base))['solutions'])
        for inactive in (False,True):
            with self.subTest(inactive=inactive):
                p=copy.deepcopy(base);procedure=p['procedures'][0]
                origin=copy.deepcopy(p['contributions'][0]['origin'])
                binding=len(p['real_bindings'])
                p['real_bindings'].append(dict(procedure_id=procedure['procedure_id'],name='discarded_role',origin=origin,lifetime='occurrence'))
                ordinal=max(s['expanded_statement_ordinal'] for s in procedure['body'])+1
                value=dict(op='affine',constant=0,terms=[dict(node=p['nodes'].index('y'),coefficient=0)])
                step=dict(expanded_statement_ordinal=ordinal+int(inactive),action=dict(kind='real_bind',binding=binding,value=value,origin=origin))
                if inactive:
                    literal=lambda x:dict(op='affine',constant=x,terms=[])
                    step=dict(expanded_statement_ordinal=ordinal,action=dict(kind='procedure_if',relation='gt',left=literal(0),right=literal(1),then_body=[step],else_body=[],origin=origin))
                procedure['body'].append(step)
                with self.assertRaises(KernelError) as caught:helper.raw(p)
                self.assertEqual(caught.exception.diagnostic['kind'],'unsupported_forcing_scope')
