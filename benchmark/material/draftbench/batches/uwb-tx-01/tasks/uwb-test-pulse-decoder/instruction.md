# Build an on-line pulse decoder for an IR-UWB transmitter

The seed transmitter sends one RF pulse per 6-bit symbol: 3 bits move the pulse position on a grid of 16 steps per frame of its clock (differential PPM), and 3 bits select one of 8 carrier frequencies (FSK). Build the measurement instrument that watches the differential RF output and the frame clock, decodes every pulse back into its symbol, and flags malformed pulses.

## Spec

Use the module name and port order of the starter. All ports are voltages relative to ground. Implement these parameters (`n_width` is an integer, the others are real):

| Parameter | Meaning | Default | Allowed range |
| --- | --- | --- | --- |
| `v_det` | detection level for \|v\|, V | 0.05 | 0.02 to 0.5 |
| `t_gap` | gaps shorter than this stay inside one pulse, s | 1e-10 | 2e-11 to 3e-10 |
| `n_width` | nominal pulse width in grid steps | 9 | 4 to 12 |
| `tol_pos` | position tolerance as a fraction of the grid step δ | 0.25 | 0.05 to 0.45 |
| `tol_f` | relative frequency tolerance | 0.03 | 0.005 to 0.1 |
| `t_lat` | delay from the last exceedance of a pulse to its outputs, s | 2e-10 | `t_gap` to 6e-10 |
| `t_pw` | time `sym_valid` stays high, s | 2e-10 | 5e-11 to 5e-10 |
| `vdd` | output high level, V | 1.0 | 0.5 to 1.8 |
| `vth` | input threshold for `clk` and `rst`, V | 0.5 | 0.2 to 1.6 |
| `tr` | duration of every output edge, s | 2e-12 | 1e-12 to 1e-11 |

The channel list is fixed: f_k = 4.5 GHz + k × 3/7 GHz, k = 0 to 7.

S1. Pulses. The signal is v = V(vp) − V(vn). An exceedance is a maximal time interval in which |v| > `v_det`, for either sign of v. Consecutive exceedances separated by a gap shorter than `t_gap` belong to the same pulse; a gap of `t_gap` or longer ends the pulse. For each pulse, t_f is the start of its first exceedance and t_l is the end of its last exceedance.

S2. Position. T_clk is the clk period, the interval between consecutive rising crossings of `clk` through `vth`, and δ = T_clk/16. The pulse centre is t_c = (t_f + t_l)/2 and its start is t_s = t_c − `n_width`·δ/2. The frame edge t_fr is the latest rising crossing of `clk` at or before t_s + δ/2. The position is P = round((t_s − t_fr)/δ), an integer from 0 to 15, and the position error is e = t_s − t_fr − P·δ.

S3. Frequency. Take the zero crossings of v (sign changes) with t_c − `n_width`·δ/4 ≤ t ≤ t_c + `n_width`·δ/4. If there are N ≥ 2 of them, the first at z_1 and the last at z_N, the measured frequency is f = (N − 1)/(2·(z_N − z_1)), and F is the index k of the channel nearest to f. If N < 2, F = 0 and the pulse is malformed.

S4. Symbol. D = (P − P_prev) mod 8, a value from 0 to 7. The symbol is sym = 8·G(D) + G(F), where G(b) = b xor (b >> 1) is the 3-bit Gray code, so `sym[5:3]` = G(D) and `sym[2:0]` = G(F), bit 0 least significant. After every pulse, malformed or not, P_prev becomes P mod 8. P_prev is 0 at the start of the simulation and after every reset.

S5. Error flag. A pulse is malformed if |e| > `tol_pos`·δ, or P > 7, or |f/f_F − 1| > `tol_f`, or N < 2. `err` is 1 for a malformed pulse and 0 otherwise.

S6. Outputs. Outputs are logic voltages, 0 V or `vdd`. Every change of an output is a linear edge of duration `tr`, so its `vdd`/2 crossing lies `tr`/2 after the edge starts. For each pulse, at t_l + `t_lat`, `sym` and `err` take the values of S4 and S5 for that pulse and `sym_valid` starts rising; `sym_valid` starts falling `t_pw` later. `sym` and `err` then hold until the outputs of the next pulse. Each pulse gives exactly one `sym_valid` pulse, and nothing else gives one. Before the first pulse after the start of the simulation or after a reset, `sym`, `err` and `sym_valid` are 0.

S7. Reset. `rst` is high when V(rst) > `vth`. At its rising crossing, every output that is high starts falling at once, a pulse in progress and any pending output are dropped, and P_prev returns to 0. Exceedances that start while `rst` is high are ignored. The clock period may be measured during a reset.

S8. Operating domain.
- `clk` and `rst` switch between 0 V and a level VIN, where `vth` + 0.3 V ≤ VIN ≤ 1.8 V, with edges no longer than 10 ps. `clk` is a square wave with a constant period T_clk from 1.1 ns to 1.75 ns, and at least two rising crossings of `clk` precede every pulse.
- `rst` starts high at time 0. Later it changes only when no pulse is in progress and no output is pending: never between 50 ps before t_f of a pulse and `t_lat` + `t_pw` + `tr` + 50 ps after its t_l.
- Carriers lie between 4 GHz and 8 GHz. Each pulse lasts at most 1.2 ns from t_f to t_l, and the frequency window of S3 lies inside [t_f, t_l].
- The t_l of consecutive pulses are at least `t_lat` + `t_pw` + 50 ps apart. Every gap between exceedances differs from `t_gap` by at least 10 ps.
- A change of `v_det` by ±1 mV does not split, join, add or remove a pulse. A peak of |v| closer than 1 mV to `v_det` can still move t_f or t_l by a carrier half period; S9 accepts both outcomes.
- The values of S2 and S3 are not near a rounding boundary of P or F at the resolution of S9.

S9. Acceptance. For every instance, the `sym_valid` pulses are compared one to one, in order, with the pulses of S1, and their counts must be equal. Each rising `vdd`/2 crossing of `sym_valid` must lie within 3 ps of t_l + `t_lat` + `tr`/2. Each falling crossing must lie within 3 ps of t_l + `t_lat` + `t_pw` + `tr`/2. In the middle of each `sym_valid` pulse, `sym` must equal S4 and `err` must equal S5. `sym` and `err` must have no `vdd`/2 crossing while `sym_valid` is high, between `tr`/2 after its rising crossing and `tr`/2 before its falling crossing. In the middle of every reset interval, all outputs must be low. The checker measures t_f, t_l and the zero crossings itself, from the RF waveform saved in the same run or, for test sources, from their closed form. A peak of |v| within 1 mV of `v_det` makes t_f or t_l a range, and any value in that range is accepted. A zero crossing within 1 ps of a window edge may count or not. When |e| is within 2 ps of `tol_pos`·δ, or |f/f_F − 1| is within 0.002 of `tol_f`, either value of `err` is accepted. Final evaluation reruns the public case and adds others inside S8. They include the transmitter at another clock frequency with inverted pulses, two instances with different parameter values on the same signals, and resets at other times. They also include test sources whose pulses start off the grid, sit at positions 8 to 15, have carriers between channels or a few percent off, have other amplitudes, polarities and carrier phases, or run at other clock periods. Every check of every instance must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and port declarations, declare the ten parameters with the names and defaults above, and implement the measurement.
- Any Verilog-A implementation that meets the interface and the external behavior is acceptable. The internal state variables, the storage of zero crossings and the event organization are your choice.
- The decoder only observes its inputs; it must not drive `vp`, `vn`, `clk` or `rst`.
- The submitted model must be self-contained apart from the standard Verilog-A headers. It must not read or write files or start external processes.

Run `python3 /app/testbench/check.py run` to simulate the public case (the fixed seed transmitter in `/app/testbench/chain/` sending known symbols into the decoder) and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating. The [public testbench guide](/app/testbench/README.md) explains the case, the simulator, the measurement and the output files.

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
