# Measured static gain and finite settling

Measure one static amplifier and one dynamic amplifier that observe the same input in parallel. They are not cascaded. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A. A dynamic response that does not settle can still be measured correctly and pass. The result covers only the stated finite window. It does not claim stability for all later time.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `gain_settling_meter(vin, static_out, dynamic_out, launch, gain, gain_valid, settling_ns, settled, status)`. `vin`, `static_out`, `dynamic_out`, and `launch` are read-only. Do not drive them. `gain`, `gain_valid`, `settling_ns`, `settled`, and `status` are outputs. The read-only DUT ports do not expose an internal settled flag for the meter to use.

Declare these defaults: real `sample_period=250 ps`, real `min_input_span=0.02` V, real `settle_tol=0.002` V, real `tr=20 ps`, integer `samples=80`, and integer `tail_samples=8`. The 80-sample count and the final-8-sample condition stay fixed. The timing guard is 80 ps. Gain error is 0.02, settling-time error is 0.03 ns, and the remaining voltage tolerance is 3 mV.

The timing guard applies around these events: every rising crossing of `launch` through 0.5 V, and the end of each window, 80 sample periods of 250 ps (20 ns) after its `launch` crossing. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

Before the first rising `launch`, `gain`, `gain_valid`, `settling_ns`, `settled`, and `status` are 0. While a validity flag is 0, the numeric reports must still be initialized or held as this contract requires. A rising `launch` captures the input and static-output baselines, clears the report, and then samples `dynamic_out` 80 times at 250 ps. The observation window is 20 ns. The input changes and then holds before the first sample. A second round captures every state again.

The span boundary uses a 1 pV numerical comparison tolerance: `abs(span) <= 0.02 V + 1 pV` is invalid. Both the normal and slow DUT stimuli leave that boundary. If the input-to-baseline span at the end of the window is invalid, `status=2` and the other reports are 0. Otherwise `gain` is the actual static-output change divided by the actual input change, and `gain_valid=1`. The final `static_out` defines the observation target.

Among all 81 dynamic samples, including the baseline, settling time is the first sample after the last sample whose error exceeds 2 mV. If no sample exceeds 2 mV, the settling time is 0. `settled=1` and `status=1` only when the last 8 samples are all inside 2 mV; the settling time is then reported. Otherwise `settled=0`, `status=3`, and `settling_ns=0`, while the actual static gain is still reported. During collection, `status=0`.

The static amplifier gain used by this contract is 2.5. Dynamic `alpha` is 0.01 to 0.35. The `vin` baseline and step lie in 0.42 V to 0.49 V. Each round completes its input step within 200 ps to 240 ps after `launch` and then holds through the end of the window. A round may have a valid span, an invalid span, or a DUT that has not settled inside the window. Rounds are at least 25 ns apart. In every case, public and final, no interval is exactly 160 ps long.

The read-only parts are `/app/testbench/dut/static_amp.va` (`programmable_gain_amplifier`) and `/app/testbench/dut/dynamic_amp.va` (`opamp_feedback_settling`). Their source defaults are not a substitute for the waveform. The static part declares `vth=0.45`, `vcm=0.45`, `gain_low=0.8`, `gain_high=2.4`, `vmin=0`, `vmax=0.9`, and `tr=200 ps`. The published static-gain condition is still 2.5. The dynamic part declares `vdd=0.9`, `vss=0`, `vcm=0.45`, `vth=0.45`, `gain_lsb=0.5`, `alpha=0.3`, `settle_tol=40e-3`, `tr=200 ps`, and `tick=250 ps`. Public cases may override instance parameters inside the ranges stated above. The candidate cannot read those parameters.

Public cases are in `/app/testbench/cases.json`. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `gain_settling_meter` on the declared ports, including the parameter defaults above.
- Deliver the static-gain and finite-settling reports. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive `vin`, `static_out`, `dynamic_out`, or `launch`, and do not edit the files under `/app/testbench/dut/`. The submitted model must not read DUT parameters or an internal settled flag. This restriction applies to the submitted model. You may read the public DUT and run the public check.
- An unsettled dynamic waveform is still a valid measurement when `status=3` and the static gain are reported as specified.

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
