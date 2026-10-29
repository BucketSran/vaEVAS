# Pipeline ADC stage

Build a clocked 1.5-bit pipeline ADC MDAC stage that samples on `PHI1` and publishes the residue and sub-ADC decision on `PHI2`.

## Spec

Use the starter declaration of `pipeline_stage`. Every port is electrical. The positional order is `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.

`VRES` is the residue output. `D1` and `D0` are the sub-ADC decision outputs. `PHI1` and `PHI2` are the two clocks. `VIN` is the analog voltage sampled by the stage. `VREF` is the reference read at the decision. `VDD` and `VSS` are the supply nodes used by the residue and decision levels. The interface sentence names the three outputs and does not say whether the supply ports are inputs or inouts. The equations read `V(VDD)` and `V(VSS)`.

Declare these overrideable parameters in the model. No legal range is stated beyond the values and equations here.

- `vth` = 0.45 V. Threshold for a rising `PHI1` or `PHI2` decision.
- `vdd` = 0.9 V. Nominal high level used only for the initial residue. It is not a substitute for `V(VDD)` in the residue equation.
- `tedge` = 200 ps. Smoothing time of each output transition.

The high intervals of `PHI1` and `PHI2` do not overlap. At the initial time, `VRES` is `vdd/2` and both `D1` and `D0` are 0 V. After a decision, high is `V(VDD)` and low is `V(VSS)`.

On each rising `PHI1` edge, sample `VIN`. That edge does not change `VRES`, `D1`, or `D0`. On each rising `PHI2` edge, let `cm = V(VDD)/2`, let `x` be the `VIN` captured at the preceding rising `PHI1` edge minus `cm`, and let `ref = V(VREF)` at this edge. The region is +1 when `x > ref/4`, -1 when `x < -ref/4`, and 0 otherwise. Equality with `+ref/4` or `-ref/4` is region 0.

The residue target is `clamp(cm + 2*x - region*ref/2, V(VSS), V(VDD))`. `D1` is high only for region +1. `D0` is high only for region 0. The other decision level is low. Both decisions update on that same edge. The outputs then hold until the next rising `PHI2` edge. Each output uses a smooth voltage transition of length `tedge`.

Initial levels and edges are unambiguous. `PHI1` and `PHI2` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tedge` apart. `VIN` is continuous at the sample. Supplies stay fixed. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each output reaches its new value within `tedge` after the rising `PHI2` crossing that sets it. Every saved point is scored, for all three outputs, except points less than `1.15*tedge` after t = 0 or after a rising `PHI2` crossing that changes an output target. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `pipeline_stage` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The equations define the observable result. They do not require a particular state name or event operator.
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
