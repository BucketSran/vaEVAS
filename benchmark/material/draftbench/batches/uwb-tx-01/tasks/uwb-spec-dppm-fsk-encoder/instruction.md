# Implement the DPPM + FSK symbol encoder of an IR-UWB transmitter

The transmitter sends one RF pulse per 6-bit symbol: 3 bits select the pulse position (differential PPM) and 3 bits select one of 8 carrier frequencies (FSK). Build the encoder that sits between the serial-to-symbol converter and the pulse generator. It takes each Gray-coded symbol, tracks the absolute pulse position, and publishes the position, frequency request and a valid strobe.

## Spec

Use the module name and port order of the starter. All ports are voltages relative to ground. Implement these real parameters:

| Parameter | Meaning | Default | Allowed range |
| --- | --- | --- | --- |
| `vdd` | output high level, V | 1.0 | 0.5 to 1.8 |
| `vth` | input threshold for `sym`, `sym_valid` and `rst`, V | 0.5 | 0.2 to 1.6 |
| `tr` | duration of every output edge, s | 2e-12 | 1e-12 to 1e-11 |
| `t_enc` | delay from a captured word to its data outputs, s | 1e-11 | 5e-12 to 1e-10 |
| `t_ev` | delay from a captured word to the rising edge of `enc_valid`, s | 3e-11 | 5e-12 to 2e-10 |
| `t_pw` | time from the rising to the falling edge of `enc_valid`, s | 4e-10 | 1e-10 to 1e-9 |

S1. Capture. An input is high when its voltage is greater than `vth`. A word is captured at each falling crossing of `sym_valid` through `vth` while `rst` is low; `sym[5:0]` is read at that instant. Words that arrive while `rst` is high are ignored.

S2. Mapping. `sym[5:3]` is the Gray code of the position increment D and `sym[2:0]` is the Gray code of the frequency index F. Decode each 3-bit group g2 g1 g0 to binary b2 = g2, b1 = g2 xor g1, b0 = g2 xor g1 xor g0. The absolute position is P[n] = (P[n-1] + D[n]) mod 8. P is 0 before the first word after the start of the simulation and after every reset, so the first word gives P = D. After each word, `pos[2:0]` = P, `inc[2:0]` = D, `fcode[2:0]` = F (bit 0 is the least significant bit), and `req[7:0]` is one-hot with only bit F high. `req` is only a frequency request; it does not enable anything by itself. Before the first word after the start or after a reset, every output is low, including all of `req`.

S3. Output edges. Outputs are logic voltages, 0 V or `vdd`. Every change of an output is a linear edge of duration `tr`, so its `vdd`/2 crossing lies `tr`/2 after the edge starts. For a captured word, the edges of `pos`, `inc`, `fcode` and `req` start `t_enc` after the capture. An output whose value does not change has no edge.

S4. Valid strobe. For every captured word, including a word equal to the previous one, `enc_valid` starts rising `t_ev` after the capture and starts falling `t_ev` + `t_pw` after the capture.

S5. Reset. `rst` acts asynchronously. At its rising crossing every output that is high starts falling at once, P returns to 0, and every output edge that an earlier word scheduled but that has not started yet is cancelled. After `rst` falls, the next captured word starts from P = 0.

S6. Operating domain. Inputs switch between 0 V and a level VIN, where `vth` + 0.3 V <= VIN <= 1.8 V, with linear edges no longer than 10 ps. `rst` may start high. Around each capture, `sym` is stable from at least 100 ps before to at least 100 ps after. `sym_valid` stays high for at least 100 ps before each falling edge. Consecutive captures are at least `t_ev` + `t_pw` + 50 ps apart. Crossings of `rst` and `sym_valid` are at least 2 ps apart.

S7. Acceptance. For every output, the observed `vdd`/2 crossings are compared one to one, in order, with the crossings that S1 to S5 give. The counts must be equal, the directions must match, and each crossing time must be within 2 ps of its expected time. In addition, while `enc_valid` is high after each word, `pos`, `inc`, `fcode` and `req` must hold the values of S2. Final evaluation reruns the public cases and adds others inside S6: other word sequences, including repeats and the minimum word spacing, nondefault parameter values, two instances with different parameters driven by the same inputs, and resets at different times relative to a capture. Every check of every instance must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and port declarations, declare the six parameters with the names and defaults above, and implement the behavior.
- Any Verilog-A implementation that meets the interface and the external behavior is acceptable. The internal state variables and the event organization are your choice.
- The submitted model must be self-contained apart from the standard Verilog-A headers. It must not read or write files or start external processes.

Run `python3 /app/testbench/check.py run` to simulate the public cases and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating. The [public testbench guide](/app/testbench/README.md) explains the cases, the simulator and the output files.

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
