"""The narrow eligibility contract excludes time and transitive electrical state."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'COMPOSE', 'TRANSITION']
from pathlib import Path
import unittest
from test_affine import KERNEL
from evas import Instance, KernelError, compile_sources, transient

class SampledPredicateRoles(unittest.TestCase):
    def reject(self, source, *, time_dependency=False):
        p = compile_sources({'roles.va': source}, [Instance('dut','sampled_predicate',{'u':'u','y':'y','z':'z'})])
        ir = p.to_dict()
        if time_dependency:
            self.assertIn('$abstime', p.nodes)
            time_node = p.nodes.index('$abstime')
            def references(value):
                if isinstance(value, dict):
                    return int(value.get('node') == time_node) + sum(references(v) for v in value.values())
                if isinstance(value, (tuple, list)):
                    return sum(references(v) for v in value)
                return 0
            self.assertGreater(references(ir['events']), 0, 'original event time tree must survive compilation')
        with self.assertRaisesRegex(KernelError, 'unsupported_condition'):
            transient(p, {'u':[[0.,0.],[1.,1.]]}, [0.,0.125,0.25,0.5,1.], stop=1.,max_step=0.125,
                      kernel=KERNEL,vabstol=1e-10,reltol=0.)

    def test_zero_time_dependency_keeps_original_rejection(self):
        source = Path(__file__).with_name('fixtures').joinpath('driven-sampled-predicate.va').read_text()
        self.reject(source.replace('q=V(u)+0.25;', 'q=V(u)+0.25+0*$abstime;'), time_dependency=True)

    def test_nonzero_time_dependency_keeps_original_rejection(self):
        source = Path(__file__).with_name('fixtures').joinpath('driven-sampled-predicate.va').read_text()
        self.reject(source.replace('q=V(u)+0.25;', 'q=V(u)+0.25+0.125*$abstime;'), time_dependency=True)

    def test_unselected_time_arm_keeps_original_rejection(self):
        source = Path(__file__).with_name('fixtures').joinpath('driven-sampled-predicate.va').read_text()
        source = source.replace('q=V(u)+0.25;', 'begin if(V(u)<0)q=V(u)+0.25+0.125*$abstime; else q=V(u)+0.25; end')
        self.reject(source, time_dependency=True)

    def test_other_event_internal_sample_cannot_launder_state_dependency(self):
        source = Path(__file__).with_name('fixtures').joinpath('driven-sampled-predicate.va').read_text()
        source = source.replace('real q;', 'real q,a; electrical w;')
        source = source.replace('@(initial_step)q=0;', '@(initial_step)begin q=0; a=0; end\n @(timer(0.125))a=V(w);')
        source = source.replace('q=V(u)+0.25;', 'q=a+V(u)+0.25;')
        source = source.replace('V(y)<+', 'V(w)<+0.25;\n V(y)<+')
        self.reject(source)

if __name__ == '__main__':
    unittest.main()
