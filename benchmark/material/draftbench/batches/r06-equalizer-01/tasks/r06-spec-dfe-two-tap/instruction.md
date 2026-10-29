# Two-tap decision-feedback equalizer receiver

Build the slicer of a receiver with two-tap decision feedback. At each rising clock edge the model subtracts a feedback correction from the input, decides high or low, and reports the correction and the corrected input that this decision used. The correction comes from the model's own two previous decisions, not from earlier input samples, so a wrong decision also changes the next two corrections. Only after the decision does the model shift it into its history. A reset empties the history, and the first two decisions after it use only the decisions that exist.

## Spec

Use the starter declaration of `dfe_rx_top`. Every port is electrical. The positional order is `vin`, `clk`, `rst`, `tap1_1`, `tap1_0`, `tap2_1`, `tap2_0`, `decision`, `fb_metric`, `slicer_in_dbg`. `vin` (the received signal), `clk`, `rst` (active-high reset), and the four tap-code inputs are inputs. `decision`, `fb_metric`, and `slicer_in_dbg` are outputs.

Declare these overrideable parameters:

- `vdd` = 0.9 V. Output level of a high decision. Legal range 0.5 V to 1.5 V.
- `vss` = 0 V. Output level of a low decision. Legal range -0.5 V to 0.5 V. `vdd - vss` is at least 0.4 V.
- `vcm` = 0.45 V. Slicer threshold. Legal range 0.2 V to 0.7 V.
- `vth` = 0.45 V. Threshold for `clk`, `rst`, and the tap-code inputs. A level above `vth` is high. Legal range 0.2 V to 0.7 V.
- `tap_lsb` = 20 mV. Feedback weight of one tap-code step. Legal range 5 mV to 50 mV.
- `tr` = 200 ps. Output transition time. Legal range 10 ps to 1 ns.

History. The model keeps two history slots: `h1` holds the most recent decision and `h2` the decision before it. A high decision counts as +1 and a low decision as -1. A slot that holds no decision counts as 0. At t = 0 both slots are empty, and a reset empties both again, so a slot is empty until enough decisions have been made after the latest reset or t = 0. The cleared `decision` output is not a decision: it shows `vss`, but the slot behind it is empty and contributes 0.

Tap codes. Each tap has an unsigned two-bit code, `k1 = 2*b(tap1_1) + b(tap1_0)` and `k2 = 2*b(tap2_1) + b(tap2_0)`, where `b(x)` is 1 when input `x` is high and 0 when it is low. `tap1_1` and `tap2_1` are the most significant bits. Each code is an integer from 0 to 3. Tap 1 weights `h1` by `tap_lsb*k1` and tap 2 weights `h2` by `tap_lsb*k2`.

Decision. A decision event is a rising crossing of `clk` through `vth` after t = 0 at which `rst` is low. At a decision event at time `t_n` the model works in this order:

1. It reads `k1` and `k2` at `t_n`, together with the current `h1` and `h2`.
2. The feedback is `fb_n = tap_lsb*(k1*h1 + k2*h2)`.
3. The slicer input is `s_n = V(vin) - fb_n`, with `V(vin)` taken at `t_n`.
4. The decision `d_n` is high (+1) when `s_n >= vcm` and low (-1) otherwise.
5. `decision` drives `vdd` for a high decision and `vss` for a low one, `fb_metric` drives `fb_n`, and `slicer_in_dbg` drives `s_n`.
6. The history shifts: `h2` takes the old `h1`, and `h1` takes `d_n`.

The feedback of a decision therefore uses only decisions made at earlier events, never the decision being made. The first decision after a reset has no feedback, and the second uses only tap 1. For example, with `tap_lsb` = 20 mV, `k1` = 2, `k2` = 1, and `vcm` = 0.45 V, a decision with `h1` = +1, `h2` = -1, and `V(vin)` = 0.46 V has `fb_n` = 20 mV and `s_n` = 0.44 V, so it is low. With `h1` = -1 and `h2` = +1 the same input gives `fb_n` = -20 mV and `s_n` = 0.48 V, so it is high.

Reset. A rising crossing of `rst` through `vth` empties both history slots and sets `decision` to `vss`, `fb_metric` to 0 V, and `slicer_in_dbg` to 0 V at once, without waiting for a clock edge. While `rst` is high, rising `clk` crossings are not decision events and change nothing. The falling crossing of `rst` changes nothing by itself; the next decision event is the first one after the reset. At t = 0 the model is in this cleared state, whatever the inputs are.

Between events. Outputs change only at decision events and at rising crossings of `rst`, and hold their values between them. A change of `vin` or of a tap input between decision events changes no output; the model reads them again at the next decision event.

Output timing. After each event that changes an output's expected value, the output reaches the new value within `tr` and then stays on it until the next change. This also holds when the next change comes before the output has reached the previous value. The waveform inside that `tr` interval is not specified.

Legal inputs:

- `clk`, `rst`, and the tap-code inputs switch between 0 V and 0.9 V, and each transition between these levels lasts at most 200 ps. They never rest at `vth`, and at t = 0 each is at least 50 mV away from `vth`. An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. `clk` starts low.
- Successive `vth` crossings of the same one of these inputs are at least 0.5 ns apart. Successive rising `clk` crossings are at least 2 ns apart.
- Every crossing of `rst` and every crossing of a tap-code input is at least 0.5 ns away from every rising `clk` crossing, so no two events coincide.
- `vin` is continuous and stays within 0.4 V of `vcm`. Within 100 ps of every rising `clk` crossing, `vin` moves by less than 0.25 mV.
- At every decision event, `s_n` is at least 5 mV away from `vcm`, so no decision is decided by a tie.

The expected outputs are calculated with the rules above from the recorded inputs. Crossing times and input values are taken by linear interpolation between saved points. Every saved point is scored, except points less than `1.25*tr` after an event that changes that output's expected value by more than δ = 0.1 mV. A change of δ or less, such as a slicer input within δ of the previous one, does not count as a change here or in the output timing rule above: it opens no such interval, the expected value keeps its previous value, and the output is scored against that value as at any other point. At each scored point the error of every output is at most 2 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `dfe_rx_top` on the module and positional ports in the starter. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The rules define the decisions and the reported values. They do not require a particular module split, state variable, analog operator, or event organization.
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
