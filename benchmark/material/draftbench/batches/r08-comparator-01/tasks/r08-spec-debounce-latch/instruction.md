# Debounce latch with cancellable qualification

Build a debounce latch for a voltage-coded comparator decision. A rising decision sets the output only after the decision has stayed high, without interruption, for a qualification time. A falling decision or an active-low reset clears the output at once and voids the qualification in progress, so a voided qualification never sets the output later.

## Spec

Use the starter declaration of `debounce_latch`. Every port is electrical. The positional order is `sig`, `rst_n`, `out`. `sig` (the comparator decision) and `rst_n` (active-low reset) are inputs. `out` is the debounced output.

Declare these overrideable parameters:

- `vth` = 0.45 V. Threshold for `sig` and `rst_n`. A level above `vth` is high. Legal range 0.2 V to 0.7 V.
- `vdd` = 0.9 V. Output high level. Legal range 0.5 V to 1.5 V.
- `stable` = 12 ns. Qualification time. Legal range 2 ns to 1 us.
- `tr` = 500 ps. Output transition time. Legal range 10 ps to 1 ns.

The behavior is defined by an ideal output level that is either 0 V or `vdd`. It is 0 V at t = 0, whatever the inputs are.

- Start. A qualification starts at a rising crossing of `sig` through `vth` after t = 0, provided `rst_n` is high at that instant. It is measured from that crossing.
- Completion. A qualification that starts at `t_r` completes at `t_r + stable` unless it is cancelled before. At completion the ideal level becomes `vdd`. It completes only if `sig` and `rst_n` both stay high for the whole interval from `t_r` to `t_r + stable`.
- Cancel and clear. A falling crossing of `sig` through `vth`, or a falling crossing of `rst_n` through `vth`, cancels the running qualification and sets the ideal level to 0 V. While `rst_n` is low the ideal level stays 0 V, and a rising `sig` crossing starts nothing.
- No other start. A rising crossing of `rst_n` (reset release) changes nothing by itself. If `sig` is already high at t = 0, or when `rst_n` rises back above `vth`, no qualification starts. The latch then waits for the next rising crossing of `sig`.
- Retrigger. Each later rising crossing of `sig` starts a new qualification from that crossing. A cancelled qualification never completes. When its completion instant arrives, nothing happens, even if `sig` and `rst_n` are both high again by then.
- Ties. If a completion instant coincides with a falling crossing of `sig` or `rst_n`, the cancellation wins and the ideal level does not become `vdd`. The evaluated stimuli keep these events apart, as stated below. They also keep rising `sig` crossings apart from `rst_n` crossings, so the outcome of a rising `sig` crossing at the same instant as a `rst_n` crossing is not specified.

Output. `out` drives the ideal level. After each change of the ideal level, `out` reaches the new level within `tr` and then stays on it until the next change. This also holds when the next change comes before `out` has reached the previous level. The waveform inside that `tr` interval is not specified.

`sig` and `rst_n` are continuous and stay between 0 V and 0.9 V. They never rest at `vth`, and at t = 0 each is at least 50 mV away from `vth`. An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. They may move between any levels, including levels between 0 V and 0.9 V, and the crossing instant is the instant at which the input passes `vth`. Between two successive crossings of `vth` by one input, that input moves at least 50 mV away from `vth`. Successive crossings of the same input are at least 0.5 ns apart. Every rising `sig` crossing is at least 0.5 ns away from every `rst_n` crossing. For every rising `sig` crossing `t_r`, no falling crossing of `sig` or `rst_n` lies closer than 0.3 ns to `t_r + stable`.

The expected ideal level is calculated with the rules above from the recorded `sig` and `rst_n` crossing times, taken by linear interpolation between saved points. Every saved point is scored except points less than `1.25*tr` after an instant at which the ideal level changes. At each scored point the error of `V(out)` is at most 10 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `debounce_latch` on the module and positional ports in the starter. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The rules define when the output changes. They do not require a particular analog operator, state variable, or event organization.
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
