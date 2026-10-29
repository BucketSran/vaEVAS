# Programmable low-pass extended from a fixed baseline

Extend the supplied healthy fixed low-pass to a code-selected cutoff. Code 0 must keep the baseline behavior. The fixed baseline is readable and must not be modified. The fixed backend is Spectre. Legal Verilog-A is not restricted. A public self-test does not replace independent final evaluation. Task weight is 1.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `programmable_lp(u, code, reset, y)`. All ports are electrical. `u`, `code`, and `reset` are inputs. `y` is the output.

Declare real `base` in hertz, default 1000, legal range 800–1200, and real `initval`, default 0, legal range ±0.1. `initval` is both the initial state and the reset voltage. `code` is a voltage from 0 through 3. `c = clip(round(code), 0, 3)` and `fc = base * 2^c`.

The continuous state is `y' = 2π fc * (u - y)`, with `y(0)=initval`. Crossing a rounding threshold changes the rate immediately and must keep `y` continuous. Do not clear the history on a code change. While `reset>0.5`, `y=initval`. After release, integrate from that state. Code 0 must preserve the baseline behavior.

The fixed baseline is `fixed_lp(u, reset, y)` in `/app/testbench/fixed_lp.va`. Its defaults are `base=1000` and `initval=0`, and its response is the same one-pole law at `fc=base`. The output error limit is 0.008 V, excluding the analog transition region of a reset switch. The width of that excluded region is not given a separate number in the contract.

The same contract text is at `/app/testbench/contract.md`. The public netlist is `/app/testbench/feedback.scs`. The candidate shell is only `/app/circuit.va`.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit only `/app/circuit.va`. Keep the module name, ports, and parameters.
- You may choose any equivalent implementation. The one-pole equation and the continuous code change are the required external behavior. Reusing the baseline's internal form is not required. Code 0 must still match the fixed baseline behavior.
- Do not edit `/app/testbench/fixed_lp.va`. The submitted model must not clear `y` when only `code` changes. This restriction applies to the submitted model. You may read the baseline and run the public check.

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
