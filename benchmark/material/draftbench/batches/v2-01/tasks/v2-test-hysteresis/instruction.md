# Bidirectional comparator hysteresis characterization

Measure the upward and downward switching points of a fixed, read-only hysteretic comparator from its actual output edges. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A. A correct report of a DUT that misses its own performance limit still passes.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `hysteresis_meter(vin, cmp_out, begin_round, up, down, width, valid)`. `vin`, `cmp_out`, and `begin_round` are read-only observation inputs. Do not drive them. `up`, `down`, `width`, and `valid` are outputs. The outputs report captured input values in volts. Logic high and low are 1 V and 0 V.

Declare real parameter `tr=20 ps`, the output edge time.

When the comparator output crosses 0.5 V rising, capture the actual `vin` into `up`. When it crosses 0.5 V falling, capture the actual `vin` into `down`. After both directions have been captured in the same round, `width = up - down` and `valid = 1`. A rising crossing of 0.5 V on `begin_round` clears all reports and the direction history. A new round that lacks either direction must keep `valid = 0`. Without a `begin_round` event, the initial round starts at t = 0. Every round, including the initial round at t = 0, starts with `up`, `down`, `width`, and `valid` at 0 V. A direction not yet captured in the current round reports 0 V, and `width` stays 0 V until both directions have been captured. Each later edge in a direction refreshes the corresponding value. The comparator delay is already part of the actual capture point; do not report an ideal threshold computed from the DUT parameters. Outputs may transition within 100 ps after an event. After that, the absolute error must not exceed 2 mV. This 100 ps timing guard applies around these events: every rising crossing of `begin_round` through 0.5 V, and every rising or falling crossing of `cmp_out` through 0.5 V, whether or not the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. In every interval, each output is scored at every saved point more than 100 ps from both ends of the interval, and at no other point, so an interval no longer than 200 ps is not scored.

The read-only DUT is `support_hysteretic_comparator` in `/app/testbench/dut/support_cmp.va`. `vin` stays within 0.35 V to 0.65 V. The comparator `offset` is -0.02 V to 0.02 V, `vhys` is 0.04 V to 0.13 V, and `td` is 100 ps to 500 ps. The input ramps, the round starts, and complete or missing-direction rounds may vary. `cmp_out` starts low, and a round start never coincides with a comparator edge. In every case, public and final, no interval is exactly 200 ps long.

Public cases are in `/app/testbench/cases.json`, and the fixed DUT implementation is in `/app/testbench/dut/`. You can use them to run your own Spectre self-test. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. The final-evaluation bench and checker are not part of the solving material. The acceptance targets and numerical tolerances are those of this public contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `hysteresis_meter` on the declared ports, including `tr=20 ps`.
- Deliver the captured `up`, `down`, and `width` values and `valid`. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive the observation inputs, and do not edit `/app/testbench/dut/support_cmp.va`. The submitted model must not replace a captured value with a threshold computed from the DUT parameters. This restriction applies to the submitted model. You may read the public DUT and run the public check.

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
