"""Ordinary analog variables that persist across evaluations (LRM 2.4 4.2, 5.3).

Independent answers are written from the dense-time procedural semantics:
the ordinary block runs at every instant and a read that is not preceded by a
write in the same evaluation observes the previous value.
"""
GUARDS=['LANG','EVENT-ORDER','COMPOSE']
import os
from pathlib import Path
import unittest
from evas import CompileError, KernelError, Instance, compile_sources, transient

KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',
    Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel'))
HEAD='`include "disciplines.vams"\nmodule m(s,r,y);input s,r;output y;electrical s,r,y;'
PULSES={'s':[[0,0],[1,0],[1.1,1],[2,1],[2.1,0],[6,0]],
        'r':[[0,0],[3,0],[3.1,1],[4,1],[4.1,0],[6,0]]}
TIMES=[0,.5,1.5,2.5,3.5,4.5,5.5]


def program(body, declarations='integer q;'):
    return compile_sources({'held.va':HEAD+declarations+'analog begin '+body+'end endmodule'},
                           [Instance('M','m',dict(s='s',r='r',y='y'))])


def run(p, drive=PULSES, times=TIMES):
    r=transient(p,drive,list(times),stop=6,max_step=.25,kernel=KERNEL)
    return [row['voltages'][r['nodes'].index('y')] for row in r['solutions']]


LATCH=('@(initial_step)q=0;'
       'if(V(s)>0.5&&V(r)<=0.5)q=1;else if(V(r)>0.5&&V(s)<=0.5)q=0;')


class OrdinaryHeldState(unittest.TestCase):
    def test_level_sensitive_latch_holds_between_pulses(self):
        # s pulse at [1.1,2]: set and hold; r pulse at [3.1,4]: reset and hold.
        p=program(LATCH+'V(y)<+q;')
        self.assertEqual(run(p),[0,0,1,1,0,0,0])
        self.assertEqual([s.name for s in p.states],['q'])

    def test_contribution_before_the_update_reads_the_same_held_value(self):
        p=program('@(initial_step)q=0;V(y)<+2*q;'
                  'if(V(s)>0.5&&V(r)<=0.5)q=1;else if(V(r)>0.5&&V(s)<=0.5)q=0;')
        self.assertEqual(run(p),[0,0,2,2,0,0,0])

    def test_initial_seed_is_held_until_the_first_write(self):
        p=program('@(initial_step)q=7;if(V(s)>0.5)q=1;V(y)<+q;','real q;')
        self.assertEqual(run(p),[7,7,1,1,1,1,1])

    def test_callback_reads_and_writes_the_held_value_in_source_order(self):
        # Ordinary reset while r is high; each s rising edge counts otherwise.
        body=('@(initial_step)n=0;'
              'if(V(r)>0.5)n=0;'
              '@(cross(V(s)-0.5,+1))n=n+1;'
              'V(y)<+n;')
        drive={'s':[[0,0],[.5,0],[.6,1],[1,1],[1.1,0],[1.5,0],[1.6,1],[2,1],[2.1,0],
                    [4.5,0],[4.6,1],[5,1],[5.1,0],[6,0]],
               'r':[[0,0],[3,0],[3.1,1],[4,1],[4.1,0],[6,0]]}
        p=program(body,'integer n;')
        self.assertEqual(run(p,drive,[0,.8,1.8,2.5,3.5,4.2,5.5]),[0,1,2,2,0,0,1])

    def test_exact_zero_plateau_uses_the_relation_at_zero(self):
        # u reaches 0.5 exactly, stays, then returns below without crossing.
        drive={'s':[[0,0],[1,.5],[2,.5],[3,0],[6,0]],'r':[[0,0],[6,0]]}
        held=program('@(initial_step)q=0;if(V(s)>=0.5)q=1;V(y)<+q;')
        self.assertEqual(run(held,drive,[0,.5,1.5,2.5,4]),[0,0,1,1,1])
        strict=program('@(initial_step)q=0;if(V(s)>0.5)q=1;V(y)<+q;')
        self.assertEqual(run(strict,drive,[0,.5,1.5,2.5,4]),[0,0,0,0,0])

    def test_timer_reads_a_held_slot_that_stays_current(self):
        body=('@(initial_step)begin t=-1;q=0;end '
              '@(cross(V(s)-0.5,+1))t=$abstime+0.5;'
              '@(timer(t))q=q+1;'
              'if(V(r)>=0.5)t=-1;'
              'V(y)<+q;')
        drive={'s':[[0,0],[1,0],[1.1,1],[2,1],[2.1,0],[3,0],[3.05,1],[6,0]],
               'r':[[0,0],[3,0],[3.1,1],[6,1]]}
        p=program(body,'real t;integer q;')
        # First edge at 1.05 fires the timer at 1.55; the second edge at 3.025
        # schedules 3.525, cancelled by the ordinary reset after r rises.
        self.assertEqual(run(p,drive,[0,1.5,2,3.5,4,5]),[0,0,1,1,1,1])

    def test_unsupported_shapes_keep_explicit_rejections(self):
        rejected=[
            # A read of the previous value inside U is not idempotent.
            ('@(initial_step)q=0;if(V(s)>0.5)q=q+1;V(y)<+q;','integer q;'),
            # A continuous-time running maximum is not piecewise constant.
            ('@(initial_step)q=0;if(V(s)>q)q=V(s);V(y)<+q;','real q;'),
            # A tracking value needs the left limit of an arbitrary node.
            ('@(initial_step)q=0;if(V(r)>0.5)q=V(s);V(y)<+q;','real q;'),
            # The exact-zero pattern of one atom agrees with neither side.
            ('@(initial_step)q=0;if(V(s)>0.5)q=1;if(V(s)>=0.5)q=2;V(y)<+q;','integer q;'),
            # Time atoms and pure local inputs are outside this slice.
            ('@(initial_step)q=0;if($abstime>0.5)q=1;V(y)<+q;','integer q;'),
            ('@(initial_step)q=0;e=V(s);if(e>0.5)q=1;V(y)<+q;','integer q;real e;'),
            # Leaving the exact-zero side writes the timer input.
            ('@(initial_step)t=-1;@(timer(t))q=1;if(V(s)>0.5)t=2;V(y)<+q;','real t;integer q;'),
            # A callback between the held writers has no single source position.
            ('@(initial_step)q=0;if(V(s)>0.5)q=1;@(cross(V(r)-0.5,+1))q=q+2;'
             'if(V(r)>0.5)q=0;V(y)<+q;','integer q;'),
        ]
        for body,declarations in rejected:
            with self.subTest(body=body),self.assertRaises(CompileError):
                program(body,declarations)

    def test_simultaneous_commits_are_rejected_not_ordered(self):
        # Both atoms cross at exactly 1.05; the rewritten bodies both write q.
        drive={'s':[[0,0],[1,0],[1.1,1],[6,1]],'r':[[0,0],[1,0],[1.1,1],[6,1]]}
        p=program(LATCH+'V(y)<+q;')
        with self.assertRaises(KernelError):
            run(p,drive)


if __name__=='__main__':
    unittest.main()
