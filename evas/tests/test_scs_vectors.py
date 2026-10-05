"""Scalar-list SCS connection order checked against explicit bits and answers."""
GUARDS = ["LANG", "COMPOSE", "DEV:scs-input"]

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evas import CompileError, Instance, compile_sources, transient
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL


def bus_source(order='1:0'):
    return f'''module bus(u,y); input [{order}] u; output [0:1] y;
      electrical [{order}] u; electrical [0:1] y;
      analog begin V(y[0])<+V(u[0])+1; V(y[1])<+2*V(u[1]); end endmodule'''


class ScsVectors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'tb.scs'

    def deck(self, source, devices='DUT (a b c d) bus', drives=None, save='c d', step='.25'):
        (self.root/'dut.va').write_text(source)
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'+devices+'\n'+
            (drives or 'VA (a 0) vsource type=dc dc=2\nVB (b 0) vsource type=dc dc=5')+
            f'\nopts options reltol=0 vabstol=1e-9\ntran tran stop=1 maxstep={step}\nsave {save}\n')
        return self.path

    def test_descending_inputs_and_ascending_outputs_match_explicit_bits(self):
        source = bus_source()
        result = simulate_scs(self.deck(source), kernel=KERNEL)
        self.assertEqual(result['saved']['values'], [[6, 4]]*5)
        program = compile_sources({'bus.va': source}, [Instance('DUT', 'bus',
            {'u[1]': 'a', 'u[0]': 'b', 'y[0]': 'c', 'y[1]': 'd'})])
        explicit = transient(program, {'a': [[0, 2], [1, 2]], 'b': [[0, 5], [1, 5]]},
                             [0, .25, .5, .75, 1], stop=1, max_step=.25,
                             kernel=KERNEL, reltol=0, vabstol=1e-9)
        self.assertEqual(result['solutions'], explicit['solutions'])

    def test_ascending_input_order_and_public_cli(self):
        self.deck(bus_source('0:1'), drives='VA (a 0) vsource type=dc dc=3\nVB (b 0) vsource type=dc dc=5')
        result = simulate_scs(self.path, kernel=KERNEL)
        self.assertEqual(result['saved']['values'], [[4, 10]]*5)
        child = subprocess.run([sys.executable, '-m', 'evas', 'simulate', str(self.path),
                                '--kernel', str(KERNEL)], text=True, capture_output=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout)['saved'], result['saved'])

    def test_mixed_scalar_negative_nonzero_and_single_bit_ranges(self):
        source = '''module bus(r,u,v,y,z,w);
          input r; input [1:0] u; input [-1:0] v;
          output y; output [-2:-1] z; output [4:4] w;
          electrical r,y; electrical [1:0] u; electrical [-1:0] v;
          electrical [-2:-1] z; electrical [4:4] w;
          analog begin V(y,r)<+V(u[0],r)+V(v[-1],r);
          V(z[-2],r)<+V(u[1],r); V(z[-1],r)<+V(v[0],r); V(w[4],r)<+9; end endmodule'''
        result = simulate_scs(self.deck(source, 'DUT (0 a b a b c d e f) bus', save='0 c d e f'), kernel=KERNEL)
        self.assertEqual(result['saved']['values'], [[0, 7, 2, 5, 9]]*5)

    def test_width_binding_and_instance_declaration_order(self):
        source = '''module bus(u,y); parameter integer N=2 from [1:4];
          input [N-1:0] u; output [0:N-1] y;
          electrical [N-1:0] u; electrical [0:N-1] y; genvar i;
          analog begin for(i=0;i<N;i=i+1) V(y[i])<+10*V(u[i])+i; end endmodule'''
        devices = ['A (a b c d) bus', 'B (a b e f g h) bus N=3']
        for order in (devices, devices[::-1]):
            with self.subTest(order=order):
                result = simulate_scs(self.deck(source, '\n'.join(order),
                    drives='VA (a 0) vsource type=dc dc=2\nVB (b 0) vsource type=dc dc=5\nVE (e 0) vsource type=dc dc=7',
                    save='c d f g h'), kernel=KERNEL)
                self.assertEqual(result['saved']['values'], [[50, 21, 70, 51, 22]]*5)

    def test_pwl_outputs_match_answer_and_common_times_after_grid_refinement(self):
        results = []
        for step in ('.25', '.125'):
            result = simulate_scs(self.deck(bus_source(), step=step,
                drives='VA (a 0) vsource type=dc dc=2\nVB (b 0) vsource type=pwl wave=[0 0 .5 1 1 0]'), kernel=KERNEL)
            observed = dict(zip(result['saved']['times'], result['saved']['values']))
            for time, (c, d) in observed.items():
                expected_c = 1+2*time if time<=.5 else 3-2*time
                self.assertAlmostEqual(c, expected_c, delta=1e-9)
                self.assertAlmostEqual(d, 4, delta=1e-9)
            results.append(observed)
        for time, coarse in results[0].items():
            for a, b in zip(coarse, results[1][time]):
                self.assertAlmostEqual(a, b, delta=1e-9)

    def test_connection_count_rejection_has_netlist_location(self):
        for connections in ('a b c', 'a b c d e'):
            with self.subTest(connections=connections), self.assertRaises(CompileError) as caught:
                load_scs(self.deck(bus_source(), f'DUT ({connections}) bus'))
            self.assertIn('requires 4 scalar ports', str(caught.exception))
            self.assertEqual(caught.exception.diagnostic['location']['line'], 4)
            self.assertEqual(caught.exception.diagnostic['location']['source'], str(self.path.resolve()))

    def test_invalid_width_declarations_and_resource_budgets_are_rejected(self):
        width = '''module bus(u,y); parameter integer N=2 from [1:4096];
          input [N-1:0] u; output [0:N-1] y; electrical [N-1:0] u;
          electrical [0:N-1] y; genvar i;
          analog begin for(i=0;i<N;i=i+1) V(y[i])<+V(u[i]); end endmodule'''
        no_loop = width.replace('for(i=0;i<N;i=i+1) V(y[i])<+V(u[i]);', 'V(y[0])<+1;')
        cases = [(width, 'DUT (a b c d) bus N=0', 'range'),
                 (width, 'DUT (a b c d) bus N=2.5', 'signed 32-bit'),
                 (no_loop.replace('integer N', 'real N'), 'DUT (a b c d) bus N=2.5', 'bound/index'),
                 (bus_source().replace('electrical [1:0] u', 'electrical [0:1] u'), 'DUT (a b c d) bus', 'mismatch'),
                 (width, 'DUT (a b c d) bus N=4097', 'range'),
                 (no_loop.replace('from [1:4096]', ''), 'DUT (a b c d) bus N=4097', 'element budget'),
                 (width, 'DUT (a b c d) bus N=2050', 'total electrical node budget')]
        for source, device, diagnostic in cases:
            with self.subTest(device=device, diagnostic=diagnostic), self.assertRaisesRegex(CompileError, diagnostic):
                load_scs(self.deck(source, device))

    def test_bus_tokens_in_connections_sources_and_save_remain_rejected(self):
        cases = [dict(devices='DUT (a[1] b c d) bus'),
                 dict(devices='DUT (a[1:0] c d) bus'),
                 dict(devices='DUT ({a b} c d) bus'),
                 dict(drives='VA (a[1] 0) vsource type=dc dc=2'),
                 dict(save='c[0]')]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(CompileError) as caught:
                load_scs(self.deck(bus_source(), **kwargs))
            self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_scs')


if __name__ == '__main__':
    unittest.main()
