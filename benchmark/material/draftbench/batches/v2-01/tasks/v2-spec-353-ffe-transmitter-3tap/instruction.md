# 3-tap FFE transmitter

Build a 3-tap feed-forward equalizer transmitter that samples NRZ symbols and tap codes on a clock and drives the equalized output plus the per-tap debug voltages.

## Spec

Use the starter declaration of `ffe_tx_3tap`. Every port is electrical. The positional order is `data`, `clk`, `rst`, `pre_1`, `pre_0`, `post_1`, `post_0`, `vout`, `main_dbg`, `pre_dbg`, `post_dbg`.

`data` is the NRZ symbol sampled on rising `clk` edges. `clk` is that clock. `rst` is the reset read on the same rising edge. `pre_1:pre_0` and `post_1:post_0` are unsigned two-bit tap-control codes, also sampled on that edge. The model drives `vout`, `main_dbg`, `pre_dbg`, and `post_dbg`. The interface sentence gives the order and the electrical discipline. It does not print a separate input and output list. The directions above are the sample and drive roles in this same contract.

Declare these overrideable parameters. No legal range is stated beyond the values and equations here.

- `vdd` = 0.9 V. Output full-scale level and the upper clamp of `vout`.
- `vss` = 0.0 V. Output low level and the lower clamp of `vout`.
- `vcm` = 0.45 V. Common-mode level.
- `vth` = 0.45 V. Logic threshold.
- `main_amp` = 0.18 V. Main-cursor amplitude around common mode.
- `tap_step` = 0.04 V. Tap contribution per code step.
- `tr` = 120 ps. Output transition smoothing time.

The three symbol-history values start at 0. All four outputs start at `vcm`. `rst` is read on a rising `clk` edge. When that sample sees `rst` high, clear the history to 0, 0, 0 and set every output target back to `vcm`.

On each rising `clk` edge that is not a reset, sample `data`, `pre_1`, `pre_0`, `post_1`, and `post_0` together. A level above `vth` is high. `data` high is symbol +1 and `data` low is symbol -1. The pre code is `2*pre_1 + pre_0` and the post code is `2*post_1 + post_0`, each an integer from 0 to 3. A higher code increases the magnitude of the corresponding contribution.

Let the current symbol be the one just sampled, the previous symbol be the prior current symbol, and the older symbol be the one before that. Unsampled history remains 0. Then `main = main_amp * current`, `pre = tap_step * pre_code * previous`, and `post = -tap_step * post_code * older`. Drive `main_dbg = vcm + main`, `pre_dbg = vcm + pre`, and `post_dbg = vcm + post`. Drive `vout = clamp(vcm + main + pre + post, vss, vdd)`. The debug ports are not clamped. A tap-code change between rising edges does not change the output targets. After the `tr` transition, the outputs hold until the next rising edge.

Initial levels and edges are unambiguous. `data`, `clk`, `rst`, `pre_1`, `pre_0`, `post_1`, and `post_0` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. Supplies stay fixed. The logic threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Every saved point is scored, for all four outputs, except points less than `1.15*tr` after t = 0 or after a rising `clk` crossing that changes an output target. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `ffe_tx_3tap` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The tap equation defines the observable voltages. It does not require a particular state name or event operator.
- The submitted model must not read grading files, replay stored answers, or start external processes. You may read this instruction, the starter, and the public testbench, and you may run the public check. Do not edit the public testbench.

From `/app`, run `python3 testbench/check.py --output /app/output/public-check`.

[testbench/README.md](testbench/README.md) describes that check. The public bench sources stay visible, including [testbench/visible_test.scs](testbench/visible_test.scs). Tool version, timeouts, and diagnostics are in that README.

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
