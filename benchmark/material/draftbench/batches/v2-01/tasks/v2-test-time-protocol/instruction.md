# Time-count instrument with re-arm, latch, and overflow

Build an 8-bit instrument that counts clock edges between start and stop events, with re-arming, result latching, and overflow. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `tdc_meter(start, stop, clk, rst, code_0, code_1, code_2, code_3, code_4, code_5, code_6, code_7, valid, overflow)`. `start`, `stop`, `clk`, and `rst` are read-only observation inputs. Do not drive them. `code_0` through `code_7`, `valid`, and `overflow` are outputs, and `code_0` is the least significant bit. The measured events are independent sources in each bench netlist; there is no fixed DUT model file. The instrument is what is scored: a correct report still passes when the measured interval misses its own target.

Declare real parameter `tr=20 ps`, the output edge time.

The input threshold is 0.5 V, and the logic outputs are 0 V and 1 V. A rising `start` clears the old result, `valid`, and `overflow`, re-arms the meter, and cancels any earlier interval. While armed, every rising `clk` edge counts once. A rising `stop` latches the count, disarms the meter, and sets `valid = 1`. A `stop` while not armed is ignored, and the result holds. The 256th `clk` edge produces the saturated value 255, sets `overflow = 1` and `valid = 1`, and disarms the meter. A rising `rst` asynchronously clears all state, and no measurement takes place while `rst` is high. The fixed scenarios have no simultaneous input edges; simultaneous-edge semantics are outside this task. Outputs may be smoothed within 40 ps after an event. After that, the error limit is 2 mV. This 40 ps timing guard applies around these events: every rising crossing of `rst`, `start`, `stop`, or `clk` through 0.5 V, whether or not the meter is armed or the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 80 ps is not scored. In every longer interval, each output is scored at every saved point more than 40 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

The code is the output of a result register. From `start` until `stop` or overflow, `code_0` through `code_7` all stay at 0, and `valid = 0` and `overflow = 0`. The internal running count does not drive the code directly. After `stop` or the 256th `clk` edge publishes a result, the code, `valid`, and `overflow` hold until the next `start` or `rst`. The initial state is the same as the state after an `rst` clear, and the meter is not armed.

The `clk` period is 90 ps to 130 ps, and the `start` and `stop` input edges are 20 ps. The measurement start and stop, re-arming, unarmed stops, and reset times may vary. Final evaluation includes a normal latch, a cancelled interval, and an interval of more than 256 edges. Input threshold crossings do not coincide and are at least 5 ps apart. In every case, public and final, no interval is exactly 80 ps long. The count boundary and the report levels are fixed.

Public cases are in `/app/testbench/cases.json`. You can use them to run your own Spectre self-test. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. The final-evaluation bench and checker are not part of the solving material. The acceptance targets and numerical tolerances are those of this public contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `tdc_meter` on the declared ports, including `tr=20 ps`.
- Deliver the result-register code, `valid`, and `overflow`. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
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
