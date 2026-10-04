"""Initialization OR is one initialization body, never a t=0 timer."""
GUARDS = ["LANG", "EVENT-ORDER"]

import unittest
from evas import CompileError, compile_sources
from test_affine import model, instance
from test_continuous_dynamics import run, values


class InitialEvents(unittest.TestCase):
    def test_redundant_initial_leaves_execute_one_body(self):
        for trigger in ('initial_step', 'initial_step or initial_step("dc")',
                        'initial_step("dc") or initial_step',
                        'initial_step or initial_step or initial_step("tran")'):
            source=model('@('+trigger+') n=7; @(timer(0,0,1e-12)) n=n+1; V(y,r)<+n;', 'integer n;')
            program=compile_sources({'init.va':source},[instance()])
            self.assertEqual(len(program.events),1)
            result=run(program,times=[0,.5,1])
            self.assertEqual(values(result),[8,8,8])
            self.assertEqual(result['transient']['events'][0]['before'],[7])

    def test_analysis_specific_and_mixed_global_monitored_events_are_explicit(self):
        for trigger in ('initial_step("dc")', 'initial_step("tran")',
                        'initial_step or timer(0,0,1e-12)',
                        'initial_step or initial_step("unknown")'):
            with self.subTest(trigger=trigger), self.assertRaises(CompileError) as caught:
                compile_sources({'init.va':model('@('+trigger+') n=7; V(y,r)<+n;', 'integer n;')},[instance()])
            self.assertEqual(caught.exception.diagnostic['code'],'unsupported_initial_event')
