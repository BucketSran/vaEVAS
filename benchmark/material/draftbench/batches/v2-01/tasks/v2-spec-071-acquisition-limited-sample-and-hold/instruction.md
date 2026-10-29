# Acquisition-limited sample-and-hold

Build a sample-and-hold whose held value approaches its input in discrete acquisition updates on a global tick grid while a sample window is open, instead of copying the input at once.

## Spec

Use the starter declaration of `acquisition_limited_sample_hold`. Every port is electrical. The positional order is `sample`, `rst`, `vin`, `vout`, `metric`. `sample` is the voltage-coded acquisition-window control, `rst` is an active-high voltage-coded reset, and `vin` is the analog input. The model drives `vout`, the acquired and held voltage, and `metric`, a monitor that is 0.9 V while acquisition is active and 0 V while the model is holding or in reset. Helper modules may be defined in the same file.

Declare these overrideable real parameters.

- `vth` = 0.45 V. Logic threshold for `sample` and `rst`.
- `vinit` = 0.45 V. Initial and reset held voltage.
- `alpha` = 0.42. Acquisition fraction per update.
- `tick` = 1 ns. Acquisition update interval.
- `tr` = 200 ps. Transition time of `vout` and `metric`.

Ticks are the global times `k*tick`, `k = 0, 1, ...`; the first tick is at t = 0. Initially the held value is `vinit` and acquisition is inactive. A rising crossing of `sample` through `vth` opens the acquisition window, unless `rst` is high at that crossing. A falling crossing of `sample` closes the window. At each tick, if `rst` is above `vth`, the held value returns to `vinit` and the window closes. Otherwise, if the window is open, the held value `v` updates once to `v + alpha*(V(vin) - v)`, with `V(vin)` read at that tick. The held value changes only at ticks; a closed window holds the last acquired value. `rst` acts only at ticks: an `rst` crossing by itself changes no output, and the reset takes effect at the next tick. Releasing `rst` does not reopen a window; acquisition resumes at the next rising `sample` crossing. `vout` is the held value. `metric` is 0.9 V exactly while the window is open, so it rises at the `sample` crossing that opens the window and falls at the `sample` crossing or the reset tick that closes it. Each `rst` high interval lasts at least `2*tick`; shorter reset pulses are not legal inputs.

If a `sample` crossing falls exactly on a tick, the crossing takes effect first: a rising crossing opens the window and that tick already updates, and a falling crossing closes the window before that tick. Wherever `rst` is read, at a tick or at a `sample` crossing, its level just after that instant is used. These rules settle every coincidence of `sample` crossings, `rst` crossings, and ticks. In the cases, every `sample` and `rst` crossing is at least 50 ps away from the nearest tick.

Initial levels and edges are unambiguous. `sample` and `rst` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. `vin` is continuous at each tick where it is read. Supplies stay fixed. The control threshold is `vth`.

Voltage error is at most 2 mV. Each output reaches its new value within `tr` after the instant that changes it. Every saved point is scored, for both outputs, except points less than `1.15*tr` after t = 0 or after an instant that changes the expected value of either output: a tick that updates or resets the held value, or a `sample` crossing that opens or closes the window. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `acquisition_limited_sample_hold` on the module and positional ports in the starter, including the parameter defaults above.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The tick grid, the window rules, and the update law define the observable outputs. They do not require a particular state name or event operator.
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
