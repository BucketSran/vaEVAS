"""Event accuracy contracts against exact rational arithmetic, not EVAS roots.

All supplied binary64 values are interpreted exactly. These are development
regressions, separate from the frozen 31-condition cross-backend suite.
"""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["CROSS"]

from fractions import Fraction as Q
import copy
import json
import math
import subprocess
import unittest

from evas import KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model
from test_events import compile_event, execute_event


def counter(guard, ttol, etol=1e-6, extra=''):
    return model(f'''@(initial_step) n=0;
      {extra}
      @(cross({guard},1,{ttol!r},{etol!r})) n=n+1;
      V(y,r)<+n;''', 'integer n; electrical z;')


class EventAccuracy(unittest.TestCase):
    def test_nonlinearity_hidden_by_coefficient_roundoff_is_rejected(self):
        # Both expressions depend on state and voltage in the original IR.
        # Rounded coefficient collection must not turn either into a constant.
        for term in ['((n+1e-16*n)-n)*1e16*V(u,r)',
                     '(1e-200*(1e-200*n))*(1e300*V(u,r))*1e100']:
            source = model(f'''@(initial_step) n=1;
              @(cross(V(u,r)-.5+{term},1,1e-12,1e-9)) n=n+1;
              V(y,r)<+n;''', 'integer n;')
            with self.subTest(term=term):
                with self.assertRaises(KernelError) as caught:
                    execute_event(source, sources={'u':[[0,0],[1,1]]},
                                  times=[0,1], stop=1, max_step=1)
                # Polynomial held guards are now structurally accepted, but original
                # arithmetic uncertainty still prevents a root certificate.
                self.assertEqual(caught.exception.detail['kind'], 'event_resolution')

    def test_raw_ir_cannot_hide_voltage_products_in_any_event_expression(self):
        program = compile_event(model('''@(initial_step) held=0;
          @(cross(V(u,r)-.5,1)) held=V(u,r); V(y,r)<+held;''',
                                      'real held;')).to_dict()
        u = program['nodes'].index('u')
        def leaf(coefficient):
            return dict(op='affine', constant=0,
                        terms=[dict(node=u, coefficient=coefficient)])
        hidden = dict(op='add', left=dict(op='add', left=leaf(1),
                      right=leaf(1e-16)), right=leaf(-1))
        product = dict(op='multiply', left=hidden, right=leaf(1e16))
        for position in ['guard', 'contribution', 'assignment', 'without_events']:
            p = copy.deepcopy(program)
            if position == 'guard':
                p['events'][0]['trigger']['guard'] = dict(op='add',
                    left=p['events'][0]['trigger']['guard'], right=product)
            elif position == 'assignment':
                p['events'][0]['body'][0]['rhs'] = product
            else:
                p['contributions'][0]['rhs'] = product
                if position == 'without_events':
                    p['events'] = []
            request = dict(program=p, driven=['u'], samples=[], transient=dict(
                pwl=[[[0,0],[1,1]]], output_times=[0,1], stop=1, max_step=1))
            with self.subTest(position=position):
                result = subprocess.run([str(KERNEL)], input=json.dumps(request),
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)['kind'],
                                 'event_resolution' if position == 'guard' else 'unsupported_transient')

    def assert_root(self, result, root, ttol, expression, etol):
        events = result['transient']['events']
        self.assertEqual(len(events), 1)
        time = Q(events[0]['time'])
        self.assertGreaterEqual(time, root, 'event precedes the exact root')
        self.assertLessEqual(time-root, Q(ttol))
        self.assertGreaterEqual(expression(time), 0)
        self.assertLessEqual(expression(time), Q(etol))
        self.assertEqual(result['transient']['states'][-1], [1])

    def test_json_preserves_binary64_inputs(self):
        source = model('V(y,r)<+V(u,r);')
        inputs = [1-2**-50, 1+2**-49, math.nextafter(.1, 0),
                  math.nextafter(1e12, math.inf)]
        result = solve(compile_event(source), ['u'], [[x] for x in inputs], kernel=KERNEL)
        node = result['nodes'].index('u')
        self.assertEqual([s['voltages'][node] for s in result['solutions']], inputs)

    def test_shallow_crossing_uses_true_root_and_post_crossing_side(self):
        a, b = 1-2**-50, 1+2**-49
        for internal in [False, True]:
            gain = 2 if internal else 1
            source = counter('V(z,r)-2' if internal else 'V(u,r)-1', 1e-15,
                             extra='V(z,r)<+V(u,r)+.5*V(z,r);' if internal else 'V(z,r)<+0;')
            for step in [1., .07]:
                result = execute_event(source, sources={'u':[[0,a],[1,b]]},
                                       times=[0,1], stop=1, max_step=step)
                self.assert_root(result, Q(1,3), 1e-15,
                                 lambda t: gain*(Q(a)+(Q(b)-Q(a))*t-1), 1e-6)

    def test_unrepresentable_time_tolerance_is_rejected(self):
        for start, ttol in [(0.,1e-18),(2.**40,1e-8)]:
            points = [[0,-1.], [start+1,2.]]
            if start:
                points.insert(1,[start,-1.])
            with self.subTest(start=start), self.assertRaises(KernelError) as caught:
                execute_event(counter('V(u,r)',ttol,extra='V(z,r)<+0;'),
                              sources={'u':points},times=[0,start+1],
                              stop=start+1,max_step=start+1)
            self.assertEqual(caught.exception.detail['kind'],'event_resolution')

    def test_expression_tolerance_is_checked_against_affine_trajectory(self):
        # Nearest post-root float is later than 1/3 by ~3.7e-17 s.
        # A 1e-20 expression tolerance cannot be met even if rounded g becomes 0.
        with self.assertRaises(KernelError) as caught:
            execute_event(counter('V(u,r)',1e-12,1e-20,extra='V(z,r)<+0;'),
                          sources={'u':[[0,-1.],[1,2.]]},times=[0,1],stop=1,max_step=1)
        self.assertEqual(caught.exception.detail['kind'],'event_resolution')

    def test_internal_solution_uncertainty_cannot_claim_tight_time_accuracy(self):
        # z = .1*u + .9*z. The ideal binary64-coefficient gain is known exactly.
        # Endpoint roundoff is comparable with this tiny input swing.
        source = counter('V(z,r)-1',1e-15,
                         extra='V(z,r)<+.1*V(u,r)+.9*V(z,r);')
        a,b = 1-2**-49,1+2**-49
        gain=Q(.1)/(1-Q(.9))
        root=(1/gain-Q(a))/(Q(b)-Q(a))
        self.assertTrue(0 < root < 1)
        try:
            result=execute_event(source,sources={'u':[[0,a],[1,b]]},
                                 times=[0,1],stop=1,max_step=1)
        except KernelError as error:
            self.assertEqual(error.detail['kind'],'event_resolution')
        else:
            self.assert_root(result,root,1e-15,
                             lambda t:gain*(Q(a)+(Q(b)-Q(a))*t)-1,1e-6)

    def test_scaled_simultaneous_guards_share_settled_voltage(self):
        for scale in [2,3,10]:
            source=model(f'''@(initial_step) begin n=0; held=0; end
              @(cross(V(u,r)-.5,1)) n=n+1;
              @(cross({scale}*(V(u,r)-.5),1)) held=V(y,r);
              V(y,r)<+n;''','integer n; real held;')
            for step in [10e-6, 97e-9]:
                result=execute_event(source,max_step=step)
                self.assertEqual(result['transient']['states'][-1],[2,2])
                times=[e['time'] for e in result['transient']['events']]
                self.assertEqual(times[0],times[1])
                self.assertEqual(times[2],times[3])

    def test_coupled_voltage_roots_against_closed_form(self):
        for a,b,c,d in [(0.25,.5,.5,.25),(.1,.2,.3,.4),(.5,-.25,.2,.5)]:
            gain=(Q(a)+Q(b)*Q(c))/(1-Q(b)*Q(d))
            source=model(f'''@(initial_step) n=0;
              V(x,r)<+{a}*V(u,r)+{b}*V(z,r);
              V(z,r)<+{c}*V(u,r)+{d}*V(x,r);
              @(cross(V(x,r)-.125,1,1e-11,1e-8)) n=n+1;
              V(y,r)<+n;''','integer n; electrical x,z;')
            root=Q(1,8)/gain
            result=execute_event(source,sources={'u':[[0,0],[1,1]]},
                                 times=[0,1],stop=1,max_step=1)
            self.assert_root(result,root,1e-11,lambda t:gain*t-Q(1,8),1e-8)

    def test_original_source_proves_neighbouring_roots_are_distinct(self):
        source=model('''@(initial_step) begin n=0; m=0; end
          @(cross(V(u,r)-.5,1,1e-12,1e-9)) n=n+1;
          @(cross(V(u,r)-.5000000000000001,1,1e-12,1e-9)) m=m+1;
          V(y,r)<+n+m;''','integer n,m;')
        result = execute_event(source,sources={'u':[[0,.1],[1,.9]]},
                               times=[0,1],stop=1,max_step=1)
        # The same two inputs previously lost their exact provenance when
        # endpoint subtraction rounded. Each original rational root now owns
        # its event; tolerance overlap cannot merge the two callbacks.
        events = result['transient']['events']
        self.assertEqual([e['event'] for e in events], [0, 1])
        self.assertLess(events[0]['time'], events[1]['time'])
        self.assertEqual(result['transient']['states'][-1], [1, 1])
        for event, threshold in zip(events, [.5, .5000000000000001]):
            root = (Q(threshold)-Q(.1))/(Q(.9)-Q(.1))
            self.assertGreaterEqual(Q(event['time']), root)
            self.assertLessEqual(Q(event['time'])-root, Q(1e-12))
            self.assertLessEqual(abs(Q(.1)+(Q(.9)-Q(.1))*Q(event['time'])-Q(threshold)), Q(1e-9))

    def test_unproved_internal_neighbouring_roots_still_reject(self):
        # Structural internal-node provenance is not an original input proof,
        # even if this particular relay has a simple mathematical answer.
        source=model('''@(initial_step) begin n=0; m=0; end
          V(z,r)<+V(u,r);
          @(cross(V(z,r)-.5,1)) n=n+1;
          @(cross(V(z,r)-.5000000000000001,1)) m=m+1;
          V(y,r)<+n+m;''','integer n,m; electrical z;')
        with self.assertRaises(KernelError) as caught:
            execute_event(source,sources={'u':[[0,.1],[1,.9]]},
                          times=[0,1],stop=1,max_step=1)
        self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
        self.assertIn('ordering', caught.exception.detail['message'])

    def test_falling_roots_and_large_time_translation(self):
        for start, ttol in [(0.,1e-14),(2.**30,1e-5)]:
            source=counter('V(u,r)',ttol,1e-5,extra='V(z,r)<+0;')
            source=source.replace('cross(V(u,r),1,','cross(V(u,r),-1,')
            points=[[0,2.],[start+1,-1.]]
            if start:
                points.insert(1,[start,2.])
            result=execute_event(source,sources={'u':points},times=[0,start+1],
                                 stop=start+1,max_step=start+1)
            self.assert_root(result,Q(start)+Q(2,3),ttol,
                             lambda t:3*(t-Q(start))-2,1e-5)

    def test_state_dependency_lost_to_underflow_is_rejected(self):
        source=model('''@(initial_step) n=0;
          V(z,r)<+V(u,r)+1e-200*(1e-200*n);
          @(cross(V(z,r)-.5,1)) n=n+1; V(y,r)<+n;''',
                     'integer n; electrical z;')
        with self.assertRaises(KernelError) as caught:
            execute_event(source)
        # The nonzero interval dependency survives coefficient underflow; the
        # candidate cannot certify a same-time guard change across its root.
        self.assertEqual(caught.exception.detail['kind'],'unsupported_cross')
        self.assertIn('depend',caught.exception.detail['message'])

    def test_inconsistent_redundant_constraints_cannot_define_a_root(self):
        constraint=model('V(y,r)<+V(u,r)+offset;',
                         'parameter real offset=0;').replace('module m(', 'module constraint(')
        program=compile_sources({'counter.va':counter('V(u,r)-.5',1e-12,extra='V(z,r)<+0;'),
                                 'constraint.va':constraint},
                                [instance(),instance('a','constraint',dict(u='u',y='w',r='0')),
                                 instance('b','constraint',dict(u='u',y='w',r='0'),dict(offset=1e-14))])
        with self.assertRaises(KernelError) as caught:
            transient(program,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'],'event_resolution')
        self.assertIn('redundant',caught.exception.detail['message'])
