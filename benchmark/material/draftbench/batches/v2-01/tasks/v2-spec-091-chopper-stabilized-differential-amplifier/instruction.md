# Chopper-stabilized differential amplifier

Build the three-module chopper-stabilized differential amplifier. The gain core chops, adds offset, amplifies, and demodulates. The low-pass module keeps the synchronous state. The top module only connects those two helpers.

## Spec

This is a signal-flow model with those two helper duties. It is not a bare sign chopper, a sampled auto-zero store, or a trim servo. Instance names, internal node names, and legal Verilog-A expression style are free. The helper port order, port roles, and which module performs which duty are not free.

`/app/circuit.va` declares the top module `chopper_stabilized_differential_amplifier`. Every top port is electrical. The positional order is `vinp`, `vinn`, `chop_clk`, `rst`, `enable`, `hold`, `voutp`, `voutn`, `settled`, `offset_residual`. `vinp`, `vinn`, `chop_clk`, `rst`, `enable`, and `hold` are inputs. `voutp`, `voutn`, `settled`, and `offset_residual` are outputs.

`/app/chopper_gain_core.va` declares `chopper_gain_core`. `/app/synchronous_lp_state.va` declares `synchronous_lp_state`. Helper ports are electrical. Positional order and role are fixed. Local port identifiers may differ. The published names below are the roles.

`chopper_gain_core` ports, in order: `vinp`, `vinn`, `chop_clk`, `rst`, `enable`, `hold`, `demod_sample`, `baseband_ref`, `event_strobe`. The first six are inputs and match the top inputs. The last three are outputs. On both chop edges, this module forms the demodulated sample and the baseband reference, then notifies the low-pass. `demod_sample = gain*(vinp-vinn) + polarity*gain*vos_amp`. `baseband_ref = gain*(vinp-vinn)`. Reset or disable clears the samples and the notification. Hold blocks an update. The samples are established before the notification starts. `event_strobe` toggles once per valid sample. The toggle is delayed by `2*tr` and uses a transition of length `tr`. Its public parameters are `vdd`, `vss`, `vth`, `gain`, `vos_amp`, and `tr`, with the same defaults as the top.

`synchronous_lp_state` ports, in order: `demod_sample`, `baseband_ref`, `event_strobe`, `rst`, `enable`, `hold`, `voutp`, `voutn`, `settled`, `offset_residual`. It consumes the two samples and both directions of the `event_strobe` crossing. It drives the four public outputs. Its public parameters are `vdd`, `vss`, `vcm`, `vth`, `gain`, `lp_alpha`, `settle_tol`, `settle_cycles`, and `tr`, with the same defaults as the top.

The top instantiates both public helpers, passes compatible values of only those public parameters, connects the core outputs to the low-pass inputs, and connects the low-pass outputs to the public outputs. Do not redo a helper duty in the top, or in a private copy, while leaving the public helper unused or empty. Extra private modules are allowed when they do not bypass a public helper. A delivered file must not include another delivered `.va` file. `constants.vams` and `disciplines.vams` remain available. The verifier loads the three files independently.

Declare these overrideable parameters on the top and pass the matching subset to each helper.

- `vdd` = 0.9 V, `vss` = 0.0 V, and `vcm` = 0.45 V. Output rails and common mode.
- `vth` = 0.45 V. Control threshold.
- `gain` = 3.0. Differential baseband gain.
- `vos_amp` = 20 mV. Internal offset added after input chopping and before amplification.
- `lp_alpha` = 0.25. Low-pass update fraction. The legal domain is `0 < lp_alpha <= 1`.
- `settle_tol` = 20 mV and integer `settle_cycles` = 3. Convergence qualification.
- `tr` = 100 ps. Output transition smoothing time.

No other parameter range is stated.

At every rising and falling `chop_clk` threshold crossing, while enabled, not in reset, and not held:

1. Multiply `vinp - vinn` by the current chopper polarity.
2. Add `vos_amp` inside the amplifier and apply `gain`.
3. Demodulate by that same polarity. The desired differential input returns to baseband with gain. The amplifier offset alternates polarity.
4. Move the retained low-pass state a fraction `lp_alpha` of the way from its previous value to that demodulated sample: `state = (1-lp_alpha)*state + lp_alpha*demod_sample`.

`voutp` and `voutn` are that retained state, centered on `vcm` and limited to `[vss, vdd]`: `voutp = clamp(vcm + state/2, vss, vdd)` and `voutn = clamp(vcm - state/2, vss, vdd)`. `offset_residual` is the retained state minus `gain*(vinp-vinn)` sampled at the most recent active update. It is not given a separate clamp. `settled` is asserted after `settle_cycles` consecutive active updates whose absolute residual is at most `settle_tol`. An active update whose absolute residual is greater than `settle_tol` clears that consecutive count.

`rst` high or `enable` low asynchronously clears the retained differential state, the residual, the convergence count, and `settled`. The differential outputs return to zero around `vcm`, so both sit at `vcm`. This clear also applies while `hold` is high. While `hold` is high and the circuit is enabled and not in reset, keep every retained state and every output exactly as it is. Later chopper edges resume the filter after hold is released.

The core builds the ideal `demod_sample` and `baseband_ref` first. The public outputs may finish within `4*tr` after the chop crossing. Final evaluation has six conditions: two original behavior conditions, one producer-component condition, one consumer-component condition, and two top-level substitute conditions. A component test uses a fixed top and a known-conforming partner component. A top substitute test keeps the submitted top and the other submitted helper.

The producer substitute keeps the control, notification, and reset contract, and on every valid sample supplies `demod_sample = baseband_ref = 0.16 V`. The low-pass must consume those values. The consumer substitute directly supplies `voutp = 0.22 V`, `voutn = 0.67 V`, `settled = 0.9 V`, and `offset_residual = 0.14 V`. The top must present those values on the matching ports. Those consumer voltages are direct contributions from the start of simulation. Do not rewrite them with the normal reset equations. The producer substitute still follows the control and reset timing. Do not recompute a substitute port from the original `vin` and ignore the substitute.

Initial levels and edges are unambiguous. `chop_clk`, `rst`, `enable`, and `hold` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. The analog inputs are continuous at a sample. Supplies stay fixed. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Every saved point is scored, for all four public outputs, except points less than `4.1*tr` after t = 0 or after an event that changes the target of any public output: a `chop_clk` crossing while enabled, not in reset, and not held, or a clear by `rst` or `enable`. In the consumer-substitute condition, every saved point from t = 0 is scored against the substitute voltages. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va`, `/app/chopper_gain_core.va`, and `/app/synchronous_lp_state.va`. The evaluator collects each of these files. It does not collect only one file.
- `/app/circuit.va` defines `chopper_stabilized_differential_amplifier` and instantiates the two helpers. `/app/chopper_gain_core.va` defines `chopper_gain_core`. `/app/synchronous_lp_state.va` defines `synchronous_lp_state`. You may rewrite a helper body. You still have to keep its port roles and its duty.
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
