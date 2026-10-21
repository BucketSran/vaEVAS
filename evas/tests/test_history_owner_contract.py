"""A physical voltage interface preserves its producer's held-state owner.

The independent values use exact binary fractions. A consumer adds one half to
one producer's q/8; its local state identifiers never authorize foreign raw IR.
"""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER', 'TIMED-OPERATOR']

import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

from evas import Instance, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL

KERNEL = Path(os.environ.get('EVAS_KERNEL', DEFAULT_KERNEL))
SOURCE = '''`include "disciplines.vams"
module producer(out, marker);
output out, marker; electrical out, marker;
parameter integer SEED=1; parameter integer NEXT=2;
parameter real WHEN=0.5;
integer q; real edge;
analog begin
 @(initial_step) begin q=SEED;edge=1;end
 @(timer(WHEN)) begin q=NEXT;edge=0;end
 if(q>0) V(out)<+q*0.125;else V(out)<+0;
 V(marker)<+transition(edge,0,0.125,0.125);
end endmodule
module consumer(port,marker,y);
input port,marker;output y;electrical port,marker,y;real value;
analog begin
 value=V(port)+0.5;
 if(V(port)>0.0625) V(y)<+value;else V(y)<+0;
end endmodule'''


def program(reverse=False):
    instances = [
        Instance('A', 'producer', dict(out='a', marker='ma'),
                 dict(SEED=1, NEXT=2, WHEN=.5)),
        Instance('B', 'producer', dict(out='b', marker='mb'),
                 dict(SEED=3, NEXT=4, WHEN=.75)),
        Instance('CA', 'consumer', dict(port='a', marker='ma', y='ya')),
        Instance('CB', 'consumer', dict(port='b', marker='mb', y='yb')),
    ]
    if reverse:
        instances.reverse()
    return compile_sources({'owner-contract.va': SOURCE}, instances)


def run(p, times):
    return transient(p, {}, times, stop=1., max_step=.0625,
                     vabstol=1e-10, reltol=0, kernel=KERNEL)


def values(result, node):
    i = result['nodes'].index(node)
    return [row['voltages'][i] for row in result['solutions']]


class HistoryOwnerContract(unittest.TestCase):
    def test_distinct_producer_states_reach_their_own_consumers(self):
        result = run(program(), [0., .25, .625, 1.])
        # A: q=1 until .5, then2. B: q=3 until .75, then4.
        # Producer out retains a real Select(q>0). Consumer's guard reads
        # that Select-bearing voltage interface, activating history admission.
        # All q here are positive, so each output is exactly q/8 + 1/2.
        self.assertEqual(values(result, 'ya'), [.625, .625, .75, .75])
        self.assertEqual(values(result, 'yb'), [.875, .875, .875, 1.])
        self.assertTrue(all(row['max_residual_ratio'] <= 1
                            for row in result['solutions']))

    def test_instance_order_and_extra_queries_preserve_values_and_epochs(self):
        times = [0., .25, .625, 1.]
        dense = sorted(set(times + [.125, .375, .5, .5625, .6875, .75, .8125, .875]))
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                p = program(reverse)
                sparse = run(p, times)
                extra = run(p, dense)
                for node, expected in [('ya', [.625, .625, .75, .75]),
                                       ('yb', [.875, .875, .875, 1.])]:
                    self.assertEqual(values(sparse, node), expected)
                    dense_values = dict(zip(dense, values(extra, node)))
                    self.assertEqual([dense_values[t] for t in times], expected)
                self.assertEqual(sparse['transient']['events'],
                                 extra['transient']['events'])

    def test_raw_foreign_state_is_rejected_at_the_public_kernel_boundary(self):
        p = program().to_dict()
        state = next(i for i, value in enumerate(p['states'])
                     if value['instance'] == 'A' and value['name'] == 'q')
        y = p['nodes'].index('ya')
        bad = copy.deepcopy(p)
        # Canonical branch orientation may put ground in positive and y in
        # negative; select by owner and either endpoint, not source spelling.
        contribution = next(c for c in bad['contributions']
                            if c['origin']['instance'] == 'CA'
                            and y in (c['positive'], c['negative']))
        # Only the legitimate voltage-interface read is replaced. Consumer CA
        # must never own A:q even if their flattened state numbers happen to fit.
        contribution['rhs'] = dict(op='state', state=state)
        response = subprocess.run([str(KERNEL)], input=json.dumps(dict(
            program=bad, driven=[], samples=[], transient=dict(
                pwl=[], output_times=[0., 1.], stop=1., max_step=.0625))),
            text=True, capture_output=True, timeout=20)
        self.assertEqual(response.returncode, 2, response.stdout + response.stderr)
        self.assertEqual(response.stdout, '')
        diagnostic = json.loads(response.stderr)
        self.assertEqual(diagnostic['kind'], 'invalid_ir')
        self.assertIn('state reference must belong to its instance',
                      diagnostic['message'])
