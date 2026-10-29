# Peak-hold envelope with two slew-limited outputs

Build a clocked envelope that holds peaks or releases to the input, and drive two outputs that follow two different targets derived from it with limited rising and falling slopes. The envelope decides where each output goes. The slope limits decide how it gets there.

## Spec

Use the starter declaration of `slew_envelope_tracker`. Every port is electrical. The positional order is `vin`, `clk`, `mode`, `rst`, `out`, `metric`. `vin`, `clk`, `mode`, and `rst` are inputs. `out` and `metric` are outputs.

Declare these overrideable parameters:

- `vth` = 0.45 V. Threshold for `clk`, `mode`, and `rst`. A level above `vth` is high.
- `rise_rate` = 8e8 V/s. Rising slope of both outputs. Legal range 1e8 V/s to 4e9 V/s.
- `fall_rate` = 3e8 V/s. Magnitude of the falling slope of both outputs. Legal range 1e8 V/s to 4e9 V/s.

Envelope. The model keeps an envelope value `env`. It is 0 V at t = 0 and changes only at the following events:

- A rising crossing of `rst` through `vth` sets `env` to 0 V at once.
- A sample event is a rising crossing of `clk` through `vth` after t = 0. `V(vin)`, `mode`, and `rst` are read at the crossing instant. If `rst` is high, `env` stays 0 V. Otherwise, if `mode` is high, `env` becomes `V(vin)` (release), and if `mode` is low, `env` becomes the larger of `env` and `V(vin)` (peak hold). In both cases the result is then limited to the range 0 V to 0.8 V.

Nothing else changes `env`. A falling `rst` crossing and changes of `vin` or `mode` between sample events have no effect until the next sample event.

Targets. The target of `out` is `env`. The target of `metric` is `env/0.8`, so it lies between 0 V and 1 V.

Outputs. Each output follows its own target along a continuous trajectory that starts at 0 V at t = 0. While an output is below its target, it rises with slope `rise_rate`. While it is above its target, it falls with slope `fall_rate`. When it reaches its target, it stays there until the target changes. An output never jumps. When its target changes during a ramp, the output turns toward the new target from its current value. The two outputs move independently, each from its own current value. When both outputs rest on their targets and `env` changes, the ramp of `metric` lasts 1.25 times as long as the ramp of `out`, unless a later event interrupts them. In general an output reaches its target after its remaining distance divided by its slope, unless the target changes first. A reset therefore moves both outputs down to 0 V at `fall_rate`; it does not force them to 0 V.

`vin` is continuous and stays between -0.5 V and 1.2 V. It may change at any time. `clk`, `mode`, and `rst` switch between 0 V and 0.9 V with transitions no longer than 200 ps, and `vth` lies strictly between those levels. Controls never rest at `vth`. A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. At t = 0 each control is at least 50 mV away from `vth`. `clk` starts low; `mode` and `rst` may start high or low. Successive rising `clk` crossings are at least 5 ns apart, and `clk` stays high and low for at least 2 ns each time. Every `mode` crossing and every `rst` crossing is at least 1 ns away from every rising `clk` crossing.

The expected trajectories are calculated from the recorded `vin`, `clk`, `mode`, and `rst` with the rules above. Each reset or sample event may take effect up to 50 ps before or after its crossing instant, independently of the other events. This allows for the time step at which a simulator starts a ramp. Every saved point of `out` and `metric` is scored. A point passes when it lies within 2 mV of the values that the trajectories allowed by this timing tolerance take at its time. A scored waveform uses a time step no coarser than 50 ps. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `slew_envelope_tracker` on the module and positional ports in the starter. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. It does not require a particular analog operator, state variable, or event organization.
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
