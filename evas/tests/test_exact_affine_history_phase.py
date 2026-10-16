"""Original frozen history queries require certified physical root phases."""
GUARDS = ["CROSS", "EVENT-ORDER", "DYNAMICS", "TIMER"]
import json
import math
from fractions import Fraction as Q
from pathlib import Path
import unittest
from evas import Instance,compile_sources,transient,KernelError
from test_affine import KERNEL

class ExactAffineHistoryPhase(unittest.TestCase):
    def test_original_changed_constant_integral_queries_and_sparse_grids(self):
        fixtures=Path(__file__).resolve().parents[1]/'validation/event_acceptance/cases'
        for name,root in [('E3',Q(1,2)),('E5',Q(1,3))]:
            baseline=None
            for profile in ['base','fine']:
                folder=fixtures/(name+'-'+profile)
                manifest=json.loads((folder/'evas-manifest.json').read_text())
                program=compile_sources({n:(folder/n).read_text() for n in manifest['models']},[Instance(**i) for i in manifest['instances']])
                config=manifest['transient']; center=float(root)
                for times in [config['output_times'],[0,math.nextafter(center,-math.inf),center,math.nextafter(center,math.inf),config['stop']],[0,config['stop']]]:
                    with self.subTest(case=name,profile=profile,points=len(times)):
                        response=transient(program,config['sources'],times,stop=config['stop'],max_step=config['max_step'],**manifest['tolerances'],kernel=KERNEL)
                        values=[dict(zip(response['nodes'],r['voltages'])) for r in response['solutions']]
                        cross=next(e for e in response['transient']['events'] if e['kind']=='cross')
                        te=Q(cross['time'])
                        trigger=program.events[cross['event']].trigger
                        self.assertGreater(te,root)
                        self.assertLessEqual(te-root,Q(trigger.time_tolerance))
                        guard=2*te-1 if name=='E3' else 3*te-1
                        self.assertGreater(guard,0)
                        self.assertLessEqual(guard,Q(trigger.expression_tolerance))
                        self.assertEqual([v['count'] for v in values],[int(Q(t)>=te) for t in times])
                        self.assertEqual(len(response['transient']['events']),2 if name=='E3' else 1)
                        if baseline is None:baseline=response['transient']['events']
                        else:self.assertEqual(response['transient']['events'],baseline)

    def test_polynomial_history_query_does_not_inherit_affine_root_certificate(self):
        folder=Path(__file__).resolve().parents[1]/'validation/event_acceptance/cases/E5-base'
        manifest=json.loads((folder/'evas-manifest.json').read_text())
        source=(folder/'dut.va').read_text().replace('V(z,r)-1','V(z,r)*V(z,r)-0.1')
        program=compile_sources({'dut.va':source},[Instance(**i) for i in manifest['instances']])
        times=[0,math.sqrt(.1)/3,2]
        response=transient(program,manifest['transient']['sources'],times,stop=2,max_step=.02,
                           vabstol=1e-8,reltol=0,kernel=KERNEL)
        cross,=response['transient']['events']
        te=Q(cross['time'])
        # z=3t in the old epoch. Squared inequalities certify the irrational
        # root's side and original time budget without a rounded sqrt oracle.
        self.assertGreater(9*te*te-Q(.1),0)
        self.assertLessEqual(9*te*te-Q(.1),Q(1e-8))
        self.assertGreater(te-Q(1e-9),0)
        self.assertLess(9*(te-Q(1e-9))**2,Q(.1))
        lo,hi=cross['observation_time_bounds']
        self.assertLess(lo,hi) # no invented point/affine root identity
        self.assertLess(Q(times[1]),te)
        self.assertEqual([row[2] for row in response['transient']['states']],[0,0,1])
        for t,row in zip(times,response['solutions']):
            values=dict(zip(response['nodes'],row['voltages']))
            z=3*Q(t) if Q(t)<te else Q(t)+2*te
            sample=Q(0) if Q(t)<te else 3*te
            self.assertLessEqual(abs(Q(values['z'])-z),Q(1e-8))
            self.assertLessEqual(abs(Q(values['sample'])-sample),Q(1e-8))
            self.assertLessEqual(abs(Q(values['history'])-2*Q(t)),Q(1e-8))
