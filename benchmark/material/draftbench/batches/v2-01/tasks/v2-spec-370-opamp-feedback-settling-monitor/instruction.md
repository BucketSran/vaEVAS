# Op-amp feedback settling monitor

Build a sampled closed-loop amplifier model that polls its controls on a global tick grid, moves its output a fixed fraction toward a gain-coded target on each enabled clock edge, and reports the remaining error and a settled flag.

## Spec

Use the starter declaration of `opamp_feedback_settling`. Every port is electrical. The positional order is `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`. `vin` is the analog input. `clk`, `rst`, `enable`, and the gain bits `gain_2`, `gain_1`, `gain_0` are voltage-coded controls. The model drives `vout`, `error_metric`, and `settled`. Helper modules may be defined in the same file; none is required.

Declare these overrideable real parameters.

- `vdd` = 0.9 V. Upper output clamp and high level of `settled`.
- `vss` = 0.0 V. Lower output clamp and low level of `settled`.
- `vcm` = 0.45 V. Common-mode reference; on `error_metric` it represents zero error.
- `vth` = 0.45 V. Threshold for the clock and control inputs.
- `gain_lsb` = 0.5. Closed-loop gain increment per gain-code step.
- `alpha` = 0.3. Sampled settling factor.
- `settle_tol` = 40e-3 V. Error tolerance for the settled flag.
- `tr` = 200 ps. Output transition time.

The model polls its controls on the global time grid `k*tick`, `k = 0, 1, ...`, with `tick` = 250 ps; the first tick is at t = 0. Nothing changes between ticks. At each tick a control counts as high when it is above `vth`. If `rst` is high or `enable` is low at a tick, that tick drives `vout = vcm`, `error_metric = vcm`, and `settled = vss`, and clears the settle counter. Otherwise, a tick at which `clk` is high while it was not high at the previous tick is an enabled rising edge, and that tick performs one update. The previous `clk` level is taken at every tick, including ticks in reset or disable, so a clock that rose during reset or disable does not cause an update when the block is released; the next rising edge does. Initially the outputs have these reset values and the counter is zero.

An update reads the gain bits and `vin` at its tick, decodes `code = 4*gain_2 + 2*gain_1 + gain_0`, and computes

`target = clamp(vcm + (1 + gain_lsb*code)*(vin - vcm), vss, vdd)`

`vout_next = clamp(vout + alpha*(target - vout), vss, vdd)`

`error = target - vout_next`

where `clamp(x, a, b)` limits `x` to the range from `a` to `b` and `vout` is the value before the update. The closed-loop gain `1 + gain_lsb*code` is therefore at least unity, and after an input step the output moves toward the target unless it is already clamped. The update drives `vout = vout_next` and encodes the signed error as `error_metric = vcm + error`. It increments the settle counter when `abs(error) < settle_tol` and otherwise clears it. `settled` is `vdd` while the counter is at least three and `vss` otherwise. Every output uses a `tr` transition.

Initial levels and edges are unambiguous. `clk`, `rst`, `enable`, `gain_2`, `gain_1`, and `gain_0` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. The three gain bits form one code bus: the bits that change in one code change may cross `vth` at the same instant, and that change counts as one control event, so distinct code changes are at least `2*tr` apart from each other and from every `clk`, `rst`, or `enable` crossing. `vin` is continuous at the ticks where it is read. Supplies stay fixed. Parameter overrides keep `0 < alpha <= 1` and `vss <= vcm <= vdd`, so each update moves the output to a point between its previous value and the clamped target. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each output reaches its new value within `tr` after the tick that changes it. Every saved point is scored, for all three outputs, except points less than `1.15*tr` after t = 0 or after a tick that changes an output target. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `opamp_feedback_settling` on the module and positional ports in the starter, including the parameter defaults above.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The polling grid, the update law, and the reset rules define the observable outputs. They do not require a particular state name or event operator.
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
