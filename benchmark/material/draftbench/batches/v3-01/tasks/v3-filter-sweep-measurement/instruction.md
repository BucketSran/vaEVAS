# Four-tone sweep meter for a fixed low-pass

Drive four tones into a fixed, read-only low-pass and report steady gain and phase from the actual `drive` and `sense` waveforms. Do not read the DUT parameters or replace the measurement with a formula. The fixed backend is Spectre. Legal Verilog-A is not restricted. A public self-test does not replace independent final evaluation. Task weight is 1.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `sweep_meter(drive, sense, gain, phase, valid)`. `drive` is the stimulus output. `sense` is the read-only DUT response. Do not drive `sense`. `gain`, `phase`, and `valid` are reports.

Declare these real parameters and defaults: `f0=1000`, `f1=4000`, `f2=16000`, and `f3=8000` Hz, each legal from 500 Hz to 20000 Hz; `amplitude=0.12` V, legal from 0.05 V to 0.2 V; `slot=0.02` s; `settle=0.004` s, legal from 0.001 s to 0.005 s; `window=0.008` s, legal from 0.001 s to 0.009 s. Require `settle+window < slot`.

Slot `k` starts at `k*slot`, for `k` = 0, 1, 2, 3, using `f0` through `f3`. `drive = Ak*sin(2π fk*(t-k*slot))`. `Ak` is `amplitude`, except slot `k=2`, which uses 0.0001 V. The pre-migration contract names that slot with the same index it uses in `k*slot`.

Over `[slot start + settle, slot start + settle + window]`, integrate the actual waveform synchronously: `C = 2/window * ∫ v(t) * exp(-j 2π fk (t - slot start)) dt`. `gain` is `|Cout/Cin|`. `phase` is `arg(Cout/Cin)` in radians, wrapped to `[-π, π]`. Update the report at the end of the window and hold it until the next window ends. A window is valid only when `|Cin|>=0.01` V, `window*fk>=6`, and `settle>=0.003` s. A low amplitude, a waveform that is not yet steady, or an insufficient window reports `valid=0`. Otherwise `valid=1`.

The fixed DUT is `healthy_lowpass` in `/app/testbench/healthy.va`, connected from `drive` to `sense`. Its declared defaults are `fc=1500` Hz and `g=1`. Public conditions may set the cutoff from 600 Hz to 4000 Hz and the gain from 0.5 to 2. Those values are read-only.

The gain-report error is 0.035. The wrapped phase error is 0.035 rad. The real stimulus error is 0.002 V. Cover every tone, including the invalid low-amplitude window.

The same contract text is at `/app/testbench/contract.md`. The public netlist is `/app/testbench/feedback.scs`. The old meter shell is only `/app/circuit.va`.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit only `/app/circuit.va`. Keep the module name, ports, and parameters.
- The meter must drive the four tones and compute gain and phase from the actual waveforms. Any implementation that meets this interface and external behavior is acceptable. A particular integrator organization is not required.
- Do not edit `/app/testbench/healthy.va`. The submitted model must not read `fc` or `g`, and must not replace the integral with the DUT's closed-form response. This restriction applies to the submitted model. You may read the public DUT and run the public check.
- The low-amplitude slot is part of the contract. Reporting `valid=0` there is required when the validity conditions fail.

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
