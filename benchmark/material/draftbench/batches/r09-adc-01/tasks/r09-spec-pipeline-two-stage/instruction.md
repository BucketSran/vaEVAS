# Two-stage pipelined ADC with a valid tag

Build a 4-bit pipelined ADC with two 2-bit stages. Stage 1 samples the input on a clock edge, decides a 2-bit coarse code, and amplifies the remaining error by four into a residue. Stage 2 decides the 2-bit fine code from that residue on the next clock edge. The complete code is published on the clock edge after that. A valid tag travels with each sample, so samples can arrive on consecutive clock edges or with empty clock edges between them.

## Spec

Use the starter declaration of `pipeline_adc_two_stage`. Every port is electrical. The positional order is `vin`, `clk`, `rst`, `valid_i`, `code_3`, `code_2`, `code_1`, `code_0`, `valid_o`, `residue_dbg`. `vin`, `clk`, `rst`, and `valid_i` are inputs. The other ports are outputs. `code_3` is the most significant bit and `code_0` the least significant bit of the 4-bit output code.

Declare these overrideable parameters:

- `vdd` = 0.9 V. Logic high output level.
- `vss` = 0 V. Low rail: the logic low output level and the bottom of the input range. Legal range -0.5 V to 0.5 V.
- `vref` = 0.9 V. Top of the input range.
- `vth` = 0.45 V. Threshold for `clk`, `rst`, and `valid_i`. A level above `vth` is high. Legal range 0.2 V to 0.7 V.
- `tr` = 200 ps. Output transition time. Legal range 10 ps to 1 ns.

`vref - vss` lies between 0.4 V and 2 V, and `vdd - vss` lies between 0.5 V and 2 V. Below, `span = vref - vss`.

Conversion of one sample. The sample `x` is `V(vin)` at the clock edge that takes it, limited to the input range: `x = vss` if `V(vin)` is below `vss`, and `x = vref` if it is above `vref`.

- Stage 1. The coarse code `k` is the number of the thresholds `vss + span/4`, `vss + span/2`, and `vss + 3*span/4` that are at or below `x`. So `x = vref` gives `k = 3`. The center of the selected quarter-range bin is `c = vss + (k + 1/2)*span/4`. The residue is `r = (vss + vref)/2 + 4*(x - c)`. It lies between `vss` and `vref`.
- Stage 2. The fine code `f` is the number of the same three thresholds that are at or below `r`.
- The code of the sample is `4*k + f`. It equals `floor(16*(x - vss)/span)` limited to 15.

Pipeline. A clock edge is a rising crossing of `clk` through `vth` after t = 0 while `rst` is low. The pipeline advances on every clock edge, whether or not a sample is taken. A clock edge takes a sample when `valid_i` is high at that edge. For a sample taken at clock edge `n`:

- At edge `n`, stage 1 takes the sample. Stage 1 holds `x`, `k`, and `r` until the next clock edge that takes a sample, or until reset. `residue_dbg` drives the `r` that stage 1 holds.
- At edge `n + 1`, stage 2 decides `f` from the residue that stage 1 held before this edge. A new sample taken at the same edge does not change that decision.
- At edge `n + 2`, the code outputs show `4*k + f` of this sample and `valid_o` goes high.

Edges `n + 1` and `n + 2` are the next two clock edges, however far apart they are in time. At every clock edge that does not publish a result, `valid_o` goes low and the code outputs keep their last value. Samples taken at consecutive clock edges therefore publish at consecutive clock edges, and `valid_o` stays high from one result to the next.

Reset. `rst` is active high. A rising crossing of `rst` clears the model at once: every sample in progress is discarded and never published, the code outputs show 0, `valid_o` goes low, and stage 1 holds `x = vss`, so `residue_dbg` is `vss`. While `rst` is high, rising `clk` crossings take no sample and publish nothing. The falling crossing of `rst` has no effect, and the next clock edge after it can take a sample. At t = 0 the model is in the same cleared state, whether `rst` is high or low.

Output. Each code output and `valid_o` drives `vdd` for 1 and `vss` for 0. The outputs change only at the events named above. After each change of the expected outputs, every output reaches its new level within `tr` and then stays on it until the next change. This also holds when the next change comes before an output has reached the previous level. The waveform inside that `tr` interval is not specified.

Legal inputs. `vin` is continuous and stays between `vss - 0.2 V` and `vref + 0.2 V`. `clk`, `rst`, and `valid_i` are continuous and stay between 0 V and 0.9 V. They never rest at `vth`, and at t = 0 each of them is at least 50 mV away from `vth`. A control input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. `clk` starts low. Successive crossings of the same input through `vth` are at least 100 ps apart. Successive rising `clk` crossings are at least 4 ns apart. Every crossing of `valid_i` and of `rst` is at least 100 ps away from every rising `clk` crossing. Within 100 ps of every rising `clk` crossing, `vin` moves by less than 0.25 mV. At every clock edge that takes a sample, `x` is at least 3 mV away from every code boundary `vss + j*span/16`, for j = 1 to 15, so no code is decided by a tie.

The expected outputs are calculated with the rules above from the recorded inputs. Crossing times and the sampled `vin` are taken by linear interpolation between saved points. Every saved point is scored except points less than `1.25*tr` after an instant at which an expected output changes. At each scored point the error of every output is at most 2 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `pipeline_adc_two_stage` on the module and positional ports in the starter. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The rules define the published code and the residue. They do not require a particular stage partition, analog operator, state variable, or event organization.
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
