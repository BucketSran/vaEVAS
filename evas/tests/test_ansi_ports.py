"""ANSI declarations preserve physical ports, binding order and circuit answers."""
GUARDS = ["LANG"]

from pathlib import Path
import tempfile
import unittest

from evas import CompileError, Instance, compile_sources, solve
from evas.frontend import parse_sources
from evas.scs import simulate_scs
from test_affine import KERNEL

PREFIX = '`include "disciplines.vams"\n'
SCALAR_BODY = 'analog begin V(y,r)<+3*V(a,r)+5*V(b,r); end endmodule'
SCALAR_ANSI = PREFIX + 'module m(input electrical a, input electrical b, output electrical y, inout electrical r); ' + SCALAR_BODY
SCALAR_CLASSIC = PREFIX + 'module m(a,b,y,r); input a,b; output y; inout r; electrical a,b,y,r; ' + SCALAR_BODY


class AnsiPorts(unittest.TestCase):
    def simulate(self, source, instances, drives, saved):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ports.va').write_text(PREFIX + source)
            deck = root / 'tb.scs'
            deck.write_text('simulator lang=spectre\nahdl_include "ports.va"\n' +
                drives + '\n' + instances + '\ntran tran stop=1 maxstep=.25\nsave ' + saved + '\n')
            return simulate_scs(deck, kernel=KERNEL)

    def test_scalar_declarations_match_classic_ports_and_independent_answers(self):
        # Unequal coefficients and inputs expose swapped ports. These answers
        # come directly from y=3*a+5*b, independent of the declaration parser.
        voltages = []
        for source in (SCALAR_CLASSIC, SCALAR_ANSI):
            program = compile_sources({'ports.va': source}, [
                Instance('DUT', 'm', dict(a='a', b='b', y='y', r='0'))])
            result = solve(program, ['a', 'b'], [[.25, .75], [-.5, .25], [2, -1]], kernel=KERNEL)
            y = result['nodes'].index('y')
            values = [row['voltages'][y] for row in result['solutions']]
            self.assertEqual(values, [4.5, -.25, 1])
            voltages.append(values)
        self.assertEqual(*voltages)

    def test_vector_header_order_survives_ordered_and_named_child_binding(self):
        # Header order is u[1],u[0],y[0],y[1],r. Distinct bit values expose
        # a reversal during either child binding or SCS scalar connection.
        leaf = ('module leaf(input electrical [1:0] u, output electrical [0:1] y, '
                'inout electrical r); analog begin V(y[0],r)<+V(u[0],r)+1; '
                'V(y[1],r)<+2*V(u[1],r); end endmodule\n')
        for binding in ('leaf child(a,z,r);', 'leaf child(.u(a),.y(z),.r(r));'):
            with self.subTest(binding=binding):
                top = ('module top(input electrical [1:0] a, output electrical [0:1] z, '
                       'inout electrical r); ' + binding + ' endmodule')
                actual = self.simulate(leaf + top, 'DUT (a1 a0 z0 z1 0) top',
                    'Va1 (a1 0) vsource dc=2\nVa0 (a0 0) vsource dc=5', 'z0 z1')
                self.assertEqual(actual['saved']['values'], [[6, 4]] * 5)

    def test_parameterized_header_ranges_are_bound_separately_per_instance(self):
        source = ('module bus(input electrical [N-1:0] u, output electrical [0:N-1] y); '
                  'parameter integer N=2 from [1:4]; genvar i; analog begin '
                  'for(i=0;i<N;i=i+1) V(y[i])<+V(u[i])+i; end endmodule')
        actual = self.simulate(source,
            'A (a1 a0 y0 y1) bus\nB (b2 b1 b0 z0 z1 z2) bus N=3',
            'Va1 (a1 0) vsource dc=2\nVa0 (a0 0) vsource dc=5\n'
            'Vb2 (b2 0) vsource dc=7\nVb1 (b1 0) vsource dc=4\nVb0 (b0 0) vsource dc=1',
            'y0 y1 z0 z1 z2')
        self.assertEqual(actual['saved']['values'], [[5, 3, 1, 5, 9]] * 5)

    def test_direction_only_header_accepts_body_electrical_declaration(self):
        for header in (
            'module m(input a, output y, inout r); electrical a,y,r; ',
            'module m(input electrical a, output y, inout electrical r); electrical y; ',
        ):
            with self.subTest(header=header):
                source = header + 'analog begin V(y,r)<+2*V(a,r); end endmodule'
                actual = self.simulate(source, 'DUT (a y 0) m',
                    'Va (a 0) vsource type=pwl wave=[0 0 1 1]', 'y')
                self.assertEqual(actual['saved']['values'], [[0], [.5], [1], [1.5], [2]])

    def test_header_preserves_timer_and_integrator_consumers(self):
        # At k/4 seconds, a fixed timer has fired k times and idt(1)=k/4.
        body = ('integer n; analog begin @(initial_step) n=0; '
                '@(timer(0.25,0.25,1e-12)) n=n+1; V(y)<+n+idt(V(u),0); end endmodule')
        for header in ('module m(input electrical u, output electrical y); ',
                       'module m(u,y); input u; output y; electrical u,y; '):
            with self.subTest(header=header):
                actual = self.simulate(header + body, 'DUT (u y) m',
                    'Vu (u 0) vsource dc=1', 'y')
                self.assertEqual(actual['saved']['values'], [[0], [1.25], [2.5], [3.75], [5]])

    def test_unsupported_or_conflicting_headers_reject_with_source_locations(self):
        # A shared ANSI name list is legal in the LRM but outside this finite
        # subset; Spectre 21.1 rejects the corresponding frozen control.
        cases = [
            ('module m(input electrical a, input electrical a);', ''),
            ('module m(input electrical a,b, output electrical y);', ''),
            ('module m(input electrical a, y);', ''),
            ('module m(a, output electrical y);', ''),
            ('module m(input electrical a, output electrical y);', 'electrical a;'),
            ('module m(input a, output y);', ''),
            ('module m(input thermal a, output electrical y);', ''),
            ('module m(input wire a, output electrical y);', ''),
            ('module m(input signed a, output electrical y);', ''),
            ('module m(input electrical a=1, output electrical y);', ''),
            ('module m(input electrical [1:0][1:0] a, output electrical y);', ''),
        ]
        for header, declarations in cases:
            with self.subTest(header=header, declarations=declarations):
                source = PREFIX + header + declarations + 'analog begin V(y)<+V(a); end endmodule'
                with self.assertRaises(CompileError) as caught:
                    parse_sources({'boundary.va': source})
                location = caught.exception.diagnostic['location']
                self.assertEqual(location['source'], 'boundary.va')
                self.assertEqual(location['line'], 2)
                self.assertGreater(location['column'], 0)
        with self.assertRaisesRegex(CompileError, 'electrical discipline is not declared'):
            parse_sources({'no-discipline.va': SCALAR_ANSI[len(PREFIX):]})

    def test_direction_only_vector_range_must_match_body_discipline(self):
        source = (PREFIX + 'module m(input [1:0] u, output electrical y); '
                  'electrical [0:1] u; analog begin V(y)<+V(u[0]); end endmodule')
        with self.assertRaises(CompileError) as caught:
            compile_sources({'range.va': source}, [
                Instance('DUT', 'm', {'u[1]': 'a', 'u[0]': 'b', 'y': 'y'})])
        self.assertEqual(caught.exception.diagnostic['code'], 'vector_declaration')


if __name__ == '__main__':
    unittest.main()
