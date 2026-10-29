# AGC receiver leveling loop

Build a voltage-domain receiver leveling loop that updates a bounded gain on a clock and drives the leveled output plus its monitors.

## Spec

Use the starter declaration of `agc_receiver_leveling_loop`. Every port is electrical. The positional order is `clk`, `rst`, `vin`, `out`, `metric`, `gain_mon`, `rssi_mon`.

`clk` is the gain-control update clock. `rst` is an active-high voltage-coded reset. `vin` is the receiver input envelope, centered on the 0.45 V common mode. `out` is the leveled receiver output. `gain_mon` exposes the bounded gain-control state. `rssi_mon` exposes the observed output envelope. `metric` indicates near-target settling. The model drives `out`, `metric`, `gain_mon`, and `rssi_mon`. It reads `clk`, `rst`, and `vin`.

Declare these overrideable parameters. No legal range is stated beyond the values and equations here.

- `tr` = 100 ps. Transition time of the smoothed voltage contributions.
- `vth` = 0.45 V. Threshold for a voltage-coded logic decision.
- `target_amp` = 0.18 V. Desired output-envelope amplitude around the 0.45 V common mode.
- `deadband` = 0.025 V. Tolerance around the target amplitude before the gain changes.

The constants 0.45 V, 0.02 V, 0.88 V, 0.43 V, 0.18, 0.10, 0.9 V, 4.0, and the gain limits 0.45 and 3.0 are part of the behavior. They are not extra parameters.

From the initial time, `out` is 0.45 V, `metric` is 0 V, `rssi_mon` is 0 V, the gain state is 2.2, and `gain_mon` is `0.9 * (2.2 - 0.45) / (3.0 - 0.45)`. The denominator equals 2.55.

`rst` is read on a rising `clk` edge. It is not an asynchronous clear between edges. On a rising `clk` crossing of `vth` while `rst` is high, restore that same initial state, including gain 2.2 and the initial `gain_mon`.

On a rising `clk` crossing of `vth` after reset has been released, use the gain from before this update. The leveled output is `out = clamp(0.45 + gain * (vin - 0.45), 0.02 V, 0.88 V)`. The observed envelope is `abs(out - 0.45)`. Drive `rssi_mon` as `clamp(0.9 * envelope / 0.43, 0 V, 0.9 V)`.

If the envelope is greater than `target_amp + deadband`, subtract 0.18 from the gain. If the envelope is less than `target_amp - deadband`, add 0.10 to the gain. Otherwise keep the gain. Then clamp the gain to `[0.45, 3.0]`. After that update, drive `gain_mon` as `0.9 * (gain - 0.45) / (3.0 - 0.45)`. Drive `metric` as `clamp(0.9 - 4.0 * abs(envelope - target_amp), 0 V, 0.9 V)`. The envelope used by `rssi_mon` and `metric` is the envelope of the output just computed, before the gain step.

Between rising edges, hold the output targets. Each voltage contribution uses a smooth transition of length `tr`. A small input envelope raises the gain. An overload window lowers `gain_mon`. The output moves toward `target_amp` around the common mode and stays inside the output clamp.

Initial levels and edges are unambiguous. `clk` and `rst` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. `vin` is continuous at the sample. Supplies stay fixed. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each output reaches its new value within `tr` after the rising `clk` crossing that sets it. Every saved point is scored, for all four outputs, except points less than `1.15*tr` after t = 0 or after a rising `clk` crossing that changes an output target. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `agc_receiver_leveling_loop` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The update order defines the observable voltages. It does not require a particular state name or event operator.
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
