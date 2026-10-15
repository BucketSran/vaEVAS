"""Initial comparisons read the uniquely solved zero-time voltage network."""
GUARDS = ['LANG', 'LIN', 'COMPOSE']

import json
import subprocess
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


class InitialNodeDependencies(unittest.TestCase):
    def execute(self, driver, reverse=False, driver_connections=None):
        source = '''`include "disciplines.vams"
module load(ctrl,y); input ctrl; output y; electrical ctrl,y; integer q;
analog begin
  @(initial_step) begin q=0; if(V(ctrl)>0.5) q=1; end
  V(y)<+q;
end endmodule
''' + driver
        instances = [Instance('D', 'load', dict(ctrl='ctrl', y='y')),
                     Instance('E', 'drive', driver_connections or dict(ctrl='ctrl'))]
        if reverse:
            instances.reverse()
        program = compile_sources({'initial.va': source}, instances)
        return transient(program, {}, [0, 1], stop=1, max_step=1, kernel=KERNEL)

    def test_initial_comparison_reads_another_instances_transition_seed(self):
        driver = '''module drive(ctrl); output ctrl; electrical ctrl; integer s;
analog begin @(initial_step)s=1; V(ctrl)<+transition(s,0,0.1,0.1); end
endmodule'''
        for reverse in [False, True]:
            result = self.execute(driver, reverse)
            y = result['nodes'].index('y')
            self.assertEqual([row['voltages'][y] for row in result['solutions']], [1., 1.])

    def test_multiple_contributions_and_coupled_voltage_equations_are_solved_together(self):
        for body in ['V(ctrl)<+0.25; V(ctrl)<+0.75;',
                     'V(a)<+0.25; V(ctrl,a)<+0.75;',
                     'V(ctrl)<+0.5*V(a)+0.5; V(a)<+0.5*V(ctrl)+0.5;']:
            with self.subTest(body=body):
                driver = ('module drive(ctrl); output ctrl; electrical ctrl,a; '
                          'analog begin '+body+' end endmodule')
                result = self.execute(driver)
                self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')], 1.)

    def test_nonground_branch_can_read_an_independently_certified_endpoint(self):
        source = '`include "disciplines.vams"\nmodule load(ctrl,y);input ctrl;output y;electrical ctrl,y;integer q;\nanalog begin @(initial_step)q=(V(ctrl)>1.5);V(y)<+q;end endmodule\nmodule drive(ctrl,aux);output ctrl;inout aux;electrical ctrl,aux;integer s;\nanalog begin @(initial_step)s=(V(aux)>0.5);V(aux)<+1;BRANCH end endmodule'
        for branch in ('V(ctrl,aux)<+s;', 'V(aux,ctrl)<+-s;'):
            for reverse in (False, True):
                with self.subTest(branch=branch, reverse=reverse):
                    instances = [Instance('D','load',dict(ctrl='ctrl',y='y')),
                                 Instance('E','drive',dict(ctrl='ctrl',aux='aux'))]
                    if reverse:
                        instances.reverse()
                    program = compile_sources({'initial.va':source.replace('BRANCH',branch)}, instances)
                    result = transient(program, {}, [0], stop=1, max_step=1, kernel=KERNEL)
                    row = dict(zip(result['nodes'],result['solutions'][0]['voltages']))
                    self.assertEqual((row['aux'], row['ctrl'], row['y']), (1.,2.,1.))

    def test_partial_branch_seed_and_late_conflict_do_not_publish_initial_states(self):
        sources = [
            # Summands are one voltage contribution equation. The constant
            # summand cannot seed aux independently of its unknown state.
            '`include "disciplines.vams"\nmodule drive(aux,y);inout aux;output y;electrical aux,y;integer s;\nanalog begin @(initial_step)s=(V(aux)>0.5);V(aux)<+2;V(aux)<+-s;V(y)<+s;end endmodule',
            # A partial independent certificate is insufficient: after q is
            # resolved, the complete original system conflicts on aux.
            '`include "disciplines.vams"\nmodule load(ctrl,aux,y);input ctrl;inout aux;output y;electrical ctrl,aux,y;integer q;\nanalog begin @(initial_step)q=(V(ctrl)>1.5);V(y)<+q;V(aux)<+2*q;end endmodule\nmodule drive(ctrl,aux);output ctrl;inout aux;electrical ctrl,aux;integer s;\nanalog begin @(initial_step)s=(V(aux)>0.5);V(aux)<+1;V(ctrl,aux)<+s;end endmodule']
        bindings = [[Instance('E','drive',dict(aux='aux',y='y'))],
                    [Instance('D','load',dict(ctrl='ctrl',aux='aux',y='y')),
                     Instance('E','drive',dict(ctrl='ctrl',aux='aux'))]]
        for source, instances in zip(sources, bindings):
            program=compile_sources({'seed-rejection.va':source},instances)
            before=program.to_dict()
            for _ in range(2):
                with self.assertRaisesRegex(KernelError, 'unsupported_initialization'):
                    transient(program,{},[0],stop=1,max_step=1,kernel=KERNEL)
                self.assertEqual(program.to_dict(),before)

    def test_initial_voltage_resolution_does_not_bypass_runtime_predicate_admission(self):
        driver = '''module drive(ctrl,gate);output ctrl;inout gate;electrical ctrl,gate;
analog begin V(ctrl)<+(V(gate)>0.5 ? 1 : 0); V(gate)<+1; end endmodule'''
        # Initialization may certify this dependency, but the unchanged
        # continuous predicate contract still rejects this internal guard.
        with self.assertRaisesRegex(KernelError, 'unsupported_transient'):
            self.execute(driver, driver_connections=dict(ctrl='ctrl', gate='gate'))

    def test_selected_transition_target_keeps_initial_statement_order(self):
        driver = '''module drive(ctrl); output ctrl; electrical ctrl; integer s;
analog begin
 @(initial_step) begin s=0; s=s+1; s=s+1; end
 V(ctrl)<+transition((s<2 ? 0 : 1),0,0.1,0.1);
end endmodule'''
        result = self.execute(driver)
        self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')], 1.)

    def test_shared_predicate_input_is_an_acyclic_dependency_in_either_instance_order(self):
        source = '''`include "disciplines.vams"
module load(ctrl,aux,y);input ctrl,aux;output y;electrical ctrl,aux,y;integer q;
analog begin @(initial_step)q=(V(ctrl)>0.5 && V(aux)>0.5);V(y)<+q;end endmodule
module drive(ctrl,aux);output ctrl;inout aux;electrical ctrl,aux;integer s;
analog begin @(initial_step)s=(V(aux)>0.5);V(ctrl)<+s;V(aux)<+1;end endmodule'''
        instances = [Instance('D','load',dict(ctrl='ctrl',aux='aux',y='y')),
                     Instance('E','drive',dict(ctrl='ctrl',aux='aux'))]
        for ordered in [instances, list(reversed(instances))]:
            program=compile_sources({'shared.va':source},ordered)
            result=transient(program,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
            self.assertEqual([row['voltages'][result['nodes'].index('y')]
                              for row in result['solutions']], [1.,1.])

    def test_state_voltage_cycles_and_hidden_dependencies_do_not_use_default_zero(self):
        for expression in ['V(y)', '($abstime>=0 ? 1 : V(y))']:
            driver = ('module drive(ctrl,feedback); output ctrl; input feedback; '
                      'electrical ctrl,feedback; analog begin V(ctrl)<+'+
                      expression.replace('V(y)', 'V(feedback)')+'; end endmodule')
            source = '''`include "disciplines.vams"
module load(ctrl,y);input ctrl;output y;electrical ctrl,y;integer q;
analog begin @(initial_step)q=(V(ctrl)>0.5);V(y)<+q;end endmodule
''' + driver
            program = compile_sources({'cycle.va': source}, [
                Instance('D', 'load', dict(ctrl='ctrl', y='y')),
                Instance('E', 'drive', dict(ctrl='ctrl', feedback='y'))])
            before = program.to_dict()
            with self.subTest(expression=expression):
                for _ in range(2):
                    with self.assertRaisesRegex(KernelError, 'unsupported_initialization'):
                        transient(program, {}, [0], stop=1, max_step=1, kernel=KERNEL)
                    self.assertEqual(program.to_dict(), before)

    def test_raw_zero_voltage_dependency_cannot_hide_an_initial_state_cycle(self):
        source = '''`include "disciplines.vams"
module load(ctrl,y);input ctrl;output y;electrical ctrl,y;integer q;
analog begin @(initial_step)q=(V(ctrl)>0.5);V(y)<+q;end endmodule
module drive(ctrl);output ctrl;electrical ctrl;
analog begin V(ctrl)<+1;end endmodule'''
        program = compile_sources({'zero-cycle.va': source}, [
            Instance('D', 'load', dict(ctrl='ctrl', y='y')),
            Instance('E', 'drive', dict(ctrl='ctrl'))]).to_dict()
        # Preserve an explicit original IR term. Ordinary affine frontend
        # simplification may erase a literal 0*V(y) before this Rust seam.
        contribution = next(c for c in program['contributions'] if c['origin']['instance']=='E')
        contribution['rhs']['terms'] = [dict(node=program['nodes'].index('y'), coefficient=0.)]
        request = dict(program=program, driven=[], samples=[], transient=dict(
            pwl=[], output_times=[0], stop=1, max_step=1))
        result = subprocess.run([str(KERNEL)], input=json.dumps(request),
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr)['kind'], 'unsupported_initialization')

    def test_singular_and_inconsistent_initial_voltage_systems_are_rejected(self):
        for body in ['V(ctrl)<+V(a); V(a)<+V(ctrl);',
                     'V(ctrl)<+1; V(ctrl,a)<+0; V(a)<+2;']:
            driver = ('module drive(ctrl);output ctrl;electrical ctrl,a;'
                      'analog begin '+body+'end endmodule')
            with self.subTest(body=body), self.assertRaisesRegex(KernelError, 'unsupported_initialization'):
                self.execute(driver)
