"""Global original read boundaries, reproduced from independent R1 controls."""
GUARDS=['LANG','ANALOG','COMPOSE']
import unittest
from evas import compile_sources, Instance, CompileError
from unittest.mock import patch

SOURCE='`include "disciplines.vams"\nmodule mixer(u,lo,y,metric); input u,lo;output y,metric;electrical u,lo,y,metric;\nreal z,pol,unused; integer q;\nanalog begin @(initial_step)q=0;@(timer(0.25))q=1;\npol=(V(lo)>0.5)?1.0:-1.0; z=0.5+1.25*(V(u)-0.5)*pol;\nif(z>0.875)z=0.875;if(z<0.125)z=0.125;\nV(y)<+z;V(metric)<+transition(q,0,0.125,0.125);end endmodule\n'
OBSERVERS={'foreign-unused': '`include "disciplines.vams"\nmodule observer(s,z);input s;output z;electrical s,z;real unused;integer i;\nanalog begin unused=V(s); V(z)<+0.125;end endmodule\n', 'foreign-zero-loop': '`include "disciplines.vams"\nmodule observer(s,z);input s;output z;electrical s,z;real unused;integer i;\nanalog begin for(i=0;i<0;i=i+1)unused=V(s); V(z)<+0.125;end endmodule\n', 'foreign-unselected': '`include "disciplines.vams"\nmodule observer(s,z);input s;output z;electrical s,z;real unused;integer i;\nanalog begin if(0>1)unused=0*V(s); V(z)<+0.125;end endmodule\n'}

class GlobalForcingOriginalReads(unittest.TestCase):
    def instances(self):
        return [Instance('force','mixer',dict(u='u',lo='lo',y='y',metric='metric')),
                Instance('observer','observer',dict(s='y',z='z'))]

    def test_foreign_discarded_reads_reject_in_both_instance_orders(self):
        for name,observer in OBSERVERS.items():
            for reverse in [False,True]:
                instances=self.instances()
                if reverse: instances.reverse()
                with self.subTest(name=name,reverse=reverse):
                    with self.assertRaises(CompileError) as error:
                        compile_sources({'synthetic-forcing.va':SOURCE,'synthetic-observer.va':observer},instances)
                    self.assertEqual(error.exception.diagnostic['code'],'unsupported_forcing_scope')
                    self.assertEqual(error.exception.diagnostic['instance'],'observer')

    def test_unrelated_bound_input_read_is_allowed(self):
        for observer in OBSERVERS.values():
            instances=self.instances();instances[1]=Instance('observer','observer',dict(s='u',z='z'))
            compile_sources({'synthetic-forcing.va':SOURCE,'synthetic-observer.va':observer},instances)

    def test_no_marker_keeps_existing_frontend_route_without_global_scan(self):
        source=SOURCE.replace('pol=(V(lo)>0.5)?1.0:-1.0;','pol=1.0;')
        # This is the already legal affine/clamp source route. Discarded input
        # reads retain their old behavior and consume no new proof scan.
        with patch('evas.instance_compiler.audit_original_reads',side_effect=AssertionError('unexpected original forcing scan')):
            for observer in OBSERVERS.values():
                p=compile_sources({'synthetic-forcing.va':source,'synthetic-observer.va':observer},self.instances())
                self.assertFalse(any(c.rhs.op=='forcing' for c in p.contributions))
