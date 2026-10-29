# Programmable gain amplifier

Build a programmable gain amplifier whose gain is selected on a clock edge and whose continuous output is clamped, with a monitor that flags clipping.

## Spec

Use the starter declaration of `programmable_gain_amplifier`. Every port is electrical. The positional order is `clk`, `rst`, `gain_sel`, `vin`, `out`, `metric`.

`clk`, `rst`, and `gain_sel` are voltage-coded control inputs. `vin` is the analog input around the common-mode level. `out` is the gain-scaled and bounded output. `metric` indicates output clipping. Its low level is 0 V and its high level is 0.9 V, independent of the output clamp parameters.

Declare these overrideable parameters. No legal range is stated beyond the values and equations here.

- `vth` = 0.45 V. Logic threshold for `clk`, `rst`, and `gain_sel`.
- `vcm` = 0.45 V. Input and output common-mode reference.
- `gain_low` = 0.8. Sampled gain when `gain_sel` is low.
- `gain_high` = 2.4. Sampled gain when `gain_sel` is high.
- `vmin` = 0.0 V. Lower output clamp.
- `vmax` = 0.9 V. Upper output clamp.
- `tr` = 200 ps. Transition time of `metric`. `out` does not use it.

The sampled gain starts at unity. On each rising `clk` crossing, sample `gain_sel` unless reset is active: when not in reset, select `gain_high` for a high `gain_sel` and `gain_low` for a low `gain_sel`. A rising `clk` that sees `rst` high resets the stored gain to 1. Reset changes the stored gain only at such a rising `clk`.

While `rst` is above `vth`, drive `out` to `vcm` and drive `metric` low. Otherwise drive `out` as `vcm + gain * (V(vin) - vcm)` after clipping to the `vmin` to `vmax` range, and drive `metric` high when that unclamped target would exceed either clamp limit, and low otherwise. `out` is a continuous analog target. It is not filtered by `tr`, and the public output needs no modeled output resistance. Only `metric` uses the `tr` transition.

Initial levels and edges are unambiguous. `clk`, `rst`, and `gain_sel` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. `vin` is continuous where it is used. Supplies stay fixed. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. `out` is scored at every saved point, from t = 0. `metric` reaches its new level within `tr` after its target changes. That target changes where the unclamped target `vcm + gain * (V(vin) - vcm)`, with `V(vin)` interpolated linearly between saved points, crosses `vmin` or `vmax` while `rst` is low, and at each `rst` crossing or rising `clk` crossing that changes it. `metric` is scored at every saved point except points less than `1.15*tr` after a change of its target, including t = 0 when its initial target is high. At those unscored points `metric` must still stay within 2 mV of the range from 0 V to 0.9 V. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `programmable_gain_amplifier` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The gain, clamp, and clipping rules define the observable voltages. They do not require a particular state name or event operator.
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
