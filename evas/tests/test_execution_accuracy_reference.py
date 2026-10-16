"""Physical execution accuracy and extra mathematical-root requirements differ."""
GUARDS = ['CROSS', 'DYNAMICS', 'COMPOSE']
from fractions import Fraction as F
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


class ExecutionAccuracyReference(unittest.TestCase):
    def test_dynamic_guard_sample_and_forcing_use_selected_execution_reference(self):
        for captured, gain in [(False, 1), (False, 1048576), (True, 1048576)]:
            with self.subTest(captured=captured, gain=gain):
                rhs = 'V(u)' if captured else '1'
                output = f'{gain}*q' if captured else f'{gain}*idt(q,0)'
                source = f'''`include "disciplines.vams"
module x(u,z,y);input u;output z,y;electrical u,z,y;real q;
analog begin @(initial_step)q=0;
V(z)<+idt(V(u),0);
@(cross(V(z)-1,1,1e-3,1e-3))q={rhs};
V(y)<+{output};end endmodule'''
                program = compile_sources({'actual-e.va': source},
                    [Instance('M','x',{'u':'u','z':'z','y':'y'})])
                result = transient(program, {'u': [[0,0],[2,2]]}, [0,1.5,2],
                    stop=2, max_step=.1, vabstol=1e-8, reltol=0, kernel=KERNEL)
                self.assertEqual(len(result['transient']['events']), 1)
                e = F(result['transient']['events'][0]['time'])
                expected = gain * (e if captured else F(2)-e)
                actual = result['solutions'][-1]['voltages'][program.nodes.index('y')]
                self.assertLessEqual(abs(F(actual)-expected), F(1e-8))
                evidence = result['observation_evidence']
                lo, hi = evidence['voltage_bounds_V'][-1][evidence['nodes'].index('y')]
                self.assertLessEqual(F(lo), expected)
                self.assertGreaterEqual(F(hi), expected)
                # This is deliberately the selected-e physical oracle. The old
                # sqrt(2) reference and its failures remain in frozen evidence.
                dense = transient(program, {'u': [[0,0],[2,2]]},
                    [0,.25,.5,1,1.5,2], stop=2, max_step=.1,
                    vabstol=1e-8, reltol=0, kernel=KERNEL)
                self.assertEqual(dense['transient']['events'], result['transient']['events'])

    def test_exact_captured_clock_does_not_erase_old_sample_uncertainty(self):
        source = '''`include "disciplines.vams"
module x(u,v,y,stamp);input u,v;output y,stamp;electrical u,v,y,stamp;real q,s;
analog begin @(initial_step)begin q=0;s=0;end
@(timer(0.5,0,0))q=V(v)-1;
@(cross(pow(V(u),2)-2,1,1e-3,1e-3))begin s=$abstime;q=1e16*q;end
V(y)<+idt(q,0);V(stamp)<+s;end endmodule'''
        program = compile_sources({'inherited-e.va': source},
            [Instance('M','x',{n:n for n in ['u','v','y','stamp']})])
        import math
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            transient(program, {'u':[[0,0],[3,3]],
                'v':[[0,1],[3,math.nextafter(1,math.inf)]]}, [0,3],
                stop=3,max_step=.1,vabstol=1e-7,reltol=0,kernel=KERNEL)
