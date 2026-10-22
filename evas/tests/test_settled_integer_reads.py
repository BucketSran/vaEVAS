"""Closed event-boundary integer encoders, with conservative composition fallback."""
GUARDS = ["LANG", "TIMER", "CROSS", "EVENT-ORDER", "EVENT-CONDITIONS"]

import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from evas.ir import Binary, Select, StateRef
from test_affine import KERNEL


def source(body, declarations="integer q;", outputs=("y",)):
    ports = ",".join(("u", *outputs))
    return ('`include "disciplines.vams"\nmodule m(' + ports + ');input u;output '
            + ",".join(outputs) + ';electrical ' + ports + ';' + declarations
            + 'analog begin ' + body + ' end endmodule')


def inst(name="dut", outputs=("y",), parameters=None):
    return Instance(name, "m", {n: n for n in ("u", *outputs)}, parameters or {})


class SettledIntegerReads(unittest.TestCase):
    def values(self, text, expected, *, outputs=("y",)):
        program = compile_sources({"settled.va": text}, [inst(outputs=outputs)])
        result = transient(program, {"u": [[0, 0], [1, 0]]}, [0, .25, .5],
                           stop=.5, max_step=.125, kernel=KERNEL)
        actual = [row["voltages"][result["nodes"].index("y")]
                  for row in result["solutions"]]
        self.assertEqual(actual, expected)
        return program

    def test_closed_boundary_nested_bits_ignore_safe_temporary_overshoot(self):
        self.values(source('@(initial_step)q=90;@(timer(0.25))begin '
                           'q=q+200;if(q>127)q=127;end '
                           'V(y)<+1.0*((q>>0)&1);'), [0, 1, 1])
        self.values(source('@(initial_step)q=90;@(timer(0.125))begin '
                           'q=q-191;if(q<0)q=0;end @(timer(0.25))begin '
                           'q=q+191;if(q>127)q=127;end '
                           'V(y)<+1.0*((q>>0)&1);'), [0, 1, 1])

    def test_declaration_seed_is_read_before_initial_step_overwrites_it(self):
        self.values(source('@(initial_step)begin captured=q;q=0;end '
                           '@(timer(0.25))begin q=2000;q=15;end '
                           'V(y)<+captured+(q&1);',
                           'integer q=17;real captured;'), [17, 18, 18])
        for initial, expected in ((16, [0, 1, 1]), (17, [1, 1, 1])):
            self.values(source('@(initial_step)q=' + str(initial) + ';'
                               '@(timer(0.25))begin q=2000;q=15;end '
                               'V(y)<+1.0*(q&1);'), expected)

    def test_cross_driven_encoder_observes_the_completed_clamp(self):
        text = source('@(cross(V(u)-0.5,+1))begin q=q+240;'
                      'if(q>127)q=127;end V(y)<+1.0*(q&1);', 'integer q=10;')
        program = compile_sources({'cross-encoder.va': text}, [inst()])
        result = transient(program, {'u': [[0, 0], [.1, 0], [.2, 1], [1, 1]]},
                           [0, .25, .5], stop=.5, max_step=.125, kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']], [0, 1, 1])
        self.assertEqual(result['transient']['events'][0]['after'], [127])

    def test_coarse_entry_proof_never_widens_existing_lifetime_facts(self):
        self.values(source('@(initial_step)q=3;@(timer(0.25))q=abs(-3);'
                           'V(y)<+1.0*(q&1);'), [1, 1, 1])

    def test_original_intermediate_overflow_is_not_hidden_by_later_clamp(self):
        text = source('@(initial_step)q=0;@(timer(0.25))begin '
                      'q=2147483647;q=q+1;q=15;end V(y)<+1.0*(q&1);')
        program = compile_sources({"overflow.va": text}, [inst()])
        with self.assertRaisesRegex(KernelError, 'signed 32-bit'):
            transient(program, {"u": [[0, 0], [1, 0]]}, [0, .5],
                      stop=.5, max_step=.125, kernel=KERNEL)
        with self.assertRaises(CompileError):
            compile_sources({"dead.va": source('@(initial_step)q=0;'
                '@(timer(0.25))if(0>1)q=2147483647+1;V(y)<+(q&1);')}, [inst()])
        with self.assertRaises(CompileError):
            compile_sources({"ordinary-overflow.va": source('@(initial_step)q=0;'
                '@(timer(0.25))begin q=2000;q=15;end '
                'V(y)<+1.0*(((q+2147483647)-2147483647)&1);')}, [inst()])

    def test_singleton_encoding_keeps_its_original_state_read(self):
        program = self.values(source('@(initial_step)q=0;@(timer(0.25))begin '
            'q=2000;q=0;end V(y)<+1.0*((q>>0)&0);'), [0, 0, 0])
        pending, reads = [program.contributions[0].rhs], set()
        while pending:
            item = pending.pop()
            if isinstance(item, StateRef):
                reads.add(item.state)
            elif isinstance(item, Binary):
                pending.extend((item.left, item.right))
            elif isinstance(item, Select):
                pending.extend((item.left, item.right, item.then_value, item.else_value))
        self.assertEqual(reads, {0})

    def test_joint_domain_256_is_preserved_and_272_is_rejected(self):
        for high, accepted in ((16, True), (17, False)):
            text = source('@(initial_step)begin a=0;b=1;end '
                '@(timer(0.25))if(V(u)>0)begin a=15;b=' + str(high)
                + ';end V(y)<+1.0*(a&b);', 'integer a,b;')
            if accepted:
                compile_sources({"joint.va": text}, [inst()])
            else:
                with self.assertRaisesRegex(CompileError, '256'):
                    compile_sources({"joint.va": text}, [inst()])

    def test_event_voltage_read_keeps_original_lifetime_admission(self):
        body = ('@(cross(V(u)-0.5,+1))begin q=q+240;s=V(bit0);'
                'if(q>127)q=127;end V(bit0)<+1.0*(q&1);V(y)<+s;')
        with self.assertRaisesRegex(CompileError, '256'):
            compile_sources({"composition.va": source(body, 'integer q=10;real s;',
                ("bit0", "y"))}, [inst(outputs=("bit0", "y"))])
        with self.assertRaisesRegex(CompileError, 'integral state arithmetic'):
            compile_sources({"typed-voltage.va": source(body, 'integer q=10,s;',
                ("bit0", "y"))}, [inst(outputs=("bit0", "y"))])

    def test_passive_or_event_observer_and_bound_net_aliases_fall_back(self):
        text = source('@(cross(V(u)-0.5,+1))begin q=q+240;'
                      'if(q>127)q=127;end V(y)<+1.0*(q&1);', 'integer q=10;')
        for body in ('V(z)<+V(x);', '@(initial_step)s=0;@(timer(0.15))s=V(x);V(z)<+s;'):
            observer = ('module observer(x,z);input x;output z;electrical x,z;'
                        'real s;analog begin ' + body + ' end endmodule')
            with self.assertRaisesRegex(CompileError, '256'):
                compile_sources({"observer.va": text + '\n' + observer},
                    [inst(), Instance('watch', 'observer', {'x': 'y', 'z': 'z'})])
        with self.assertRaisesRegex(CompileError, '256'):
            compile_sources({"alias.va": text}, [Instance('dut', 'm', {'u': 'a', 'y': 'a'})])
        two = source('@(cross(V(u)-0.5,+1))begin q=q+240;'
                     'if(q>127)q=127;end V(y)<+1.0*(q&1);V(z)<+q;',
                     'integer q=10;', ("y", "z"))
        with self.assertRaisesRegex(CompileError, '256'):
            compile_sources({"outputs.va": two}, [Instance('dut', 'm', {'u': 'u', 'y': 'x', 'z': 'x'})])

    def test_internal_passive_paths_and_nonunique_or_floating_outputs_fall_back(self):
        prefix = '@(cross(V(u)-0.5,+1))begin q=q+240;if(q>127)q=127;end '
        cases = [
            source(prefix + 'V(bit0)<+1.0*(q&1);V(y)<+V(bit0);',
                   'integer q=10;', ("bit0", "y")),
            source(prefix + 'V(y)<+1.0*(q&1);V(y)<+0.0;', 'integer q=10;'),
            source(prefix + 'V(y,u)<+1.0*(q&1);', 'integer q=10;'),
            source(prefix + 'V(hidden)<+1.0*(q&1);V(y)<+V(hidden);',
                   'integer q=10;electrical hidden;'),
        ]
        for text in cases:
            outputs = ("bit0", "y") if 'output bit0,y;' in text else ("y",)
            with self.subTest(source=text), self.assertRaisesRegex(CompileError, '256'):
                compile_sources({"network.va": text}, [inst(outputs=outputs)])

    def test_array_slots_and_two_instance_parameter_seeds_remain_isolated(self):
        self.values(source('@(initial_step)begin a[0]=0;a[1]=2;end '
            '@(timer(0.25))begin a[0]=16;a[0]=15;a[1]=3;end '
            'V(y)<+1.0*(a[0]&1)+2.0*(a[1]&1);', 'integer a[0:1];'), [0, 3, 3])
        text = source('@(initial_step)q=seed;@(timer(0.25))begin '
                      'q=31;q=15;end V(y)<+1.0*(q&1);',
                      'parameter integer seed=0;integer q;')
        instances = [Instance('a', 'm', {'u': 'u', 'y': 'y'}, {'seed': 16}),
                     Instance('b', 'm', {'u': 'u', 'y': 'z'}, {'seed': 17})]
        program = compile_sources({"instances.va": text}, instances)
        result = transient(program, {"u": [[0, 0], [1, 0]]}, [0, .25, .5],
                           stop=.5, max_step=.125, kernel=KERNEL)
        self.assertEqual([[row['voltages'][result['nodes'].index(n)] for n in ['y', 'z']]
                          for row in result['solutions']], [[0, 1], [1, 1], [1, 1]])
        with self.assertRaisesRegex(CompileError, '256'):
            compile_sources({"instances-wide.va": text.replace('q=31;', 'q=2000;')}, instances)


if __name__ == '__main__':
    unittest.main()
