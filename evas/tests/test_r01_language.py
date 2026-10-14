"""Independent controls for R01's language and timestep entry gaps."""
GUARDS = ["LANG", "ANALOG", "EVENT-CONDITIONS", "DEV:scs-input"]

import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model, execute
from test_event_conditions import source, execute as event_execute, states
import test_scs


class R01Language(unittest.TestCase):
    def test_compound_event_conditions_short_circuit_and_equality(self):
        for predicate, expected in [
            ('V(u,r)>=0.5 && V(u,r)<1', [0,2,3]),
            ('V(u,r)<0.5 || V(u,r)==1', [0,3,2]),
            ('!(V(u,r)==0.5)', [0,3,2]),
            ('V(u,r)!=0.5', [0,3,2]),
            ('V(u,r)-0.5', [0,3,2]),
        ]:
            with self.subTest(predicate=predicate):
                self.assertEqual(states(event_execute(source(f'if({predicate}) q=2; else q=3;'))), expected)

    def test_conditional_contributions_accumulate_and_keep_direction(self):
        text = model('''V(y,r)<+0.125;
            if(V(u,r)>0 && V(u,r)<=1) begin
                V(y,r)<+V(u,r); V(r,y)<+-0.25;
            end else V(y,r)<+-1;''')
        rows = execute(text, [instance()], ['u'], [[-1],[0],[0.5],[1],[2]])
        self.assertEqual([r['y'] for r in rows], [-.875,-.875,.875,1.375,-.875])

    def test_conditional_contribution_requires_continuous_branch_presence(self):
        with self.assertRaisesRegex(CompileError, 'inactive.*branch|branch.*inactive'):
            compile_sources({'switch.va':model('if(V(u,r)>0) V(y,r)<+1;')}, [instance()])

    def test_model_bound_limits_real_accepted_steps(self):
        text = model('$bound_step(0.125); V(y,r)<+idt(1,0);')
        p = compile_sources({'bound.va':text}, [instance()])
        r = transient(p, {'u':[[0,0],[1,0]]}, [0,1], stop=1,max_step=1,kernel=KERNEL)
        self.assertGreaterEqual(r['transient']['accepted_steps'], 8)
        self.assertAlmostEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], 1)


class R01Grid(unittest.TestCase):
    def test_stop_rounding_keeps_one_endpoint_and_preserves_interior_grid(self):
        from evas.scs import load_scs
        case=test_scs.ScsContracts()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.deck(source='Vin (u 0) vsource dc=1', tran='tran tran stop=1.033e-6 maxstep=100p')
        times=load_scs(case.path).manifest['transient']['output_times']
        self.assertEqual(times[0], 0)
        self.assertEqual(times[-1], 1.033e-6)
        self.assertEqual(len(times),10331)
        self.assertTrue(all(a<b for a,b in zip(times,times[1:])))


if __name__ == '__main__':
    unittest.main()
