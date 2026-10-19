"""Exact oracle derives from original binary64 leaves, never kernel proof output."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'COMPOSE', 'TRANSITION']
from fractions import Fraction as Q
import json
from pathlib import Path
import unittest
from test_affine import KERNEL
from evas import Instance, KernelError, compile_sources, transient

# The PWL segment is defined by binary64(0.2), not the decimal rational1/5.
def u(time):
    return Q(0.2)*Q(time)/Q(2.)

SAMPLED = u(0.25)+Q(0.25)
THRESHOLD = Q(0.125)
SPARSE = [0.,0.25,0.375,0.5,0.625,0.75,1.5,2.]
DENSE = [0.,0.125,0.25,0.3125,0.375,0.5,0.5625,0.625,0.6875,0.75,1.,1.25,1.375,1.5,1.75,2.]

def expected(time):
    t=Q(time)
    q=SAMPLED if t>=Q(0.25) else Q(0)
    z=SAMPLED*max(Q(0),min(Q(1),(t-Q(0.25))/Q(0.125)))
    w=max(Q(0),min(Q(1),(t-Q(0.5))/Q(0.25)))
    return {'y':float(q-u(time)>THRESHOLD),'h':float(q),'z':float(z),'w':float(w)}

class ProvenLineagePointQuery(unittest.TestCase):
    def program(self):
        source=Path(__file__).with_name('fixtures').joinpath('proven-lineage-point-query.va').read_text()
        return compile_sources({'proven-lineage-point-query.va':source},
            [Instance('dut','proven_lineage',{n:n for n in ('u','y','z','h','w')})])

    def run_case(self,times,*,errors=None):
        p=self.program()
        result=transient(p,{'u':[[0.,0.],[2.,0.2]]},times,stop=2.,max_step=0.125,
            source_errors=errors,kernel=KERNEL,
            vabstol=0.01 if errors else 1e-10,reltol=0.)
        return result

    def test_fraction_lineage_beats_point_representative_and_queries_preserve_history(self):
        exact_gap=SAMPLED-u(1.5)-THRESHOLD
        representative_gap=Q(float(SAMPLED))-u(1.5)-THRESHOLD
        self.assertEqual(exact_gap,-Q(1,2**57))
        self.assertEqual(representative_gap,Q(1,2**56))
        self.assertLess(exact_gap,0)
        self.assertGreater(representative_gap,0)
        print(json.dumps({'oracle':'original binary64 Fraction recursion',
            'sampled':str(SAMPLED),'exact_gap':str(exact_gap),
            'incorrect_representative_gap':str(representative_gap),
            'threshold_query_y':0}),flush=True)
        sparse=self.run_case(SPARSE)
        dense=self.run_case(DENSE)
        for times,result in ((SPARSE,sparse),(DENSE,dense)):
            for time,row in zip(times,result['solutions'],strict=True):
                for name,value in expected(time).items():
                    actual=row['voltages'][result['nodes'].index(name)]
                    if name=='y': self.assertEqual(actual,value,(time,name))
                    else: self.assertAlmostEqual(actual,value,delta=1e-12,msg=str((time,name)))
            at=times.index(1.5)
            node=result['nodes'].index('h')
            lo,hi=result['observation_evidence']['voltage_bounds_V'][at][node]
            self.assertLess(lo,hi,'certified nonpoint state must remain a nonpoint voltage enclosure')
            self.assertLessEqual(Q(lo),SAMPLED)
            self.assertGreaterEqual(Q(hi),SAMPLED)
            self.assertEqual(result['solutions'][at]['voltages'][result['nodes'].index('y')],0.)
        for time in SPARSE:
            a=sparse['solutions'][SPARSE.index(time)]['voltages']
            b=dense['solutions'][DENSE.index(time)]['voltages']
            self.assertEqual(a,b,('extra queries changed physical output/history',time))

    def test_nonzero_source_error_preserves_existing_early_total_gate(self):
        # Actual RED established unsupported_source_uncertainty before the new
        # consumer. Preserve that existing gate; this case cannot establish
        # direct exact-consumer rejection of unknown/error-bearing provenance.
        with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
            self.run_case(SPARSE,errors={'u':1e-4})

if __name__=='__main__': unittest.main()
