# Repair the active-low PFD reset

Repair the supplied phase-frequency detector so that its active-low reset matches the public timing contract. The fixed backend is Spectre. The starter at `/app/circuit.va` is the complete erroneous module, not an empty port shell.

## Spec

The module is `pfd_active_low_reset`. Its electrical ports, in order, are `ref`, `fb`, `rstb`, `up`, and `down`. `ref`, `fb`, and `rstb` are inputs. `up` and `down` are outputs. Keep this module name, port order, and the parameter defaults supplied in the source.

The supplied real parameters are `vth` defaulting to 0.45 V, `vh` defaulting to 0.9 V, and `reset_delay` defaulting to 80 ps. Those defaults stay the source defaults. Output high is 0.9 V and the output transition time is 10 ps. The logic threshold is 0.45 V.

While `rstb` is low, clear both outputs immediately and cancel a pending reset. While reset is not asserted, a rising `ref` sets `up` and a rising `fb` sets `down`. After both outputs are high, clear them 80 ps later. A falling input edge does not set an output. An input edge during an active reset is not remembered. After reset is released, only a new edge is accepted. Both outputs start at 0.

Conditions that forbid an action must still meet the on-time startup requirement. The final test covers two different stimuli. The acceptance stimuli and the checker stay fixed.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va`. It already contains the full erroneous `pfd_active_low_reset` source. You may rewrite that module. Keep the public ports, the module name, and the source parameter defaults.
- Deliver the external reset, set, and delayed-clear behavior. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
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
