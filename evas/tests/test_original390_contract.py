"""Original390 modules with a small independently solved dyadic stimulus.

These are the unchanged frozen four source files. Test parameters and stimulus
form a separate integration contract, not a substitute for the original96ns
request and its complete frozen checker.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE', 'TIMED-OPERATOR']
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest
from evas import Instance, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL
KERNEL = Path(os.environ.get('EVAS_KERNEL', DEFAULT_KERNEL))
SOURCES = {
  "cm_sensor.va": "`include \"constants.vams\"\n`include \"disciplines.vams\"\n\nmodule cm_sensor(vop_in, von_in, cm_error_raw);\n    input vop_in, von_in;\n    output cm_error_raw;\n    electrical vop_in, von_in, cm_error_raw;\n\n    parameter real vcm = 0.45;\n    parameter real tr = 200p from (0:inf);\n\n    analog begin\n        V(cm_error_raw) <+ (0.5 * (V(vop_in) + V(von_in)) - vcm);\n    end\nendmodule\n",
  "cmfb_loop_top.va": "`include \"constants.vams\"\n`include \"disciplines.vams\"\n\nmodule cmfb_loop_top(vop_in, von_in, clk, rst, enable, vop_out, von_out, trim_2, trim_1, trim_0, cm_error, locked);\n    input vop_in, von_in, clk, rst, enable;\n    output vop_out, von_out, trim_2, trim_1, trim_0, cm_error, locked;\n    electrical vop_in, von_in, clk, rst, enable, vop_out, von_out, trim_2, trim_1, trim_0, cm_error, locked;\n\n    parameter real vdd = 0.9;\n    parameter real vss = 0.0;\n    parameter real vcm = 0.45;\n    parameter real vth = 0.45;\n    parameter real trim_lsb = 10e-3;\n    parameter real lock_tol = 10e-3;\n    parameter real tr = 200p from (0:inf);\n\n    electrical cm_error_raw, trim_corr;\n\n    cm_sensor #(.vcm(vcm), .tr(tr)) u_sensor (\n        vop_in, von_in, cm_error_raw\n    );\n    trim_controller #(.vdd(vdd), .vss(vss), .vth(vth), .trim_lsb(trim_lsb), .lock_tol(lock_tol), .tr(tr)) u_trim (\n        clk, rst, enable, cm_error_raw, trim_2, trim_1, trim_0, trim_corr, locked\n    );\n    output_balancer #(.vdd(vdd), .vss(vss), .vcm(vcm), .vth(vth), .tr(tr)) u_balance (\n        vop_in, von_in, enable, rst, trim_corr, vop_out, von_out, cm_error\n    );\nendmodule\n",
  "output_balancer.va": "`include \"constants.vams\"\n`include \"disciplines.vams\"\n\nmodule output_balancer(vop_in, von_in, enable, rst, trim_corr, vop_out, von_out, cm_error);\n    input vop_in, von_in, enable, rst, trim_corr;\n    output vop_out, von_out, cm_error;\n    electrical vop_in, von_in, enable, rst, trim_corr, vop_out, von_out, cm_error;\n\n    parameter real vdd = 0.9;\n    parameter real vss = 0.0;\n    parameter real vcm = 0.45;\n    parameter real vth = 0.45;\n    parameter real tr = 200p from (0:inf);\n\n    real correction;\n    real out_p;\n    real out_n;\n    real residual;\n\n    analog begin\n        correction = V(trim_corr);\n        out_p = V(vop_in) - correction;\n        out_n = V(von_in) - correction;\n        residual = 0.5 * (out_p + out_n) - vcm;\n\n        if ((V(rst) > vth) || (V(enable) <= vth)) begin\n            out_p = V(vop_in);\n            out_n = V(von_in);\n            residual = 0.0;\n        end\n\n        if (out_p < vss)\n            out_p = vss;\n        if (out_p > vdd)\n            out_p = vdd;\n        if (out_n < vss)\n            out_n = vss;\n        if (out_n > vdd)\n            out_n = vdd;\n\n        V(vop_out) <+ out_p;\n        V(von_out) <+ out_n;\n        V(cm_error) <+ residual;\n    end\nendmodule\n",
  "trim_controller.va": "`include \"constants.vams\"\n`include \"disciplines.vams\"\n\nmodule trim_controller(clk, rst, enable, cm_error_raw, trim_2, trim_1, trim_0, trim_corr, locked);\n    input clk, rst, enable, cm_error_raw;\n    output trim_2, trim_1, trim_0, trim_corr, locked;\n    electrical clk, rst, enable, cm_error_raw, trim_2, trim_1, trim_0, trim_corr, locked;\n\n    parameter real vdd = 0.9;\n    parameter real vss = 0.0;\n    parameter real vth = 0.45;\n    parameter real trim_lsb = 10e-3;\n    parameter real lock_tol = 10e-3;\n    parameter real tr = 200p from (0:inf);\n\n    integer trim_code;\n    integer lock_count;\n    real correction;\n    real residual;\n    real lock_value;\n\n    analog begin\n        @(initial_step) begin\n            trim_code = 0;\n            lock_count = 0;\n            lock_value = vss;\n        end\n\n        @(cross(V(clk) - vth, +1) or cross(V(rst) - vth, +1) or\n          cross(V(enable) - vth, -1)) begin\n            correction = trim_code * trim_lsb;\n            residual = V(cm_error_raw) - correction;\n            if ((V(rst) > vth) || (V(enable) <= vth)) begin\n                trim_code = 0;\n                lock_count = 0;\n                lock_value = vss;\n            end else begin\n                if ((residual > lock_tol) && (trim_code < 7))\n                    trim_code = trim_code + 1;\n                else if ((residual < -lock_tol) && (trim_code > 0))\n                    trim_code = trim_code - 1;\n\n                residual = V(cm_error_raw) - trim_code * trim_lsb;\n                if ((residual <= lock_tol) && (residual >= -lock_tol)) begin\n                    if (lock_count < 2)\n                        lock_count = lock_count + 1;\n                    if (lock_count >= 2)\n                        lock_value = vdd;\n                end else begin\n                    lock_count = 0;\n                    lock_value = vss;\n                end\n            end\n        end\n\n        correction = trim_code * trim_lsb;\n        if ((V(rst) > vth) || (V(enable) <= vth))\n            correction = 0.0;\n\n        V(trim_corr) <+ correction;\n        V(locked) <+ transition(lock_value, 0, tr, tr);\n        V(trim_0) <+ transition((trim_code % 2) ? vdd : vss, 0, tr, tr);\n        V(trim_1) <+ transition(((trim_code / 2) % 2) ? vdd : vss, 0, tr, tr);\n        V(trim_2) <+ transition(((trim_code / 4) % 2) ? vdd : vss, 0, tr, tr);\n    end\nendmodule\n"
}

PORTS = 'vop_in von_in clk rst enable vop_out von_out trim_2 trim_1 trim_0 cm_error locked'.split()


def program():
    return compile_sources(SOURCES, [Instance('XDUT', 'cmfb_loop_top',
        dict(zip(PORTS, PORTS)), dict(vdd=1., vss=0., vcm=.5, vth=.5,
                                    trim_lsb=.0625, lock_tol=.03125, tr=.125))])


def run(times, *, disable=False):
    clock = [[0., 0.]]
    for center in [.5, 1.5, 2.5, 3.5, 4.5]:
        clock += [[center-.125, 0.], [center+.125, 1.], [center+.25, 0.]]
    clock += [[5., 0.]]
    enable = ([[0., 1.], [2., 1.], [2.125, 0.], [3., 0.], [3.125, 1.], [5., 1.]]
              if disable else [[0., 1.], [5., 1.]])
    return transient(program(), dict(vop_in=[[0., .75], [5., .75]],
        von_in=[[0., .375], [5., .375]], clk=clock,
        rst=[[0., 1.], [.0625, 1.], [.125, 0.], [5., 0.]], enable=enable),
        times, stop=5., max_step=.0625, vabstol=1e-10, reltol=0., kernel=KERNEL)


def column(result, name):
    i = result['nodes'].index(name)
    return [row['voltages'][i] for row in result['solutions']]


class Original390Contract(unittest.TestCase):
    def test_trim_then_lock_uses_updated_residual_and_preserves_differential(self):
        r = run([0., .25, .875, 1.875, 2.875])
        # raw CM = (.75+.375)/2-.5 = 1/16. First tick increments
        # code0 to1, then recomputes residual0 and lock_count1; second
        # tick keeps code1 and lock_count2. Differential stays3/8.
        self.assertEqual(column(r, 'trim_0'), [0., 0., 1., 1., 1.])
        self.assertEqual(column(r, 'trim_1'), [0.]*5)
        self.assertEqual(column(r, 'trim_2'), [0.]*5)
        self.assertEqual(column(r, 'locked'), [0., 0., 0., 1., 1.])
        self.assertEqual(column(r, 'cm_error'), [0., .0625, 0., 0., 0.])
        self.assertEqual(column(r, 'vop_out'), [.75, .75, .6875, .6875, .6875])
        self.assertEqual(column(r, 'von_out'), [.375, .375, .3125, .3125, .3125])
        for vp, vn in zip(column(r, 'vop_out'), column(r, 'von_out')):
            self.assertEqual(vp-vn, .375)

    def test_disable_clears_state_and_reenable_requires_two_fresh_ticks(self):
        r = run([1.875, 2.375, 3.375, 3.875, 4.875], disable=True)
        self.assertEqual(column(r, 'trim_0'), [1., 0., 0., 1., 1.])
        self.assertEqual(column(r, 'locked'), [1., 0., 0., 0., 1.])
        self.assertEqual(column(r, 'vop_out'), [.6875, .75, .75, .6875, .6875])
        self.assertEqual(column(r, 'cm_error'), [0., 0., .0625, 0., 0.])

    def test_extra_queries_do_not_change_accepted_trim_or_lock_epochs(self):
        times = [0., .25, .875, 1.875, 2.875, 4.875]
        sparse = run(times)
        dense_times = sorted(set(times + [k/16 for k in range(81)]))
        dense = run(dense_times)
        for name in ['trim_0', 'locked', 'cm_error', 'vop_out', 'von_out']:
            lookup = dict(zip(dense_times, column(dense, name)))
            self.assertEqual(column(sparse, name), [lookup[t] for t in times])
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])

    def test_original_interface_cannot_be_replaced_by_raw_foreign_trim_state(self):
        p = program().to_dict()
        state = next(i for i, s in enumerate(p['states'])
                     if s['instance'] == 'XDUT/u_trim' and s['name'] == 'trim_code')
        bad = copy.deepcopy(p)
        contribution = next(c for c in bad['contributions']
                            if c['origin']['instance'] == 'XDUT/u_balance')
        contribution['rhs'] = dict(op='state', state=state)
        r = subprocess.run([str(KERNEL)], input=json.dumps(dict(program=bad,
            driven=['vop_in', 'von_in', 'clk', 'rst', 'enable'], samples=[],
            transient=dict(pwl=[[[0., v], [5., v]] for v in [.75, .375, 0., 0., 1.]],
                           output_times=[0., 5.], stop=5., max_step=.0625))),
            text=True, capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 2, r.stdout+r.stderr)
        self.assertEqual(r.stdout, '')
        error = json.loads(r.stderr)
        self.assertEqual(error['kind'], 'invalid_ir')
        self.assertIn('state reference must belong to its instance', error['message'])
