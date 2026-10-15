# Polyphase Quadrature Filter Macro Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `polyphase_quadrature_filter.va`:
  - Module `polyphase_quadrature_filter` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `i_out` (inout, electrical)
    - position 5: `q_out` (inout, electrical)
    - position 6: `amp_metric` (inout, electrical)
    - position 7: `phase_metric` (inout, electrical)
    - position 8: `valid` (inout, electrical)

## Public Parameter Contract

- `polyphase_quadrature_filter.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `polyphase_quadrature_filter.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `polyphase_quadrature_filter.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `polyphase_quadrature_filter.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `polyphase_quadrature_filter.alpha` defaults to `0.25`; valid range: finite; overrides alpha.
- `polyphase_quadrature_filter.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `polyphase_quadrature_filter.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_ON_RESET_OR_WHEN_ENABLE_IS`: restore: On reset or while disabled restore i_state=q_state=vcm, clear the update count, and drive amp_metric=phase_metric=valid=vss. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `amp_metric`, `phase_metric`, `valid`.
- `P_ON_EACH_RISING_CLK_EDGE_WHILE`: restore: Poll every tick=250ps and on each enabled rising clk edge update i_state=i_state+alpha*(vin-i_state). Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `amp_metric`, `phase_metric`, `valid`.
- `P_UPDATE_A_QUADRATURE_SAMPLED_STATE_USING`: restore: Save old_i before the I update and then update q_state=q_state+alpha*(old_i-q_state). Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `amp_metric`, `phase_metric`, `valid`.
- `P_DRIVE_I_OUT_AND_Q_OUT`: restore: Drive `i_out` and `q_out` around `vcm` from the two path states. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `amp_metric`, `phase_metric`, `valid`.
- `P_REPORT_A_BOUNDED_PHASE_ORDER_METRIC`: restore: After each enabled update drive amp_metric=min(vdd,2*abs(i_state-q_state)) and phase_metric=0.65V when i_state>=q_state, otherwise 0.25V. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `amp_metric`, `phase_metric`, `valid`.
- `P_ASSERT_VALID_AFTER_AT_LEAST_FOUR`: restore: Increment the enabled-update count once per detected rising edge and drive valid=vdd starting with update four, otherwise vss. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `amp_metric`, `phase_metric`, `valid`.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, clear path states, metrics, `valid`, and drive outputs to `vcm`.
- On each rising `clk` edge while enabled, update an in-phase sampled state from `vin`.
- Update a quadrature sampled state using the previous in-phase state so the Q output is phase-shifted relative to I.
- Drive `i_out` and `q_out` around `vcm` from the two path states.
- Report a bounded phase/order metric on `phase_metric` and an amplitude-balance metric on `amp_metric`.
- Assert `valid` after at least four enabled sample updates.
- The I and Q outputs must not collapse to identical waveforms during enabled operation.

Poll controls every `tick = 250 ps` and detect rising `clk` edges from adjacent
polls. Initialize both states to `vcm`. On each enabled rising edge save
`old_i=i_state`, then update

`i_state = i_state + alpha*(vin-i_state)`

`q_state = q_state + alpha*(old_i-q_state)`.

Drive `i_out=i_state` and `q_out=q_state` with `tr` smoothing. After the update,
drive `amp_metric = min(vdd,2*abs(i_state-q_state))` and drive `phase_metric`
to 0.65 V when `i_state >= q_state`, otherwise 0.25 V. Assert `valid=vdd`
starting with the fourth enabled update. Reset or disable restores both states
to `vcm`, clears the update count, and drives both metrics and `valid` to vss.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `polyphase_quadrature_filter.va`.
Every supplied `.va` file is editable; do not add or omit files.
