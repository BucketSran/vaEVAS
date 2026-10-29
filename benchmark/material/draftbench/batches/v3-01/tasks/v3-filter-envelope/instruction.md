# Envelope detector with a continuous energy state

Implement an envelope detector whose energy state follows a first-order continuous law and decays when the input is disabled. The fixed backend is Spectre. Legal Verilog-A is not restricted. A public self-test does not replace independent final evaluation. Task weight is 1.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `envelope(i, q, en, reset, env)`. All ports are electrical. `i`, `q`, `en`, and `reset` are inputs, and `env` is the output.

Declare these real parameters. `bandwidth` is in hertz, default 200, legal range 100–300. `initval` is in V², default 0, legal range 0–0.02.

The continuous energy state follows `e' = 2π*bandwidth*(P - e)`, and `env = sqrt(max(e, 0))`. While `en > 0.5`, `P = i² + q²`. While disabled, `P = 0`, so the envelope decays exponentially; it neither holds nor drops to zero at once. `e(0) = initval`. While `reset > 0.5`, `e = initval`. After release, integration continues from that state. The inputs `i` and `q` stay within ±0.5 V.

The output error limit is 0.01 V, excluding the analog transition region of a reset switch. Output samples taken while `V(reset)` is strictly between 0.01 V and 0.99 V are not checked. The public bench drives `reset` and `en` between 0 V and 1 V.

The public netlist is `/app/testbench/feedback.scs`. There is no fixed DUT file. The old candidate shell is only `/app/circuit.va`. `/app/testbench/contract.md` keeps the pre-migration public contract text, with the parameter name corrected to `initval`. That text does not quantify the excluded reset region; this Spec does.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit only `/app/circuit.va`. Keep the module name, ports, and parameters, and implement the external behavior.
- Any equivalent internal realization is acceptable. The state equation states the required response, reset, and initial condition. It does not require a particular state name or operator in the source.
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
