# Chopper-Stabilized Differential Amplifier

## Task Contract

Implement a three-module L2 behavioral model of a chopper-stabilized differential amplifier. The circuit must compose input chopping and offset-bearing gain with a separate synchronous event-driven low-pass stage. This is a complete signal-flow model, not a bare sign chopper, sampled auto-zero store, or trim servo.

Target artifacts: `chopper_stabilized_differential_amplifier.va`, `chopper_gain_core.va`, and `synchronous_lp_state.va`.

## Public Verilog-A Interface

Declare this positional electrical interface exactly:

```verilog
module chopper_stabilized_differential_amplifier(
    vinp, vinn, chop_clk, rst, enable, hold,
    voutp, voutn, settled, offset_residual
);
```

`vinp`, `vinn`, `chop_clk`, `rst`, `enable`, and `hold` are inputs. `voutp`, `voutn`, `settled`, and `offset_residual` are outputs.

Also declare helper modules `chopper_gain_core` and `synchronous_lp_state`. The top module must instantiate both helpers and connect them through electrical internal demodulated-sample and event-strobe nodes.

## Public Parameter Contract

- `vdd = 0.9 V`, `vss = 0.0 V`, and `vcm = 0.45 V` define the output rails and common mode.
- `vth = 0.45 V` is the control threshold.
- `gain = 3.0` is the differential baseband gain.
- `vos_amp = 20 mV` is the internal offset added after input chopping and before amplification.
- `lp_alpha = 0.25` is the low-pass update fraction, with `0 < lp_alpha <= 1`.
- `settle_tol = 20 mV` and integer `settle_cycles = 3` define convergence qualification.
- `tr = 100 ps` is output transition smoothing time.

## Required Behavior

At every rising and falling `chop_clk` threshold crossing while enabled, not reset, and not held:

1. Multiply `vinp-vinn` by the current chopper polarity.
2. Add `vos_amp` inside the amplifier and apply `gain`.
3. Synchronously demodulate by the same polarity. The desired differential input therefore returns to baseband with gain, while amplifier offset alternates polarity.
4. Update the retained low-pass state by `lp_alpha` toward that demodulated sample.

Drive `voutp-voutn` from the retained low-pass state, centered on `vcm` and limited to the `vss`/`vdd` rails. Drive `offset_residual` to the retained state minus `gain*(vinp-vinn)` sampled at the most recent active update. Assert `settled` after `settle_cycles` consecutive active updates whose absolute residual is at most `settle_tol`.

Active-high `rst` or low `enable` asynchronously clears the retained differential state, residual, convergence count, and `settled`; the differential outputs return to zero around `vcm`. While `hold` is high, preserve all retained state and outputs exactly. Resume event-driven filtering on later chopper edges after hold is released.

## Modeling Constraints

Use deterministic voltage-domain Verilog-A and event-driven retained state. Use both chopper polarities and voltage contributions only. Apply `transition()` only to retained output targets. Do not implement a continuously tracking sign multiplier, an auto-zero sample/subtract cell, a digital trim loop, transistor-level circuitry, current contributions, hidden pass/fail outputs, file I/O, `final_step`, or simulator-generated artifacts. Do not hard-code testbench times or input values.

## Output Contract

Return exactly these complete source files and no other artifact:

- `chopper_stabilized_differential_amplifier.va`
- `chopper_gain_core.va`
- `synchronous_lp_state.va`
