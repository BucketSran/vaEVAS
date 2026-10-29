# Measured DCO frequency and divider ratio

Measure the actual clocks of a fixed, read-only DCO. The frequency code is not connected to the candidate. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A. A correct report of a DUT that misses its own frequency target still passes.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `frequency_meter(dco_clk, div_clk, enable, reset, freq_mhz, divider_ratio, valid)`. `dco_clk`, `div_clk`, `enable`, and `reset` are read-only observations. Do not drive them. `freq_mhz`, `divider_ratio`, and `valid` are outputs.

Declare real `tr=20 ps`. The edge threshold is 0.45 V. The timing guard is 80 ps. `freq_mhz` must agree within 0.8 MHz, `divider_ratio` within 0.03, and logic levels within 0.01 V.

The timing guard applies around these events: every rising crossing of `dco_clk` or `div_clk`, every rising crossing of `reset`, and every falling crossing of `enable`, all through 0.45 V, whether or not the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

A complete period on a clock requires at least two rising edges. `freq_mhz` is `1e-6` divided by the most recent DCO period. `divider_ratio` is the most recent divided period divided by the most recent DCO period, and it updates when either clock completes a new period. When both periods have been acquired, `valid` is 1 V; otherwise it is 0. A rising `reset` or a falling `enable` clears all history and the report. Edges are not taken while the meter is disabled or held in reset.

The DUT parameter `divide_ratio` means how many DCO rising edges occur before the divided clock toggles once. The full-period ratio is twice that parameter. The parameter must not replace the measurement.

The read-only DUT is `frequency_word_dco` in `/app/testbench/dut/dco.va`. Its declared defaults are `vdd=0.9`, `vss=0`, `vth=0.45`, `f_min=80e6`, `f_step=2e6`, `f_max=250e6`, integer `divide_ratio=4`, and `tr=100 ps`. Public conditions may set `f_min` from 80 MHz to 130 MHz, `f_step` from 2 MHz to 5 MHz, and `divide_ratio` from 3 to 7, and may change the frequency code and the reset and disable times. In every case, public and final, no interval is exactly 160 ps long. The candidate cannot read those settings. It may report only after real edges form a complete period. A fragment that does not yet contain a complete period is allowed, and the report then follows the history and reset contract. The threshold and the units above stay fixed.

Public cases are in `/app/testbench/cases.json`. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `frequency_meter` on the declared ports, including `tr=20 ps`.
- Deliver the measured frequency and period ratio. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive the observation ports and do not edit `/app/testbench/dut/dco.va`. The submitted model must not read the DUT frequency settings or substitute `divide_ratio` for a measured period. This restriction applies to the submitted model. You may read the public DUT and run the public check.

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
