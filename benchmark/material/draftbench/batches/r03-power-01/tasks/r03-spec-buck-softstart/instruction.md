# Buck controller with soft start, PWM carrier and power-good qualification

Build the clocked voltage-domain controller of a buck converter: a soft-start reference, a duty integrator driven by the feedback error, a modulo-20 PWM carrier and a three-cycle power-good flag. This is a controller model only. It does not model the inductor, the switches or the power stage, and it makes no claim about converter stability, efficiency or ripple.

## Spec

Use the starter declaration of `buck_ctrl_top`. Every port is electrical. The positional order is `vfb`, `vref`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`, `soft_ref`, `pgood`. The first five ports are inputs and the last four are outputs.

Declare these overrideable parameters:

- `vdd` = 0.9 V. Logic high level of `pwm` and `pgood`.
- `vss` = 0.0 V. Logic low level of `pwm` and `pgood`, and the cleared level of `soft_ref`. `vss` is below `vdd`.
- `vth` = 0.45 V. Threshold for `clk`, `rst` and `enable`. A level above `vth` is high.
- `duty_min` = 0.05 and `duty_max` = 0.95. Duty clamp. Each is a multiple of 0.05, and 0 <= `duty_min` < `duty_max` <= 1.
- `soft_step` = 25 mV. Largest soft-reference change per clock edge. Legal range 5 mV to 100 mV.
- `pgood_tol` = 25 mV. Power-good window half-width. Legal range 5 mV to 100 mV.
- `tr` = 200 ps. Output transition time. Legal range 10 ps to 1 ns.

The duty step 0.05 and the carrier modulus 20 are fixed constants.

The controller holds six states: the soft reference, the duty (a dimensionless number), the carrier count, the power-good count, and the `pwm` and `pgood` levels. Before the first sample event every state is cleared: soft reference `vss`, duty 0, both counts 0, `pwm` and `pgood` at `vss`.

A sample event is a rising crossing of `clk` through `vth`. States change only at sample events. At each sample event, read `vfb`, `vref`, `rst` and `enable` at the crossing, then apply exactly one of the two rules below.

1. Clear. If `rst` is high or `enable` is low, clear every state as at start-up. This rule has priority over every update in rule 2, and `rst` and `enable` act only at sample events.
2. Update. Otherwise, with the states held before this event:
   1. `duty_up` is true exactly when `vfb` is below the held soft reference, that is, the value before this event's soft-start step.
   2. The soft reference moves toward the current `vref`: if it is within `soft_step` of `vref` it becomes `vref`, otherwise it moves by `soft_step` toward `vref`. When `vref` is below the soft reference the soft reference steps down in the same way, without undershoot.
   3. The duty becomes `duty + 0.05` if `duty_up`, otherwise `duty - 0.05`, and the result is clamped to `[duty_min, duty_max]`. After a clear the duty restarts from 0.
   4. The carrier count becomes `(carrier + 1) mod 20`. Then `pwm` is `vdd` exactly when `carrier + 0.5 < 20*duty`, with the new carrier count and the new duty, and `vss` otherwise. The duty may change at every event, including inside a 20-event carrier cycle. After a clear the carrier restarts from 0, so the old carrier phase is not resumed.
   5. If `|vfb - vref| <= pgood_tol`, the power-good count increases by one and saturates at 3. Otherwise it returns to 0. `pgood` is `vdd` while the count is 3 and `vss` otherwise. Power good depends on `vfb` and `vref` only. A soft reference that has reached `vref` does not by itself qualify the output.

Outputs. `soft_ref` drives the soft reference in volts. `duty_metric` drives the duty as a voltage of 1 V per unit duty, so a cleared duty is 0 V even when `vss` is not 0 V. `pwm` and `pgood` drive their levels. After each sample event every output reaches its new value within `tr` and then stays on it until the next sample event. The waveform inside that `tr` interval is not specified.

Operating range:

- `vfb` and `vref` stay between `vss` and `vdd`. Each may change at any time except within 1 ns of a rising `clk` crossing.
- At every update event, `vfb` differs from the held soft reference by at least 2 mV, and `|vfb - vref|` differs from `pgood_tol` by at least 2 mV, so no comparison is a tie.
- `clk`, `rst` and `enable` switch between 0 V and 0.9 V with transitions no longer than 200 ps, and `vth` lies strictly between those levels. Controls never rest at `vth`. A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.
- `clk` starts low. Successive rising `clk` crossings are at least 5 ns apart, and `clk` stays high and low for at least 2 ns each time.
- Every `rst` and `enable` crossing is at least 1 ns away from every rising `clk` crossing.

The expected states are calculated from the recorded inputs at the recorded `clk` crossings with the rules above. Every saved point of the four outputs is scored except points less than `1.25*tr` after a sample event. At each scored point the error of each output is at most 2 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `buck_ctrl_top` on the module and positional ports in the starter. Only this file is collected.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. You may keep all states in one module or define helper modules inside `/app/circuit.va`. No particular module split, state variable, or event organization is required.
- The submitted model must not read grading files, replay stored answers, or start external processes. You may read this instruction, the starter, and the public testbench, and you may run the public check. Do not edit the public testbench.

From `/app`, run `python3 testbench/check.py --output /app/output/public-check`.

[testbench/README.md](testbench/README.md) describes that check. The public bench sources stay visible, including [testbench/visible_test.scs](testbench/visible_test.scs). Tool version, timeouts, and diagnostics are in that README.

This is an implementation task, not a repository-audit task.
Work in /app and modify only the declared deliverable; do not edit public development benches, model libraries, or external fixtures.
Make one bounded inspection pass over this instruction, the declared deliverable, supplied starter material, and public development benches.
As the task solver, create a runnable candidate in the file named in the Deliverable section before beginning detailed exploration, and keep that file updated as you work.
If your working time expires, the evaluator copies that file exactly as it exists at that moment and runs the verifier on it.
If the file is missing or empty, the result is zero reward.
Temporary files are not submitted.

If a concrete model, tool, or execution problem appears, investigate it as needed before continuing.
Iterate by editing the declared deliverable and using public development benches to diagnose observed behavior.
Do not repeatedly enumerate files, reread unchanged references, or retry unchanged discovery commands instead of editing and simulating.
