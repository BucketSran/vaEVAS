"""Public admission boundaries for initial-only ordinary real aliases.

Settings must remain independent of the new alias role, and an indexed input
must not bypass the scalar physical-source proof. These are EVAS support
boundaries, not claims that the rejected Verilog-A is invalid.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']

import unittest

from evas import CompileError, Instance, compile_sources


HEAD = ('`include "disciplines.vams"\n'
        'module m(u,y,z); input u; output y,z; electrical u,y,z; real q,e;')


def ordinary(tail):
    source = (HEAD + 'analog begin @(initial_step)q=7; q=V(u); '
              + tail + ' V(y)<+q; V(z)<+1; end endmodule')
    return compile_sources({'settings.va': source}, [
        Instance('M', 'm', dict(u='u', y='y', z='z'))])


def foreign_vector(rhs, direction, *, initial=True):
    seed = '@(initial_step)q=7; ' if initial else ''
    source = ('`include "disciplines.vams"\n'
              'module m(u,y,z); input [0:0] u; output y,z; '
              'electrical [0:0] u; electrical y,z; real q; analog begin '
              + seed + 'q=' + rhs + '; V(y)<+q; V(z)<+1; '
              'end endmodule\nmodule d(o); ' + direction
              + ' o; electrical o; analog begin V(o)<+0.5; end endmodule')
    return compile_sources({'foreign-vector.va': source}, [
        Instance('driver', 'd', dict(o='u')),
        Instance('M', 'm', {'u[0]': 'u', 'y': 'y', 'z': 'z'})])


class InitialOrdinaryAliasAdmission(unittest.TestCase):
    def assert_a_rejection(self, compile_program):
        with self.assertRaises(CompileError) as caught:
            compile_program()
        self.assertEqual(caught.exception.diagnostic['code'],
                         'unsupported_local_event')
        self.assertIn('initial-only ordinary alias', str(caught.exception))

    def test_transitive_bound_step_alias_is_rejected(self):
        # e must retain its q dependency after the lexical assignment.
        self.assert_a_rejection(lambda: ordinary('e=q; $bound_step(e);'))

    def test_zero_weight_setting_dependency_is_rejected(self):
        # Numerical cancellation cannot erase the dependency obligation.
        self.assert_a_rejection(lambda: ordinary('e=0*q+0.125; $bound_step(e);'))

    def test_unselected_expression_setting_dependency_is_rejected(self):
        self.assert_a_rejection(lambda: ordinary(
            'e=(1>0)?0.125:q; $bound_step(e);'))

    def test_conditional_arm_setting_dependency_is_rejected(self):
        # Either incoming value can carry the prohibited setting dependency.
        self.assert_a_rejection(lambda: ordinary(
            'if(V(u)>0)e=q; else e=0.125; $bound_step(e);'))

    def test_conditional_predicate_setting_dependency_is_rejected(self):
        # Constant arms still depend on q through the selecting predicate.
        self.assert_a_rejection(lambda: ordinary(
            'if(q>0)e=0.125; else e=0.25; $bound_step(e);'))

    def test_unselected_statement_setting_dependency_is_rejected(self):
        self.assert_a_rejection(lambda: ordinary(
            'if(1>0)e=0.125; else e=q; $bound_step(e);'))

    def test_direct_A_predicate_cannot_activate_a_bound_step_setting(self):
        self.assert_a_rejection(lambda: ordinary(
            'if(q>0)$bound_step(0.125);'))

    def test_transitive_A_predicate_cannot_activate_a_bound_step_setting(self):
        self.assert_a_rejection(lambda: ordinary(
            'e=q; if(e>0)$bound_step(0.125);'))

    def test_unrelated_bound_step_keeps_existing_admission(self):
        program = ordinary('e=V(u); $bound_step(e);')
        self.assertEqual([(state.name, state.initial) for state in program.states],
                         [('q', 7.0)])
        self.assertEqual(len(program.step_bounds), 1)

    def test_unrelated_input_predicate_keeps_bound_step_admission(self):
        program = ordinary('if(V(u)>0)$bound_step(0.125);')
        self.assertEqual([(state.name, state.initial) for state in program.states],
                         [('q', 7.0)])
        self.assertEqual(len(program.step_bounds), 1)

    def test_foreign_vector_output_is_rejected_before_zero_cancellation(self):
        self.assert_a_rejection(lambda: foreign_vector('0*V(u[0])', 'output'))

    def test_foreign_vector_inout_is_rejected_before_zero_cancellation(self):
        self.assert_a_rejection(lambda: foreign_vector('0*V(u[0])', 'inout'))

    def test_foreign_vector_unselected_arm_is_rejected(self):
        self.assert_a_rejection(lambda: foreign_vector(
            '(1>0)?1:V(u[0])', 'output'))

    def test_vector_fixture_without_A_role_keeps_existing_admission(self):
        # This control reaches the existing local route with the same vector
        # ports and foreign driver, independently of the new A admission proof.
        for direction in ('output', 'inout'):
            with self.subTest(direction=direction):
                program = foreign_vector('V(u[0])', direction, initial=False)
                self.assertFalse(program.states)


if __name__ == '__main__':
    unittest.main(verbosity=2)
