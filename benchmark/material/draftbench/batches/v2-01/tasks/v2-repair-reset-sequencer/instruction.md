# Repair the reset-release sequencer

Repair the supplied reset-release sequencer so that its staged outputs follow the qualification and reset contract on rising clock edges. The fixed backend is Spectre. The starter at `/app/circuit.va` is the complete erroneous module, not an empty port shell.

## Spec

The module is `reset_release_sequencer`. Its electrical ports, in order, are `clk`, `rst`, `supply_ok`, `bias_ok`, `stage1`, `stage2`, `ready`, and `progress`. `clk`, `rst`, `supply_ok`, and `bias_ok` are inputs. `stage1`, `stage2`, `ready`, and `progress` are outputs. Keep this module name, port order, and the parameter defaults supplied in the source.

The supplied parameters are real `vth` defaulting to 0.45 V, real `vhi` defaulting to 0.9 V, integer `final_stage` defaulting to 3, and real `tr` defaulting to 60 ps. `final_stage` may only take the integers 3 to 5, and the final test covers that whole range. The other parameters stay the source defaults. The logic threshold is 0.45 V.

The stage count updates only on a rising `clk` edge. If `rst` is high, or `supply_ok` or `bias_ok` is not high, the stage becomes 0. Otherwise the stage increments and saturates at `final_stage`. `stage1` is 0.9 V when the stage is at least 1. `stage2` is 0.9 V when the stage is at least 2. `ready` is 0.9 V when the stage is at least `final_stage`. `progress` is `0.9*stage/final_stage`. An output whose condition does not hold is 0. The stage starts at 0. While the clock is stopped, a change of `rst` does not update the state.

Within 0.2 ns before and after a `clk` threshold crossing, `rst` and the qualification inputs stay stable. An input threshold transition that coincides with a `clk` crossing is not scored. If a valid reset and a stage advance fall on the same sampling edge, the clear takes priority and `ready` is not asserted.

Acceptance compares `stage1`, `stage2`, `ready`, and `progress` with their expected levels at every saved waveform point and allows an error of 25 mV. It does not score the first 0.12 ns after time 0, or the points within 0.12 ns before or after each rising threshold crossing of `clk`. After each rising `clk` crossing, every output must therefore reach its new level, including its `tr` smoothing, within 0.12 ns.

Conditions that forbid an action must still meet the on-time startup requirement. The final test uses different qualification and reset traces. The acceptance stimuli and the checker stay fixed.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va`. It already contains the full erroneous `reset_release_sequencer` source. You may rewrite that module. Keep the public ports, the module name, and the source parameter defaults.
- Deliver the external staging, saturation, and reset behavior. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
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
