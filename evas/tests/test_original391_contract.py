"""Original391 source with an independent rational event/linear-ramp oracle.

The SOURCE bytes are the frozen original VA, SHA256 b837527258f4bf55593e4a771936f9270572f93a63a35c3f7da7aa3e2a2447d2.
This regression does not replace the original six-property checker or its grid.
It follows the full scheduling consumers at selected independent witness times.
"""
import hashlib
import os
from fractions import Fraction as Q
from pathlib import Path
import unittest
from evas import Instance, compile_sources, transient

GUARDS = ['TIMER', 'TRANSITION', 'EVENT-ORDER', 'COMPOSE']
KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))
SOURCE = '''`include "constants.vams"
`include "disciplines.vams"

module lc_vco_behavioral_source(vctrl, enable, rst, osc_p, osc_n, freq_metric, amp_metric, valid);
    input vctrl, enable, rst;
    output osc_p, osc_n, freq_metric, amp_metric, valid;
    electrical vctrl, enable, rst, osc_p, osc_n, freq_metric, amp_metric, valid;

    parameter real vdd = 0.9;
    parameter real vss = 0.0;
    parameter real vcm = 0.45;
    parameter real fmin = 5e6;
    parameter real fmax = 25e6;
    parameter real vth = 0.45;
    parameter real amplitude = 0.4;
    parameter real tr = 200p from (0:inf);

    integer osc_state;
    integer half_edges;
    real next_edge_time;
    real ctrl_v;
    real freq;
    real osc_p_v;
    real osc_n_v;
    real freq_v;
    real amp_v;
    real valid_v;

    analog begin
        @(initial_step) begin
            osc_state = 0;
            half_edges = 0;
            next_edge_time = 1.0e99;
            osc_p_v = vcm;
            osc_n_v = vcm;
            freq_v = vss;
            amp_v = vss;
            valid_v = vss;
        end

        @(cross(V(rst) - vth, +1) or cross(V(enable) - vth, -1)) begin
            osc_state = 0;
            half_edges = 0;
            next_edge_time = 1.0e99;
            osc_p_v = vcm;
            osc_n_v = vcm;
            freq_v = vss;
            amp_v = vss;
            valid_v = vss;
        end

        @(cross(V(enable) - vth, +1)) begin
            if (V(rst) <= vth) begin
                osc_state = 0;
                half_edges = 0;
                osc_p_v = vcm;
                osc_n_v = vcm;
                ctrl_v = V(vctrl);
                if (ctrl_v < vss) ctrl_v = vss;
                if (ctrl_v > vdd) ctrl_v = vdd;
                freq = fmin + (fmax - fmin) * (ctrl_v - vss) / (vdd - vss);
                freq_v = ctrl_v;
                amp_v = amplitude;
                valid_v = vss;
                next_edge_time = $abstime + 0.5 / freq;
            end
        end

        @(timer(next_edge_time)) begin
            if (V(rst) > vth || V(enable) <= vth) begin
                osc_state = 0;
                half_edges = 0;
                next_edge_time = 1.0e99;
                osc_p_v = vcm;
                osc_n_v = vcm;
                freq_v = vss;
                amp_v = vss;
                valid_v = vss;
            end else begin
                osc_state = 1 - osc_state;
                half_edges = half_edges + 1;
                if (osc_state != 0) begin
                    osc_p_v = vcm + amplitude;
                    osc_n_v = vcm - amplitude;
                end else begin
                    osc_p_v = vcm - amplitude;
                    osc_n_v = vcm + amplitude;
                end
                if (half_edges >= 4) valid_v = vdd;
                ctrl_v = V(vctrl);
                if (ctrl_v < vss) ctrl_v = vss;
                if (ctrl_v > vdd) ctrl_v = vdd;
                freq = fmin + (fmax - fmin) * (ctrl_v - vss) / (vdd - vss);
                freq_v = ctrl_v;
                amp_v = amplitude;
                next_edge_time = $abstime + 0.5 / freq;
            end
        end

        V(osc_p) <+ transition(osc_p_v, 0, tr, tr);
        V(osc_n) <+ transition(osc_n_v, 0, tr, tr);
        V(freq_metric) <+ transition(freq_v, 0, tr, tr);
        V(amp_metric) <+ transition(amp_v, 0, tr, tr);
        V(valid) <+ transition(valid_v, 0, tr, tr);
    end
endmodule
'''


def ns(number):
    # Same native numeric literal operation as a value with n suffix. The
    # oracle then interprets these binary64 endpoints as exact rationals.
    return float(number)*1e-9


STOP = ns(1050)
SOURCES = {
    'enable': [[0.,0.], [ns(10),0.], [ns(10.1),.9],
               [ns(820),.9], [ns(820.1),0.], [ns(870),0.],
               [ns(870.1),.9], [STOP,.9]],
    'rst': [[0.,.9], [ns(4),.9], [ns(4.1),0.], [STOP,0.]],
    'vctrl': [[0.,-.1], [ns(250),-.1], [ns(250.1),.45],
              [ns(600),.45], [ns(600.1),1.], [STOP,1.]],
}
TIMES = [ns(t) for t in [0, 5, 10, 50, 110.5, 210.5, 260, 270,
                          300, 310.5, 450, 600.5, 620, 800, 821,
                          850, 870.5, 900, 1049, 1050]]
OUTPUTS = ['osc_p', 'osc_n', 'freq_metric', 'amp_metric', 'valid']


def pwl(signal, time):
    points = [(Q(t), Q(v)) for t, v in SOURCES[signal]]
    for (left, a), (right, b) in zip(points, points[1:]):
        if left <= time <= right:
            return a+(b-a)*(time-left)/(right-left)
    raise AssertionError('oracle query outside original PWL')


def control_edges():
    roots = []
    for (left, a), (right, b) in zip(SOURCES['enable'], SOURCES['enable'][1:]):
        if a == b:
            continue
        root = Q(left)+(Q(.45)-Q(a))*(Q(right)-Q(left))/(Q(b)-Q(a))
        roots.append((root, 'enable' if b > a else 'disable'))
    return roots


def independent_calendar():
    # Only an edge event samples control. A later source change never edits
    # an already scheduled due time. Reset is inactive at all enable events.
    remaining = list(control_edges())
    due = None
    state = 0
    count = 0
    values = [Q(.45), Q(.45), Q(0), Q(0), Q(0)]
    events = []
    while remaining or due is not None:
        control = remaining[0] if remaining else None
        timer = due if due is not None else Q(STOP)+1
        if control is not None and control[0] <= timer:
            time, kind = remaining.pop(0)
            assert time != timer, 'this fixture requires distinct physical events'
        else:
            time, kind = timer, 'timer'
        if time > Q(STOP):
            break
        if kind == 'disable':
            due = None
            state = count = 0
            values = [Q(.45), Q(.45), Q(0), Q(0), Q(0)]
        else:
            if kind == 'enable':
                assert pwl('rst', time) <= Q(.45)
                state = count = 0
                values[0] = values[1] = Q(.45)
                values[4] = Q(0)
            else:
                assert pwl('rst', time) <= Q(.45) < pwl('enable', time)
                state = 1-state
                count += 1
                values[0] = Q(.45)+(Q(.4) if state else -Q(.4))
                values[1] = Q(.45)-(Q(.4) if state else -Q(.4))
                if count >= 4:
                    values[4] = Q(.9)
            ctrl = max(Q(0), min(Q(.9), pwl('vctrl', time)))
            freq = Q(5_000_000)+Q(20_000_000)*ctrl/Q(.9)
            due = time+Q(1,2)/freq
            values[2] = ctrl
            values[3] = Q(.4)
        events.append((time, kind, tuple(values)))
    return events


def expected_wave(time, events):
    current = [Q(.45), Q(.45), Q(0), Q(0), Q(0)]
    duration = Q(200*1e-12)
    for at, _, target in events:
        if time < at:
            break
        # All physical events are separated by more than the original tr.
        fraction = min(Q(1), (time-at)/duration)
        current = [old+(new-old)*fraction for old, new in zip(current, target)]
        if fraction != 1:
            break
    return current


def execute(times):
    program = compile_sources({'original391.va': SOURCE}, [Instance(
        'XDUT', 'lc_vco_behavioral_source', {p:p for p in [
            'vctrl', 'enable', 'rst', *OUTPUTS]})])
    return transient(program, SOURCES, times, stop=STOP, max_step=350*1e-12,
                     vabstol=1e-12, reltol=1e-10, kernel=KERNEL, timeout=120)


class Original391Contract(unittest.TestCase):
    def assert_original_values(self, result, times):
        events = independent_calendar()
        for time, row in zip(times, result['solutions']):
            expected = expected_wave(Q(time), events)
            for node, want in zip(OUTPUTS, expected):
                actual = Q(row['voltages'][result['nodes'].index(node)])
                tolerance = Q(1e-12)+Q(1e-10)*abs(want)
                self.assertLessEqual(abs(actual-want), tolerance, (time, node, float(want)))
        self.assertEqual(len(result['transient']['events']), len(events))

    def test_full_original391_consumers_clamp_pending_timer_reset_and_reenable(self):
        self.assertEqual(hashlib.sha256(SOURCE.encode()).hexdigest(),
            'b837527258f4bf55593e4a771936f9270572f93a63a35c3f7da7aa3e2a2447d2')
        result = execute(TIMES)
        self.assert_original_values(result, TIMES)

    def test_original391_query_density_preserves_physical_events(self):
        sparse = [0., ns(270), ns(620), ns(850), ns(900), STOP]
        baseline = execute(sparse)
        dense = execute(sorted(set(TIMES+sparse)))
        self.assert_original_values(baseline, sparse)
        self.assertEqual(baseline['transient']['events'], dense['transient']['events'])
        for time, row in zip(sparse, baseline['solutions']):
            other = dense['solutions'][sorted(set(TIMES+sparse)).index(time)]
            for node in OUTPUTS:
                index = baseline['nodes'].index(node)
                self.assertEqual(row['voltages'][index], other['voltages'][index])
