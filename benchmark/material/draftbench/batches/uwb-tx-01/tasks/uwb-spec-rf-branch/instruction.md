# Implement an RF branch ring oscillator of an IR-UWB transmitter

The transmitter has eight RF branch ring oscillators, one per carrier frequency. A scheduler powers a branch, precharges it and releases it at the start of a pulse; after the release the branch oscillates with a start-up transient until it is stopped. Build the voltage-domain model of one branch, with control inputs `pwr`, `pre` and `rel` and RF output `vro`.

## Spec

Use the module name and port order of the starter. All ports are voltages relative to ground. Implement these real parameters:

| Parameter | Meaning | Default | Allowed range |
| --- | --- | --- | --- |
| `f_rf` | settled carrier frequency, Hz | 6e9 | 4e9 to 8e9 |
| `a_ro` | settled output amplitude, V | 1.0 | 0.1 to 1.5 |
| `t99_amp` | time after a release at which the amplitude reaches 99 % of `a_ro`, s; 0 means full amplitude from the release | 2e-10 | 0 to 1e-9 |
| `t99_freq` | time after a release at which the start frequency offset has fallen to 1 % of `df_start`, s; 0 means no offset | 2e-10 | 0 to 1e-9 |
| `df_start` | relative frequency offset at the release (dimensionless) | 0.01 | -0.05 to 0.05 |
| `phi0` | preset phase at the release, rad | 0 | -π to π |
| `vth` | input threshold for `pwr`, `pre` and `rel`, V | 0.5 | 0.2 to 1.0 |

S1. Control. An input is high when its voltage is greater than `vth`. A release is a rising crossing of `rel` through `vth` while `pwr` is high. A rising `rel` while `pwr` is low, and a rising `pwr` while `rel` is already high, are not releases. Outside the interval from a release to its stop (S4), `vro` is 0 V: while the branch is off (`pwr` low), while it is precharged (`pwr` and `pre` high, `rel` low) and after a stop.

S2. Oscillation. Let t_r be the time of the `vth` crossing of `rel` that releases the branch, and u = t − t_r. From the release until the stop,

- `vro` = `a_ro` · a(u) · cos φ(u);
- a(u) = 1 − exp(−u/τa) with τa = `t99_amp` / ln 100, and a(u) = 1 when `t99_amp` = 0;
- φ(u) = `phi0` + 2π · `f_rf` · [u + `df_start` · τf · (1 − exp(−u/τf))] with τf = `t99_freq` / ln 100, and φ(u) = `phi0` + 2π · `f_rf` · u when `t99_freq` = 0.

φ is the integral of the instantaneous frequency `f_rf` · (1 + `df_start` · exp(−u/τf)): the branch starts with the relative offset `df_start` and settles to `f_rf`.

S3. Local phase. The phase depends only on the time since the latest release. It continues without a reset for as long as the branch stays released, however long `rel` stays high, and it does not depend on the absolute time or on earlier releases. Every release is a cold start from u = 0 with phase `phi0`, so two releases of the same instance give the same waveform relative to their release times.

S4. Stop. A falling crossing of `rel` or of `pwr` through `vth` stops the branch at that instant: `vro` returns to 0 V at once, with no decaying tail, and stays at 0 V until the next release.

S5. Operating domain. All inputs start at 0 V and switch between 0 V and a level VIN, where `vth` + 0.3 V <= VIN <= 1.8 V, with linear edges no longer than 10 ps. `pre` is high only while `pwr` is high and `rel` is low, except that at each release `pre` falls at the same time as `rel` rises (edges centred on the same instant). Each release follows at least 100 ps during which `pwr` and `pre` are high and `rel` is low. Crossings of `pwr` and `rel` are at least 100 ps apart, except that `pwr` and `rel` may fall at the same time. `rel` may rise while `pwr` is low, and `pwr` may rise while `rel` is high; by S1 neither is a release.

S6. Acceptance. The test bench saves `vro` with time steps of at most 1 ps, and `vro` must be finite at every saved point. Saved points within 3 ps of a `vth` crossing of `pwr` or `rel` are not compared with the expected value. At every other saved point, `vro` must be within 5 mV of the value that S1 to S4 give (S2 during a release, 0 V elsewhere). In each release, the zero crossings of `vro`, located by linear interpolation between saved points from 5 ps after the release to 5 ps before its stop, must match the zero crossings of S2 (φ = π/2 + kπ) one to one, each within 0.2 ps; where an expected crossing lies within 1 ps of a window end, that end moves 2 ps inward. For every instance with two or more releases, the zero crossings of each release, measured from its release time, must agree with those of the first release within 0.2 ps, over as many crossings as the shortest release has. Final evaluation reruns the public case and adds others inside S5: other carriers and parameter values (including zero settling times, negative `df_start`, nonzero `phi0`, other `a_ro` and `vth`), other VIN, several instances with different parameters driven by the same inputs, a release held for 5 ns, stops by `pwr` while `rel` is high, `rel` rising while `pwr` is low, `pwr` rising while `rel` is high, and repeated cold starts of different lengths with release times between saved points. Every check of every instance must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and port declarations, declare the seven parameters with the names and defaults above, and implement the behavior.
- Any Verilog-A implementation that meets the interface and the external behavior is acceptable. The internal state variables and the event organization are your choice. You may declare additional parameters, for example a time-step control, if their defaults keep the behavior above; the test bench sets only the seven parameters of the table.
- The submitted model must be self-contained apart from the standard Verilog-A headers. It must not read or write files or start external processes.

Run `python3 /app/testbench/check.py run` to simulate the public case and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating. The [public testbench guide](/app/testbench/README.md) explains the case, the simulator and the output files.

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
