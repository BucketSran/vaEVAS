# Sampling front end with aperture delay and hold droop

Build a voltage-domain sampling front end. Each rising clock crossing schedules one sample after an aperture delay. At that instant the model reads the input, clamps it to the supply rails of that instant, holds it on `vout`, decides it on `coarse`, and flags it on `valid`. While the clock is low, the held value droops toward `vss` in fixed update steps.

## Spec

Use the starter declaration of `sample_hold_droop`. Every port is electrical. The positional order is `vdd`, `vss`, `clk`, `vin`, `vout`, `valid`, `coarse`. `vdd` and `vss` are the local supply rails. `clk` and `vin` are inputs. `vout`, `valid`, and `coarse` are outputs.

Declare these overrideable parameters:

- `vth` = 0.45 V. Threshold of `clk` and of the coarse decision, measured from `V(vss)`. Legal range 0.2 V to 0.7 V.
- `trf` = 40 ps. Transition time of all three outputs. Legal range 10 ps to 200 ps, and at most `dt/4`.
- `tau` = 90 ns. Droop time constant. Legal range 10 ns to 1 us.
- `dt` = 0.5 ns. Interval between droop updates. Legal range 0.2 ns to 5 ns.
- `taperture` = 200 ps. Delay from a rising clock crossing to its sample instant. Legal range 20 ps to 2 ns.
- `valid_width` = 2 ns. Duration of the valid pulse. Legal range 0.5 ns to 10 ns.

Rails. `V(vss)` is constant during a run and lies between -0.2 V and +0.2 V. `V(vdd) - V(vss)` stays between 0.8 V and 1.5 V. `vdd` may change during a run, but only while `valid` and `coarse` are both low, and it stays constant within 0.5 ns of every sample instant. The model keeps a held value `h`, measured from `V(vss)`.

Sampling. A trigger is a rising crossing of `V(clk) - V(vss)` through `vth` after t = 0. A trigger at time `t_k` schedules exactly one sample at the sample instant `c_k = t_k + taperture`. At `c_k`:

1. The model reads `V(vin) - V(vss)` and `V(vdd) - V(vss)` at `c_k`.
2. `h` becomes the input value clamped to the range from 0 V to `V(vdd) - V(vss)`. So `vout`, at `V(vss) + h`, lies between the two rails of the sample instant.
3. `coarse` becomes high if `h > vth` and low otherwise. It keeps this value until the next sample instant; droop does not change it.
4. `valid` becomes high. It stays high until `c_k + valid_width` and is low otherwise.

The value of `vin` at the trigger is not used. Falling crossings and the level of `clk` at `c_k` neither start nor cancel a sample, so a sample also happens when `clk` is already low again at `c_k`. A level of `clk` above the threshold at t = 0 is not a trigger.

Droop. The droop update instants are `u_j = j*dt` for j = 1, 2, 3, and so on, counted from t = 0. The model generates these instants itself; triggers and samples never add, skip, or move one. At each update instant at which `clk` is low, that is `V(clk) - V(vss) < vth`, `h` becomes `h*exp(-dt/tau)`. At an update instant at which `clk` is high, `h` does not change. `h` changes only at sample instants and at these updates, and it keeps its value between them; it does not decay continuously. So `vout` droops toward `V(vss)` and never crosses it.

Initial state. At t = 0, `h` is 0 V, and `valid` and `coarse` are low, whatever the inputs are. Before the first sample instant, `vout` equals `V(vss)`.

Outputs. `vout` drives `V(vss) + h`. `valid` and `coarse` drive `V(vdd)` when high and `V(vss)` when low. After each instant that changes an output's expected value, that output reaches the new value within `trf` and then stays on it until its next change. This also holds when the next change comes before the output has reached the previous value. The waveform inside that `trf` interval is not specified.

Legal inputs:

- `clk` switches between `V(vss)` and `V(vss) + 0.9 V`, and each transition between these levels, the time during which `V(clk) - V(vss)` is more than 1 mV away from both levels, lasts at most 200 ps. It never rests at the threshold `V(vss) + vth`, and at t = 0 it is at least 50 mV away from it. When `clk` reaches the threshold it always crosses it; it never touches the threshold and returns to the same side.
- Successive threshold crossings of `clk` are at least 1 ns apart. Successive triggers are at least `max(taperture, valid_width) + 0.5 ns` apart, so no sample is pending at a trigger and every valid pulse ends before the next sample instant.
- Every threshold crossing of `clk` and every sample instant is at least 50 ps away from every droop update instant, so the clock level at an update is unambiguous and no sample coincides with an update.
- `vin` is continuous and stays between -0.5 V and +1.8 V. Within `trf/4` of every sample instant, `vin` moves by less than 0.25 mV.
- At every sample instant, `h` is at least 5 mV away from `vth`, so no coarse decision is decided by a tie.

The expected outputs are calculated with the rules above from the recorded inputs. Crossing times and input values are taken by linear interpolation between saved points. Every saved point is scored, except points less than `1.25*trf` after an instant at which that output's expected value changes by more than 0.1 mV. A change of 0.1 mV or less opens no such interval. At each scored point the error of every output is at most 2 mV. A scored waveform uses a time step no coarser than `trf/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `sample_hold_droop` on the module and positional ports in the starter, including the parameter defaults above. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The sampling, clamping, decision, valid, and droop rules define the observable outputs. They do not require a particular state variable, event operator, or event organization.
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
