"""Successful simulations carry notices without inventing boundary evidence."""
GUARDS = ["TIMER", "CROSS", "DYNAMICS", "DEV:boundary-portability"]
import copy
from fractions import Fraction
import math
import unittest

from evas import Instance, KernelError, compile_sources, transient
from evas.protocol import validate_response
from test_affine import EVAS, KERNEL, instance, model


class PortabilityCoverage(unittest.TestCase):
    def test_extra_strobe_and_timer_observations_are_bound_to_their_own_grid(self):
        for trigger,code in [('timer(0.5)', 'timer_observation_boundary'),
                             ('cross(V(u,r)-0.5,1)', 'cross_observation_boundary')]:
            program=compile_sources({'test.va':model(
                '@(initial_step) q=0; @('+trigger+') q=1; V(y,r)<+q;',
                'integer q;')},[instance()])
            result=transient(program,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,
                             strobetimes=[.5],kernel=KERNEL)
            advice=result['portability_advisories']
            self.assertEqual(advice['schema_version'],2)
            records=[r for r in advice['records'] if r['code']==code]
            self.assertEqual(len(records),1)
            record=records[0]
            self.assertEqual((record['query_source'],record['query_index'],record['query_time_s']),
                             ('strobetimes',0,.5))
            self.assertEqual(record['time_bounds_s'],[.5,.5])
            self.assertEqual(result['solutions'][-1]['voltages'][-1],1)
            bad=copy.deepcopy(result)
            bad['portability_advisories']['records'][0]['query_source']='output_times'
            with self.assertRaisesRegex(KernelError,'invalid_response'):
                validate_response(bad,program,2,[0,1],strobetimes=[.5])

    def test_modulo_notice_identifies_model_without_claiming_observed_wrap(self):
        program=compile_sources({'test.va':model('V(y,r)<+idtmod(1,0,1,0);')},[instance()])
        result=transient(program,{'u':[[0,0],[.25,0]]},[0,.25],stop=.25,max_step=.25,kernel=KERNEL)
        advice=result['portability_advisories']
        self.assertEqual(advice['records'],[])
        record=advice['model_records'][0]
        self.assertEqual(record['code'],'modulo_phase_sensitive')
        self.assertEqual(record['operator'],0)
        self.assertTrue(record['nonblocking'])
        self.assertNotIn('query_time_s',record)
        self.assertNotIn('time_bounds_s',record)
        self.assertEqual(result['solutions'][-1]['voltages'][-1],.25)
        for changes in [dict(operator=99),dict(origin='invented'),dict(nonblocking=False)]:
            bad=copy.deepcopy(result);bad['portability_advisories']['model_records'][0].update(changes)
            with self.assertRaisesRegex(KernelError,'invalid_response'):
                validate_response(bad,program,2,[0,.25])

    def test_original_vco_wrap_observations_keep_nonblocking_source_notice(self):
        path=EVAS.parent/'experiments/backends/event-alignment/vco-controls/original--tight/dut.va'
        program=compile_sources({'dut.va':path.read_text()},[
            Instance('dut','layer_vco',{p:p for p in ('ctl','freq','phase','out')},{})])
        roots=[float((Fraction(n)-Fraction(1,8))/524288) for n in range(1,5)]
        stop=8/1048576
        times=sorted({0.,stop,*[t for root in roots for t in
            (math.nextafter(root,-math.inf),root,math.nextafter(root,math.inf))]})
        result=transient(program,{'ctl':[[0,0],[stop,0]]},times,
                         stop=stop,max_step=stop,kernel=KERNEL)
        records=result['portability_advisories']['model_records']
        self.assertEqual([r['code'] for r in records],['modulo_phase_sensitive'])
        self.assertTrue(records[0]['nonblocking'])
        self.assertNotIn('query_time_s',records[0])
        for t,solution in zip(times,result['solutions']):
            values=dict(zip(result['nodes'],solution['voltages']))
            phase=float((Fraction(1,8)+524288*Fraction(t))%1)
            distance=abs(values['phase']-phase)
            self.assertLessEqual(min(distance,abs(1-distance)),1e-12)
            self.assertAlmostEqual(values['out'],math.sin(2*math.pi*phase),delta=1e-12)
        self.assertEqual(validate_response(result,program,len(times),times),result)


if __name__=='__main__':unittest.main()
