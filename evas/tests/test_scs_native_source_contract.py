"""Restricted native SCS source entry, with independent literal/quarter-cycle answers.

Parser tests stop at load_scs. Kernel tests traverse simulate_scs or the public
compile_sources/transient path. Archived Spectre evidence is limited to zero
transient phase without delay/modulation; MEG/meg remain outside this contract.
"""
GUARDS = ['LANG', 'ANALOG', 'COMPOSE']

import copy
import os
from pathlib import Path
import tempfile
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from evas.scs import load_scs, simulate_scs

KERNEL = Path(os.environ.get('EVAS_KERNEL',
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel'))
NATIVE_ZERO = 'spectre-native-transient-zero-phase-v1'
MODEL = '''`include "disciplines.vams"
module native_probe(x,y); input x; output y; electrical x,y;
analog begin V(y)<+V(x); end endmodule
'''


class NativeSourceFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'probe.va').write_text(MODEL)
        self.path = self.root/'source.scs'

    def deck(self, settings='type=sine sinedc=0.5 ampl=0.25 freq=1'):
        self.path.write_text('simulator lang=spectre\nglobal 0\n'
            'ahdl_include "probe.va"\n'
            'VX (x 0) vsource '+settings+'\n'
            'XD (x y) native_probe\n'
            'tran tran stop=1 maxstep=0.25\nsave x y\n')
        return self.path

    def descriptor(self, settings):
        return load_scs(self.deck(settings)).manifest['transient']['analytic_sources']['x']


class NativeSourceParserContracts(NativeSourceFixture):
    def test_native_Meg_M_m_preserve_distinct_scales(self):
        # Values come from native SI scaling, not from EVAS source arithmetic.
        for spelling, expected in [('29Meg', 29000000.), ('29M', 29000000.),
                                   ('29m', .029), ('20Meg', 20000000.),
                                   ('13Meg', 13000000.)]:
            with self.subTest(spelling=spelling):
                source = self.descriptor('type=sine sinedc=0.5 ampl=0.25 '
                                         f'freq={spelling} sinephase=0')
                self.assertEqual(source['freq'], expected)
                self.assertEqual(source['parameter_origin'], 'explicit-v1')

    def test_omitted_zero_phase_has_native_origin_not_explicit_origin(self):
        settings = 'type=sine sinedc=0.5 ampl=0.25 freq=1'
        implicit = self.descriptor(settings)
        explicit = self.descriptor(settings+' sinephase=0')
        self.assertEqual(implicit['sinephase'], 0.)
        self.assertEqual(implicit['parameter_origin'], NATIVE_ZERO)
        self.assertEqual(explicit['parameter_origin'], 'explicit-v1')
        for field in ('kind', 'sinedc', 'ampl', 'freq', 'sinephase',
                      'source_name', 'terminals', 'polarity'):
            self.assertEqual(implicit[field], explicit[field], field)

    def test_Meg_decimal_exponent_and_signed_values_without_frequency_domain_changes(self):
        for sinedc, ampl, dc_value, amplitude in [
                ('+1.25Meg', '-2.5e-1Meg', 1250000., -250000.),
                ('-.5Meg', '+2e-3Meg', -500000., 2000.)]:
            with self.subTest(sinedc=sinedc, ampl=ampl):
                source = self.descriptor(
                    f'type=sine sinedc={sinedc} ampl={ampl} freq=1 sinephase=0')
                self.assertEqual(source['sinedc'], dc_value)
                self.assertEqual(source['ampl'], amplitude)

    def test_phase20_70_do_not_become_transient_sinephase(self):
        settings = 'type=sine sinedc=0.5 ampl=0.25 freq=1'
        for phase in (20, 70, -17.25, 123.5):
            with self.subTest(phase=phase):
                source = self.descriptor(settings+f' phase={phase}')
                self.assertEqual(source['sinephase'], 0.)
                self.assertEqual(source['parameter_origin'], NATIVE_ZERO)

    def test_native_origin_keeps_original_tokens_and_small_signal_phase_metadata(self):
        bench = load_scs(self.deck('type=sine sinedc=0.5 ampl=0.25 freq=29Meg phase=-17.25'))
        origin = bench.metadata['sine_source_origins']['VX']
        self.assertEqual(origin['dialect'], 'spectre-native')
        self.assertEqual(origin['analysis'], 'tran')
        self.assertEqual(origin['parameter_origin'], NATIVE_ZERO)
        self.assertEqual(origin['settings']['phase'], -17.25)
        self.assertNotIn('sinephase', origin['settings'])
        tokens = origin['tokens']
        self.assertIn('29Meg', [item['text'] for item in tokens])
        self.assertIn('phase', [item['text'] for item in tokens])
        self.assertTrue(all(item['source'] == str(self.path.resolve()) for item in tokens))
        self.assertTrue(all(item['line'] == 4 and item['column'] > 0 for item in tokens))

    def test_continued_statement_preserves_parameter_reference_tokens(self):
        path = self.deck('type=sine sinedc=0.5 ampl=0.25 freq=freq0 \\\n phase=phase0')
        path.write_text(path.read_text().replace('VX (x 0)',
            'parameters freq0=1 phase0=-17.25\nVX (x 0)'))
        origin = load_scs(path).metadata['sine_source_origins']['VX']
        # Meaningful tokens retain the original spellings, references and
        # positions across the continuation. Whitespace is not a token.
        expected = ('VX ( x 0 ) vsource type = sine sinedc = 0.5 ampl = 0.25 '
                    'freq = freq0 phase = phase0').split()
        self.assertEqual([item['text'] for item in origin['tokens']], expected)
        self.assertEqual(origin['settings']['freq'], 1.)
        self.assertEqual(origin['settings']['phase'], -17.25)
        reference = next(item for item in origin['tokens'] if item['text'] == 'freq0')
        phase = next(item for item in origin['tokens'] if item['text'] == 'phase0')
        self.assertEqual((reference['line'], phase['line']), (5, 6))
        self.assertTrue(all(item['source'] == str(path.resolve()) for item in origin['tokens']))

    def test_unknown_spellings_delay_modulation_and_parameters_stay_rejected(self):
        settings = 'type=sine sinedc=0.5 ampl=0.25 freq=1 sinephase=0'
        cases = [settings.replace('freq=1', 'freq=29MEG'),
                 settings.replace('freq=1', 'freq=29meg'),
                 settings+' delay=0', settings+' damping=0',
                 settings+' modulation=0', settings+' unknown=0',
                 settings+' sinephase=0', settings.replace('freq=1', 'freq=0'),
                 settings+' freq=2', settings.replace('ampl=0.25', 'ampl=1e309Meg'),
                 settings.replace('freq=1', 'freq=29Megx'),
                 settings.replace('freq=1', 'freq=29Meg2'),
                 settings.replace('sinephase=0', 'sinephase=90 phase=20')]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CompileError):
                load_scs(self.deck(source))


class NativeSourceKernelContracts(NativeSourceFixture):
    def assert_quarter_cycle(self, result):
        # dc + A*sin(2*pi*t), t=0,1/4,1/2,3/4,1. Exact analytic values.
        expected = [.5, .75, .5, .25, .5]
        self.assertEqual(result['saved']['times'], [0., .25, .5, .75, 1.])
        for node in ('x', 'y'):
            saved_index = result['saved']['nodes'].index(node)
            evidence_index = result['nodes'].index(node)
            for row, want in enumerate(expected):
                self.assertLessEqual(abs(result['saved']['values'][row][saved_index]-want), 1e-12)
                bounds = result['observation_evidence']['voltage_bounds_V'][row][evidence_index]
                self.assertLessEqual(bounds[0], want)
                self.assertGreaterEqual(bounds[1], want)

    def test_native_default_and_phase20_70_follow_zero_phase_in_actual_kernel(self):
        settings = 'type=sine sinedc=0.5 ampl=0.25 freq=1'
        for extra in (' sinephase=0', '', ' phase=20', ' phase=70', ' phase=-17.25'):
            with self.subTest(extra=extra):
                result = simulate_scs(self.deck(settings+extra), kernel=KERNEL, timeout=30)
                self.assert_quarter_cycle(result)

    def test_kernel_rejects_unknown_origin_and_nonzero_forged_default(self):
        bench = load_scs(self.deck('type=sine sinedc=0.5 ampl=0.25 freq=1 sinephase=0'))
        program = compile_sources(bench.sources, [Instance(**item) for item in bench.manifest['instances']],
                                  external_nodes=bench.manifest['transient']['sources'])
        for origin, sinephase in [('unknown', 0.), (NATIVE_ZERO, 90.)]:
            with self.subTest(origin=origin, sinephase=sinephase):
                request = copy.deepcopy(bench.manifest['transient'])
                request['analytic_sources']['x'].update(parameter_origin=origin, sinephase=sinephase)
                with self.assertRaises(KernelError):
                    transient(program, kernel=KERNEL, timeout=30, **request, **bench.manifest['tolerances'])


if __name__ == '__main__':
    unittest.main()
