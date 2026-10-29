# Four-sample online true-RMS meter

Build a meter that reports the true RMS of the sampled differential input over non-overlapping four-sample windows. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `sampled_true_rms_to_dc(vinp, vinn, clk, reset, enable, rms_out, valid)`. `vinp`, `vinn`, `clk`, `reset`, and `enable` are read-only observation inputs. Do not drive them. `rms_out` and `valid` are outputs. The measured inputs and the clock, reset, and enable signals are independent sources in each bench netlist; there is no fixed DUT model file. The instrument is what is scored: a correct report still passes when the measured signal misses its own target.

Declare these real parameters and defaults: `vth=0.45` V, the logic threshold; `vhigh=0.9` V, the high level of `valid`; and `tr=100 ps` from `(0:inf)`, the output transition time. The public benches instantiate the meter with `tr=80p`.

Every rising `clk` edge with `enable` high and `reset` low samples the actual differential input `V(vinp) - V(vinn)`. Exactly four samples form one non-overlapping window, and the output is `sqrt(mean(x*x))` over those four samples. A sampling edge with `enable` low does not discard a partial window, but it clears `valid`. Each completed window keeps `valid` high for one sampling interval; the next rising `clk` edge clears `valid`. A rising `reset` asynchronously clears the accumulation, the report, and `valid`. A sampling edge while `reset` is high also clears them. `rms_out` holds until the next complete window. From t = 0 until the first complete window, `rms_out` and `valid` are 0 V. The error limit is 2 mV, and outputs may transition within 320 ps after an event. This 320 ps timing guard applies around these events: every rising crossing of `clk` or `reset` through 0.45 V, whether or not a sample is taken or the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 640 ps is not scored. In every longer interval, each output is scored at every saved point more than 320 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

Each of the two inputs stays within 0 V to 0.9 V and is DC or a sine wave with amplitude 0 V to 0.35 V and frequency 10 MHz to 35 MHz. The clock period is 4 ns to 6 ns. The reset and enable times may vary and may cross partial windows. Control threshold crossings are at least 200 ps away from sampling edges. In every case, public and final, no interval is exactly 640 ps long. The four-sample window, the threshold, and the report units are fixed.

Public cases are in `/app/testbench/cases.json`. You can use them to run your own Spectre self-test. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. The final-evaluation bench and checker are not part of the solving material. The acceptance targets and numerical tolerances are those of this public contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `sampled_true_rms_to_dc` on the declared ports, including the parameters above.
- Deliver `rms_out` and `valid`. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive the observation inputs. This restriction applies to the submitted model. You may read the public bench and run the public check.

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
