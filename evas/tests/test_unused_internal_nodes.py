"""Never referenced internal declarations are not voltage unknowns."""
GUARDS = ['LANG', 'LIN', 'COMPOSE']
from pathlib import Path
import unittest
from evas import Instance, CompileError, KernelError, compile_sources, solve

KERNEL=Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel'
def source(body,extra='electrical dead;',ports='u,y',declarations=''):
    outputs=','.join(ports.split(',')[1:])
    return '`include "disciplines.vams"\nmodule m('+ports+');input u;output '+outputs+';electrical '+ports+';'+extra+declarations+'analog begin '+body+' end endmodule'
def compile_model(text,connections=None):
    return compile_sources({'unused.va':text},[Instance('dut','m',connections or {'u':'u','y':'y'})])

class UnusedInternalNodes(unittest.TestCase):
    def test_dead_scalar_does_not_make_valid_transfer_singular(self):
        p=compile_model(source('V(y)<+2*V(u)+0.25;'))
        r=solve(p,['u'],[[0.],[0.5]],kernel=KERNEL)
        self.assertNotIn('dut:dead',r['nodes'])
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],[0.25,1.25])

    def test_dead_vector_is_removed_but_declarations_still_validated(self):
        p=compile_model(source('V(y)<+V(u);','electrical [3:1] dead;'))
        self.assertFalse(any('dead' in n for n in p.nodes))
        with self.assertRaises(CompileError):
            compile_model(source('V(y)<+V(u);','electrical [5000:0] dead;'))

    def test_zero_weight_inactive_branch_and_zero_iteration_are_structural_uses(self):
        for body,decl in [
            ('V(y)<+V(u)+0*V(dead);',''),
            ('if(0) V(y)<+V(dead);else V(y)<+V(u);',''),
            ('for(i=0;i<0;i=i+1) V(y)<+V(dead);V(y)<+V(u);','integer i;'),
            ('@(timer(0.25)) $display("%.17g",V(dead));V(y)<+V(u);',''),
            ('@(final_step) $display("%.17g",V(dead));V(y)<+V(u);',''),
            ('V(y)<+idt(V(dead),0);',''),
            ('$bound_step(1+V(dead));V(y)<+V(u);',''),
        ]:
            with self.subTest(body=body):
                self.assertIn('dut:dead',compile_model(source(body,declarations=decl)).nodes)

    def test_referenced_underconstrained_internal_node_is_not_grounded(self):
        p=compile_model(source('V(y)<+V(dead);'))
        with self.assertRaisesRegex(KernelError,'singular_system'):
            solve(p,['u'],[[0.]],kernel=KERNEL)

    def test_unused_port_and_requested_external_node_remain(self):
        p=compile_model(source('V(y)<+V(u);',extra='',ports='u,y,z'),{'u':'u','y':'y','z':'z'})
        self.assertIn('z',p.nodes)
        with self.assertRaisesRegex(KernelError,'singular_system'):
            solve(p,['u'],[[0.]],kernel=KERNEL)
        text=source('V(y)<+V(u);')
        p=compile_sources({'m.va':text},[Instance('dut','m',{'u':'u','y':'y'})],external_nodes=['probe'])
        self.assertIn('probe',p.nodes)

    def test_branch_endpoints_and_any_used_vector_bit_are_retained(self):
        self.assertIn('dut:dead',compile_model(source('V(dead)<+V(u);V(y)<+V(dead);')).nodes)
        p=compile_model(source('V(y)<+V(dead[2]);','electrical [3:1] dead;'))
        self.assertTrue({'dut:dead[1]','dut:dead[2]','dut:dead[3]'}.issubset(p.nodes))

    def test_child_connections_and_instance_private_names_are_retained(self):
        text='''`include "disciplines.vams"
module child(a,y);input a;output y;electrical a,y,unused;analog begin V(y)<+2*V(a);end endmodule
module m(u,y);input u;output y;electrical u,y,link,dead;
child c(link,y);analog begin V(link)<+V(u);end endmodule'''
        p=compile_model(text)
        self.assertIn('dut:link',p.nodes)
        self.assertNotIn('dut:dead',p.nodes)
        self.assertNotIn('dut/c:unused',p.nodes)
        r=solve(p,['u'],[[0.25]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('y')],0.5)

if __name__=='__main__':unittest.main()
