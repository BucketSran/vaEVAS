"""Successful simulations carry notices without inventing boundary evidence."""
GUARDS = ["TIMER", "CROSS", "DYNAMICS", "DEV:boundary-portability"]
import copy
import unittest

from evas import KernelError, compile_sources, transient
from evas.protocol import validate_response
from test_affine import KERNEL, instance, model


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


if __name__=='__main__':unittest.main()
