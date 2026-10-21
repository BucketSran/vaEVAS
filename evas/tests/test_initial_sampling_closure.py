"""Ordinary voltage aliases are sampled only at their lexical initial_step."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']

import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


class InitialVoltageAliases(unittest.TestCase):
    def compile(self, body, declarations='real a,b,q;'):
        return compile_sources({'initial-alias.va': model(body, declarations)}, [instance()])

    def test_preceding_voltage_alias_is_sampled_once_and_keeps_ordinary_execution(self):
        # a follows the live input; q captures a+.125 only at time zero.
        program = self.compile('a=V(u,r); b=a+0.125; @(initial_step) q=b; V(y,r)<+q+a;')
        result = transient(program, {'u': [[0,.5],[1,1.]]}, [0,1],
                           stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']], [1.125,1.625])
        self.assertEqual([state.name for state in program.states], ['q'])

    def test_alias_predicate_keeps_integer_state_and_selected_voltage_arms(self):
        program = self.compile('a=V(u,r); @(initial_step) begin '
                               'q=(a>0.25); b=(a>0.25)?a:0.125; end V(y,r)<+q+b;',
                               'real a,b; integer q;')
        for voltage, expected in [(.5,1.5),(.25,.125)]:
            with self.subTest(voltage=voltage):
                result = transient(program, {'u': [[0,voltage],[1,0]]}, [0,1],
                                   stop=1, max_step=1, kernel=KERNEL)
                self.assertEqual([row['voltages'][result['nodes'].index('y')]
                                  for row in result['solutions']], [expected,expected])

    def test_future_conditional_reassigned_and_feedback_aliases_reject(self):
        bodies = [
            '@(initial_step) q=a; a=V(u,r);',
            'a=b; b=V(u,r); @(initial_step) q=a;',
            'a=V(u,r); @(initial_step) q=a; a=2*V(u,r);',
            'if(V(u,r)>0) a=V(u,r); @(initial_step) q=a;',
            'a=q; @(initial_step) q=a;',
            'a=V(y,r); @(initial_step) q=a;',
            'a=0*V(y,r); @(initial_step) q=a;',
            'a=V(u,r)*V(u,r); @(initial_step) q=a;',
            'a=$abstime; @(initial_step) q=a;',
            'a=idt(V(u,r),0); @(initial_step) q=a;',
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body+' V(y,r)<+q;')

    def test_initial_and_runtime_selected_alias_samples_are_distinct(self):
        # u(0)=0 selects0 at startup; u(1/2)=1/2 selects the live
        # voltage at the timer. Later observations retain that sample.
        program = self.compile('a=(V(u,r)>0.25)?V(u,r):0; @(initial_step) q=a; '
                               '@(timer(0.5)) q=a; V(y,r)<+q;')
        result = transient(program, {'u': [[0,0],[1,1]]}, [0,.25,.75,1],
                           stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']], [0,0,.5,.5])

    def test_alias_cannot_hide_integer_real_conversion(self):
        with self.assertRaises(CompileError):
            self.compile('a=V(u,r); @(initial_step) q=a; V(y,r)<+q;',
                         'real a; integer q;')
        with self.assertRaises(CompileError):
            self.compile('a=V(u,r); @(initial_step) q=a; V(y,r)<+q;',
                         'integer a; real q;')

    def test_alias_cannot_discard_real_source_uncertainty_or_rounding(self):
        for rhs, voltage, errors in [('V(u,r)',.5,{'u':.01}),
                                      ('V(u,r)+0.2',.1,None)]:
            with self.subTest(rhs=rhs):
                program = self.compile('a='+rhs+'; @(initial_step) q=a; V(y,r)<+1000000*q;')
                with self.assertRaisesRegex(KernelError, 'initialization_precision'):
                    transient(program, {'u': [[0,voltage],[1,voltage]]}, [0,1],
                              stop=1, max_step=1, source_errors=errors, kernel=KERNEL)


class BootstrapNonseedBounds(unittest.TestCase):
    def compile(self, gain=1):
        # x is not read by either initial transition target. Its nonpoint
        # product must still reach p and the transition after timer(.5).
        body = '''@(initial_step) begin x=0; p=0; span=0; end
            @(timer(0)) begin span=1; x=0.45*V(u,r); end
            @(timer(0.5)) p=x;
            V(y,r)<+GAIN*transition(p,0,0.125,0.125)+transition(span,0,0.125,0.125);'''
        return compile_sources({'bootstrap-nonseed.va':model(body.replace('GAIN',str(gain)),
                                                             'real x,p,span;')}, [instance()])

    def test_rounding_of_an_unrelated_bootstrap_state_does_not_block_point_seeds(self):
        from fractions import Fraction
        # The answer uses the exact mathematical product of the two binary64
        # constants, rather than the rounded nominal state computed by EVAS.
        product = Fraction.from_float(.45)*Fraction.from_float(.16)
        self.assertNotEqual(Fraction.from_float(float(product)), product)
        result = transient(self.compile(), {'u':[[0,.16],[1,.16]]}, [0,.25,.75,1],
                           stop=1, max_step=1, kernel=KERNEL, vabstol=1e-8, reltol=0)
        for row, expected in zip(result['solutions'], [Fraction(1),Fraction(1),1+product,1+product]):
            self.assertLessEqual(abs(Fraction.from_float(row['voltages'][result['nodes'].index('y')])-expected),
                                 Fraction(1,10**8))

    def test_nonseed_rounding_is_retained_by_future_transition_and_amplification(self):
        # With relative tolerance zero, the inherited arithmetic interval after
        # 1e12 gain exceeds the unchanged 1e-8 absolute voltage budget.
        with self.assertRaises(KernelError) as failure:
            transient(self.compile(10**12), {'u':[[0,.16],[1,.16]]}, [0,.25,.75,1],
                      stop=1, max_step=1, kernel=KERNEL, vabstol=1e-8, reltol=0)
        self.assertEqual(failure.exception.detail['kind'], 'waveform_accuracy')
        self.assertIn('forward error', failure.exception.detail['message'])


class FixedArrayVoltageAliases(unittest.TestCase):
    def compile(self, body, declarations='real a[0:1],q;'):
        return compile_sources({'array-alias.va': model(body, declarations)}, [instance()])

    def test_only_preceding_fixed_slots_are_sampled_at_the_event(self):
        program = self.compile('a[0]=V(u,r); a[1]=2*a[0]; @(initial_step) q=0; '
                               '@(timer(0.5)) q=a[0]+a[1]; V(y,r)<+q;')
        result = transient(program, {'u': [[0,0],[1,1]]}, [0,.75,1],
                           stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']], [0.,1.5,1.5])
        self.assertEqual([state.name for state in program.states], ['q'])

    def test_array_initial_sampling_and_cross_use_the_same_fixed_slot(self):
        program = self.compile('a[0]=V(u,r); @(initial_step) q=a[0]; '
                               '@(cross(a[0]-0.5,+1)) q=a[0]+1; V(y,r)<+q;')
        result = transient(program, {'u': [[0,.25],[1,.75]]}, [0,.75,1],
                           stop=1, max_step=1, kernel=KERNEL)
        for actual, expected in zip([row['voltages'][result['nodes'].index('y')]
                                    for row in result['solutions']], [.25,1.5,1.5]):
            self.assertAlmostEqual(actual, expected, places=8)

    def test_future_or_reassigned_slot_is_never_made_lexically_available(self):
        for before, read, after in [
            ('a[0]=V(u,r);','a[1]','a[1]=V(u,r);'),
            ('','a[0]','a[0]=V(u,r);'),
            ('a[0]=V(u,r);','a[0]','a[0]=2*V(u,r);'),
            ('if(V(u,r)>0) a[0]=V(u,r);','a[0]',''),
        ]:
            with self.subTest(before=before,read=read,after=after), self.assertRaises(CompileError):
                self.compile('@(initial_step) q=0; '+before+
                             '@(timer(0.5)) q='+read+'; '+after+' V(y,r)<+q;')

    def test_instance_index_parameters_and_array_sizes_keep_scopes_private(self):
        text = model('a[SLOT]=V(u,r); @(initial_step) q=a[SLOT]; '
                     '@(timer(0.5)) q=2*a[SLOT]; V(y,r)<+q;',
                     'parameter integer N=1; parameter integer SLOT=0; real a[0:N],q;')
        program = compile_sources({'array-alias.va':text}, [
            instance('first', connections={'u':'u','y':'ya','r':'0'}, parameters={'N':1,'SLOT':0}),
            instance('second', connections={'u':'u','y':'yb','r':'0'}, parameters={'N':3,'SLOT':3})])
        result = transient(program, {'u': [[0,.25],[1,.75]]}, [0,.75,1],
                           stop=1, max_step=1, kernel=KERNEL)
        for name in ('ya','yb'):
            self.assertEqual([row['voltages'][result['nodes'].index(name)]
                              for row in result['solutions']], [.25,1.,1.])
        self.assertEqual([(state.instance,state.name) for state in program.states],
                         [('first','q'),('second','q')])

    def test_index_validation_in_dead_branches_remains_mandatory(self):
        for body in ['if(0>1) a[2]=V(u,r);',
                     'if(0>1) q=a[2];',
                     'if(0>1) a[V(u,r)]=1;']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile('a[0]=V(u,r); @(initial_step) q=0; '
                             '@(timer(0.5)) begin '+body+' q=a[0]; end V(y,r)<+q;')


class RuntimeVoltageAliases(unittest.TestCase):
    def compile(self, body, declarations='real a,q;'):
        return compile_sources({'runtime-alias.va': model(body, declarations)}, [instance()])

    def test_cross_guard_and_sample_use_the_physical_root_voltage(self):
        # a(t)=2t+.25 crosses 1.25 at t=.5. The sampled value is 1.25,
        # independent of a(0)=.25 and of the later output observation time.
        program = self.compile('a=2*V(u,r)+0.25; @(initial_step) q=0; '
                               '@(cross(a-1.25,+1)) q=a; V(y,r)<+q;')
        for times in ([0,.75,1], [0,.25,.75,1]):
            result = transient(program, {'u': [[0,0],[1,1]]}, times,
                               stop=1, max_step=1, kernel=KERNEL)
            values = [row['voltages'][result['nodes'].index('y')]
                      for row in result['solutions']]
            for time, value in zip(times, values):
                self.assertAlmostEqual(value, 0 if time < .5 else 1.25, places=8)

    def test_fixed_timer_alias_samples_current_input_and_condition(self):
        program = self.compile('a=2*V(u,r)+0.25; @(initial_step) q=0; '
                               '@(timer(0.5)) if(a>1) q=a; else q=-1; V(y,r)<+q;')
        for start, expected in [(0.25,1.75),(-0.25,-1.)]:
            result = transient(program, {'u': [[0,start],[1,start+1]]}, [0,.75,1],
                               stop=1, max_step=1, kernel=KERNEL)
            self.assertEqual([row['voltages'][result['nodes'].index('y')]
                              for row in result['solutions']], [0.,expected,expected])

    def test_runtime_aliases_keep_instance_parameter_binding(self):
        text = model('a=gain*V(u,r); @(initial_step) q=0; '
                     '@(timer(0.5)) q=a; V(y,r)<+q;',
                     'parameter real gain=1; real a,q;')
        program = compile_sources({'runtime-alias.va':text}, [
            instance('first', connections={'u':'u','y':'ya','r':'0'}),
            instance('second', connections={'u':'u','y':'yb','r':'0'}, parameters={'gain':2})])
        result = transient(program, {'u': [[0,0],[1,1]]}, [0,.75,1],
                           stop=1, max_step=1, kernel=KERNEL)
        for name, expected in [('ya',.5),('yb',1.)]:
            self.assertEqual([row['voltages'][result['nodes'].index(name)]
                              for row in result['solutions']], [0.,expected,expected])

    def test_reassigned_affine_alias_samples_its_event_position_and_holds(self):
        # Migrate exactly the former before/after repeated affine definition.
        # u(t)=t gives the sampled value1/2, which must still be held at t=1.
        # The later ordinary redefinition does not turn q into a live voltage.
        program = self.compile('@(initial_step)q=0; a=V(u,r); '
                               '@(timer(0.5))q=a; a=V(u,r); V(y,r)<+q;')
        result = transient(program, {'u': [[0,0],[1,1]]}, [0,.25,.75,1],
                           stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']], [0.,0.,.5,.5])

    def test_future_state_history_time_and_output_aliases_reject(self):
        aliases = [('', 'a=V(u,r);'), ('a=q;', ''),
                   ('a=V(y,r);', ''), ('a=0*V(y,r);', ''),
                   ('a=$abstime;', ''), ('a=idt(V(u,r),0);', ''),
                   ('if(V(u,r)>0) a=V(u,r);', '')]
        for before, after in aliases:
            with self.subTest(before=before,after=after), self.assertRaises(CompileError):
                self.compile('@(initial_step) q=0; '+before+
                             '@(timer(0.5)) q=a; '+after+' V(y,r)<+q;')

    def test_selected_body_alias_does_not_expand_cross_guard_admission(self):
        with self.assertRaises(CompileError):
            self.compile('a=(V(u,r)>0)?1:0; @(initial_step)q=0; '
                         '@(cross(a-0.5,+1))q=1; V(y,r)<+q;')

    def test_voltage_alias_cannot_be_a_dynamic_timer_or_cross_setting(self):
        for event in ['@(timer(a)) q=1;', '@(timer(0.5,0,a)) q=1;',
                      '@(cross(V(u,r)-0.5,a)) q=1;']:
            with self.subTest(event=event), self.assertRaises(CompileError):
                self.compile('a=V(u,r); @(initial_step) q=0; '+event+' V(y,r)<+q;')

    def test_sampling_retains_real_source_uncertainty_after_amplification(self):
        program = self.compile('a=V(u,r); @(initial_step) q=0; '
                               '@(timer(0.5)) q=a; V(y,r)<+1000000*q;')
        with self.assertRaises(KernelError):
            transient(program, {'u': [[0,.5],[1,.5]]}, [0,1], stop=1,
                      max_step=1, source_errors={'u':.01}, kernel=KERNEL)


if __name__ == '__main__':
    unittest.main()
