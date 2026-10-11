"""Exercise the authored alternative's deadline expressions without a simulator.

This focused scheduler replay injects a timer callback just below its nominal
floating-point time. It does not certify Verilog-A elaboration or waveforms.
"""
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / 'experiments/benchmark_v2/spec_modeling/candidates/v2-spec-375-nonoverlap-clock-generator/alternative/dut.va'


class AuthoredDeadline:
    def __init__(self):
        source = CANDIDATE.read_text()
        request = source.split('@(cross(V(clk_in) - vth, +1))')[1].split('@(cross(')[0]
        self.request = re.findall(r'wait_ticks\s*=\s*([^;]+);', request)[-1]
        timer = source.split('@(timer(0, tick))')[1]
        self.release = re.search(r'if\s*\(([^\n]+)\)\s*begin\s*active_phase = pending_phase;', timer)[1]
        self.indexed = 'global_tick_index' in source
        if self.indexed:
            self.initial_index = re.search(r'global_tick_index\s*=\s*([^;]+);', source)[1]
            self.advance = re.search(r'global_tick_index\s*=\s*([^;]+);', timer)[1]

    @staticmethod
    def expression(expr, values):
        return eval(expr.replace('$abstime', 'abstime').replace('$rtoi', 'int'),
                    {'__builtins__': {}, 'ceil': math.ceil, 'int': int}, values)

    def replay(self, request_time, callbacks, tick=200e-12, dead_ticks=5):
        values = dict(abstime=0., tick=tick, dead_ticks=dead_ticks)
        if self.indexed:
            values['global_tick_index'] = self.expression(self.initial_index, values)
        deadline = None
        for index, callback in enumerate(callbacks):
            # Deliver the clock request between the previous and current tick.
            if deadline is None and callback > request_time:
                values['abstime'] = request_time
                deadline = self.expression(self.request, values)
            values['abstime'] = callback
            if self.indexed:
                values['global_tick_index'] = self.expression(self.advance, values)
            if deadline is not None:
                values['wait_ticks'] = deadline
                if self.expression(self.release, values):
                    return index
        return None


class AlternativeGlobalTickTests(unittest.TestCase):
    def test_timer_roundoff_does_not_delay_fifth_future_tick(self):
        # Actual failing handoff: request 21.59ns, future ticks 21.6 through
        # 22.4ns. A callback one ULP below 22.4ns must still be tick 112.
        tick = 200e-12
        callbacks = [math.nextafter(k*tick, -math.inf) if k else 0. for k in range(115)]
        self.assertEqual(AuthoredDeadline().replay(21.59e-9, callbacks), 112)

    def test_deadline_is_counted_from_request_at_any_global_tick(self):
        for tick, count in [(200e-12, 1), (200e-12, 5), (310e-12, 7)]:
            for preceding_tick in [0, 7, 107]:
                with self.subTest(tick=tick, count=count, preceding=preceding_tick):
                    callbacks = [k*tick for k in range(preceding_tick+count+3)]
                    self.assertEqual(AuthoredDeadline().replay((preceding_tick+.95)*tick, callbacks, tick, count), preceding_tick+count)


if __name__ == '__main__':
    unittest.main()
