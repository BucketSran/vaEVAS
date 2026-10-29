# Switched-capacitor integrator phase pair

Build the three-module switched-capacitor integrator. One helper samples on `phi1`. The other consumes that sample on `phi2` and integrates it. The top module only connects those two helpers.

## Spec

`/app/circuit.va` declares the top module `switched_cap_integrator_phase_pair_top`. Every top port is electrical. The positional order is `vin`, `phi1`, `phi2`, `rst`, `enable`, `vout`, `phase_metric`, `valid`. The top sentence says the ports are electrical and gives this order. It does not itself print the words input and output. The system contract below says the integrator drives the three public outputs, and the top reads `vin` and the controls into the sampler.

`/app/sample_phase_cell.va` declares `sample_phase_cell`. `/app/integrator_state_cell.va` declares `integrator_state_cell`. Helper ports are electrical. Positional order and role are fixed. Local port identifiers may differ. The published names below are the roles.

`sample_phase_cell` ports, in order: `vin`, `phi1`, `phi2`, `rst`, `enable`, `sample_node`, `sample_valid`. The first five are inputs. `sample_node` and `sample_valid` are outputs. On a legal rising `phi1`, store the actual `vin` on `sample_node` and drive `sample_valid` to `vdd`. If `phi2` is already above `vth` at that edge, do not accept the sample. Reset or disable sets `sample_node` to `vcm` and `sample_valid` to `vss`. The `sample_node` transition finishes before the following normal `phi2`. Its public parameters are `vdd`, `vss`, `vcm`, `vth`, and `tr`, with the same defaults as the top.

`integrator_state_cell` ports, in order: `phi1`, `phi2`, `rst`, `enable`, `sample_node`, `sample_valid`, `vout`, `phase_metric`, `valid`. The first six are inputs. `vout`, `phase_metric`, and `valid` are the three public outputs this module drives. On a legal rising `phi2` it consumes the actual `sample_node` and `sample_valid`. One accepted `phi1` may be consumed only once. The increment is `k_int*(sample_node-vcm)`. Overlap, a repeated `phi2`, and reset follow the rules below. Its public parameters are `vdd`, `vss`, `vcm`, `vth`, `tr`, and `k_int`, with the same defaults as the top.

The top instantiates both public helpers, passes compatible values of only those public parameters, connects the sampler outputs to the integrator inputs, and connects the integrator outputs to the public outputs. Do not redo a helper duty in the top, or in a private copy, while leaving the public helper unused or empty. Extra private modules are allowed when they do not bypass a public helper. A delivered file must not include another delivered `.va` file. `constants.vams` and `disciplines.vams` remain available. The verifier loads the three files independently. Use voltage-domain state and voltage contributions on the public electrical outputs. Do not add a pass or fail flag. The only public results are the named ports.

Declare these overrideable parameters on the top and pass the matching subset to each helper. No legal range is stated beyond the values and equations here.

- `vdd` = 0.9 V. Logic high and upper output rail.
- `vss` = 0.0 V. Logic low and lower output rail.
- `vcm` = 0.45 V. Signal common-mode reference.
- `vth` = 0.45 V. Threshold for a voltage-coded control.
- `tr` = 200 ps. Output transition smoothing time.
- `k_int` = 0.2. Integration increment per accepted phase pair.

`phase_metric` starts at `vcm`. While `rst` is high or `enable` is low, clear the sample validity, set the integrator state to `vcm`, drive `vout` to `vcm`, drive `phase_metric` to `vcm`, and drive `valid` to `vss`. This clear is asynchronous. The sampler uses the same clear for `sample_node` and `sample_valid`.

On a rising `phi1` edge, while enabled and not in reset, sample `vin` when `phi2` is not above `vth`. That saved voltage is `vin` itself. The deviation from `vcm` is applied later, at the integrator. On the following rising `phi2` edge, when `phi1` is not above `vth` and a new sample is still valid, update the integrator state `q` to `q_next = clamp(q + k_int*(sample_node-vcm), vss, vdd)`, where `clamp(x, vss, vdd)` limits `x` to `[vss, vdd]`. Drive `vout` to `q_next`. The clamped value is the stored state, so the integrator keeps no accumulation beyond a rail. After it saturates, the first accepted pair with an opposite-direction increment moves `vout` away from that rail. On an accepted pair, `phase_metric` is the most recent accepted `phi1` sample, clamped to `[vss, vdd]`, and `valid` is `vdd`. Then that sample is spent.

If the two phases overlap, or a rising `phi2` arrives without a new accepted `phi1`, hold the previous integrator state and `phase_metric`, and drive `valid` to `vss` for that cycle. A normal pair keeps the phases at least `4*tr` apart, and the sample transition has finished before that `phi2`.

Final evaluation has six conditions: two original behavior conditions, one producer-component condition, one consumer-component condition, and two top-level substitute conditions. A component test uses a fixed top and a known-conforming partner component. A top substitute test keeps the submitted top and the other submitted helper.

The producer substitute keeps the sample-valid, control, and reset contract, and on every valid `phi1` supplies `sample_node = 0.62 V`. The integrator must consume that value. The consumer substitute directly supplies `vout = 0.63 V`, `phase_metric = 0.22 V`, and `valid = 0 V`. The top must present those values on the matching ports. Those consumer voltages are direct contributions from the start of simulation. Do not rewrite them with the normal reset equations. The producer substitute still follows the control and reset timing. Do not recompute a substitute port from the original `vin` and ignore the substitute.

Initial levels and edges are unambiguous. `phi1`, `phi2`, `rst`, and `enable` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. `vin` is continuous at a sample. Supplies stay fixed. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each public output reaches its new value within `tr` after the event that changes it. Every saved point is scored, for all three public outputs, except points less than `1.15*tr` after t = 0 or after an event that changes the target of any public output: a rising `phi2` crossing, or a clear by `rst` or `enable`. In the consumer-substitute condition, every saved point from t = 0 is scored against the substitute voltages. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va`, `/app/sample_phase_cell.va`, and `/app/integrator_state_cell.va`. The evaluator collects each of these files. It does not collect only one file.
- `/app/circuit.va` defines `switched_cap_integrator_phase_pair_top` and instantiates the two helpers. `/app/sample_phase_cell.va` defines `sample_phase_cell`. `/app/integrator_state_cell.va` defines `integrator_state_cell`. You may rewrite a helper body. You still have to keep its port roles and its duty.
- The submitted models must not read grading files, replay stored answers, or start external processes. You may read this instruction, the starter, and the public testbench, and you may run the public check. Do not edit the public testbench.

From `/app`, run `python3 testbench/check.py --output /app/output/public-check`.

[testbench/README.md](testbench/README.md) describes that check. The public bench sources stay visible, including [testbench/visible_test.scs](testbench/visible_test.scs). Tool version, timeouts, and diagnostics are in that README.

This is an implementation task, not a repository-audit task.
Work in /app and modify only the declared deliverables; do not edit public development benches, model libraries, or external fixtures.
Make one bounded inspection pass over this instruction, the declared deliverables, supplied starter material, and public development benches.
As the task solver, create a runnable candidate in every file named in the Deliverable section before beginning detailed exploration, and keep those files updated as you work.
If your working time expires, the evaluator copies those files exactly as they exist at that moment and runs the verifier on them.
If any declared file is missing or empty, the result is zero reward.
Temporary files are not submitted.

If a concrete model, tool, or execution problem appears, investigate it as needed before continuing.
Iterate by editing the declared deliverables and using public development benches to diagnose observed behavior.
Do not repeatedly enumerate files, reread unchanged references, or retry unchanged discovery commands instead of editing and simulating.
