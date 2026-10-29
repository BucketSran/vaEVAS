# Four-bit SAR ADC system

Build a four-bit successive-approximation ADC from four reusable modules: a sample-and-hold, a binary-weighted DAC, a comparator, and a SAR controller. A top module connects them. A start request arms a conversion. The next clock edge samples the input. Four more clock edges each decide one bit, from the most significant bit down, by comparing the held sample with the DAC level of the current trial code. Then `done` goes high.

## Spec

The starter declares five modules with their positional ports. Every port is electrical. Keep these module names and port orders, and declare the parameters listed for each module with the defaults below. Final evaluation instantiates the top module, and it also instantiates each of the other four modules on its own.

Parameters (each module declares only the ones listed for it; the top passes its values to the modules it instantiates):

- `vdd` = 0.9 V. Logic high level of every logic output.
- `vss` = 0 V. Logic low level of every logic output, and the lower end of the conversion range. Legal range -0.5 V to 0.5 V.
- `vref` = 0.9 V. Upper end of the conversion range.
- `vth` = 0.45 V. Threshold of every logic input. A level above `vth` is high. Legal range 0.2 V to 0.7 V, and at least 0.1 V above `vss` and 0.1 V below `vdd`.
- `tr` = 200 ps. Output transition time. Legal range 10 ps to 1 ns.

`vref - vss` lies between 0.4 V and 2 V, and `vdd - vss` lies between 0.5 V and 2 V. Below, `span = vref - vss`, and `DAC(c) = vss + span*c/16` for a code `c` from 0 to 15. A logic output drives `vdd` for 1 and `vss` for 0. A four-bit value appears on four ports named `_3` to `_0`, with `_3` the most significant bit.

Output timing in every module: after each event that changes an output's expected value, the output reaches the new value within its deadline and then stays on it until the next change. This also holds when the next change comes before the output has reached the previous value. The waveform inside the deadline is not specified. The deadline is `tr`, except for `dac_dbg` of the top module (see below). Outputs change only at the events named for their module.

`binary_weighted_cdac(bit_3, bit_2, bit_1, bit_0, dac_o, dac_dbg)`. Parameters `vss`, `vref`, `vth`, `tr`. The input code `c` has bit `k` equal to 1 when `bit_k` is high. `dac_o` and `dac_dbg` both drive `DAC(c)`. An event is a crossing of a bit input through `vth` that changes `c`.

`sar_comparator(sample_i, dac_i, cmp_o)`. Parameters `vdd`, `vss`, `vth`, `tr`; `vth` has no effect in this module. `cmp_o` is 1 while `V(sample_i) >= V(dac_i)` and 0 otherwise. An event is any change of whether `V(sample_i) >= V(dac_i)`: a crossing of the difference `V(sample_i) - V(dac_i)` through 0, the difference reaching 0 from below, or the difference leaving 0 toward negative values. In tests of the comparator only crossings occur.

`sample_hold(vin, clk, rst, sample_en, sample_o, sample_dbg)`. Parameters `vss`, `vth`, `tr`. The module holds one value, `vss` at t = 0. A sampling edge is a rising crossing of `clk` through `vth` after t = 0 at which `rst` is low and `sample_en` is high. It sets the held value to `V(vin)` at that crossing, without limiting it to the conversion range. A rising crossing of `rst` sets the held value to `vss` at once. `sample_o` and `sample_dbg` both drive the held value.

`sar_controller(clk, rst, start, cmp_i, sample_en, trial_3, trial_2, trial_1, trial_0, code_3, code_2, code_1, code_0, done)`. Parameters `vdd`, `vss`, `vth`, `tr`. Every output is a logic output. The controller holds a trial code `T` on `trial_3..trial_0`, a result code `R` on `code_3..code_0`, and the levels of `sample_en` and `done`.

- A clock edge is a rising crossing of `clk` through `vth` after t = 0 at which `rst` is low. A start request is a rising crossing of `start` through `vth` after t = 0 at which `rst` is low.
- At t = 0, and at each rising crossing of `rst`, the controller becomes idle with `T = 0`, `R = 0`, and `sample_en` and `done` low. Nothing else happens while `rst` is high. The falling crossing of `rst` has no effect.
- Every start request arms a new conversion, whether the controller is idle, armed, or converting. A conversion in progress is abandoned. `T = 0`, `R = 0`, `done` goes low and `sample_en` goes high.
- The first clock edge after the start request is the sample edge. `sample_en` goes low and `T = 8`.
- Each of the next four clock edges decides one bit `b`, from `b = 3` down to `b = 0`. The bit is kept when `cmp_i` is high at that edge, so `R = T`. Otherwise `R = T - 2^b`. After deciding a bit `b > 0`, `T = R + 2^(b-1)`. After deciding bit 0, `T = R`, `done` goes high, and the controller is idle.
- Clock edges while the controller is idle have no effect. `T`, `R`, and `done` keep their values until the next start request or reset.

`sar_adc_top(vin, clk, rst, start, code_3, code_2, code_1, code_0, done, sample_dbg, dac_dbg)`. Parameters `vdd`, `vss`, `vref`, `vth`, `tr`. The top instantiates the four modules and connects them. The sample-and-hold samples `vin` under the controller's `sample_en`. The DAC converts the controller's trial code. The comparator compares the held sample with the DAC output and drives the controller's `cmp_i`. `code_3..code_0` and `done` are the controller's outputs, `sample_dbg` is the held sample, and `dac_dbg` is the DAC output. The top-level behavior that follows:

- A conversion with sample `x`, which is `V(vin)` at its sample edge, keeps a bit when `x >= DAC(T)`, where `T` is the trial code set at the previous clock edge. The trial codes are 8, then `R + 4`, `R + 2`, `R + 1`, and finally `R`. Inside the top module both comparator inputs are `vss` at t = 0 and after a reset, so their difference is 0 there and `cmp_o` is 1; at the next sample edge the difference leaves 0, toward negative values when `x <= vss`.
- The final code is `floor(16*(x - vss)/span)`, limited to 0 to 15. An input below `vss` gives 0 and an input above `vref` gives 15.
- `dac_dbg` is `DAC(T)`, so it is `vss` after a reset and after each start request. Its deadline is `2*tr` after the clock edge, start request, or reset that changes `T`, because the change passes through the controller and then the DAC. The deadline of `code_3..code_0`, `done`, and `sample_dbg` is `tr`.

Simultaneous events. Reset has priority: a clock edge or start request at the same instant as a crossing of `rst` has no effect. A start request at the same instant as a clock edge counts as after that edge, so the sample edge is the next clock edge. The legal inputs below keep these events apart in final evaluation, and the rules above decide every evaluated case.

Legal inputs:

- `vin` is continuous and stays between `vss - 0.2 V` and `vref + 0.2 V`. `clk`, `rst`, `start`, and every logic input driven by a test (`sample_en`, `cmp_i`, and the bit inputs) stay between 0 V and 0.9 V. They never rest at `vth`, and at t = 0 each is at least 50 mV away from `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. `clk` starts low.
- Successive crossings of the same input through `vth` are at least 100 ps apart. Successive rising `clk` crossings are at least 4 ns apart.
- Every crossing of `rst`, `sample_en`, and `cmp_i` is at least 100 ps away from every rising `clk` crossing, and every crossing of `start` is at least 100 ps away from every crossing of `rst`. Every rising crossing of `start` is at least 100 ps away from every rising `clk` crossing, and at least `2*tr` away when the top module is tested.
- When the top module is tested, every rising `clk` crossing at which `rst` is low is at least `2*tr` after every earlier rising crossing of `rst`. After a reset, the sample-and-hold stops sampling only once the controller's `sample_en` is low, which can take up to `tr`.
- When the top module is tested, every rising crossing of `rst` is at least `tr` after the preceding rising `clk` crossing. A reset therefore changes the controller's outputs, including the trial code that drives the DAC, only after they have reached the levels set at that clock edge.
- Bit inputs of the DAC that change together cross `vth` within 5 ps of one another, and these crossings count as simultaneous. Other crossings of bit inputs are at least 100 ps apart.
- Within 100 ps of every sampling edge, `vin` moves by less than 0.25 mV.
- In tests of the top module, every sample `x` is at least 3 mV away from every DAC level `DAC(j)`, for j = 1 to 15, so no bit is decided by a tie.
- In tests of the comparator, `V(sample_i) - V(dac_i)` never rests at 0, always crosses 0 when it reaches 0 (it never touches 0 and returns to the same sign), is at least 5 mV away from 0 at t = 0, and its successive zero crossings are at least 1 ns apart.

The expected outputs are calculated with the rules above from the recorded inputs. Crossing times and input values are taken by linear interpolation between saved points. Every saved point is scored, except points less than 1.25 times an output's deadline after an event that changes that output's expected value by more than δ = 0.1 mV. That is `1.25*tr`, and `2.5*tr` for `dac_dbg` of the top module. A change of δ or less, such as a new sample within δ of the held one, does not count as a change here or in the output timing rule above: it opens no such interval, the expected value keeps its previous value, and the output is scored against that value as at any other point. At each scored point the error of every output is at most 2 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement the five modules on the module names and positional ports in the starter. `sar_adc_top` instantiates the four other modules and connects them as described. You may define further helper modules in the same file.
- Any Verilog-A implementation that meets those interfaces and the external behavior in Spec is acceptable. The rules define each module's outputs and the top-level conversion. They do not require a particular analog operator, state variable, or event organization inside a module.
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
