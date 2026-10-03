"""Process boundary tests: fault injection plus a real timed-out child."""
GUARDS = ["LANG", "DEV:runtime-protocol"]

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from evas import KernelError, compile_sources, solve, transient
from test_affine import instance, model


class RuntimeContracts(unittest.TestCase):
    def setUp(self):
        self.program=compile_sources({'runtime.va':model('V(y,r)<+V(u,r);')},[instance()])
        self.response=dict(engine='evas-static-0.12.2',schema_version=16,nodes=list(self.program.nodes),
                           solutions=[dict(voltages=[0,.2,.2],max_residual_v=0,max_residual_ratio=0)])

    def invoke(self,response,**kwargs):
        with patch('evas.runtime.subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps(response),'')) as run:
            result=solve(self.program,['u'],[[.2]],kernel='/not-executed',**kwargs)
            return result,run.call_args.kwargs

    def test_complete_response_and_configurable_timeout(self):
        result,kwargs=self.invoke(self.response,timeout=3)
        self.assertEqual(result,self.response)
        self.assertEqual(kwargs['timeout'],3)
        _,kwargs=self.invoke(self.response)
        self.assertGreater(kwargs['timeout'],0)
        _,kwargs=self.invoke(self.response,timeout=None)
        self.assertIsNone(kwargs['timeout'])

    def test_rejects_invalid_success_payloads(self):
        mutations=[None,[],dict(self.response,solutions=[{}]),dict(self.response,solutions=None)]
        for value in ([],[0,.2],[0,.2,float('nan')],[0,.2,True],[0,.2,'0.2']):
            r=copy.deepcopy(self.response); r['solutions'][0]['voltages']=value; mutations.append(r)
        r=copy.deepcopy(self.response); r['solutions'][0]['max_residual_v']=float('inf'); mutations.append(r)
        for payload in mutations:
            with self.subTest(payload=payload),self.assertRaises(KernelError) as caught:
                self.invoke(payload)
            self.assertEqual(caught.exception.detail['kind'],'invalid_response')

    def test_bad_error_objects_become_process_diagnostics(self):
        for stderr in ('{}','null','[]','{"kind":4,"message":"bad"}','not JSON',
                       '{"kind":"broken","message":"bad","value":1e999}'):
            with self.subTest(stderr=stderr),patch('evas.runtime.subprocess.run',return_value=subprocess.CompletedProcess([],2,'',stderr)):
                with self.assertRaises(KernelError) as caught:
                    solve(self.program,['u'],[[.2]],kernel='/not-executed')
                self.assertEqual(caught.exception.detail['kind'],'kernel_process')
                self.assertIn(stderr,caught.exception.detail['message'])

    def test_success_json_rejects_overflowed_numbers_even_in_extra_fields(self):
        payload = json.dumps(self.response)[:-1] + ', "extra": 1e999}'
        with patch('evas.runtime.subprocess.run', return_value=subprocess.CompletedProcess([], 0, payload, '')):
            with self.assertRaises(KernelError) as caught:
                solve(self.program, ['u'], [[.2]], kernel='/not-executed')
        self.assertEqual(caught.exception.detail['kind'], 'invalid_response')

    def test_structured_kernel_error_keeps_sample(self):
        detail=dict(kind='residual_failure',message='wrong',sample=1)
        with patch('evas.runtime.subprocess.run',return_value=subprocess.CompletedProcess([],2,'',json.dumps(detail))):
            with self.assertRaises(KernelError) as caught:
                solve(self.program,['u'],[[.2]],kernel='/not-executed')
        self.assertEqual(caught.exception.detail,detail)

    def test_transient_state_rows_and_times_are_validated(self):
        r=copy.deepcopy(self.response)
        r['transient']=dict(times=[0],state_names=[],states=[[]],events=[],accepted_steps=0,discarded_trials=0)
        for broken in (False,True):
            value=copy.deepcopy(r)
            if broken: value['transient']['states']=[[1]]
            with patch('evas.runtime.subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps(value),'')):
                if broken:
                    with self.assertRaises(KernelError):
                        transient(self.program,{'u':[[0,.2],[1,.2]]},[0],stop=1,max_step=1,kernel='/not-executed')
                else:
                    self.assertEqual(transient(self.program,{'u':[[0,.2],[1,.2]]},[0],stop=1,max_step=1,kernel='/not-executed'),value)

    def test_invalid_timeout_fails_before_launch(self):
        for value in (0,-1,float('nan'),float('inf'),True,'1'):
            with self.subTest(value=value),patch('evas.runtime.subprocess.run') as run:
                with self.assertRaises(ValueError):
                    solve(self.program,['u'],[[.2]],kernel='/not-executed',timeout=value)
                run.assert_not_called()

    def test_mixed_or_records_cannot_fabricate_a_timer_guard_or_leaf_type(self):
        from evas.protocol import validate_response
        self.program=compile_sources({'runtime.va':model('''@(initial_step) n=0;
            @(timer(.5,0,.001) or cross(V(u,r)-.5,1,.001,.001)) n=n+1;
            V(y,r)<+n;''','integer n;')},[instance()])
        record=dict(time=.5,event=0,origin='runtime.va',kind='or',before=[0],after=[1],
                    fired_triggers=[dict(trigger=0,kind='timer',time_bounds=[.5,.5]),
                                    dict(trigger=1,kind='cross',guard_value=0,time_bounds=[.5,.5])])
        r=copy.deepcopy(self.response)
        r['transient']=dict(times=[0],state_names=['dut:n'],states=[[0]],events=[record],
                            accepted_steps=1,discarded_trials=0)
        self.assertEqual(validate_response(r,self.program,1,[0]),r)
        for mutation in (lambda a:a.update(guard_value=0),lambda a:a.update(kind='cross'),
                         lambda a:a.update(trigger=2)):
            bad=copy.deepcopy(r)
            mutation(bad['transient']['events'][0]['fired_triggers'][0])
            with self.assertRaises(KernelError):
                validate_response(bad,self.program,1,[0])

    def test_timeout_stops_and_reaps_real_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); pid=root/'pid'; done=root/'done'; child=root/'kernel'
            child.write_text('#!'+sys.executable+'\nimport os,time\nfrom pathlib import Path\n'+
                             'Path('+repr(str(pid))+').write_text(str(os.getpid()))\n'+
                             'time.sleep(5)\nPath('+repr(str(done))+').write_text("unexpected")\n')
            child.chmod(0o700)
            with self.assertRaises(KernelError) as caught:
                solve(self.program,['u'],[[.2]],kernel=child,timeout=1.5)
            self.assertEqual(caught.exception.detail['kind'],'kernel_timeout')
            self.assertTrue(pid.exists(),'child must have started for the reap check')
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid.read_text()),0)
            self.assertFalse(done.exists())
