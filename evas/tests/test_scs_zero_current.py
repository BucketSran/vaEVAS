"""Literal exact-zero branch is neutral, preserves provenance and cannot anchor."""
GUARDS = ['LANG', 'LIN', 'COMPOSE', 'DEV:scs-input']

from fractions import Fraction as Q
from pathlib import Path
import tempfile
import unittest

from evas import CompileError, Instance, KernelError, compile_sources
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class ScsZeroCurrent(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.va = self.root / 'm.va'
        self.va.write_text(model('V(y,r)<+3*V(u,r);'))
        self.path = self.root / 'tb.scs'

    def deck(self, extra='', *, sources='VU (u 0) vsource type=pwl wave=[0 0 .5 1 1 0]',
             device='DUT (u y 0) m', step='.25'):
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n' +
            sources+'\n'+device+'\n'+extra+'\ntran tran stop=1 maxstep='+step+'\nsave u y\n')
        return self.path

    def program(self, bench):
        return compile_sources(bench.sources, [Instance(**i) for i in bench.manifest['instances']],
                               external_nodes=bench.manifest['transient']['sources']).to_dict()

    def test_literal_ledger_and_canonical_program_preserve_original_topology(self):
        baseline = load_scs(self.deck())
        expected = self.program(baseline)
        for literal in ['0', '+0', '-0.0', '0m', '0e-400', '-0.000e9999']:
            for terminals in ['y 0', '0 y', 'u y']:
                with self.subTest(literal=literal, terminals=terminals):
                    bench = load_scs(self.deck(f'IZ ({terminals}) isource type=dc dc={literal}'))
                    self.assertEqual(bench.manifest, baseline.manifest)
                    self.assertEqual(self.program(bench), expected)
                    ledger = bench.metadata['zero_current_sources']
                    self.assertEqual(len(ledger), 1)
                    entry = ledger[0]
                    self.assertEqual(entry['name'], 'IZ')
                    self.assertEqual(entry['terminals'], terminals.split())
                    self.assertEqual(entry['settings']['type'], 'dc')
                    self.assertEqual(entry['proof']['dc_literal'], literal)
                    self.assertEqual(entry['proof']['kind'], 'exact_zero_dc_literal')
                    self.assertEqual(entry['origin']['source'], str(self.path.resolve()))
                    self.assertEqual(entry['origin']['line'], 6)
                    self.assertEqual([f['name'] for f in entry['fields']], ['type', 'dc'])
                    self.assertEqual(''.join(t['text'] for t in entry['fields'][1]['tokens']), literal)
        # All independently valid branches must survive in the ledger; none is a source input.
        bench = load_scs(self.deck('\n'.join(f'I{i} (y 0) isource dc=0' for i in range(300))))
        self.assertEqual([e['name'] for e in bench.metadata['zero_current_sources']],
                         [f'I{i}' for i in range(300)])
        self.assertEqual(bench.manifest, baseline.manifest)
        self.assertEqual(self.program(bench), expected)

    def test_actual_kernel_static_response_is_neutral_and_matches_fraction_answer(self):
        baseline = simulate_scs(self.deck(), kernel=KERNEL)
        for terminals in ['y 0', '0 y', 'u y']:
            actual = simulate_scs(self.deck(f'IZ ({terminals}) isource dc=0'), kernel=KERNEL)
            self.assertEqual({k:v for k,v in actual.items() if k != 'testbench'},
                             {k:v for k,v in baseline.items() if k != 'testbench'})
            self.assertEqual(actual['saved']['values'], [[0,0], [.5,1.5], [1,3], [.5,1.5], [0,0]])
            y = actual['nodes'].index('y')
            for time, box in zip(actual['saved']['times'],
                                 actual['observation_evidence']['voltage_bounds_V'], strict=True):
                t = Q(time); want = 6*t if t <= Q(1,2) else 6*(1-t)
                self.assertLessEqual(Q(box[y][0]), want)
                self.assertGreaterEqual(Q(box[y][1]), want)

    def test_actual_timer_transition_history_and_all_physical_fields_are_neutral(self):
        self.va.write_text(model('@(initial_step) q=0.0; @(timer(0.25)) q=1.0; '
                                 'V(y,r)<+transition(q,0.0,0.125,0.125);', 'real q;'))
        baseline = simulate_scs(self.deck(sources='VU (u 0) vsource dc=.5', step='.0625'), kernel=KERNEL)
        actual = simulate_scs(self.deck('IZ (y 0) isource dc=-0e-400',
                              sources='VU (u 0) vsource dc=.5', step='.0625'), kernel=KERNEL)
        self.assertEqual({k:v for k,v in actual.items() if k != 'testbench'},
                         {k:v for k,v in baseline.items() if k != 'testbench'})
        y = actual['nodes'].index('y')
        for t,row,boxes in zip(actual['saved']['times'], actual['solutions'],
                               actual['observation_evidence']['voltage_bounds_V'], strict=True):
            want = min(Q(1), max(Q(0), 8*(Q(t)-Q(1,4))))
            self.assertLessEqual(abs(Q(row['voltages'][y])-want), Q(1,10**12))
            self.assertLessEqual(Q(boxes[y][0]), want)
            self.assertGreaterEqual(Q(boxes[y][1]), want)

    def test_nonzero_underflow_and_parameter_values_cannot_be_zero_proofs(self):
        for literal in ['1e-400', '-1e-400', '5e-324', '1a', '1e-9999', 'Z', 'tiny', 'missing']:
            with self.subTest(literal=literal), self.assertRaises(CompileError):
                load_scs(self.deck('parameters Z=0 tiny=1e-400\nIZ (y 0) isource dc='+literal))

    def test_all_fields_names_terminal_and_invalid_numeric_checks_remain(self):
        for source in ['IZ (y 0) isource dc=0 acmag=0', 'IZ (y 0) isource dc=0 noise=0',
                       'IZ (y 0) isource type=pulse dc=0', 'IZ (y 0) isource dc=0 wave=[0 0 1 0]',
                       'IZ (y 0) isource type=dc', 'IZ (y 0) isource dc=[0]',
                       'IZ (y 0) isource dc=0 mystery=0', 'IZ (y 0) isource dc=0 dc=0',
                       'IZ (y 0) isource dc=1e999', 'IZ (y 0) isource dc=0/0',
                       'IZ (y y) isource dc=0', 'IZ (y) isource dc=0',
                       'IZ (y 0 x) isource dc=0', 'IZ (y 0) isource dc=0\nIZ (u 0) isource dc=0',
                       'DUT (y 0) isource dc=0']:
            with self.subTest(source=source), self.assertRaises(CompileError):
                load_scs(self.deck(source))

    def test_zero_edges_cannot_create_nodes_or_anchor_an_existing_floating_voltage(self):
        for source in ['IZ (x 0) isource dc=0',
                       'IZ (x z) isource dc=0\nI2 (z 0) isource dc=0',
                       'VR (ref 0) vsource dc=.25\nVF (u ref) vsource dc=.5\n'
                       'IZ (__evas_scs_voltage 0) isource dc=0']:
            with self.subTest(source=source), self.assertRaises(CompileError):
                load_scs(self.deck(source, sources=''))
        self.va.write_text(model('V(y,r)<+3*V(u,r);', ports='u,y,r,x',
                                 directions='input u; output y; inout r,x;'))
        with self.assertRaises(KernelError):
            simulate_scs(self.deck('IZ (x 0) isource dc=0', device='DUT (u y 0 x) m'), kernel=KERNEL)
