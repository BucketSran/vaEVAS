"""Native sampled floor retains the original write before later saturation.

Answers are floor(3)=3, floor(-0.5)=-1 and exact signed32 limits. The
cross-root input is -1/8 so its floor argument is exactly -1, not its
rounded execution-time representative. No deck ranges prove admission.
"""
GUARDS=['LANG','EVENT-ORDER','CROSS','EVENT-CONDITIONS','COMPOSE']
import copy
import json
import unittest
from evas import CompileError, KernelError, compile_sources, transient
from evas.ir import SCHEMA_VERSION
from evas.runtime import _invoke
from test_affine import KERNEL, instance, model


def program(body='q=floor(8*V(u,r));',decl='integer q;',event='timer(0.25)'):
    return compile_sources({'native_floor.va':model('@(initial_step) q=0; @('+event+') begin '+body+' end V(y,r)<+q;',decl)},[instance()])


def run(p,value=.375,**options):
    return transient(p,{'u':[[0,value],[1,value]]},[0,.5,1],stop=1,max_step=.125,kernel=KERNEL,**options)


class NativeEventFloor(unittest.TestCase):
    def test_unbounded_operand_positive_negative_and_integer_boundaries(self):
        for value,want in [(0.375,3),(-0.0625,-1),(0.5,4),(-0.125,-1),(-0.12500000000000003,-2),(268435455.875,2147483647),(-268435456.,-2147483648)]:
            with self.subTest(value=value):
                r=run(program(),value)
                self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],[0,want,want])

    def test_original_integer_write_overflow_cannot_be_erased_by_clamp(self):
        p=program('q=floor(8*V(u,r));if(q<0)q=0;if(q>7)q=7;')
        for value in [268435456.,-268435456.125,1e308]:
            with self.subTest(value=value),self.assertRaises(KernelError):run(p,value)
        for value,want in [(-0.0625,0),(0.375,3),(2,7)]:
            with self.subTest(value=value):
                r=run(p,value);self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],want)

    def test_floor_sample_drives_contribution_mode_after_original_clamps(self):
        text=model('@(initial_step)q=0;@(timer(0.25))begin q=floor(8*V(u,r));if(q<0)q=0;if(q>7)q=7;end V(y,r)<+(q<2?0:1);','integer q;')
        p=compile_sources({'floor_mode.va':text},[instance()])
        r=run(p)
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],[0,1,1])

    def test_real_floor_value_does_not_gain_source_integer_type(self):
        with self.assertRaises(CompileError):program('q=floor(8*V(u,r))&1;')

    def test_hidden_state_internal_feedback_and_time_are_not_native_inputs(self):
        for body in ['q=floor(q+V(u,r));','q=floor(V(y,r));','q=floor(0*V(y,r)+V(u,r));','q=floor($abstime+V(u,r));']:
            with self.subTest(body=body),self.assertRaises(CompileError):program(body)

    def test_floor_keeps_real_division_and_exact_physical_root(self):
        p=program('q=floor(8*V(u,r))/2;','real q;')
        r=run(p);self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],1.5)
        text=model('@(initial_step) q=0; @(cross(V(u,r)-0.5,+1)) q=floor(8*(V(u,r)-0.625)); V(y,r)<+q;', 'integer q;')
        p=compile_sources({'root_floor.va':text},[instance()])
        r=transient(p,{'u':[[0,0],[1,1]]},[0,.75,1],stop=1,max_step=.125,kernel=KERNEL)
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],[0,-1,-1])

    def test_original_unselected_floor_operands_are_audited(self):
        for expression in ['floor(0*V(y,r)+V(u,r))', 'floor(q+V(u,r))', 'floor(V(u,r)+$abstime)']:
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                program('if(1>0) q=1;else q='+expression+';')

    def test_actual_driven_nodes_are_verified_by_kernel(self):
        p=program().to_dict()
        with self.assertRaises(KernelError):
            _invoke(dict(program=p,driven=[],samples=[],transient=dict(pwl=[],output_times=[0,1],stop=1,max_step=.125)),KERNEL)

    def test_cross_bin_source_error_is_not_frozen_by_later_clamp(self):
        p=program('q=floor(8*V(u,r));if(q<0)q=0;if(q>7)q=7;')
        with self.assertRaises(KernelError):run(p,-.125,source_errors={'u':1e-8},vabstol=.1,reltol=0)

    def test_old_finite_table_path_is_preserved(self):
        p=program('c=V(u,r);if(c<0)c=0;if(c>1)c=1;q=floor(8*c);','integer q;real c;')
        self.assertNotIn('"function": "floor"',json.dumps(p.to_dict()))
        self.assertEqual(run(p)['solutions'][-1]['voltages'][2],3)

    def test_native_ir_arity_origin_and_old_version_reject(self):
        p=program().to_dict()
        floor=p['events'][0]['body'][0]['rhs']
        for field,value in [('args',[]),('args',list(floor['args'])*2),('origin',dict(floor['origin'],instance='other')),('origin',dict(floor['origin'],line=0))]:
            bad=copy.deepcopy(p);bad['events'][0]['body'][0]['rhs'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(KernelError):
                _invoke(dict(program=bad,driven=['u'],samples=[],transient=dict(pwl=[[[0,.375],[1,.375]]],output_times=[0,1],stop=1,max_step=.125)),KERNEL)
        for version in [SCHEMA_VERSION-1,SCHEMA_VERSION+1]:
            bad=copy.deepcopy(p);bad['schema_version']=version
            with self.subTest(version=version),self.assertRaises(KernelError):
                _invoke(dict(program=bad,driven=['u'],samples=[[1]]),KERNEL)
