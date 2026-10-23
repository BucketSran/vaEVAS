# Repair the warm restart of the RF branches in an IR-UWB transmit chain

The supplied Verilog-A project is the transmit chain of an 8DPPM + 8FSK impulse-radio UWB transmitter: a serial-to-symbol converter, a symbol encoder, a 16-phase master ring oscillator, a pulse generator, a scheduler for eight RF branch oscillators, two envelope lanes and the combiner and output stage. A bench engineer reports this symptom:

> When two consecutive symbols use the same carrier and the second pulse starts soon after the first one, the carrier should run on into the second pulse. Instead, the precharge line of that branch rises again a few taps before the second pulse, its release line drops at the same moment, and the second pulse starts like a cold start: the carrier phase restarts and the amplitude ramps up again. When the second pulse follows very closely, the end of the first pulse is cut off as well. Pulses whose neighbors use other carriers look normal.

Find the cause and repair the project so that the whole chain meets the Spec below.

## Spec

All signals are voltages relative to ground. Logic signals are 0 V or 1 V, count as high above 0.5 V and change with 2 ps linear edges. Constants: frame period Ts = 1/(672 MHz) = 1488.095 ps, tap spacing δ = Ts/16 = 93.006 ps, bit period Tb = Ts/6 = 248.016 ps, carriers f_k = 4.5 GHz + k × 3/7 GHz for branch k = 0 to 7.

C1. Bench. The fixed bench instantiates each module of `/app/modules` once and connects its ports by position, as listed in the [public testbench guide](/app/testbench/README.md). The master RO receives the fixed code 288 (672 MHz). The pulse-generator enable `en` is tied high. The frequency-calibration module is compiled but not instantiated. `bclk` is an ideal clock with period Tb: its rising edge j (j = 0, 1, 2, ...) starts at t_d + j × Tb. `rst` is high from t = 0 and falls midway between bit-clock edges 4 and 5. `din` carries the case's 6-bit words, most significant bit first, one bit per bit period, and changes midway between bit-clock edges. After the last word it keeps its last level, so the chain goes on forming words (all ones or all zeros) until the run ends. `pol` carries one polarity bit per word and is stable around the instant the pulse generator latches the word. A case may set the parameters below. Every other module parameter keeps its default. The bench passes `t_tail` and `t_hold` only when a case uses values other than the defaults.

| Parameter | Where | Meaning | Default | Range in the cases |
| --- | --- | --- | --- | --- |
| `n_pre` | pulse generator and scheduler, same value | precharge lead, taps | 2 | 1 to 15 |
| `t_tail` | scheduler | TAIL duration, s | 150e-12 | 50e-12 to 300e-12 |
| `t_hold` | scheduler | hold limit, s | 200e-12 | 0 to 3e-9 |
| `dpc_db0` to `dpc_db7` | output stage | gain of branch k, dB | 0 | -6 to 6 |
| t_d | bench clock | delay of bit-clock edge 0, s | 10e-12 | 5e-12 to 1.4e-9, see C8 |

Fixed values used below: serial-to-symbol output delay t_cq = 10 ps, encoder strobe delay t_ev = 30 ps, pulse width 9 taps, conflict pulse width t_conf = 200 ps.

C2. Words. The first bit captured after the reset release (at bit-clock edge 5) is bit 5 of word 0. Word n is made of the bits captured at edges 5 + 6n to 10 + 6n. For word n the encoder computes D = Gray-to-binary of bits 5:3 and F = Gray-to-binary of bits 2:0 (b2 = g2, b1 = g2 xor g1, b0 = g2 xor g1 xor g0). It also computes the absolute position P[n] = (P[n-1] + D) mod 8, with P = 0 before word 0. F selects the carrier, that is, branch F. The serial-to-symbol converter lowers `sym_valid` of word n t_cq after it captures the third bit of word n + 1. The encoder takes the word at that falling crossing and raises `enc_valid` t_ev later. The pulse generator latches the word (P, F and the `pol` bit) at the rising crossing of `enc_valid`, at t_L(n) = t_b(13 + 6n) + t_cq + t_ev + 2 ps, where t_b(j) = t_d + j × Tb + 1 ps is the crossing of bit-clock edge j.

C3. Frames and pulses. `clk672` is tap 0 of the master RO. It is high from t = 0 to Ts/2, rises at m × Ts and falls at m × Ts + Ts/2 for m = 1, 2, .... Rising edge m starts frame m. Tap j of frame m rises at m × Ts + j × δ, and tap 16 + j of frame m is tap j of frame m + 1. At each rising crossing of `clk672`, the pulse generator takes the word latched since the previous crossing, if there is one, and schedules it into the next frame. For a word scheduled at the start of frame m with position P, the pulse window runs from tap P to tap P + 9 of frame m + 1, and the precharge request runs from tap P - n_pre to tap P (it can begin in frame m). Scheduled words alternate between lane a and lane b, starting with lane a after reset. Lane x raises `pre_x` for the request and `rf_x` for the window, and sets `sel_x` = F and `pol_x` = the polarity bit when the word is scheduled.

C4. Scheduler. Branch k is in one of the states OFF, PRECHARGE, ACTIVE, TAIL or HOLD. It is powered in every state except OFF. `pwr_k` is high while k is powered, `pre_k` while it is in PRECHARGE, and `rel_k` while it is in ACTIVE, TAIL or HOLD. `nsup` is 1 V per powered branch. At most two branches are powered: the scheduler has two supply slots, slot 0 and slot 1, and a branch is powered only while it holds a slot. After reset all branches are OFF and both slots are free. A rising `pre_x` is a request for branch k = `sel_x`. The first rule that applies decides it:
- (a) Warm grant. If k is powered, the request is granted on k and k does not change state. There is no new precharge and no new release, and the branch keeps oscillating (or keeps precharging).
- (b) Cold grant. If a slot is free, k takes it (slot 0 before slot 1) and enters PRECHARGE.
- (c) Preemption. If a slot holds a branch in HOLD with no granted pulse waiting (an idle HOLD; slot 0 is checked first), that branch turns OFF, and k takes the slot and enters PRECHARGE at the same instant.
- (d) Drop. Otherwise the request is not granted. No branch changes state, the symbol gets no gate, and `conflict` is high for t_conf from the request (a later drop restarts the t_conf interval).

The rest of a pulse's life follows these rules:
- Start. At the rising `rf_x` of a granted pulse, its branch enters ACTIVE and `gate_x` rises. A branch in PRECHARGE is released at that instant. A branch in ACTIVE, TAIL or HOLD continues without a new release.
- End. At the falling `rf_x` of a granted pulse, `gate_x` falls. If no other lane's pulse is active on the branch, the branch enters TAIL. If the other lane starts a pulse on the same branch at the same instant, the branch stays ACTIVE.
- TAIL end. t_tail after it entered TAIL, the branch enters HOLD. If a granted pulse is waiting for the branch, the branch stays in HOLD until that pulse starts. Otherwise it is an idle HOLD: the branch turns OFF t_wait = max(0, t_hold - n_pre × δ) after the TAIL end (at once if t_wait = 0), unless a request for it arrives first. That request is a warm grant under (a), and the branch then stays in HOLD until its pulse starts.

As a consequence, unless a preemption intervenes, the second of two pulses on the same branch continues the oscillation if it starts at most max(t_hold, n_pre × δ) after the TAIL end of the first. Otherwise the branch has turned off and the second pulse starts cold. The scheduler's `st` outputs are not checked.

C5. RF branches. Branch k outputs `vro_k` = 0 while it is OFF or in PRECHARGE. At the rising crossing t_r of `rel_k` (with `pwr_k` high) it starts oscillating: vro_k = (1 - e^(-u/τ)) × cos(2π f_k (u + 0.01 τ (1 - e^(-u/τ)))), with u = t - t_r and τ = 200 ps/ln 100 = 43.43 ps. The oscillation continues as long as `rel_k` stays high, and its phase is never reset during that time. It stops at the falling crossing of `rel_k` or `pwr_k`.

C6. Envelopes and output. At the rising crossing t_g of `gate_x`, lane x starts the envelope env_x(u) with u = t - t_g. The envelope is the response of a first-order lag with τe = 50 ps/ln 100 = 10.86 ps to the raised cosine (1 - cos(2πu/Tw))/2 of length Tw. Tw is 9/16 of the interval between the last two rising crossings of `clk672` before t_g. In closed form, env(u) = (1 - e^(-v/τe))/2 - κ (cos(ωv) + ωτe sin(ωv) - e^(-v/τe))/2, with v = min(u, Tw), ω = 2π/Tw and κ = 1/(1 + ω²τe²). For u > Tw this value is multiplied by e^(-(u - Tw)/τe). After `gate_x` falls at t_e, env_x decays from its value at t_e as e^(-(t - t_e)/τe). The output is outp - outn = Σ over x = a, b of (-1)^q_x × g_k × env_x × vro_k. Here k = `sel_x` and q_x = `pol_x` are latched at the rising crossing of `gate_x`, and g_k = 10^(dpc_dbk/20). The common mode (outp + outn)/2 is 0.5 V.

C7. Timing references. Each block acts at the 0.5 V crossing of an input edge and starts its own output edges at that instant. The exceptions are t_cq and t_ev (C2) and the timed intervals of C4. Every logic edge crosses 0.5 V 1 ps after it starts. So, for a tap edge that starts at time t, the pulse generator's `pre_x` or `rf_x` edge crosses at t + 2 ps, the scheduler acts at that instant, and a scheduler output that changes in response crosses at t + 3 ps. TAIL lasts t_tail from the falling `rf_x` crossing. The idle part of HOLD lasts t_wait from the TAIL end. A `conflict` pulse lasts t_conf from the rising `pre_x` crossing. An output that changes at the end of one of these intervals crosses 1 ps after the interval ends. `nsup` steps by 1 V per branch with the same 2 ps edges.

C8. Operating domain. The case parameters stay within the table in C1, and the words and polarity bits are arbitrary. The bench chooses t_d so that every t_L(n) is at least 50 ps away from every rising crossing of `clk672`. The cases are chosen so that no timed interval of C4 ends within 5 ps of a `pre_x` or `rf_x` crossing, and no observed signal changes twice within 5 ps. Each run lasts at most 135 ns.

C9. Acceptance. Edge monitors on the actual nodes record the 0.5 V crossings of `clk672`, of `pwr_k`, `pre_k` and `rel_k` for k = 0 to 7, of `gate_a`, `gate_b` and `conflict`, and the crossings of `nsup` through 0.5 V, 1.5 V and 2.5 V. For each of these, the observed crossings before the last 5 ps of the run are compared one to one, in order, with the crossings that C2 to C7 give. The counts must be equal, the directions must match, and each crossing time must be within 2 ps of its expected time. In addition:
- At most two `pwr_k` are high at any time.
- outp - outn is within 2 mV of the C5 and C6 reconstruction at every saved simulator point. The reconstruction takes t_r, t_g and t_e from the observed `rel_k` and `gate_x` crossings and Tw from the observed `clk672` period.
- In the middle half of each granted pulse, the zero crossings of outp - outn give the carrier of its branch within 2 %. A pulse whose middle half extends past the end of the run is skipped.
- Outside the granted pulses and their 300 ps tails, |outp - outn| < 1 µV.

Final evaluation reruns the public cases and adds others inside C8. These use other word sequences, including random data, n_pre from 1 to 15, longer t_hold, another t_tail, other DPC gains and polarity patterns, and another bit-clock delay. Some of them also check behavior that the reported symptom does not involve, such as drops, preemption and the hold timeout. Every check of every case must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- The project to repair is the directory `/app/modules`. It contains nine files: `serial_to_symbol6.va`, `dppm_fsk_encoder8.va`, `master_ro16.va`, `ro_frequency_cal.va`, `pulse_generator.va`, `ro_scheduler8.va`, `rf_ro_branch.va`, `envelope_lane.va` and `tx_output.va`. You may edit any of them.
- Keep every module interface unchanged: the file names, module names, port lists in their order, and parameter names with their default values. The bench includes these files, instantiates each module by name and connects it by port order (C1).
- You may add `.va` files with helper modules to `/app/modules`, because the bench compiles every `.va` file in that directory. Do not delete or rename the nine supplied files, and do not leave scratch `.va` files there.
- Repair the fault so that the whole chain meets C2 to C9. A change that removes the symptom but changes other specified behavior fails.
- The models must be self-contained apart from the standard Verilog-A headers. They must not read or write files or start external processes.
- The bench in `/app/testbench` is fixed.

Run `python3 /app/testbench/check.py run` to simulate the public cases and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating. The [public testbench guide](/app/testbench/README.md) explains the bench wiring, the cases, the simulator and the output files.

This is an implementation task, not a repository-audit task.
Work in /app and modify only the declared deliverable; do not edit public development benches, model libraries, or external fixtures.
Make one bounded inspection pass over this instruction, the declared deliverable, supplied starter material, and public development benches.
The supplied directory named in the Deliverable section is already a runnable candidate; keep it runnable as you work.
If your working time expires, the evaluator copies that directory exactly as it exists at that moment and runs the verifier on it.
If the directory is missing or contains no Verilog-A file, the result is zero reward.
Files outside that directory are not submitted.

If a concrete model, tool, or execution problem appears, investigate it as needed before continuing.
Iterate by editing the declared deliverable and using public development benches to diagnose observed behavior.
Do not repeatedly enumerate files, reread unchanged references, or retry unchanged discovery commands instead of editing and simulating.
