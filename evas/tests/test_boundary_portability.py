"""Nonblocking diagnostics for observations adjacent to committed cross certificates."""
GUARDS = ["CROSS", "DEV:boundary-portability"]
import copy
import json
import math
from pathlib import Path
import unittest
import tempfile

from evas import Instance, KernelError, compile_sources, transient
from evas.protocol import validate_response
from test_affine import KERNEL, EVAS, instance, model


def run_c1(kernel=KERNEL):
    folder=EVAS/'validation/event_alignment/C1'
    case=json.loads((folder/'case.json').read_text())
    program=compile_sources({'C1/dut.va':(folder/'dut.va').read_text()},
        [Instance('dut',case['module'],{p:('0' if p=='r' else p) for p in case['ports']},{})])
    settings=case['settings']['evas']
    result=transient(program,case['inputs'],case['times'],stop=case['stop'],kernel=kernel,**settings)
    return program,case['times'],result


class BoundaryPortability(unittest.TestCase):
    def test_original_c1_reports_local_query_risk_without_rewriting_source(self):
        program,times,result=run_c1()
        advice=result['portability_advisories']
        self.assertEqual(advice['schema_version'],1)
        self.assertFalse(advice['truncated'])
        records=advice['records']
        self.assertTrue(records)
        record=next(r for r in records if r['query_time_s']==1.4e-6)
        self.assertEqual(record['event'],0)
        self.assertEqual(record['trigger'],0)
        self.assertEqual(record['origin'],result['transient']['events'][record['event_record']]['origin'])
        self.assertTrue(record['nonblocking'])
        self.assertEqual(times[record['query_index']],record['query_time_s'])
        self.assertIn('cross',record['message'])
        self.assertEqual(validate_response(result,program,len(times),times),result)

    def test_binary64_neighbors_warn_but_far_queries_and_timer_do_not(self):
        program=compile_sources({'test.va':model('@(initial_step) q=0; @(cross(V(u,r)-0.5,1)) q=q+1; V(y,r)<+q;','integer q;')},[instance()])
        times=[0,math.nextafter(.5,-math.inf),.5,math.nextafter(.5,math.inf),.75,1]
        result=transient(program,{'u':[[0,0],[1,1]]},times,stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([r['query_index'] for r in result['portability_advisories']['records']],[1,2,3])
        sparse=transient(program,{'u':[[0,0],[1,1]]},[0,.75,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertNotIn('portability_advisories',sparse)
        self.assertEqual(result['transient']['events'],sparse['transient']['events'])
        self.assertEqual(result['solutions'][-1],sparse['solutions'][-1])
        timer=compile_sources({'test.va':model('@(initial_step) q=0; @(timer(0.5)) q=1; V(y,r)<+q;','integer q;')},[instance()])
        self.assertNotIn('portability_advisories',transient(timer,{'u':[[0,0],[1,1]]},times,stop=1,max_step=1,kernel=KERNEL))

    def test_public_budget_counts_all_cross_query_matches(self):
        # Fifty distinct same-time cross statements each have three neighboring queries.
        names=[f'q{i}' for i in range(50)]
        body='@(initial_step) begin '+''.join(f'{name}=0;' for name in names)+' end '
        body+=''.join(f'@(cross(V(u,r)-0.5,1)) {name}=1;' for name in names)
        body+='V(y,r)<+'+'+'.join(names)+';'
        program=compile_sources({'test.va':model(body,'integer '+','.join(names)+';')},[instance()])
        times=[0,math.nextafter(.5,-math.inf),.5,math.nextafter(.5,math.inf),1]
        result=transient(program,{'u':[[0,0],[1,1]]},times,stop=1,max_step=1,kernel=KERNEL)
        advice=result['portability_advisories']
        self.assertEqual(len(advice['records']),128)
        self.assertEqual(advice['dropped_records'],22)
        self.assertTrue(advice['truncated'])
        self.assertEqual(result['transient']['states'][-1],[1]*50)
        self.assertEqual(validate_response(result,program,len(times),times),result)

    def test_or_cross_identity_and_capture_result_bundles_retain_advisories(self):
        from evas.diagnostics import capture
        from evas.results import run
        # The matching event group includes a timer and a cross; the notice names the cross leaf.
        body='@(initial_step) q=0; @(timer(0.5) or cross(V(u,r)-0.5,1)) q=q+1; V(y,r)<+q;'
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            (folder/'dut.va').write_text(model(body,'integer q;'))
            manifest=dict(models=['dut.va'],instances=[dict(name='dut',module='m',connections=dict(u='u',y='y',r='0'))],
                transient=dict(sources={'u':[[0,0],[1,1]]},output_times=[0,.5,1],stop=1,max_step=1))
            path=folder/'input.json';path.write_text(json.dumps(manifest))
            artifact=capture(path,KERNEL)
            response=artifact['payload']['response']
            advice=response['portability_advisories']
            self.assertEqual(advice['records'][0]['trigger'],1)
            self.assertEqual(advice['records'][0]['root_time_bounds_s'],[.5,.5])
            status=run(path,kernel=KERNEL,out=folder/'result')
            self.assertEqual(status['status'],'complete')
            bundled=json.loads((folder/'result/result.json').read_text())
            self.assertEqual(bundled,response)

    def test_optional_protocol_rejects_malformed_and_unbound_records(self):
        program,times,result=run_c1()
        old=copy.deepcopy(result);old.pop('portability_advisories')
        self.assertEqual(validate_response(old,program,len(times),times),old)
        mutations=[lambda a:a.update(schema_version=True),lambda a:a.update(record_limit=129),
            lambda a:a.update(truncated=True),lambda a:a.update(dropped_records=-1),
            lambda a:a['records'][0].update(query_index=True),lambda a:a['records'][0].update(event=999),
            lambda a:a['records'][0].update(trigger=999),lambda a:a['records'][0].update(origin='invented'),
            lambda a:a['records'][0].update(query_time_s=0),lambda a:a['records'][0].update(root_time_bounds_s=[0,1]),
            lambda a:a['records'][0].update(nonblocking=False),lambda a:a['records'][0].update(message=42)]
        for mutation in mutations:
            bad=copy.deepcopy(result);mutation(bad['portability_advisories'])
            with self.subTest(advice=bad['portability_advisories']),self.assertRaisesRegex(KernelError,'invalid_response'):
                validate_response(bad,program,len(times),times)

if __name__=='__main__':unittest.main()
