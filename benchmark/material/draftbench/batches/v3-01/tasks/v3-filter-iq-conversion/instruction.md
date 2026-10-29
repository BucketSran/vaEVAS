# I/Q upconversion and downconversion

Implement the fixed mixer below. The local oscillator is a healthy external sine. Real I and Q voltages must be translated. Do not synthesize the target carrier directly. The fixed backend is Spectre. Legal Verilog-A is not restricted. A public self-test does not replace independent final evaluation. Task weight is 1.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `iq_mixer(i, q, lc, ls, rf, en, up, di, dq)`. All ports are electrical. `i`, `q`, `lc`, `ls`, `rf`, and `en` are inputs. `up`, `di`, and `dq` are outputs. `lc` is cos θ and `ls` is sin θ. The inputs are actual voltages.

Declare real `gain` defaulting to 1, legal range 0.5–2, and real `fbw` defaulting to 2000 Hz, legal range 1500–3000 Hz.

While enabled, `up = gain * (i*lc - q*ls)`. A real I/Q input moves to the sum-frequency sideband. The downconversion state is `a' = 2π fbw * (2*rf*lc - a)` and `b' = 2π fbw * (-2*rf*ls - b)`, both starting at 0. `di=a` and `dq=b`. When `en<=0.5`, all three outputs are 0, while the internal low-pass state continues to integrate. Enabling again reveals that state.

The LO is 10–16 kHz. The baseband is 100–1000 Hz. The RF offset is within ±1500 Hz. There is no noise, clipping, or image-rejection specification. The pointwise upconversion error limit is 0.002 V. The downconversion error limit is 0.008 V. The sum-frequency amplitude error limit is 0.015 V.

The public contract text is also at `/app/testbench/contract.md`. The public netlist is `/app/testbench/feedback.scs`. There is no fixed DUT file. The old candidate shell is only `/app/circuit.va`.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit only `/app/circuit.va`. Keep the module name, ports, and parameters.
- Upconversion must use the actual `i`, `q`, `lc`, and `ls` inputs. Any equivalent internal realization of the stated state is acceptable. Particular state names are not required. While disabled, the low-pass state still integrates.
- Do not edit the public contract or netlist. The submitted model must not synthesize the carrier without the input product. This restriction applies to the submitted model. You may read the public bench and run the public check.

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
