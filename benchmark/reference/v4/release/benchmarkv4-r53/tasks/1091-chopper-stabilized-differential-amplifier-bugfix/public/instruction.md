# Chopper-Stabilized Differential Amplifier Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `chopper_stabilized_differential_amplifier.va`:
  - Module `chopper_stabilized_differential_amplifier` (entry)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `chop_clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `hold` (input, electrical)
    - position 6: `voutp` (output, electrical)
    - position 7: `voutn` (output, electrical)
    - position 8: `settled` (output, electrical)
    - position 9: `offset_residual` (output, electrical)
- Artifact `chopper_gain_core.va`:
  - Module `chopper_gain_core` (support)
- Artifact `synchronous_lp_state.va`:
  - Module `synchronous_lp_state` (support)

## Public Parameter Contract

- `chopper_stabilized_differential_amplifier.vdd` defaults to `0.9` V; valid range: vdd > vss; logic-high and upper output rail.
- `chopper_stabilized_differential_amplifier.vss` defaults to `0.0` V; valid range: vss < vdd; logic-low and lower output rail.
- `chopper_stabilized_differential_amplifier.vcm` defaults to `0.45` V; valid range: vss <= vcm <= vdd; differential output common mode.
- `chopper_stabilized_differential_amplifier.vth` defaults to `0.45` V; valid range: finite real; control threshold.
- `chopper_stabilized_differential_amplifier.gain` defaults to `3.0` V/V; valid range: gain > 0; baseband differential gain.
- `chopper_stabilized_differential_amplifier.vos_amp` defaults to `0.02` V; valid range: finite real; internal post-chopper amplifier offset.
- `chopper_stabilized_differential_amplifier.lp_alpha` defaults to `0.25` 1; valid range: 0 < lp_alpha <= 1; event-driven low-pass update fraction.
- `chopper_stabilized_differential_amplifier.settle_tol` defaults to `0.02` V; valid range: settle_tol >= 0; residual convergence tolerance.
- `chopper_stabilized_differential_amplifier.settle_cycles` defaults to `3` edges; valid range: settle_cycles >= 1; consecutive qualified update count.
- `chopper_stabilized_differential_amplifier.tr` defaults to `1e-10` s; valid range: tr > 0; output smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_CHOP_DEMOD_BASEBAND_GAIN`: restore: Synchronous chopping and demodulation preserve gain times the differential input at baseband. Required traces: `time`, `vinp`, `vinn`, `chop_clk`, `voutp`, `voutn`.
- `P_INTERNAL_OFFSET_SUPPRESSION`: restore: The post-chopper amplifier offset alternates after demodulation and is attenuated by the retained low-pass state. Required traces: `time`, `vinp`, `vinn`, `chop_clk`, `offset_residual`.
- `P_EVENT_DRIVEN_LOWPASS`: restore: Outputs update toward each demodulated sample only on either chopper edge and remain retained between events. Required traces: `time`, `chop_clk`, `voutp`, `voutn`, `offset_residual`.
- `P_RESET_ENABLE_CLEAR`: restore: Active reset or disabled operation clears state, residual, and settled asynchronously. Required traces: `time`, `rst`, `enable`, `voutp`, `voutn`, `settled`, `offset_residual`.
- `P_HOLD_PRESERVES_STATE`: restore: Hold preserves every retained output across chopper edges. Required traces: `time`, `chop_clk`, `hold`, `voutp`, `voutn`, `settled`, `offset_residual`.
- `P_SETTLED_QUALIFICATION`: restore: Settled asserts only after the configured consecutive residual-qualified active updates. Required traces: `time`, `chop_clk`, `settled`, `offset_residual`.


The following canonical public behavior is normative for this derived form:

At every rising and falling `chop_clk` threshold crossing while enabled, not reset, and not held:

1. Multiply `vinp-vinn` by the current chopper polarity.
2. Add `vos_amp` inside the amplifier and apply `gain`.
3. Synchronously demodulate by the same polarity. The desired differential input therefore returns to baseband with gain, while amplifier offset alternates polarity.
4. Update the retained low-pass state by `lp_alpha` toward that demodulated sample.

Drive `voutp-voutn` from the retained low-pass state, centered on `vcm` and limited to the `vss`/`vdd` rails. Drive `offset_residual` to the retained state minus `gain*(vinp-vinn)` sampled at the most recent active update. Assert `settled` after `settle_cycles` consecutive active updates whose absolute residual is at most `settle_tol`.

Active-high `rst` or low `enable` asynchronously clears the retained differential state, residual, convergence count, and `settled`; the differential outputs return to zero around `vcm`. While `hold` is high, preserve all retained state and outputs exactly. Resume event-driven filtering on later chopper edges after hold is released.


## Modeling Constraints

- Both chopper polarities must update a retained low-pass state.
- The amplifier offset is inserted between chopping and synchronous demodulation.
- Reset and disable clear asynchronously; hold preserves retained state.
- No file I/O, final_step, current contributions, auto-zero storage, or trim servo.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `chopper_stabilized_differential_amplifier.va`, `chopper_gain_core.va`, `synchronous_lp_state.va`.
Every supplied `.va` file is editable; do not add or omit files.
