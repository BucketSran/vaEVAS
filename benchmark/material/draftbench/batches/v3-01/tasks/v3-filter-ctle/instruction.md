# Continuous-time linear equalizer

Implement the one-zero, two-pole CTLE behavior below. The fixed backend is Spectre. Legal Verilog-A is not restricted. A public self-test does not replace independent final evaluation. Task weight is 1.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `ctle(u, y)`. Both ports are electrical. `u` is the input and `y` is the output.

Declare these real parameters. `fz`, `fp1`, and `fp2` are in hertz. Their legal ranges are 500–2000, 2000–8000, and 8000–24000. `gain` is 0.5–2. The defaults are `fz=1000`, `fp1=4000`, `fp2=12000`, and `gain=1`. `x1init` and `x2init` default to 0 and each lies in ±0.1.

The transfer function is `H(s) = gain * (1 + s/(2π fz)) / ((1 + s/(2π fp1)) * (1 + s/(2π fp2)))`. The DC gain is `gain`.

The initial-state contract is `x1' = 2π fp1 * (u - x1)`, `x2' = 2π fp2 * (x1 - x2)`, and `y = gain * (x2 + (fp2/fz) * (x1 - x2))`, with `x1(0)=x1init` and `x2(0)=x2init`. Any equivalent internal implementation is acceptable. The output voltage error is at most 0.006 V. The steady complex frequency-response error is at most 3 percent of the target magnitude, with an absolute cap of 0.03 when the target magnitude is below 1. Acceptance covers DC, several frequency points, and recovery from a nonzero initial state.

The public contract text is also at `/app/testbench/contract.md`. The public netlist is `/app/testbench/feedback.scs`. There is no fixed DUT file. The old candidate shell is only `/app/circuit.va`.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit only `/app/circuit.va`. Keep the module name, ports, and parameters, and implement the external behavior.
- Any equivalent internal realization is acceptable. The state equations state the required response and initial conditions. They do not require those state names in the source.
- Do not edit `/app/testbench/contract.md` or `/app/testbench/feedback.scs`. The submitted model must not read grading files. This restriction applies to the submitted model. You may read the public bench and run the public check.

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
