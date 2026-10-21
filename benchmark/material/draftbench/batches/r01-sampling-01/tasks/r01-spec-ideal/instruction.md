# Implement an ideal track-and-hold

Build a reusable Verilog-A model that tracks an analog input while a window is open and freezes the input when that window closes.

## Spec

This is an implementation draft. Named TBD fields below must be resolved before scored execution.

Use the starter port order. `vin`, `track`, and `rst` are voltage inputs relative to ground. `vout` is an ideal voltage output relative to ground. Implement real parameters `vth` and `vinit`, both in volts, both defaulting to 0.9. `vth` is the common control threshold. `vinit` is the initial and reset output value. Permitted parameter intervals are `TBD_PARAMETER_DOMAIN`.

S1. A control is high exactly when its voltage is greater than `vth`; equality is low. At startup, with reset low and track low, output `vinit` without sampling `vin`. With reset low and track high, output the current `vin` immediately. An initially high reset outputs `vinit`, regardless of track.

S2. Reset has priority. While reset is high, output `vinit`. Otherwise, while track is high, output the instantaneous `vin` throughout the window, including input changes inside it. Acquisition and reset are ideal and instantaneous. Do not add finite settling, output delay, or intentional output smoothing.

S3. When track crosses downward through `vth` with reset inactive, freeze `vin` at the crossing time. During hold, retain that value regardless of later input changes or hold duration. Reopening track resumes continuous tracking. There is no droop, clock feedthrough, charge injection, or other device mechanism.

S4. Reset discards the previous sample. Releasing reset into hold retains `vinit`, including when track closed during reset. Releasing reset into track resumes following `vin`; a later window close samples the then-current input. Each instance obeys these rules independently, including simultaneous events in different instances.

S5. The intended input class is finite continuous piecewise-linear voltage stimuli, with controls initially constant and subsequent isolated, strict threshold crossings. Initial controls may equal the threshold. A later control excursion that stops at or dwells on the threshold, an input discontinuity at a sampling edge, and simultaneous track/reset crossings within one instance have boundary rules `TBD_CONTROL_BOUNDARIES` and are not graded until resolved. Input and control voltage bounds, time horizon, ramp slopes, minimum crossing separation, and distances of crossings from the start and end are `TBD_STIMULUS_DOMAIN`. Different instances may cross simultaneously.

S6. Expected output follows S1 through S4. At each required observation, measure absolute voltage error against that output, not against a reference model trace. During hold the reference is the input at window close, not the input at the observation time. All required observations must satisfy `TBD_VOLTAGE_ATOL` volts. Observation spacing, timestamp tolerance, and any excluded event neighborhood are `TBD_MEASUREMENT_BUDGET`. No observation offset changes the sampling instant or permits model delay. Startup is observed at time zero and is not removed by a later event exclusion. Every required case, instance, and observation must be present and finite.

Final evaluation reruns the public representative conditions from the frozen `/app/circuit.va` in an author-controlled environment and adds new input, parameter, timing, and history combinations inside the finalized public domain. All required behaviors must pass for task score 1. An executed unsuccessful attempt scores 0, with its cause recorded separately. Unexecuted or unresolved evaluation has no score. Public diagnostic results and solver-written tests do not supply the final score.

## Deliverable

- Edit `/app/circuit.va` using the supplied module name and port declarations, and implement both parameters and the complete behavior.
- Any Verilog-A implementation that satisfies the interface and external behavior is acceptable. Internal state representation and event organization are your choice.
- The submitted model must be self-contained apart from standard Verilog-A headers. It must not read files, invoke external processes, or use external model libraries.

Run `python3 /app/testbench/check.py plan` to inspect the public stimuli and analytical observations. The [public testbench guide](/app/testbench/README.md) documents draft bench generation and offline trace diagnostics. Simulator execution and numerical PASS/FAIL remain pending the named TBD fields.

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
