# Online gain meter for a real amplifier

Measure the online gain of a fixed, read-only programmable-gain amplifier from the spans of its actual input and output differences on a global sample grid. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A. A correct report of a DUT that misses its own performance limit still passes.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `gain_estimator(VDD, VSS, vinp, vinn, voutp, voutn, gain_out, valid, begin_round)`. `VDD` and `VSS` are the supply terminals; in every case `VDD` is 0.9 V and `VSS` is ground. `vinp`, `vinn`, `voutp`, `voutn`, and `begin_round` are read-only observation inputs. Do not drive them. `gain_out` and `valid` are outputs. Helper modules may be defined in the same file.

Declare these real parameters with these defaults; the cases set the same values on the instance: `sample_period` = 1 ns, `start_time` = 20 ns, `gain_scale` = 10, `min_input_span` = 0.02 V, and `tedge` = 200 ps, the output edge time. The timing parameters, the span condition, and `gain_scale` stay fixed.

Samples are taken at the global times `k*sample_period`, `k = 0, 1, ...`, that are at or after `start_time`. The sample at `start_time` itself counts, so with the defaults the first sample is at 20 ns. A sample reads the actual input difference `V(vinp, vinn)` and the actual output difference `V(voutp, voutn)`. A round accumulates the minimum and maximum of both differences over its samples. When the input span of the round, its maximum minus its minimum input difference, is strictly greater than `min_input_span`, `valid` is at the supply high level `V(VDD)` and `gain_out = (VDD - VSS) * output span / input span / gain_scale`, where the output span is the maximum minus the minimum output difference of the same round. Both reports are refreshed at every sample. While the input span of the round is at most `min_input_span`, `valid` stays at 0 V and `gain_out` is 0 V. A rising crossing of `begin_round` through 0.5 V clears the extremes, `gain_out`, and `valid`; the new round collects from the next sample. Without a `begin_round` event the initial round starts at t = 0 with both reports at 0 V. Measure the actual waveforms: do not read the amplifier's internal gain or clipping state as the result, and do not substitute an independent signal source for the observed amplifier output.

The timing guard is 350 ps, and the voltage error limit is 2 mV. The timing guard applies around these events: every sample instant `k*sample_period` at or after `start_time`, whether or not the report changes there, and every rising crossing of `begin_round` through 0.5 V. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 700 ps is not scored. In every longer interval, each output is scored at every saved point more than 350 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

The read-only DUT is `programmable_gain_amplifier` in `/app/testbench/dut/amplifier.va`. Its `gain_low` is 0.2 to 1.2 and its `gain_high` is 1 to 2.6. The input common mode is 0.45 V, and the input sine has an amplitude of 0.001 V to 0.07 V and a frequency of 15 MHz to 25 MHz. The gain-switching and `begin_round` times may change. In every case, public and final, every rising `begin_round` crossing is at least 200 ps away from every global sample instant, and no interval is exactly 700 ps long.

Public cases are in `/app/testbench/cases.json`, and the fixed DUT implementation is in `/app/testbench/dut/`. You can use them to run your own Spectre self-test. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. The final-evaluation bench and checker are not part of the solving material. The acceptance targets and numerical tolerances are those of this public contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `gain_estimator` on the declared ports, including the parameter defaults above.
- Deliver the `gain_out` and `valid` reports. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive the observation inputs, and do not edit `/app/testbench/dut/amplifier.va`. The submitted model must not read the amplifier's parameters, internal gain, or clipping state. This restriction applies to the submitted model. You may read the public DUT and run the public check.

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
