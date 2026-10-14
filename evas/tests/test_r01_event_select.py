"""Event-controlled affine modes retain joint voltage/state settlement."""
GUARDS = ["EVENT-ORDER", "EVENT-CONDITIONS", "COMPOSE"]

import unittest
from evas import compile_sources, transient, KernelError
from test_affine import KERNEL, instance, model


def execute(body, declarations, times=(0, .25, .5, .75, 1)):
    p = compile_sources({'event-select.va': model(body, declarations)}, [instance()])
    result = transient(p, {'u': [[0, 0], [1, 1]]}, list(times),
                       stop=1, max_step=1, kernel=KERNEL)
    index = result['nodes'].index('y')
    return [row['voltages'][index] for row in result['solutions']]


class EventSelectContracts(unittest.TestCase):
    def test_track_sample_and_hold(self):
        body = """@(initial_step) begin hold=0; q=0; end
            @(timer(0.5)) begin q=V(u,r); hold=1; end
            V(y,r)<+(hold ? q : V(u,r));"""
        self.assertEqual(execute(body, 'integer hold; real q;'), [0, .25, .5, .5, .5])

    def test_enter_hold_uses_joint_sampling_equation(self):
        # q=0.5*y+u and y=q settle to q=2*u at the sampling event.
        # Substituting all candidate state values before solving would give u.
        body = """@(initial_step) begin hold=0; q=0; end
            @(timer(0.5)) begin hold=1; q=0.5*V(y,r)+V(u,r); end
            V(y,r)<+(hold ? q : V(u,r));"""
        self.assertEqual(execute(body, 'integer hold; real q;'), [0, .25, 1, 1, 1])

    def test_reset_reenters_track(self):
        body = """@(initial_step) begin hold=0; q=0; end
            @(timer(0.25)) begin q=V(u,r); hold=1; end
            @(timer(0.75)) hold=0;
            V(y,r)<+(hold ? q : V(u,r));"""
        self.assertEqual(execute(body, 'integer hold; real q;'), [0, .25, .25, .75, 1])

    def test_source_predicate_at_falling_cross_keeps_crossing_sample(self):
        body = """@(initial_step) q=0.9;
            @(cross(V(clk,r)-0.3,-1)) q=V(u,r);
            if(V(clk,r)>0.3) V(y,r)<+V(u,r); else V(y,r)<+q;"""
        source = model(body, 'real q;', ports='u,clk,y,r',
                       directions='input u,clk; output y; inout r;')
        p = compile_sources({'source-select.va': source}, [instance(connections=dict(u='u',clk='clk',y='y',r='0'))])
        result = transient(p, {'u': [[0,0],[1,1]], 'clk': [[0,1],[1,0]]},
                           [0,.6,.8,1], stop=1, max_step=1, kernel=KERNEL)
        index = result['nodes'].index('y')
        actual = [row['voltages'][index] for row in result['solutions']]
        for value, expected in zip(actual, [0,.6,.7,.7]):
            self.assertAlmostEqual(value, expected, places=10)

    def test_reset_source_release_into_hold_discards_stale_sample(self):
        body = """@(initial_step) q=0.9; @(timer(0.25)) q=V(u,r);
            @(cross(V(rst,r)-0.5,-1)) if(V(clk,r)<=0.5) q=0.9;
            if(V(rst,r)>0.5) V(y,r)<+0.9;
            else if(V(clk,r)>0.5) V(y,r)<+V(u,r); else V(y,r)<+q;"""
        source = model(body, 'real q;', ports='u,clk,rst,y,r',
                       directions='input u,clk,rst; output y; inout r;')
        p = compile_sources({'reset-select.va': source}, [instance(connections=dict(u='u',clk='clk',rst='rst',y='y',r='0'))])
        result = transient(p, {'u': [[0,0],[1,1]], 'clk': [[0,0],[1,0]],
                           'rst': [[0,0],[.25,0],[.5,1],[.75,0],[1,0]]},
                           [0,.25,.3,.5,.7,1], stop=1, max_step=1, kernel=KERNEL)
        index = result['nodes'].index('y')
        actual = [row['voltages'][index] for row in result['solutions']]
        self.assertEqual(actual, [.9,.25,.25,.9,.9,.9])

    def test_voltage_sampled_mode_predicate_is_explicitly_rejected(self):
        body = """@(initial_step) q=0; @(timer(0.5)) q=V(y,r);
            V(y,r)<+(q>0.25 ? 1 : V(u,r));"""
        with self.assertRaisesRegex(KernelError, 'voltage-assigned state'):
            execute(body, 'real q;')


class SampledOperatorCoefficientContracts(unittest.TestCase):
    def test_zero_timer_unit_feedback_rejects_inconsistent_joint_equations(self):
        # Frozen original source and old [0,0,1,1.5,2] criterion remain in
        # validation/r01/legacy-transition-coefficient-v1.json. With the final
        # zero-time seed, c=1: q=y+1 and y=q are inconsistent. Spectre's
        # disaster-recovery skip is not a valid accepted event to reproduce.
        body = """@(initial_step) begin q=0; valid=0; end
            @(timer(0)) valid=1;
            @(timer(0.5)) q=V(y,r)+1;
            V(y,r)<+q*transition(valid,0,1,1);"""
        with self.assertRaisesRegex(KernelError, 'singular_system'):
            execute(body, 'real q; integer valid;')

    def test_joint_state_update_uses_current_transition_coefficient(self):
        # Positive-time enable: c(.5)=.375, so q=y+1 and y=.375*q
        # give q=8/5. A stale/pre-event coefficient yields a different answer.
        body = """@(initial_step) begin q=0; valid=0; end
            @(timer(0.125)) valid=1;
            @(timer(0.5)) q=V(y,r)+1;
            V(y,r)<+q*transition(valid,0,1,1);"""
        values = execute(body, 'real q; integer valid;')
        for actual, expected in zip(values, [0,0,.6,1,1.4]):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_unit_feedback_model_completes_before_inconsistent_event(self):
        import json
        from pathlib import Path
        frozen = json.loads((Path(__file__).resolve().parents[1] / 'validation'
                             / 'r01' / 'legacy-transition-coefficient-v1.json').read_text())
        p = compile_sources({'event-select.va': frozen['source']}, [instance()])
        result = transient(p, {'u': [[0,0],[1,1]]}, [0,.25,.499999],
                           stop=.499999, max_step=1, kernel=KERNEL)
        index = result['nodes'].index('y')
        self.assertEqual([row['voltages'][index] for row in result['solutions']], [0,0,0])

    def test_state_times_internal_voltage_stays_unsupported(self):
        body = """@(initial_step) q=1; @(timer(0.5)) q=2;
            V(y,r)<+q*V(y,r);"""
        with self.assertRaisesRegex(KernelError, 'jointly affine'):
            execute(body, 'real q;')

    def test_operator_denominator_stays_unsupported(self):
        body = """@(initial_step) begin q=1; valid=1; end
            V(y,r)<+q/(1+transition(valid,0,1,1));"""
        with self.assertRaisesRegex(KernelError, 'denominator|division|unsupported_implicit_dynamics'):
            execute(body, 'real q; integer valid;')
