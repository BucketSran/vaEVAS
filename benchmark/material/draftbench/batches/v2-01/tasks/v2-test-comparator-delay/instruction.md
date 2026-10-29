# Comparator propagation delay and overdrive measurement

Measure the propagation delay and overdrive of a fixed, read-only comparator. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A. A correct report of a DUT that misses its own performance limit still passes.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `delay_meter(vdd, vss, clk, vinp, vinn, outp, outn, delay_ps, overdrive_mv, polarity, valid)`. `vdd`, `vss`, `clk`, `vinp`, `vinn`, `outp`, and `outn` are read-only observation inputs. Do not drive them. `delay_ps`, `overdrive_mv`, `polarity`, and `valid` are outputs.

Declare real parameter `tr=20 ps`. The supplies are fixed at 0.9 V and 0 V, and the logic detection threshold is 0.45 V. The `valid` and `polarity` reports also use 0.9 V logic. The timing guard is 80 ps. The allowed delay error is 0.7 ps, the allowed overdrive error is 0.2 mV, and the allowed logic error is 0.002 V.

The timing guard applies around these events: every rising crossing of `clk`, `outp`, or `outn` through 0.45 V, whether or not the meter is armed or the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

Before the first rising `clk` edge, `delay_ps`, `overdrive_mv`, `polarity`, and `valid` are all 0. While `valid` is 0, the numeric reports must still be initialized or held as this contract requires. Every rising `clk` edge re-arms the meter and clears `valid`. `overdrive_mv` is the absolute value of the input difference at that instant, multiplied by 1000. After arming, the first rising edge of `outp` or `outn` latches its actual interval from `clk`, multiplied by 1e12, into `delay_ps`; `polarity` is 0.9 V or 0 V respectively, and `valid` is 0.9 V. A missing decision must not carry over the old `valid`. Edges that occur while the meter is not armed are ignored. Re-arming keeps the previous values until a new decision.

The read-only DUT is `support_overdrive_delay_comparator` in `/app/testbench/dut/support_cmp.va`. In the public self-tests and the final evaluation, the absolute differential overdrive is 0.001 V to 0.08 V, and the input common mode is 0.45 V. The clock period is 5 ns to 7 ns. In each round, the inputs are stable for at least 200 ps before launch, and the actual response is no longer than 1 ns. The DUT may vary its propagation-delay parameters, or it may lack a decision in any later round. In every case, public and final, no interval is exactly 160 ps long. The supplies and units stay unchanged.

Public cases are in `/app/testbench/cases.json`, and the fixed DUT implementation is in `/app/testbench/dut/`. You can use them to run your own Spectre self-test. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. The final-evaluation bench and checker are not part of the solving material. The acceptance targets and numerical tolerances are those of this public contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `delay_meter` on the declared ports, including `tr=20 ps`.
- Deliver the `delay_ps`, `overdrive_mv`, `polarity`, and `valid` reports. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive the observation inputs, and do not edit `/app/testbench/dut/support_cmp.va`. This restriction applies to the submitted model. You may read the public DUT and run the public check.

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
