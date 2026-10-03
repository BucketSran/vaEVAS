# Loop Filter Abstraction Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `loop_filter_abstraction.va`:
  - Module `loop_filter_abstraction` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

## Public Parameter Contract

- `loop_filter_abstraction.tr` defaults to `1e-10` s; valid range: tr > 0; sets rise and fall smoothing for out and metric.
- `loop_filter_abstraction.deadband` defaults to `0.05` V; valid range: deadband >= 0; sets the sampled error magnitude below which proportional and integral state hold.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RESET_STATE`: restore: Active reset restores the proportional state to 0.45 V, the step to 0.20 V, the integral residual and accepted-update count to zero, and metric to 0 V. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_DEADBAND_HOLD`: restore: At a rising clk crossing, an error vin - 0.45 V whose magnitude does not exceed deadband produces no proportional, integral, step, or count update. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_SIGNED_UPDATE`: restore: Each accepted positive error increases the proportional state by the current step and each accepted negative error decreases it, while the integral residual accumulates 0.04 times the sampled error. Required traces: `time`, `clk`, `vin`, `out`.
- `P_STEP_HALVING`: restore: The proportional step halves after every accepted update, producing successively smaller proportional corrections for equal-sign errors. Required traces: `time`, `clk`, `vin`, `out`.
- `P_LOCK_COUNT_METRIC`: restore: Metric remains low for fewer than four accepted updates and is 0.9 V once the accepted-update count reaches four; reset clears it. Required traces: `time`, `clk`, `rst`, `vin`, `metric`.
- `P_PROPORTIONAL_CLAMP`: restore: The proportional state is clamped to 0.05 V through 0.85 V before the accumulated integral residual is added to form out. Required traces: `time`, `clk`, `vin`, `out`.


The following canonical public behavior is normative for this derived form:

The module is a sampled/event-driven PLL loop-filter abstraction that approximates proportional and integral loop-control trends without modeling a transistor-level or KCL/KVL RC network.

- Treat `clk` and `rst` as voltage-coded logic with a 0.45 V threshold.
- Interpret `vin` as a signed loop-error stimulus around 0.45 V.
- Initialize and reset the proportional state to `0.45 V`, the proportional step to `0.20 V`, the integral residual to `0`, the accepted-update count to `0`, and `metric` to `0 V`.
- On each rising `clk` crossing, compute `err = V(vin) - 0.45`.
- When reset is low and `abs(err) > deadband`, accept an update: increase the proportional state by the current step for positive `err`, decrease it by the current step for negative `err`, then accumulate `integral += 0.04 * err`.
- After each accepted update, halve the step and increment the accepted-update count.
- Clamp the proportional state to `[0.05 V, 0.85 V]`.
- Drive `out` from the proportional state plus the accumulated integral residual.
- Drive `metric` to `0.9 V` once the accepted-update count reaches `4`, otherwise keep it at `0 V`. Reset clears the count and metric.


## Modeling Constraints

- Use deterministic voltage-domain event-driven state updates and voltage contributions only.
- Do not use current contributions, ddt(), idt(), transistor-level devices, or validation-only observables.
- Do not encode a particular stimulus schedule, stop time, or checker sample window.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `loop_filter_abstraction.va`.
Every supplied `.va` file is editable; do not add or omit files.
