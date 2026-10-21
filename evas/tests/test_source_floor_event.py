"""Exact original binary64 Divide/Floor event contract; no original benchmark.

Fraction supplies independent original-tree answers. This is the explicit new
engineering contract; it makes no Spectre tie-behavior assertion.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'CROSS', 'COMPOSE']
import json
import math
import unittest
from fractions import Fraction as F

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def program(body='q=floor((V(u,r)/0.9)*15+0.5);', declarations='integer q;', initial='q=0;'):
    text = model('@(initial_step) begin '+initial+' end @(timer(0.25)) begin '+body+' end V(y,r)<+q;', declarations)
    return compile_sources({'source_floor_event.va': text}, [instance()])


def run(p, value, **options):
    return transient(p, {'u': [[0, value], [1, value]]}, [0, .5, 1], stop=1,
                     max_step=.125, kernel=KERNEL, **options)


def final(result):
    return result['solutions'][-1]['voltages'][result['nodes'].index('y')]


class SourceFloorEvent(unittest.TestCase):
    def test_original_divide_point_box_bin_agree_at_rounding_cuts(self):
        p = program()
        for v in [.03, .09, .15, .87, -.03, -.09]:
            expected = math.floor((F.from_float(v)/F.from_float(.9))*15+F(1, 2))
            with self.subTest(v=v):
                self.assertEqual(final(run(p, v)), expected)
        self.assertEqual(final(run(program('q=floor(0.1*V(u,r));'), -10.)), -2)
        self.assertEqual(final(run(program('q=pow(floor((V(u,r)/0.9)*15+0.5),2);'), .03)), 0)
        tree = json.dumps(p.to_dict())
        self.assertIn('"op": "divide"', tree)
        self.assertIn('"function": "floor"', tree)

    def test_certified_bin_controls_source_order_branch_and_display(self):
        p = program('q=floor((V(u,r)/0.9)*15+0.5); $display("floor=%d",q);$display("direct=%g",floor((V(u,r)/0.9)*15+0.5)); if(q<1)q=7;else q=8;')
        r = run(p, .03)
        self.assertEqual(final(r), 7)
        self.assertIn('floor=0', json.dumps(r))
        self.assertIn('direct=0', json.dumps(r))

    def test_divide_exact_cut_negative_and_real_floor_result_type(self):
        for v, expected in [(3., 1), (-1., -1), (math.nextafter(3., 0), 0)]:
            with self.subTest(v=v):
                self.assertEqual(final(run(program('q=floor(V(u,r)/3);'), v)), expected)
        self.assertEqual(final(run(program('q=floor(V(u,r)/3)/2;', 'real q;'), 3.)), .5)
        with self.assertRaises(CompileError):
            program('q=floor(V(u,r)/3)&1;')

    def test_source_constant_lsb_binding_retains_division(self):
        p = program('lsb=0.9/8.0;q=floor(V(u,r)/lsb);if(q<0)q=0;if(q>7)q=7;',
                    'real lsb;integer q;', 'lsb=0.9/8.0;q=0;')
        for v in [0., .1, .45, .9]:
            expected = min(7, max(0, math.floor(F.from_float(v)/(F.from_float(.9)/8))))
            with self.subTest(v=v):
                self.assertEqual(final(run(p, v)), expected)

    def test_true_source_uncertainty_crossing_bin_refuses_before_clamp(self):
        p = program('q=floor(V(u,r)/3);if(q<0)q=0;if(q>7)q=7;')
        with self.assertRaises(KernelError):
            run(p, 3., source_errors={'u': 1e-8}, vabstol=.1, reltol=0)

    def test_first_assignment_overflow_cannot_be_erased_by_postclamp(self):
        p = program('q=floor(V(u,r)/3);if(q<0)q=0;if(q>7)q=7;')
        with self.assertRaises(KernelError):
            run(p, 6442450944.)

    def test_original_child_domain_overflow_and_hidden_dependence_remain_errors(self):
        for expr in ['floor(0*V(y,r)+V(u,r)/3)', 'floor(q+V(u,r)/3)',
                     'floor($abstime+V(u,r)/3)', 'floor(V(u,r)/(q+1))']:
            with self.subTest(expr=expr), self.assertRaises(CompileError):
                program('q='+expr+';')
        for expr in ['floor(V(u,r)/0)', 'floor((V(u,r)*1e308)*0)']:
            with self.subTest(expr=expr):
                try:
                    p = program('q='+expr+';')
                except CompileError:
                    continue
                with self.assertRaises(KernelError):
                    run(p, 1e308)

    def test_direct_original_floor_predicate_uses_paired_bin_without_prior_assignment(self):
        p=program('if(floor((V(u,r)/0.9)*15+0.5)<1)q=7;else q=8;')
        for v in [.03,.09,.15,.87,-.03,-.09]:
            k=math.floor((F.from_float(v)/F.from_float(.9))*15+F(1,2))
            with self.subTest(v=v):self.assertEqual(final(run(p,v)),7 if k<1 else 8)

    def test_inactive_original_constant_divisor_is_audited_in_raw_and_source(self):
        from evas.runtime import _invoke
        import copy
        p=program('if(V(u,r)>10)q=floor(V(u,r)/3);else q=7;', 'real q;')
        for divisor in [dict(op='affine',constant=0,terms=[]),dict(op='add',left=dict(op='affine',constant=1,terms=[]),right=dict(op='affine',constant=-1,terms=[]))]:
            raw=copy.deepcopy(p.to_dict())
            raw['events'][0]['body'][0]['then_body'][0]['rhs']['args'][0]['right']=divisor
            request=dict(program=raw,driven=['u'],samples=[],transient=dict(pwl=[[[0,1],[1,1]]],output_times=[0,.5,1],stop=1,max_step=.125))
            with self.subTest(divisor=divisor),self.assertRaises(KernelError) as rejected:_invoke(request,KERNEL,20)
            self.assertEqual(rejected.exception.detail['kind'],'unsupported_floor')
        # Unsupported wrappers cannot hide a new Divide from the token and
        # then enter the old binary-only raw admission path without an owner.
        raw=copy.deepcopy(p.to_dict())
        floor=raw['events'][0]['body'][0]['then_body'][0]['rhs']
        floor['args']=[dict(op='power',base=floor['args'][0],exponent=1)]
        request=dict(program=raw,driven=['u'],samples=[],transient=dict(pwl=[[[0,1],[1,1]]],output_times=[0,.5,1],stop=1,max_step=.125))
        with self.assertRaises(KernelError) as rejected:_invoke(request,KERNEL,20)
        self.assertEqual(rejected.exception.detail['kind'],'unsupported_floor')
        with self.assertRaises(CompileError):program('if(V(u,r)>10)q=floor(V(u,r)/0);else q=7;', 'real q;')
