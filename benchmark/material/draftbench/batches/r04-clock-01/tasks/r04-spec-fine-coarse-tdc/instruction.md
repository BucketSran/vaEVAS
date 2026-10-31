# Fine/coarse TDC with fine times at both ends

Build a time-to-digital converter that measures the interval from a start event to a stop event. A coarse counter counts reference clock periods. Fine interpolation quantizes the position of the start and of the stop inside their reference periods. The converter combines the coarse count and both fine codes into one interval code.

## Spec

Use the starter declaration of `fine_coarse_tdc`. Every port is electrical. The positional order is `start`, `stop`, `ref_clk`, `rst`, `code_7`, `code_6`, `code_5`, `code_4`, `code_3`, `code_2`, `code_1`, `code_0`, `valid`, `overflow`. `start`, `stop`, `ref_clk`, and `rst` are inputs. The other ports are outputs. `code_7` is the most significant bit and `code_0` the least significant bit of an 8-bit unsigned code.

Declare these overrideable parameters:

- `vth` = 0.45 V. Threshold for every input. A level above `vth` is high. Legal range 0.2 V to 0.7 V.
- `vdd` = 0.9 V. Output high level. Output low is 0 V. Legal range 0.5 V to 1.5 V.
- `tr` = 200 ps. Output transition time. Legal range 10 ps to 1 ns.

An event is a rising crossing of an input through `vth` after t = 0, except that `rst` acts on both crossing directions as stated below. Falling crossings of `start`, `stop`, and `ref_clk` have no effect. `rst` is active high.

Reference and fine codes. `ref_clk` is low until its first rising crossing. From then on its rising crossings are equally spaced by the reference period `T_ref`, which is the same for the whole transient and lies between 1 ns and 20 ns. `T_ref` is not a parameter, and different evaluations use different periods. The fine step is `T_ref/16`. For a start or stop event at time `t`, let `r` be the latest rising crossing of `ref_clk` at or before `t`. The fine code of the event is `floor(16*(t - r)/T_ref)`, an integer from 0 to 15. A `ref_clk` crossing at the same instant as a start or stop event therefore counts as before it.

Warm-up. The converter is ready once `ref_clk` has had two rising crossings after the later of t = 0 and the latest falling crossing of `rst`, with `rst` low at both crossings. Before that, a start has no effect.

Measurement.

- A start event while `rst` is low and the converter is ready begins a measurement. It records the start fine code `q_s` and sets every code bit, `valid`, and `overflow` low. A start during a measurement cancels that measurement and begins a new one from the new start. A start at any other time has no effect.
- `N` is the number of rising `ref_clk` crossings after the start event and at or before the stop event.
- The first stop event of a measurement ends it with the stop fine code `q_e`. The result is `D = 16*N + q_e - q_s`. The outputs then show `D` in binary, `valid` high, and `overflow` low. `D` is the interval in fine steps: it differs from `16*(t_stop - t_start)/T_ref` by less than 1.
- If the 16th rising `ref_clk` crossing after the start comes before a stop, the measurement ends at that crossing as an overflow. The outputs then show code 255 (every bit high), `valid` high, and `overflow` high. A later stop belongs to no measurement.
- A stop event outside a measurement has no effect, and the outputs hold.
- Reset. A rising crossing of `rst` sets every output low and ends a measurement in progress without a result. While `rst` is high no measurement begins, and after its falling crossing the warm-up starts again.
- At t = 0 every output is low, no measurement is in progress, and the converter is not ready.

The outputs change only at the events named above. Each output drives 0 V or `vdd`. After each change of the expected outputs, every output reaches its new level within `tr` and then stays on it until the next change. This also holds when the next change comes before an output has reached the previous level. The waveform inside that `tr` interval is not specified.

Every input is continuous and stays between 0 V and 0.9 V. Inputs never rest at `vth`, and at t = 0 each input is at least 50 mV away from `vth`. An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. They may move between any levels, including levels between 0 V and 0.9 V, and an event is the instant at which the input passes `vth`. Between two successive crossings of `vth`, each input moves at least 50 mV away from `vth`. Successive crossings of the same input are at least 100 ps apart, and every start event is at least 100 ps away from every stop event. Every start and stop event after the first rising `ref_clk` crossing is at least 20 ps away from every instant `r + k*T_ref/16`, where `r` is the latest rising `ref_clk` crossing before it and `k` is an integer, so no fine code or count is decided by a tie. Every `rst` crossing is at least 100 ps away from every rising crossing of `start`, `stop`, and `ref_clk`.

The expected outputs are calculated with the rules above from the recorded input crossing times, taken by linear interpolation between saved points, with `T_ref` taken from the recorded `ref_clk` crossings. Every saved point is scored except points less than `1.25*tr` after an instant at which an expected output changes. At each scored point the error of every output is at most 10 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs, the reference period, and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `fine_coarse_tdc` on the module and positional ports in the starter. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The rules define the published code. They do not require a particular analog operator, state variable, counter structure, or event organization.
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
