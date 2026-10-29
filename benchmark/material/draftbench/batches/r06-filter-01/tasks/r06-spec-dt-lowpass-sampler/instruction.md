# Discrete-time low-pass filter with a clocked output sampler

Build a first-order discrete-time low-pass filter that updates on its own fixed time grid, and sample its value on an external clock and hold it on the output. The two time bases are independent. A reset sample clears only the held value; the filter keeps updating through reset.

## Spec

Use the starter declaration of `dt_lowpass_sampler`. Every port is electrical. The positional order is `vin`, `clk`, `rst`, `out`. `vin`, `clk`, and `rst` are inputs. `out` is the output.

Declare these overrideable parameters:

- `tupdate` = 100 ns. Filter update period. Legal range 20 ns to 1 us.
- `vth` = 0.45 V. Threshold for `clk` and `rst`. A level above `vth` is high.
- `tr` = 200 ps. Output transition time. Legal range 10 ps to 1 ns.

Filter. The model contains a discrete-time filter value `y`. It changes only at the update instants `t_k = k*tupdate`, for k = 0, 1, 2, and so on, counted from t = 0. The model generates these instants itself; they do not depend on `clk` or `rst`. At each update instant the model takes the input sample `x_k`, which is `V(vin)` at the instant `t_k`, and sets

`y_k = 0.25*x_k + 0.75*y_(k-1)`

This is the transfer function `H(z) = 0.25/(1 - 0.75*z^-1)`, with unity DC gain. The new sample enters `y_k` at its own update instant, without an extra period of delay. From `t_k` until the next update instant, `y` equals `y_k`. It is not interpolated between updates and does not follow `vin`, so a change of `vin` that starts and ends between two update instants has no effect on `y`. At t = 0 the filter is in equilibrium with its input: `y_(-1)` equals `V(vin)` at t = 0, as in a DC operating point, so `y_0` also equals that value. Clock edges and reset never add, skip, move, or clear an update.

Sampler. A sample event is a rising crossing of `clk` through `vth` after t = 0. At each sample event the held value becomes 0 V if `rst` is high. Otherwise it becomes `y` at the crossing instant, which is the value set by the latest update instant before the crossing. The held value changes only at sample events. A change of `rst` between sample events has no effect until the next sample event. From t = 0 until the first sample event the held value is 0 V.

Output. `out` drives the held value. After each sample event, `out` reaches the new held value within `tr` and then stays on it until the next sample event. The waveform inside that `tr` interval is not specified.

`vin` is continuous and stays between -1 V and +1 V. It may change at any time, including between update instants and between sample events. `clk` and `rst` switch between 0 V and 0.9 V with transitions no longer than 200 ps, and `vth` lies strictly between those levels. Controls never rest at `vth`. A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. At t = 0 each control is at least 50 mV away from `vth`. `clk` starts low. Successive rising `clk` crossings are at least 5 ns apart, and `clk` stays high and low for at least 2 ns each time. Every rising `clk` crossing is at least 0.5 ns away from every update instant. Every `rst` crossing is at least 1 ns away from every rising `clk` crossing.

The expected held value is calculated from the recorded `vin` at the update instants and the recorded `clk` crossing times with the filter law and initial state above. Every saved point is scored except points less than `1.25*tr` after a sample event. At each scored point the error of `V(out)` is at most 2 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `dt_lowpass_sampler` on the module and positional ports in the starter. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The filter law defines the value that is sampled. It does not require a particular analog operator, state variable, or event organization.
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
