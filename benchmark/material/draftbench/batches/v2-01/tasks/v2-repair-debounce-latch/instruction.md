# Repair the debounce latch

Repair the supplied debounce latch so that a rising input sets the output only after an uninterrupted high qualification. The fixed backend is Spectre. The starter at `/app/circuit.va` is the complete erroneous module, not an empty port shell.

## Spec

The module is `debounce_latch`. Its electrical ports, in order, are `sig`, `rst_n`, and `out`. `sig` and `rst_n` are inputs. `out` is the output. `rst_n` is an active-low reset. Keep this module name, port order, and the parameter defaults supplied in the source.

The supplied real parameters are `vth` defaulting to 0.45 V, `vdd` defaulting to 0.9 V, `stable` defaulting to 12 ns, and `tr` defaulting to 500 ps. Those defaults stay the source defaults. The output high level is `vdd`. The logic threshold is 0.45 V.

A rising `sig` edge starts a 12 ns qualification that requires `sig` to stay high continuously. When that qualification completes, `out` goes high. A falling `sig`, or `rst_n` going low, cancels the qualification immediately and clears `out`. If `sig` is already high when the reset is released, no qualification starts; the latch waits for the next rising edge of `sig`. `out` starts at 0.

Acceptance compares `out` with its expected level at every saved waveform point and allows an error of 25 mV. It does not score the first 0.6 ns after time 0, or the points within 0.6 ns before or after each falling threshold crossing of `sig` or `rst_n` and the end of each completed qualification. After each of those events, `out` must therefore reach its new level, including its `tr` smoothing, within 0.6 ns.

Conditions that forbid an action must still meet the on-time startup requirement. The final test covers two different stimuli. The acceptance stimuli and the checker stay fixed.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va`. It already contains the full erroneous `debounce_latch` source. You may rewrite that module. Keep the public ports, the module name, and the source parameter defaults.
- Deliver the external qualification, cancel, and reset behavior. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not edit the public development bench. The submitted model must not run an external program or read hidden final-evaluation material. This restriction applies to the submitted model. You may build your own diagnostic stimuli and run the public check.
- Submit the declared file. Acceptance uses the public external timing and voltage requirements.

Run `python3 /app/testbench/check.py --output /app/output/public-check`. The [public testbench guide](/app/testbench/README.md) documents the Spectre dependency, case selection, timeouts, output layout, and diagnostic exit codes. Public feedback is not the final task score.

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
