"""Independent recurrence cases for R2 physical reads and complete activations."""
from fractions import Fraction
from itertools import permutations
import struct
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


def execute(source, instances=None, times=(0, .25, .5, .75, 1)):
    program = compile_sources({'scope.va': source}, instances or [
        Instance('M', 'm', {'u': 'u', 'y': 'y'})])
    return transient(program, {'u': [[0, 0], [3, 8]]}, list(times),
                     stop=1, max_step=.25, kernel=KERNEL)


class SameTimeActivationScope(unittest.TestCase):
    def test_independent_physical_loop_keeps_its_program_sample(self):
        expected = float(Fraction.from_float(float(Fraction(4, 3))) - 1)
        self.assertEqual(struct.pack('>d', expected).hex(), '3fd5555555555554')
        for physical in ('V(z)<+2-0.5*V(z);', 'V(z)<+4.0/3.0;',
                         'V(z)<+2-0.5*V(z)+(0*q);', 'V(z)<+2-0.5*V(z)+q*0;',
                         'V(z)<+2-0.5*V(z)+0*V(y);'):
            for times in ((0, .25, .5, .75, 1), (0, .125, .25, .5, .625, .75, 1)):
                for feedback in ('1-0.5*V(y)', '1'):
                    for read in ('$display("p=%.17g",V(z)-1);',
                                 'p=V(z)-1; $display("p=%.17g",p);'):
                        source = ('`include "disciplines.vams"\n'
                                  'module m(u,y); input u; output y; electrical u,y,z; real q,p; '
                                  'analog begin @(initial_step) begin q=0;p=0;end '
                                  '@(timer(0.5)) begin q=' + feedback + '; ' + read + ' end '
                                  'V(y)<+5*q; ' + physical + ' end endmodule')
                        with self.subTest(physical=physical, times=times,
                                          feedback=feedback, read=read):
                            records = execute(source, times=times)['transient']['display_records']
                            self.assertEqual([(r['time'], r['text']) for r in records],
                                             [(.5, f'p={expected:.17g}')])

    def test_partial_active_statements_do_not_prove_complete_multiplicity(self):
        for expression in ('1/(1-V(y))', '1/(V(y)*(1-V(y)))'):
            for tail in ('', 'p=0;', '$display("p=%.17g",p);'):
                for event in (True, False):
                    body = 'q=V(y)*V(y); p=' + expression + '; ' + tail
                    if event:
                        body = ('@(initial_step) begin q=0;p=0;end '
                                '@(timer(0.5)) begin ' + body + ' end ')
                    source = ('`include "disciplines.vams"\n'
                              'module m(u,y); input u; output y; electrical u,y; real q,p; '
                              'analog begin ' + body + ' V(y)<+q; end endmodule')
                    with self.subTest(expression=expression, tail=tail, event=event):
                        if not event and tail == '$display("p=%.17g",p);':
                            # SL-R2-ORDINARY-DISPLAY-APPLICABILITY-20261030-01
                            with self.assertRaises(CompileError) as caught:
                                execute(source)
                            diagnostic = caught.exception.diagnostic
                            self.assertEqual(diagnostic['code'], 'unsupported_event_context')
                            self.assertEqual(diagnostic['category'], 'unsupported')
                            self.assertEqual(diagnostic['stage'], 'binding')
                            self.assertEqual(
                                diagnostic['message'],
                                'ordinary procedure step requires executable capture support')
                            self.assertEqual(diagnostic['instance'], 'M')
                            self.assertEqual(diagnostic['location'], {
                                'source': 'scope.va', 'line': 2,
                                'column': source.splitlines()[1].index('$display') + 1})
                        else:
                            with self.assertRaisesRegex(KernelError, r'^unsupported_transient: .*'
                                                       r'component-root extension .*capability limit'):
                                execute(source)

    def test_driven_constraint_and_original_terminal_classes_ignore_instance_order(self):
        source = ('`include "disciplines.vams"\n'
                  'module pin(y); inout y; electrical y; analog begin V(y)<+1; end endmodule\n'
                  'module loop(u,y); inout u,y; electrical u,y; real q; '
                  'analog begin q=0.5*V(y)+0.5; V(u)<+q-V(y); end endmodule')
        instances = [Instance('A', 'pin', {'y': 'y'}),
                     Instance('Z', 'loop', {'u': 'u', 'y': 'y'})]
        for order in permutations(instances):
            with self.subTest(order=[i.name for i in order]):
                with self.assertRaisesRegex(KernelError, r'^unsupported_transient: .*'
                                           r'unknowns are not each defined by one grounded relation .*'
                                           r'capability limit'):
                    execute(source, list(order))

        source = ('`include "disciplines.vams"\n'
                  'module one(y); inout y; electrical y; analog begin V(y)<+1; end endmodule\n'
                  'module zero(z); inout z; electrical z; analog begin V(z)<+0; end endmodule\n'
                  'module loop(u,y,z); inout u,y,z; electrical u,y,z; real q; '
                  'analog begin q=0.5*V(y,z)+0.5; V(y,z)<+q; end endmodule')
        instances = [Instance('A', 'one', {'y': 'y'}), Instance('B', 'zero', {'z': 'z'}),
                     Instance('Z', 'loop', {'u': 'u', 'y': 'y', 'z': 'z'})]
        for order in permutations(instances):
            with self.subTest(order=[i.name for i in order]):
                with self.assertRaisesRegex(KernelError, r'^unsupported_transient: .*'
                                           r'between two unknown nodes .*capability limit'):
                    execute(source, list(order))

    def test_unexecuted_partial_branch_does_not_add_a_domain_obligation(self):
        for expression in ('1/(1-V(y))', '1/(V(y)*(1-V(y)))'):
            source = ('`include "disciplines.vams"\n'
                      'module m(u,y); input u; output y; electrical u,y; real q,p; '
                      'analog begin q=V(y)*V(y); if(0) p=' + expression + '; '
                      'V(y)<+q; end endmodule')
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(KernelError, r'^unsupported_transient: .*'
                                           r'its exact equation has more than one solution$'):
                    execute(source)

    def test_selected_driven_input_guards_do_not_vary_between_root_candidates(self):
        for extra in ('if(V(u)>-2) begin end', 'unused=0; if(V(u)>-2) unused=1;'):
            source = ('`include "disciplines.vams"\n'
                      'module m(u,y); input u; output y; electrical u,y; real q,unused; '
                      'analog begin q=V(y)*V(y); ' + extra + ' V(y)<+q; end endmodule')
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(KernelError, r'^unsupported_transient: .*'
                                           r'its exact equation has more than one solution$'):
                    execute(source)
