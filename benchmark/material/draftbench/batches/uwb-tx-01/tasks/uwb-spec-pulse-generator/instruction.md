# Implement the two-lane pulse generator of an IR-UWB transmitter

The transmitter sends one RF pulse per symbol. The pulse position comes from a grid of 16 phases of a master ring oscillator, and the frequency index selects one of 8 RF oscillators. Build the pulse generator that sits between the symbol encoder and the RF branch scheduler. It latches each symbol descriptor, schedules it into the next frame, and drives two alternating command lanes. Each lane has a precharge command, an RF window, a frequency select and a polarity.

## Spec

Use the module name and port order of the starter. All ports are voltages relative to ground. Implement these parameters:

| Parameter | Meaning | Default | Allowed range |
| --- | --- | --- | --- |
| `n_width` | integer, length of the RF window in tap intervals | 9 | 1 to 9 |
| `n_pre` | integer, length of the precharge command in tap intervals | 2 | 0 to 15 |
| `t_ovr` | real, width of an `overrun` pulse, s | 2e-10 | 2e-11 to 1e-9 |
| `vdd` | real, output high level, V | 1.0 | 0.5 to 1.8 |
| `vth` | real, input threshold for every input, including `ph`, V | 0.5 | 0.2 to 0.7 |
| `tr` | real, duration of every output edge, s | 2e-12 | 1e-12 to 5e-12 |

S1. Levels and edges. An input is high when its voltage is greater than `vth`. Outputs are logic voltages, 0 V or `vdd`, and all of them are low at the start of the simulation. Every change of an output is a linear edge of duration `tr`, so its `vdd`/2 crossing lies `tr`/2 after the edge starts. An output whose value does not change has no edge.

S2. Tap edges. `ph[15:0]` are the 16 phase taps of the master ring oscillator. A tap edge is a rising crossing of any `ph[j]` through `vth`. A frame edge is a rising crossing of `ph[0]`; it is also a tap edge. Within S8, `ph[j]` rises j·δ after each frame edge, where δ = T/16 and T is the oscillator period. Count the tap edges after a frame edge E from 1: tap edge m comes m·δ after E, and tap edge 16 is the next frame edge. All pulse timing below is counted in tap edges, not in absolute time.

S3. Latch and overrun. At each rising crossing of `enc_valid` through `vth` while `rst` is low, the descriptor is read: P = `pos[2:0]`, F = `fcode[2:0]` (bit 0 is the least significant bit) and the polarity `pol`. The descriptor becomes the pending descriptor. If a pending descriptor already exists (latched but not yet scheduled), the new one replaces it and `overrun` gives one pulse. The pulse starts rising at that `enc_valid` crossing and starts falling `t_ovr` later. Rising crossings of `enc_valid` while `rst` is high are ignored.

S4. Scheduling and lanes. A pending descriptor is scheduled at a frame edge E if `rst` is low and `en` is high at E. It then stops being pending and goes to a lane. The first descriptor scheduled after the start of the simulation or after a reset goes to lane a, the next one to lane b, and so on. A descriptor that is overwritten before it is scheduled takes no lane. Without a pending descriptor, a frame edge schedules nothing and no window follows. `en` has an effect only at frame edges. If `en` falls, windows that are already scheduled continue to their end. While `en` is low, the pending descriptor is kept; later latches overwrite it as S3 states. The pending descriptor is scheduled at the first frame edge with `en` high.

S5. Windows. Take a descriptor (P, F, pol) that is scheduled at frame edge E on lane x (x = a or b), and let s = 16 + P. Count the tap edges after E as in S2:
- `rf_x` starts rising at tap edge s and starts falling at tap edge s + `n_width`.
- If `n_pre` >= 1, `pre_x` starts rising at tap edge s − `n_pre` and starts falling at tap edge s.
- If `n_pre` = 0, `pre_x` stays low.

An edge "at tap edge m" starts at the instant that tap crosses `vth`. The RF window therefore starts at tap P of the frame after E and can run into the following frame. The precharge can start in the frame that begins at E. The windows of lanes a and b may overlap.

S6. Select and polarity. At the frame edge E where a descriptor is scheduled on lane x, `sel_x[2:0]` starts changing to F and `pol_x` to pol. The edges start at E. Both outputs then hold until lane x is scheduled again. The end of a window and a reset do not change them.

S7. Reset. `rst` acts asynchronously. Its rising crossing does all of the following at once:
- discards the pending descriptor;
- clears both lanes: a high `pre_x` or `rf_x` starts falling, and every window edge that has not started yet is cancelled;
- makes the next scheduled descriptor go to lane a.

While `rst` is high, nothing is latched or scheduled. `rst` does not change `sel_x`, `pol_x` or an `overrun` pulse in progress. `rst` may start high.

S8. Operating domain.
- The taps come from the fixed oscillator model `/app/testbench/master_ro16.va` with a constant code from 0 to 1023, so T is between 1.169 ns and 1.667 ns. The model can have any initial phase, and its taps switch between 0 V and 1.0 V with 2 ps edges.
- The other inputs switch between 0 V and a level VIN, where `vth` + 0.3 V <= VIN <= 1.8 V. Their edges are linear and no longer than 10 ps.
- `pos`, `fcode` and `pol` are stable from at least 20 ps before to at least 20 ps after each rising crossing of `enc_valid`. At other times they can change.
- `enc_valid` stays high for at least 100 ps and low for at least 100 ps. Its consecutive rising crossings are at least `t_ovr` + 100 ps apart.
- Rising crossings of `enc_valid` and all crossings of `en` are at least 30 ps away from every frame edge.
- Crossings of `rst` are at least 30 ps away from every tap edge and from every rising crossing of `enc_valid`. `rst` stays high for at least 100 ps.

S9. Acceptance. For every output, the observed `vdd`/2 crossings are compared one to one, in order, with the crossings that S3 to S7 give. The expected crossings use the tap edges observed through `vth` in the same run. The counts must be equal, the directions must match, and each crossing time must be within 2 ps of its expected time. In addition, at every window start `rf_x` must be high and `sel_x` and `pol_x` must equal F and pol of the descriptor.

Final evaluation reruns the public cases. It adds other cases inside S8:
- nondefault values of every parameter, including `n_pre` = 0 and 15 and shorter windows;
- two instances with different parameters on the same taps and inputs;
- another oscillator code and initial phase;
- random descriptor sequences with empty frames, overruns and `en` low over several frame edges;
- descriptor inputs that change soon after the latch;
- resets in each of these states: during a precharge, during an RF window, with only a pending descriptor, across a frame edge and during an `overrun` pulse.

Every check of every instance must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and port declarations, declare the six parameters with the names, types and defaults above, and implement the behavior.
- Any Verilog-A implementation that meets the interface and the external behavior is acceptable. The internal state variables and the event organization are your choice.
- The submitted model must be self-contained apart from the standard Verilog-A headers. It must not read or write files or start external processes. The oscillator model in `/app/testbench/` is part of the testbench, not of the deliverable.

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
