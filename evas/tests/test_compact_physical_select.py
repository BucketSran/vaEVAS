"""Physical source decisions keep compact IR without erasing event obligations."""
GUARDS = ['LANG', 'EVENT-CONDITIONS', 'EVENT-ORDER', 'TIMED-OPERATOR']

import dataclasses
from fractions import Fraction as Q
import os
from pathlib import Path
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get('EVAS_COMPACT_SOURCE_KERNEL', DEFAULT_KERNEL))


def source_sum(count=12, operand='V(u,r)'):
    return '+'.join(f'({operand}>{i+1}.0/16.0 ? {2**i}.0:0.0)' for i in range(count))


def wire_items(value):
    if dataclasses.is_dataclass(value):
        return 1+sum(wire_items(getattr(value, f.name)) for f in dataclasses.fields(value))
    if isinstance(value, (list, tuple)):
        return 1+sum(map(wire_items, value))
    if isinstance(value, dict):
        return 1+sum(map(wire_items, value.values()))
    return 1


class CompactPhysicalSelect(unittest.TestCase):
    def compile(self, body, declarations='real q;'):
        return compile_sources({'compact-physical.va':model(body, declarations)}, [instance()])

    def run_values(self, program, source=.6, **kwargs):
        result=transient(program, {'u':[[0,source],[1,source]]}, [0,.375,.625,1],
                         stop=1,max_step=.125,kernel=KERNEL,vabstol=kwargs.pop('vabstol',1e-12),reltol=0,**kwargs)
        return [row['voltages'][program.nodes.index('y')] for row in result['solutions']]

    def test_small_root_correlated_choice_keeps_legacy_conditional_certification(self):
        # At the physical root u=1/2 the strict comparison is false. The
        # ordinary Conditional path carries that root equality certificate;
        # a raw numeric Select over the root box cannot guess its nominal arm.
        p=self.compile('@(initial_step)q=0;@(cross(V(u,r)-0.5,+1))'
                       'q=(V(u,r)>0.5?1.0:0.0);V(y,r)<+q;')
        result=transient(p,{'u':[[0,0],[1,3]]},[0,.25,.5,1],
                         stop=1,max_step=.25,kernel=KERNEL,vabstol=1e-12,reltol=0)
        self.assertEqual([row['voltages'][p.nodes.index('y')] for row in result['solutions']],
                         [0,0,0,0])

    def test_small_clamped_ratio_keeps_legacy_exact_boundary_certification(self):
        # The original driven value is exactly the same binary64 number as the
        # divisor, so the real ratio is1. Interval division still encloses both
        # sides of1; legacy Conditional certification retains the exact value.
        p=self.compile('@(timer(0.25))q=(V(u,r)/0.9>1.0?1.0:V(u,r)/0.9);'
                       'V(y,r)<+q;')
        self.assertEqual(self.run_values(p,source=.9),[0,1,1,1])

    def test_small_internal_input_choice_keeps_existing_joint_voltage_path(self):
        # The consumer's input port is supplied by another instance's ordinary
        # affine equation. It is not an actual driven source, yet the legacy
        # Conditional can certify it in the joint event-voltage solve.
        consumer=model('@(initial_step)q=0;@(timer(0.25))'
                       'q=(V(u,r)>0.5?1.0:0.0);V(y,r)<+q;','real q;')
        driver=model('V(y,r)<+1.5*V(u,r);').replace('module m(', 'module driver(')
        p=compile_sources({'joint.va':consumer+driver},[
            instance(name='A',module='driver',connections=dict(u='u',y='z',r='0')),
            instance(name='B',connections=dict(u='z',y='y',r='0'))])
        result=transient(p,{'u':[[0,.5],[1,.5]]},[0,.5,1],
                         stop=1,max_step=.25,kernel=KERNEL,vabstol=1e-12,reltol=0)
        self.assertEqual([row['voltages'][p.nodes.index('y')] for row in result['solutions']],
                         [0,1,1])

    def test_twelve_independent_source_decisions_drive_physical_transition(self):
        p=self.compile(f'@(initial_step) q=0; @(timer(0.25)) begin q={source_sum()};'
                       'q=q/4095.0-0.5;end V(y,r)<+transition(q,0,0.03125,0.03125);')
        self.assertLess(wire_items(p),4096)
        want=Q(511,4095)-Q(1,2)
        values=self.run_values(p)
        self.assertEqual(values[0],0)
        for value in values[1:]:self.assertLessEqual(abs(Q(value)-want),Q(1,10**12))

    def test_compact_value_is_sampled_and_later_gain_keeps_source_error(self):
        p=self.compile(f'@(initial_step) begin q=0;s=0;end @(timer(0.25)) q={source_sum()};'
                       '@(timer(0.5)) s=V(z); V(z)<+q; V(y,r)<+s;','real q,s;electrical z;')
        self.assertEqual(self.run_values(p),[0,0,511,511])
        # A value arm still depends continuously on its source inside one branch;
        # storage and a later gain must retain that source band's uncertainty.
        rhs='+'.join(['(V(u,r)>0.0?V(u,r):0.0)']*12)
        p=self.compile(f'@(initial_step) begin q=0;s=0;end @(timer(0.25)) q={rhs};'
                       '@(timer(0.5)) s=1e8*q; V(y,r)<+s;','real q,s;')
        with self.assertRaisesRegex(KernelError,'(event_accuracy|waveform_accuracy).*at y'):
            self.run_values(p,source=1,source_errors={'u':1e-5},vabstol=1e-3)

    def test_source_box_crossing_a_guard_is_not_replaced_by_nominal_selection(self):
        p=self.compile(f'@(timer(0.25)) q={source_sum()};V(y,r)<+q;')
        with self.assertRaisesRegex(KernelError,'event_condition: cannot certify event expression selection'):
            self.run_values(p,source=.5,source_errors={'u':.01},vabstol=.1)

    def test_original_dead_arm_name_and_history_obligations_remain(self):
        for tail,reason in [('missing','unknown'),('idt(V(u,r),0)','history/operator')]:
            rhs=source_sum()+'+(V(u,r)>0.0?0.0:'+tail+')'
            with self.subTest(tail=tail),self.assertRaisesRegex(CompileError,reason):
                self.compile(f'@(timer(0.25)) q={rhs};V(y,r)<+q;')

    def test_declared_input_port_still_requires_an_actual_driven_source(self):
        # Declaration is only a frontend candidate; an input port driven by an
        # internal equation cannot supply the causal sampled-value certificate.
        p=self.compile(f'@(timer(0.25)) q={source_sum()};V(u,r)<+1.0;V(y,r)<+q;')
        with self.assertRaisesRegex(KernelError,'state-independent driven voltage inputs'):
            transient(p,{},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_legacy_expansion_boundary_counts_each_wire_use_and_guard_choice(self):
        from evas.compact_source_select import _exceeds_legacy_expansion
        from evas.instance_compiler import Compilation,InstanceCompiler
        from evas.ir import Affine,Binary,Origin,Select,Term
        origin=Origin('expansion.va',1,1,'D')
        zero,one=Affine(0.,()),Affine(1.,())
        choice=Select('gt',Affine(0.,(Term(1,1.),)),zero,one,zero,origin)
        legacy=InstanceCompiler.__new__(InstanceCompiler)
        legacy.compilation=Compilation(('0','u'),False)
        legacy.compact_event_candidate=lambda:False
        def expression(first,count):
            for _ in range(count):first=Binary('add',first,choice)
            return first
        #11 independent choices have2048 leaves/4095 visited expansion nodes.
        # Reusing the same Python object does not reduce wire multiplicity.
        within=expression(choice,10)
        self.assertFalse(_exceeds_legacy_expansion(within))
        InstanceCompiler.event_assignment(legacy,0,within,origin)
        beyond=expression(choice,11)
        self.assertTrue(_exceeds_legacy_expansion(beyond))
        with self.assertRaisesRegex(CompileError,'4096'):
            InstanceCompiler.event_assignment(legacy,0,beyond,origin)
        # Choices inside a predicate multiply both value alternatives, whose
        # own leaf counts add rather than multiply. This tree starts with6
        # leaves, so8/9 extra independent choices straddle the old limit.
        guarded=Select('gt',choice,zero,choice,one,origin)
        within=expression(guarded,8)
        self.assertFalse(_exceeds_legacy_expansion(within))
        InstanceCompiler.event_assignment(legacy,0,within,origin)
        beyond=expression(guarded,9)
        self.assertTrue(_exceeds_legacy_expansion(beyond))
        with self.assertRaisesRegex(CompileError,'4096'):
            InstanceCompiler.event_assignment(legacy,0,beyond,origin)

    def test_small_assignment_ir_matches_the_existing_legacy_route(self):
        from unittest.mock import patch
        bodies=[f'@(timer(0.25))q={source_sum(n)};V(y,r)<+q;' for n in [1,2,3]]
        bodies+=['@(timer(0.25))q=(V(u,r)/0.9>1.0?1.0:V(u,r)/0.9);V(y,r)<+q;']
        for body in bodies:
            actual=self.compile(body).to_dict()
            # This is a representation compatibility check against the real
            # legacy producer; analytic public tests above own the semantics.
            with patch('evas.instance_compiler.compact_source_assignment',return_value=False):
                original=self.compile(body).to_dict()
            self.assertEqual(actual,original)

    def test_integer_257_bins_and_original_4096_dispatch_budget_remain(self):
        for maximum in [255,256]:
            body=(f'@(initial_step) if(V(u,r)>0) n=0;else n={maximum};'
                  '@(timer(0.25)) q=n/1;V(y,r)<+q;')
            if maximum==255:
                self.compile(body,'integer n;real q;')
            else:
                with self.assertRaisesRegex(CompileError,r'quotient-bin budget \(256\)'):
                    self.compile(body,'integer n;real q;')
        # Both writes are parameter-dead. Their original4098 slot dispatch
        # leaves still count before pruning, independently of compact scalars.
        with self.assertRaisesRegex(CompileError,r'dispatch budget \(4096'):
            self.compile('@(timer(0.25)) if(mode==0) begin a[n]=1;a[n]=2;end V(y,r)<+1;',
                         'parameter integer mode=1;integer n;real a[0:2048];')

    def test_wire_budget_still_counts_repeated_source_subtrees(self):
        from evas.ir import Affine,Binary
        from evas.limits import check_ir
        value=Affine(1.,())
        for _ in range(15):value=Binary('add',value,value)
        with self.assertRaisesRegex(CompileError,'100000'):
            check_ir(value)

    def test_held_time_and_observer_math_do_not_gain_compact_physical_admission(self):
        for operand in ['q','$abstime']:
            with self.subTest(operand=operand),self.assertRaisesRegex(CompileError,'expanded event decision budget'):
                self.compile(f'@(timer(0.25)) q={source_sum(operand=operand)};V(y,r)<+q;')
        with self.assertRaises(CompileError):
            self.compile(f'@(timer(0.25)) q={source_sum()}+sin(V(u,r));V(y,r)<+q;')


if __name__=='__main__':unittest.main()
