# Assemble the IR-UWB seed transmitter from its module library

The seed transmitter sends 6-bit words at 4.032 Gb/s as one RF pulse per word: 3 bits select the pulse position (differential PPM) and 3 bits select one of eight carriers (FSK). Its nine modules already exist and work. Build the top level `uwb_tx_seed` that connects them, so that the transmitter first calibrates its master ring oscillator (RO) against a 48 MHz reference and then sends the incoming bit stream.

## Spec

The library is in `/app/modules/`. The [library guide](/app/modules/README.md) gives each module's ports in order, its parameters and its role. Use the module name and ports of the starter. All ports are voltages relative to ground; a logic signal is high above 0.5 V. Below, a time is the 0.5 V crossing of a signal, and the frequency of code c is f(c) = 600 MHz + 0.25 MHz × c.

S1. Parameters. Declare these parameters on `uwb_tx_seed`:

| Parameter | Meaning | Default | Allowed range |
| --- | --- | --- | --- |
| `n_pre` | integer: precharge lead, in RO taps | 2 | 1 to 15 |
| `n_win` | integer: calibration counting window, in reference periods | 192 | 1 to 192 |
| `code_init` | integer: RO code before calibration and after reset | 512 | 0 to 1023 |
| `g_pa` | real: output-stage gain, V/V | 1.0 | 0.25 to 2 |
| `vcm` | real: output common-mode voltage, V | 0.5 | 0.2 to 0.8 |
| `f0` to `f7` | real: carrier of RF branch k, Hz | 4.5e9 + k × 3e9/7 | 3.5e9 to 8e9, any two at least 5 % apart |

S2. Architecture. The transmitter uses one instance of each library module, except eight RF branches and two envelope lanes. Library parameters not named here keep their defaults.
- Data path: `bclk`, `din` → serial-to-symbol → `sym`, `sym_valid` → encoder → `pos`, `fcode`, `enc_valid` → pulse generator (PG). The `pol` pin is the PG's `pol` input.
- Clock path: `ref` and `cal_start` → calibration; its `code` drives the master RO. The calibration's `done` and `fail` drive the pins `done` and `fail`, and `done` is the PG enable `en`.
- RO tap `ph[0]` is the frame clock: it is the calibration's `roclk`, the `clk` of both envelope lanes, the first tap of the PG's `ph` bus (the PG takes all 16 taps in order), and the pin `clk672` copies it.
- PG lane a (`pre_a`, `rf_a`, `sel_a`) and lane b go to the scheduler's lanes a and b. The scheduler's `pwr[k]`, `pre[k]` and `rel[k]` drive RF branch k, whose `f_rf` is the parameter `f0` to `f7` with the same k, and branch k's output is `vro[k]` of the output stage. The scheduler's `gate_a` gates envelope lane a and is the output stage's `gate_a`; lane b likewise. The output stage takes `sel_a`, `pol_a`, `sel_b`, `pol_b` from the PG and drives the pins `outp` and `outn`.
- `n_pre` goes to both the PG and the scheduler, `n_win` and `code_init` to the calibration, `g_pa` and `vcm` to the output stage. `rst` goes to the serial-to-symbol, encoder, calibration, PG and scheduler. The pins `conflict` and `nsup` are the scheduler's outputs.

S3. Calibration and frame clock. `clk672` crosses within 2 ps of `ph[0]` and runs at f(code).
- The code is `code_init` from the start and from 10 ps after each rising `rst`.
- A rising `cal_start` while `rst` is low starts a 10-bit successive-approximation search from code 0, most significant bit first: each trial sets the next lower bit (512, 256, …, 1) on the kept code. For each trial, the 2nd rising `ref` crossing after the previous decision (or after `cal_start`) opens a counting window and the n_win-th rising `ref` crossing after that closes it; the count is the number of rising `clk672` crossings strictly inside the window. A count above 14 × n_win clears the trial bit, otherwise it is kept. After the last bit, the kept code is measured once more in the same way: the search ends with `done` if |count − 14 × n_win| ≤ 1, otherwise with `fail`.
- If the 65th rising `clk672` crossing after the last rising `ref` crossing arrives during the search, the search ends with `fail` there and the code returns to the last kept code.
- Every new trial code, the final code and the outcome take effect 10 ps after the crossing that decides them (for the first trial, 512, the rising `cal_start`): `done` or `fail` rises 11 ps after it, and the RO reads a new code 5 ps after it changes and keeps its phase. A rising `rst` clears `done` and `fail` 11 ps after it.

S4. Transmission. Count the rising `bclk` crossings after `rst` falls from 0. Word n is the bits at crossings 6n to 6n+5, first bit most significant. With D = gray2bin(word[5:3]), F = gray2bin(word[2:0]) and gray2bin(g2 g1 g0) = (g2, g2 xor g1, g2 xor g1 xor g0), the absolute position is P_n = (P_{n−1} + D_n) mod 8 with P_{−1} = 0. The PG receives word n, with the level of `pol` at that moment, 42 ps after `bclk` crossing 6n+8.
- Frame m starts at the m-th rising `clk672` crossing E_m. Tap j of frame m is at E_m + j × (E_{m+1} − E_m)/16; tap 16 + j is tap j of frame m+1.
- At E_m, if `done` is high and a word is pending, the PG schedules the latest pending word into frame m+1 and clears it; scheduled words alternate between lanes a and b, starting with a. A word replaced before it is scheduled is never sent. The word requests branch F at tap P − n_pre of frame m+1, and its pulse window runs from tap P to tap P + 9.
- A granted word (S5) gives one RF pulse, starting at t_s = tap P + 2 ps: outp − outn = g_pa × (−1)^pol × env(t − t_s) × vro_F(t), with env the envelope lane response for a window of 9/16 of the last frame period and vro_F branch F's oscillation (library guide). After a cold start the branch is released at t_s; a branch kept powered continues its phase.
- There is no RF (outp = outn) before the first pulse, outside each pulse window and the 300 ps after it, and from 5 ps after a rising `rst`. At all times outp + outn = 2 × vcm.

S5. Supplies and conflicts. At most two branches are powered. At a word's request (1 ps after the request tap):
- if branch F is powered, the word uses it and its phase continues;
- otherwise, if fewer than two branches are powered, branch F is powered and precharges, and is released at t_s (cold start);
- otherwise, if a powered branch is in an idle hold (below), it is switched off and branch F takes its place as a cold start;
- otherwise the word is dropped: no RF, and `conflict` is high for 200 ps from the request (crossings 1 ps after the request and 201 ps after it; a further drop inside the pulse extends it).
- When no lane is active on a branch any more (1 ps after the end tap), the branch has a 150 ps tail. After the tail it holds while a request for it is pending; otherwise it stays in an idle hold for max(0, 200 ps − n_pre × 93.006 ps) and then switches off. A rising `rst` switches every branch off and clears both lanes and the pending word.
- `nsup` is 1 V per powered branch; each change is a 2 ps step that starts at the event above.

S6. Operating domain. `ref` is a 48 MHz square wave with 2 ps edges and may stop during the search. `rst` is high from 0 to 10 ns and may rise again once later; `cal_start` rises once, 20 ns or more after `rst` falls. `pol` is constant. The bit clock is derived from `clk672`, so it stays frequency-locked to the calibrated RO (the CDC test condition): from a rising `clk672` crossing chosen by the case, each frame of length T carries six `bclk` pulses rising (j + 0.25) × T/6 after the frame edge, and `din` changes at the falling `bclk` edges. Data starts after the last trial code of the search has been applied, either before or after `done`. Cases are designed so that no `clk672` crossing lies within 3 ps of a counting-window boundary, and `done`, requests and supply deadlines are at least 3 ps from each other and from frame edges; the checker reports these margins as stimulus validity rows. A simulation lasts up to about 1.3 µs.

S7. Acceptance. In every case:
- the frequency of `clk672` before `cal_start`, and between consecutive code changes of the S3 replay (from 7 ps after a change), is within 0.1 MHz of f(code);
- the crossings of `done`, `fail`, `conflict` and of `nsup` through 0.5 V and 1.5 V match S3 and S5 one to one in order and direction, each within 5 ps; `nsup` never exceeds 2 V;
- the number of pulses in outp − outn equals the number of granted words. For every pulse not cut by `rst`: its measured start is within 10 ps of t_s; the decoded P, F and D equal the sent ones; the carrier frequency is within 2 % of f_F; the correlation with (−1)^pol times the expected waveform is at least 0.9; and the peak |outp − outn| is between 0.85 and 1.01 times g_pa;
- |outp − outn| ≤ 1 mV wherever S4 says there is no RF, and |outp + outn − 2 vcm| ≤ 1 µV.

The [public testbench guide](/app/testbench/README.md) describes the measurement. Final evaluation reruns the public cases and adds others inside S6: other parameter values (n_pre, n_win, code_init, g_pa, vcm and carriers in another order), other word sequences and polarity, other reference and data phases, a lost reference, and a reset during a pulse. Every check of every case must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and ports, declare the parameters of S1, and build the transmitter of S2 from the library.
- Include each library file you use with `` `include "modules/<file>.va" `` (a path relative to `/app/circuit.va`). The testbench includes only `/app/circuit.va` and resolves these paths against a fresh copy of `/app/modules`.
- The library is fixed: do not edit, copy or redefine its modules. Glue code and helper modules with other names are allowed in `/app/circuit.va`.
- Connect every bus port of a library module to a bus net with the same name as the port, for example the RO's `ph` port to `electrical [15:0] ph`. The current simulator resolves bus connections by port name, and the public check rejects other bus connections. Bits of these nets, such as `ph[0]` or `pwr[3]`, may connect to scalar ports.
- Instance names, internal scalar net names, helper modules and their order are your choice. The submitted model must not read or write files or start external processes.

Run `python3 /app/testbench/check.py run` to check the Deliverable rules, simulate the public cases and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating.

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
