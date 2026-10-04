"""Declared vector order and independent scalar circuit answers."""
GUARDS = ["LANG"]

import unittest
from evas import CompileError, Instance, compile_sources, solve
from test_affine import KERNEL


def bus_model(bounds='1:0', body='V(y[0])<+V(u[0])+1; V(y[1])<+2*V(u[1]);'):
    return f'''module bus(u,y); input [{bounds}] u; output [{bounds}] y;
        electrical [{bounds}] u,y; analog begin {body} end endmodule'''


class VectorPorts(unittest.TestCase):
    def test_literal_integer_division_cannot_change_vector_bounds_or_indices(self):
        for source in (bus_model('3/2*2:0'),
                       bus_model('3:0',body='V(y[3/2*2])<+1;')):
            with self.subTest(source=source):
                with self.assertRaises(CompileError) as caught:
                    compile_sources({'bus.va':source},[Instance('dut','bus',
                        {f'{port}[{i}]':f'{port}{i}' for port in ('u','y') for i in range(4)})])
                self.assertEqual(caught.exception.diagnostic['code'],'unsupported_integer_arithmetic')

    def test_each_bit_has_its_own_relation_in_both_orders(self):
        for bounds in ('1:0','0:1'):
            program = compile_sources({'bus.va':bus_model(bounds)}, [Instance('dut','bus',
                {'u[0]':'a','u[1]':'b','y[0]':'c','y[1]':'d'})])
            result = solve(program,['a','b'],[[3,5]],kernel=KERNEL)
            row = dict(zip(result['nodes'],result['solutions'][0]['voltages']))
            self.assertEqual((row['c'],row['d']),(4,10))

    def test_parameterized_internal_nodes_genvar_and_separate_instances(self):
        source = '''module bus(y); output [N-1:0] y; electrical [N-1:0] y;
          parameter integer N=2 from [1:4]; genvar i;
          analog begin for(i=0;i<N;i=i+1) begin V(y[i])<+i+1; V(y[i])<+1; end end endmodule'''
        program = compile_sources({'bus.va':source},[
            Instance('a','bus',{'y[0]':'a0','y[1]':'a1'}),
            Instance('b','bus',{'y[0]':'b0','y[1]':'b1','y[2]':'b2'},{'N':3})])
        result = solve(program,[],[[]],kernel=KERNEL)
        row = dict(zip(result['nodes'],result['solutions'][0]['voltages']))
        self.assertEqual([row[n] for n in ('a0','a1','b0','b1','b2')],[2,3,2,3,4])

    def test_vector_child_connection_uses_declared_order(self):
        leaf = bus_model('0:1')
        parent = '''module top(u,y); input [1:0] u; output [1:0] y;
          electrical [1:0] u,y; bus child(u,y); endmodule'''
        program = compile_sources({'hier.va':leaf+'\n'+parent},[Instance('dut','top',
            {'u[0]':'a','u[1]':'b','y[0]':'c','y[1]':'d'})])
        result = solve(program,['a','b'],[[3,7]],kernel=KERNEL)
        row = dict(zip(result['nodes'],result['solutions'][0]['voltages']))
        self.assertEqual((row['c'],row['d']),(6,8))

    def test_range_mismatch_unindexed_and_dynamic_bits_are_rejected(self):
        cases = [bus_model().replace('electrical [1:0]','electrical [0:1]'),
                 bus_model(body='V(y)<+1;'), bus_model(body='V(y[2])<+1;'),
                 bus_model(body='V(y[V(u[0])])<+1;'),
                 bus_model('100000:0')]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CompileError):
                compile_sources({'bus.va':source},[Instance('dut','bus',
                    {'u[0]':'a','u[1]':'b','y[0]':'c','y[1]':'d'})])
