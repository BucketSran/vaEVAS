# Implement the frequency calibration of the master ring oscillator of an IR-UWB transmitter

The transmitter derives its symbol clock and pulse-position grid from a 16-phase master ring oscillator (RO) that must run at 14 times a 48 MHz crystal reference. A 10-bit code sets the RO frequency. Build the calibration block that finds this code by successive approximation, counting RO edges against the reference, and that reports success, failure and a lost reference.

## Spec

Use the module name and port order of the starter. All ports are voltages relative to ground. `ref` is the reference clock, `roclk` is the RO clock, `cal_start` requests a calibration and `rst` is the reset. `code[9:0]` drives the RO tuning code (bit 0 is the least significant bit). `done`, `fail` and `busy` are status flags. Declare these parameters with the names, types and defaults shown:

| Parameter | Type | Meaning | Default | Allowed range |
| --- | --- | --- | --- | --- |
| `ratio` | integer | target number of RO periods per reference period | 14 | 1 to 64 |
| `n_win` | integer | length of each counting window, reference periods | 192 | 1 to 1024 |
| `n_settle` | integer | wait before each counting window, reference periods | 2 | 1 to 16 |
| `tol` | integer | largest accepted difference between the final count and the target | 1 | 0 to 16 |
| `n_lost` | integer | `roclk` rising edges without a reference edge that are still accepted | 64 | 16 to 1023 |
| `code_init` | integer | code shown after start-up and after a reset | 512 | 0 to 1023 |
| `vdd` | real | output high level, V | 1.0 | 0.5 to 1.8 |
| `vth` | real | input threshold for all four inputs, V | 0.5 | 0.2 to 1.6 |
| `tr` | real | duration of every output edge, s | 2e-12 | 1e-12 to 1e-11 |
| `t_cq` | real | delay from a deciding event to the start of the output edges, s | 1e-11 | 5e-12 to 5e-10 |

Context: in the testbench, each instance drives a fixed public RO model whose frequency is f = f0 + code × fstep, by default 600 MHz + code × 0.25 MHz. With the default model, code 288 gives 672 MHz, and with `n_win` = 192 one code step changes the count by one. Some tests use other RO frequencies. The block must find the code by counting edges, not from this law.

S1. Events. An input is high when its voltage is greater than `vth`. The events are the rising crossings of `cal_start` (a start), of `rst` (a reset), of `ref` (reference edges) and of `roclk` (RO edges), each at its crossing of `vth`.

S2. Start and windows. A start while `rst` is low begins a calibration: `busy` = 1, `done` = `fail` = 0, the kept code K = 0 and the trial code 512 is shown. A calibration makes 11 measurements: one trial for each bit from bit 9 down to bit 0, then one verification. The window of the first measurement opens at the `n_settle`-th reference edge after the start. Each later window opens at the `n_settle`-th reference edge after the edge that closed the previous window. A window closes at the `n_win`-th reference edge after the edge that opened it. The count of a window is the number of RO edges strictly between its opening and closing edges.

S3. Successive approximation. The trial for bit b measures the code K + 2^b. At the edge that closes its window, the bit is kept (K becomes K + 2^b) if count <= target, where target = `n_win` × `ratio`, and cleared otherwise. The next trial code K + 2^(b−1) is then shown. After bit 0, the code K is shown and measured once more for the verification.

S4. Verification. At the edge that closes the verification window, `done` = 1 if |count − target| <= `tol`, otherwise `fail` = 1. `busy` = 0 and `code` keeps showing K.

S5. Hold and restart. After `done` or `fail` is set, by S4 or S6, all outputs hold until the next start or reset. A start while `rst` is low always begins a new calibration as in S2, also during a calibration, which is then abandoned.

S6. Lost reference. During a calibration, count the RO edges since the start or since the most recent reference edge, whichever is later. The RO edge that makes this count `n_lost` + 1 ends the calibration: `fail` = 1, `busy` = 0, and `code` shows K, the bits kept so far, not the trial code.

S7. Start-up and reset. From the start of the simulation until the first start, `code` = `code_init` and `done` = `fail` = `busy` = 0. A reset acts at once: it abandons any calibration and sets `code` = `code_init`, `done` = `fail` = `busy` = 0. Starts are ignored while `rst` is high. `rst` may be high at t = 0.

S8. Output edges. Outputs are logic voltages, 0 V or `vdd`. Each output change caused by a start, a closing reference edge, the RO edge of S6 or a reset is a linear edge of duration `tr` that starts `t_cq` after the crossing of that event, so its `vdd`/2 crossing lies `t_cq` + `tr`/2 after the event. An output whose value does not change has no edge. Window-opening edges change no output.

S9. Operating domain. Inputs switch between 0 V and a level VIN, where `vth` + 0.3 V <= VIN <= 1.8 V, with linear edges no longer than 10 ps. `ref` and `roclk` are clocks with high and low phases of at least 0.4 ns. `ref` may stop and then stays low. `cal_start` pulses are at least 1 ns wide. Every rising crossing of `cal_start` and `rst` is at least 1 ns from every rising crossing of `ref`. Any two events that change outputs are at least 1 ns apart. No RO edge is within 3 ps of a reference edge that opens or closes a window, of a start, or of the last reference edge before an S6 fail. The tests are built so that the correct code sequence meets these conditions.

S10. Acceptance. For every output, the observed `vdd`/2 crossings are compared one to one, in order, with the crossings that S2 to S8 give for the stimulus and the observed `ref` and `roclk` crossings. The counts must be equal, the directions must match, and each crossing time must be within 20 ps of its expected time. In addition, 5 ns before the first start or rising crossing of `rst`, and after each calibration that ends by S4 or S6, `code`, `done`, `fail` and `busy` must hold the values of S2 to S7. A test in which the event order or spacing conditions of S9 do not hold fails; with the correct code sequence every test meets them. Final evaluation reruns the public cases and adds others inside S9: the default parameters, RO frequency ranges that the code cannot bring to the target from above and from below, a second calibration after `done`, resets and starts at different points of a search, a start during a search, a reference that stops before a start, nondefault parameter values, and two instances with different parameters driven by the same inputs. Every check of every instance must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and port declarations, declare the ten parameters with the names, types and defaults above, and implement the behavior.
- Any Verilog-A implementation that meets the interface and the external behavior is acceptable. The internal state variables and the event organization are your choice.
- The submitted model must be self-contained apart from the standard Verilog-A headers. It must not read or write files or start external processes.

Run `python3 /app/testbench/check.py run` to simulate the public cases and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating. The [public testbench guide](/app/testbench/README.md) explains the cases, the fixed RO and reference models, the simulator and the output files.

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
