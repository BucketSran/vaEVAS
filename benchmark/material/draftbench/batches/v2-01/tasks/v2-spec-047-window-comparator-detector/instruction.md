# Polled window comparator detector

Build a window detector that polls its input on a global time grid and reports whether the input is strictly inside a voltage window relative to a floating low rail.

## Spec

Use the starter declaration of `window_comparator_ref`. Every port is electrical. The positional order is `VDD`, `VSS`, `vin`, `out`. `VDD` and `VSS` are fixed supplies with `VDD > VSS`. `vin` is the polled input. The model drives `out`.

Declare these overrideable parameters. No legal range is stated beyond the values and rules here.

- `vlow` = 0.3 V. Lower window edge, measured from `vin` to `VSS`.
- `vhigh` = 0.6 V. Upper window edge, measured from `vin` to `VSS`.
- `tedge` = 200 ps. Output transition smoothing time.
- `tick` = 500 ps. Polling interval.

The initial state is decided by `vin` relative to `VSS`. At the global times `k*tick`, `k = 0, 1, ...`, poll `vin`. When `V(vin, VSS)` lies strictly inside `(vlow, vhigh)`, drive `out` to `VDD`; otherwise drive `out` to `VSS`. Smooth each target change with `tedge`. Between two ticks the decision holds, even if the input leaves the window; it does not update immediately. The covered range includes a nonzero `VSS`, exact boundary values, and windows shorter than one tick.

Voltage error is at most 2 mV. `out` reaches its new level within `tedge` after the tick that changes its target. Every saved point is scored, except points less than `1.15*tedge` after t = 0 or after a tick `k*tick` at which the polled decision changes the target of `out`. A crossing of a window edge between ticks starts no unscored interval. Final evaluation covers different stimuli inside this public contract. Simultaneous events that this contract does not define are not checked.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `window_comparator_ref` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The polling grid and the strict window define the observable output. They do not require a particular state name or event operator.
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
