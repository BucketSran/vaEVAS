# Non-overlapping clock generator

Build a two-phase non-overlapping clock generator that turns input clock edges into phase requests and enforces a dead time on a global tick grid.

## Spec

Use the starter declaration of `nonoverlap_clock_generator`. Every port is electrical. The positional order is `clk_in`, `rst`, `enable`, `phi1`, `phi2`, `deadtime_metric`, `valid`.

`clk_in`, `rst`, and `enable` are voltage-coded control inputs. `phi1` and `phi2` are the generated non-overlapping phase outputs. `deadtime_metric` marks the enforced both-low handoff interval, and `valid` marks that at least one active phase handoff has completed.

Declare these overrideable parameters.

- `vdd` = 0.9 V. Logic-high output level.
- `vss` = 0.0 V. Logic-low output level.
- `vth` = 0.45 V. Logic threshold for the input controls.
- `dead_ticks` = 5. Number of internal timer ticks held both-low after a phase request.
- `tick` = 200 ps. Internal discrete update interval for dead-time scheduling.
- `tr` = 100 ps. Output transition smoothing time, with `0 < tr <= tick/2`. The defaults meet that range, including the equality.

Reset or a low `enable` clears both phases, `deadtime_metric`, and `valid`. A rising `clk_in` request eventually enables `phi1`; a falling `clk_in` request eventually enables `phi2`. During each handoff, both `phi1` and `phi2` stay low for the configured dead time, and `deadtime_metric` is high only while a pending phase request is in that enforced both-low interval. `valid` becomes high after the first enabled handoff completes and stays high until reset or disable.

The dead time is counted on the global tick grid `k*tick`. After an edge requests a phase at time `t`, the new phase is enabled only at the `dead_ticks`-th global `k*tick` event after `t`, so the dead time lies in `((dead_ticks-1)*tick, dead_ticks*tick]`. Edges do not coincide with ticks. Each new edge cancels the old request and restarts the count. A rising `rst` or a falling `enable` immediately clears the active phase, the pending request, the counter, and `valid`, including for a control pulse shorter than one tick. Releasing the controls does not request a phase by itself; the generator waits for the next `clk_in` edge. Adjacent `clk_in` edges are at least `dead_ticks*tick + 4*tr` apart. Every output uses a `tr` transition.

`phi1` and `phi2` must never be high at the same time. The mutual-exclusion check covers every output transition and hold interval. A phase counts as high above `(vdd+vss)/2`, and the two phases are never above that level together.

Initial levels and edges are unambiguous. `clk_in`, `rst`, and `enable` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. The two edges of one `rst` or `enable` clearing pulse are not independent of each other, so such a pulse may be narrower than `2*tr` and shorter than one tick. Each edge of that pulse is still at least `2*tr` away from every `clk_in` edge. Supplies stay fixed. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each output reaches its new value within `tr` after the event that changes it. Every saved point is scored, for all four outputs, except points less than 115 ps after t = 0 or after an event that changes an output target: a `clk_in` crossing in either direction while enabled and not in reset, the `dead_ticks`-th tick after it, at which the requested phase starts, or a clear by a rising `rst` or a falling `enable`. The mutual-exclusion check applies at every saved point, including the unscored ones. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `nonoverlap_clock_generator` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The tick grid, cancel, and clear rules define the observable outputs. They do not require a particular state name or event operator.
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
