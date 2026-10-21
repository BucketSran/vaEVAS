"""Independent differential-source contracts through the SCS/Rust entry."""
GUARDS = ["LANG", "LIN", "COMPOSE", "DEV:scs-input"]

from fractions import Fraction as Q
from pathlib import Path
import tempfile
import unittest

from evas import CompileError, KernelError, Instance, compile_sources, transient
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class ScsFloatingVoltage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'm.va').write_text(model('V(y,r)<+3*V(u,r);'))
        self.path = self.root / 'tb.scs'

    def deck(self, sources, save='u y ref'):
        self.path.write_text('simulator lang=spectre\nahdl_include "m.va"\n' + sources +
                             '\nDUT (u y 0) m\ntran tran stop=1 maxstep=.25\n' +
                             (f'save {save}\n' if save else ''))
        return self.path

    def test_nonzero_reference_and_reversed_floating_pwl(self):
        # V(u)-V(ref)=+/-triangle; ref=.25; y=3u.
        for terminals, sign in [('u ref', 1), ('ref u', -1)]:
            with self.subTest(terminals=terminals):
                result = simulate_scs(self.deck('VR (ref 0) vsource dc=.25\n'
                    f'VS ({terminals}) vsource type=pwl wave=[0 0 .5 1 1 0]'), kernel=KERNEL)
                for row, v in zip(result['saved']['values'], [0, .5, 1, .5, 0]):
                    self.assertEqual(row, [.25 + sign*v, 3*(.25 + sign*v), .25])

    def test_reference_can_be_a_solved_voltage_and_source_order_is_irrelevant(self):
        # y=3u and u-y=.25 force u=-.125, y=-.375.
        result = simulate_scs(self.deck('VS (u y) vsource dc=.25', save='u y'), kernel=KERNEL)
        for u, y in result['saved']['values']:
            self.assertAlmostEqual(u, -.125, delta=1e-12)
            self.assertAlmostEqual(y, -.375, delta=1e-12)

    def test_internal_drive_name_does_not_shadow_user_node_or_default_save(self):
        result = simulate_scs(self.deck('VR (ref 0) vsource dc=.25\n'
            'VX (__evas_scs_voltage 0) vsource dc=.75\nVS (u ref) vsource dc=.5', save=''), kernel=KERNEL)
        self.assertIn('__evas_scs_voltage', result['saved']['nodes'])
        self.assertEqual(set(result['saved']['nodes']), {'0', 'u', 'y', 'ref', '__evas_scs_voltage'})

    def test_floating_pulse_preserves_shape_and_inherited_voltage_error(self):
        # At large times the rounded .2-second edges move by > 2e-7 V.
        # An analytic rational pulse checks the original curve through ref+.pulse
        # and gain=3. Without the shape, that uncertainty must still reject.
        self.deck('VR (ref 0) vsource dc=.25\n'
                  'VS (u ref) vsource type=pulse val0=0 val1=1 delay=1e9 '
                  'rise=.2 width=.2 fall=.2 period=1', save='u y')
        self.path.write_text(self.path.read_text().replace('stop=1 maxstep=.25',
                                                         'stop=1000000001 maxstep=1000000001'))
        bench = load_scs(self.path)
        program = compile_sources(bench.sources, [Instance(**i) for i in bench.manifest['instances']],
                                  external_nodes=bench.manifest['transient']['sources'])
        generic = {k:v for k,v in bench.manifest['transient'].items() if k != 'source_shapes'}
        with self.assertRaisesRegex(KernelError, 'at y'):
            transient(program, kernel=KERNEL, reltol=0, vabstol=5e-7, **generic)
        result = simulate_scs(self.path, kernel=KERNEL)
        for t, (u, y) in zip(result['saved']['times'], result['saved']['values']):
            elapsed, edge = Q(t)-Q(1e9), Q(.2)
            pulse = (Q(0) if elapsed<=0 else elapsed/edge if elapsed<edge else Q(1)
                     if elapsed<2*edge else 3-elapsed/edge if elapsed<3*edge else Q(0))
            expected = Q(1,4)+pulse
            for actual, gain in ((u,1), (y,3)):
                self.assertLessEqual(abs(Q(actual)-gain*expected),
                                     Q(1e-12)+Q(1e-10)*abs(Q(actual)))

    def test_unanchored_and_inconsistent_source_constraints_reject(self):
        for sources in ('VS (u ref) vsource dc=.5',
                        'VR (ref 0) vsource dc=.25\nVS (u ref) vsource dc=.5\nVU (u 0) vsource dc=2'):
            with self.subTest(sources=sources), self.assertRaises((CompileError, KernelError)):
                simulate_scs(self.deck(sources), kernel=KERNEL)

    def test_same_terminal_and_unsupported_floating_source_settings_reject(self):
        for source in ('VS (u u) vsource dc=1', 'VS (u ref) vsource dc=1 mystery=2',
                       'VS (u ref) vsource type=sine ampl=1 freq=1'):
            with self.subTest(source=source), self.assertRaises(CompileError):
                load_scs(self.deck(source))


class NonzeroReferenceGuardProjection(unittest.TestCase):
    def program(self, extra='', *, gain=1, slope=1, threshold=.5):
        # x=ref+u and x-ref=u: the supplied PWL fixes the threshold root.
        # An unrelated rail*history output must not alter that source identity.
        va = ('`include "disciplines.vams"\nmodule alias_guard(u,ref,vdd,y); '
              'input u,ref,vdd; output y; electrical u,ref,vdd,y,x; integer q; '
              f'analog begin V(x,ref)<+{float(slope)!r}*V(u); @(initial_step) q=0; '
              f'@(cross(V(x,ref)-{float(threshold)!r},+1)) q=1; '
              f'V(y)<+{float(gain)!r}*V(vdd)*transition(q,0,0.01,0.01); '
              +extra+' end endmodule')
        return compile_sources({'alias.va':va},
            [Instance('dut','alias_guard',dict(u='u',ref='ref',vdd='vdd',y='y'))],
            external_nodes=['u','ref','vdd'])

    def run_alias(self, program, times, **kwargs):
        return transient(program, {'u':[[0,0],[1,1]],'ref':[[0,.125],[1,.125]],
            'vdd':[[0,.9],[1,.9]]}, times, stop=1, max_step=.25, kernel=KERNEL, **kwargs)

    def test_nonzero_reference_alias_uses_original_root_despite_unrelated_product(self):
        result = self.run_alias(self.program(), [0,.25,.5,.505,.51,1])
        column = result['nodes'].index('y')
        for row, expected in zip(result['solutions'], [0,0,0,.45,.9,.9]):
            self.assertAlmostEqual(row['voltages'][column], expected, delta=1e-10)

    def test_root_query_does_not_change_accepted_history_after_amplification(self):
        program = self.program(gain=1e6, slope=3, threshold=1)
        baseline = self.run_alias(program, [0,.25,.35,1])
        queried = self.run_alias(program, [0,.25,1/3,.35,1])
        b = dict(zip([0,.25,.35,1], baseline['solutions']))
        q = dict(zip([0,.25,1/3,.35,1], queried['solutions']))
        for time in b:
            self.assertEqual(b[time], q[time])
        self.assertAlmostEqual(b[1]['voltages'][baseline['nodes'].index('y')], 9e5, delta=1e-7)

    def test_alias_guard_retains_original_shape_and_rejects_insufficient_source_band(self):
        # The true ramp is 1.001*t, enclosed by the nominal t ramp with 1mV.
        # Its event is at .5/1.001, not the nominal .5-second crossing.
        shape = [dict(time_numerator='0', time_denominator='1', value_V=0.),
                 dict(time_numerator='1', time_denominator='1', value_V=1.001)]
        program = self.program()
        result = self.run_alias(program, [0,.5,1], source_errors={'u':.001},
                                source_shapes={'u':shape})
        root = Q(.5)/Q(1.001)
        expected = Q(.9)*(Q(.5)-root)/Q(.01)
        actual = result['solutions'][1]['voltages'][result['nodes'].index('y')]
        self.assertAlmostEqual(actual, float(expected), delta=1e-10)
        with self.assertRaises(KernelError):
            self.run_alias(program, [0,.5,1], source_errors={'u':.0001},
                           source_shapes={'u':shape})

    def test_alias_projection_cannot_hide_conflicting_or_cyclic_voltage_constraints(self):
        for extra in ('V(x)<+9;', 'V(u)<+V(x,ref)+1;'):
            with self.subTest(extra=extra), self.assertRaises((CompileError, KernelError)):
                self.run_alias(self.program(extra), [0,.5,1])


class AliasRootIdentity(unittest.TestCase):
    def test_one_physical_alias_root_owns_both_transition_deadlines(self):
        # This three-term guard has rounded endpoint enclosures. The physical
        # source expression, rather than those enclosures, proves one root.
        va = ('`include "disciplines.vams"\nmodule deadlines(u,ref,vinn,y,z); '
              'input u,ref,vinn; output y,z; electrical u,ref,vinn,y,z,x; integer q; '
              'analog begin V(x,ref)<+V(u); @(initial_step) q=0; '
              '@(cross(V(x,ref)-V(vinn)-0.005,+1)) q=1; '
              'V(y)<+transition(q,0,0.05,0.05); '
              'V(z)<+transition(1-q,0,0.05,0.05); end endmodule')
        program = compile_sources({'deadlines.va':va}, [Instance('dut','deadlines',
            dict(u='u',ref='ref',vinn='vinn',y='y',z='z'))], external_nodes=['u','ref','vinn'])
        root = (Q(.45)+Q(.005)-Q(.44))/(Q(.456)-Q(.44))
        sources = {'u':[[0,.44],[1,.456]], 'ref':[[0,.125],[1,.125]],
                   'vinn':[[0,.45],[1,.45]]}
        for times in ([0,.25,.95,1], [0,.25,float(root),.95,1]):
            with self.subTest(times=times):
                result = transient(program, sources, times, stop=1, max_step=.25, kernel=KERNEL)
                y, z = (result['nodes'].index(n) for n in ('y','z'))
                for time, row in zip(times, result['solutions']):
                    expected = min(Q(1), max(Q(0), (Q(time)-root)/Q(.05)))
                    self.assertAlmostEqual(row['voltages'][y], float(expected), delta=1e-10)
                    self.assertAlmostEqual(row['voltages'][z], float(1-expected), delta=1e-10)

    def test_distinct_neighbouring_alias_roots_keep_separate_callbacks(self):
        # Near roots have overlapping tolerance windows but different original
        # rational times. An alias must retain that distinction, not batch them.
        va = ('`include "disciplines.vams"\nmodule neighbours(u,ref,y); '
              'input u,ref; output y; electrical u,ref,y,x; integer n,m; '
              'analog begin V(x,ref)<+V(u); @(initial_step) begin n=0; m=0; end '
              '@(cross(V(x,ref)-0.5,+1)) n=n+1; '
              '@(cross(V(x,ref)-0.5000000000000001,+1)) m=m+1; '
              'V(y)<+1.0*n+m; end endmodule')
        program = compile_sources({'neighbours.va':va}, [Instance('dut','neighbours',
            dict(u='u',ref='ref',y='y'))], external_nodes=['u','ref'])
        result = transient(program, {'u':[[0,.1],[1,.9]],'ref':[[0,.125],[1,.125]]},
                           [0,1], stop=1, max_step=1, kernel=KERNEL)
        events = result['transient']['events']
        self.assertEqual([event['event'] for event in events], [0,1])
        self.assertLess(events[0]['time'], events[1]['time'])
        self.assertEqual(result['transient']['states'][-1], [1,1])
