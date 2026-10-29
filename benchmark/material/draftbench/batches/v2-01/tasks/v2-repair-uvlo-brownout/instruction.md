# Repair the UVLO brownout detector

Repair the supplied undervoltage brownout detector so that its clocked hysteresis follows the public thresholds. The fixed backend is Spectre. The starter at `/app/circuit.va` is the complete erroneous module, not an empty port shell.

## Spec

The module is `uvlo_brownout_detector`. Its electrical ports, in order, are `clk`, `rst`, `vin`, `out`, and `metric`. `clk`, `rst`, and `vin` are inputs. `out` and `metric` are outputs. Keep this module name, port order, and the parameter defaults supplied in the source.

The supplied real parameters are `tr` defaulting to 100 ps and `vth` defaulting to 0.45 V. Those defaults stay the source defaults. The logic threshold is 0.45 V.

The state updates only on a rising `clk` edge. `rst` high clears it. While `out` is low and `vin` is above 0.65 V, the edge sets `out` high. While `out` is high and `vin` is below 0.55 V, the edge clears `out`. Between the two thresholds, and at either threshold exactly, the state holds. The two thresholds are the binary64 (IEEE double-precision) values of the decimal numbers 0.65 and 0.55. This fixes their values, not their spelling: any way of writing them is acceptable if it gives exactly these values. `out` is 0 V or 0.9 V. `metric` is 0.9 V while `out` is 0 V and 0.1 V while `out` is 0.9 V. `out` starts at 0 V and `metric` starts at 0.9 V.

Acceptance compares `out` and `metric` with their expected levels at every saved waveform point and allows an error of 25 mV. It does not score the first 0.15 ns after time 0, or the points within 0.15 ns before or after each rising threshold crossing of `clk`. After each rising `clk` crossing, both outputs must therefore reach their new levels, including their `tr` smoothing, within 0.15 ns.

Conditions that forbid an action must still meet the on-time startup requirement. The final test covers two different stimuli. The acceptance stimuli and the checker stay fixed.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va`. It already contains the full erroneous `uvlo_brownout_detector` source. You may rewrite that module. Keep the public ports, the module name, and the source parameter defaults.
- Deliver the external clocked hysteresis, reset, and metric behavior. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
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
