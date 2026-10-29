# Two-stage track-and-hold with a clock-phase hand-off

Build a voltage-domain Verilog-A model of a two-stage (master-slave) track-and-hold. An input stage acquires the analog input while the clock is low and holds while it is high. An output stage acquires the value held by the input stage while the clock is high and holds while it is low. Both stages acquire in finite steps on the model's own update grid, so a short clock phase can leave either stage short of its target.

## Spec

Use the starter declaration of `dual_track_sample_hold`. Every port is electrical. The positional order is `vdd`, `vss`, `clk`, `vin`, `vout`, `phase`. `vdd` and `vss` are the local supply rails, `clk` is the voltage-coded phase clock, and `vin` is the analog input. The model drives `vout`, the output-stage value, and `phase`, a logic monitor that shows when the output stage tracks.

Declare these overrideable real parameters.

- `vth` = 0.45 V. Clock threshold, measured from `vss`. Legal range 0.1 V to 0.8 V.
- `tick` = 0.5 ns. Update interval. Legal range 0.25 ns to 5 ns.
- `alpha_in` = 0.45. Input-stage acquisition fraction per update. Legal values are greater than 0 and at most 1.
- `alpha_out` = 0.55. Output-stage acquisition fraction per update. Legal values are greater than 0 and at most 1.
- `tedge` = 50 ps. Output transition time. Legal range 10 ps to `tick/4`.
- `vinit` = 0 V. Initial value of both stages, measured from `vss`. Legal range 0 V to the rail span at t = 0.

Reference and state. `vss` is the local ground. The clock level, the input `u = V(vin) - V(vss)`, the rail span `s = V(vdd) - V(vss)`, both stored values, and `vout` are measured from `vss`. The model keeps two stored values: `a` for the input stage and `b` for the output stage. At t = 0 both equal `vinit`. The clock is high when `V(clk) - V(vss)` is above `vth` and low otherwise.

Updates. The stored values change only at the ticks `t_k = k*tick`, for k = 0, 1, 2, and so on, counted from t = 0; the first tick is at t = 0. The model generates the ticks itself. Clock crossings do not add, move, or skip a tick, and they change no stored value. At each tick the model works in this order:

1. It reads `s`, `u`, and the clock level at `t_k`.
2. If the clock is low, `a` becomes `a + alpha_in*(u - a)` and `b` keeps its value. If the clock is high, `b` becomes `b + alpha_out*(a - b)`, using `a` as it was before this tick, and `a` keeps its value.
3. Each of `a` and `b` that is above `s` is set to `s`, and each that is below 0 V is set to 0 V. This limit applies to both stored values at every tick, including the one that kept its value in step 2.

So the input stage keeps the value of its last low-clock tick through the following high phase, and at each high-clock tick the output stage closes the fraction `alpha_out` of its distance to that held value. A clock phase that contains no tick changes neither stored value.

Outputs. `V(vout) - V(vss)` shows `b`. After each tick that changes `b`, `vout` reaches the new value within `tedge` and then stays on it until the next change. `phase` shows `vdd` while the output stage tracks and `vss` while it holds. It changes at each crossing of `V(clk) - V(vss)` through `vth`: to `vdd` at a rising crossing and to `vss` at a falling crossing, reaching the new rail within `tedge`. At t = 0 it shows the initial clock level. Between crossings it follows its rail when the rails move. The waveform inside a `tedge` interval is not specified.

Legal inputs:

- The rails are continuous. `V(vss)` stays between -0.5 V and 0.5 V, and `s` stays between 0.4 V and 1.5 V. Over any interval of length `tick`, `V(vss)` and `s` each change by at most 1 mV.
- `vin` is continuous, and `u` stays between -0.5 V and `s + 0.5 V`. It may lie outside the range from 0 V to `s`.
- Measured from `vss`, `clk` is at least 50 mV away from `vth` at t = 0. It never rests at `vth`. A `clk` that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Between two successive crossings of `vth`, `V(clk) - V(vss)` moves at least 50 mV away from `vth`. Successive crossings of `vth` are at least `4*tedge` apart, and every crossing is at least 50 ps away from every tick, so no crossing coincides with a tick.
- `vinit` lies between 0 V and the value of `s` at t = 0.

The expected outputs are calculated with the rules above from the recorded `vdd`, `vss`, `clk`, and `vin`. Crossing times and input values are taken by linear interpolation between saved points. Every saved point is scored, except points of `vout` less than `1.25*tedge` after a tick that changes `b` by more than 0.1 mV, and points of `phase` less than `1.25*tedge` after a crossing of `vth`. A change of `b` of 0.1 mV or less opens no such interval, and the point at t = 0 is always scored. At each scored point, `V(vout) - V(vss)` is within 2 mV of `b`, and `phase` is within 2 mV of the rail that it shows. A scored waveform uses a time step no coarser than `tedge/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `dual_track_sample_hold` on the module and positional ports in the starter, including the parameter defaults above. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The tick grid and the update rules define the observable outputs. They do not require a particular state variable, event operator, or event organization.
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
