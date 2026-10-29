# 4-bit SAR front-end logic

Build only the 4-bit SAR front-end controller that handshakes with a fixed comparator and trial DAC, publishes DAC controls, and emits the previous conversion word.

## Spec

Use the starter declaration of `sarfend_logic_4b`. Every port is electrical. The positional order is `clks`, `dcomp`, `dcompb`, `test`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `clkc`, `dp1`, `dp2`, `dp3`, `dp4`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`.

`clks` is the sample and reset clock. `test` enables the captured override bits `dtest0` through `dtest3`. The model reads those eight ports. `dcomp` and `dcompb` are the comparator's decision pair. The interface sentence calls them comparator outputs because they are outputs of the comparator. This module consumes them. It does not drive them. The model drives `clkc`, `dp1` through `dp4`, `dm1` through `dm4`, and `dout0` through `dout3`. `clkc` requests comparator activity. Each `dp`/`dm` pair is a differential DAC control. `dout0` through `dout3` publish the previous conversion word.

No overrideable public parameters are required. Use a 0.45 V threshold and 0 V / 1 V voltage-coded controls. Every digital output change of this controller completes within 200 ps of the triggering control or comparator event. Choose smoothing inside that limit. The 200 ps limit belongs to this controller. It is separate from the fixed comparator delay below.

At the initial time, `dp4` and `dm4` are 0 V, `dp3`, `dm3`, `dp2`, `dm2`, `dp1`, and `dm1` are 1 V, and `dout0` through `dout3` and `clkc` are 0 V. The conversion pointer is waiting for the MSB pair `dp4`/`dm4`. All four bits are still undecided. `clks` starts low. Until the first rising `clks` edge, a both-low comparator pair is not a valid decision and `clkc` stays 0 V. Capture of the test override starts at that first rising edge.

On each rising `clks` crossing, first publish the previous P-side word: `dout3 = dp4`, `dout2 = dp3`, `dout1 = dp2`, and `dout0 = dp1`. The first rising edge therefore publishes `dout3:dout0` as 0111 from the power-on P-side state. After that publish, reset the pointer, initialize the new conversion to `dp4 = dm4 = 0` and `dp3 = dm3 = dp2 = dm2 = dp1 = dm1 = 1`, capture `dtest3` through `dtest0`, and clear `clkc`. Equal values on a pair are an undecided trial state. Only an accepted decision makes that pair complementary.

On the falling `clks` edge, assert `clkc` to start comparison. While `clks` is low and decisions remain, a comparator reset that leaves both comparator outputs low reasserts `clkc`. Accept decisions in the order `dp4`/`dm4`, `dp3`/`dm3`, `dp2`/`dm2`, then `dp1`/`dm1`. A `dcomp`-high and `dcompb`-low pair writes P/M as 1/0. A `dcomp`-low and `dcompb`-high pair writes P/M as 0/1. Clear `clkc` when a decision is accepted. Stop requesting comparisons after four accepted decisions.

While `test` is low, use the live comparator decision. While `test` is high, use the bits captured at the rising `clks` edge, in the order `dtest3`, `dtest2`, `dtest1`, `dtest0`, for those four decisions. `test` itself is read at the decision. The override bits are the captured word.

The public system bench connects this controller to the fixed module `sar_fixed_frontend` in [testbench/sar_support.va](testbench/sar_support.va). Do not modify that module or [testbench/system_test.scs](testbench/system_test.scs). On each rising `clkc`, the fixed frontend builds the next trial level from the `dp` bits already decided, compares `vin`, and returns a complementary decision after 100 ps. A falling `clkc` resets that comparator. After both of its outputs are low, this controller requests the next decision. The conversion is four cooperating decisions. The next rising `clks` publishes the saved whole word. Public tests may change `vin` and the frame period. The local public bench also keeps the test-override path and does not treat an extra decision after the four accepted decisions as another request.

Initial levels and edges are unambiguous. `clks`, `dcomp`, `dcompb`, `test`, and `dtest0` through `dtest3` never rest at the 0.45 V threshold. Each of them that reaches the threshold always crosses it; it never touches the threshold and returns to the same side. Independent control edges are at least two controller output-transition times apart. Supplies stay fixed. The control threshold is 0.45 V. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Every saved point is scored, for all thirteen outputs, except points less than 230 ps (`1.15*200 ps`) after t = 0 or after a `clks`, `dcomp`, or `dcompb` crossing that changes an output target. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `sarfend_logic_4b` on the module and positional ports in the starter.
- Deliver only that controller. Keep the fixed comparator and weighted trial DAC as the public module `sar_fixed_frontend`. The controller's handshake, publish-before-reinitialize order, test capture, and four-decision stop are required behavior. Any Verilog-A organization that meets those external duties is acceptable. A particular state name or event operator is not required.
- The submitted model must not read grading files, replay stored answers, or start external processes. You may read this instruction, the starter, and the public testbench, and you may run the public check. Do not edit the public testbench.

From `/app`, run `python3 testbench/check.py --output /app/output/public-check`.

[testbench/README.md](testbench/README.md) describes that check. The public bench sources stay visible, including [testbench/visible_test.scs](testbench/visible_test.scs), [testbench/system_test.scs](testbench/system_test.scs), and [testbench/sar_support.va](testbench/sar_support.va). Tool version, timeouts, and diagnostics are in that README.

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
