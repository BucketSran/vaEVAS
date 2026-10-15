# Deterministic Jittered Clock Source Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `deterministic_jittered_clock.va`:
  - Module `deterministic_jittered_clock` (entry)
    - position 0: `jitter_en` (input, electrical)
    - position 1: `seed0` (input, electrical)
    - position 2: `seed1` (input, electrical)
    - position 3: `seed2` (input, electrical)
    - position 4: `seed3` (input, electrical)
    - position 5: `seed4` (input, electrical)
    - position 6: `seed5` (input, electrical)
    - position 7: `seed6` (input, electrical)
    - position 8: `seed7` (input, electrical)
    - position 9: `clk_out` (output, electrical)

## Public Parameter Contract

- `deterministic_jittered_clock.vdd` defaults to `0.9` V; valid range: vdd > 0; sets the voltage-coded clk_out high level.
- `deterministic_jittered_clock.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets the threshold for jitter_en and all seed inputs.
- `deterministic_jittered_clock.tr` defaults to `2e-11` s; valid range: tr > 0; sets clk_out rise and fall smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_NOMINAL_CLOCK`: restore: With jitter_en below vth, clk_out has a constant 10 ns half-period and 20 ns full period. Required traces: `time`, `jitter_en_default`, `clk_out_default`, `jitter_en_override`, `clk_out_override`.
- `P_SEED_DECODE`: restore: Seed7:seed0 is sampled through vth only at each output transition and interpreted as one unsigned eight-bit seed with seed7 as MSB; seed changes affect the next scheduled half-period, not the already scheduled current edge. Required traces: `time`, `jitter_en_default`, `seed0_default`, `seed1_default`, `seed2_default`, `seed3_default`, `seed4_default`, `seed5_default`, `seed6_default`, `seed7_default`, `clk_out_default`, `jitter_en_override`, `seed0_override`, `seed1_override`, `seed2_override`, `seed3_override`, `seed4_override`, `seed5_override`, `seed6_override`, `seed7_override`, `clk_out_override`.
- `P_EDGE_MODULATION`: restore: For edge index k, the next half-period is 10 ns plus (((seed + 3*k) modulo 5) minus 2) times 0.8 ns. Required traces: `time`, `jitter_en_default`, `seed0_default`, `seed1_default`, `seed2_default`, `seed3_default`, `seed4_default`, `seed5_default`, `seed6_default`, `seed7_default`, `clk_out_default`, `jitter_en_override`, `seed0_override`, `seed1_override`, `seed2_override`, `seed3_override`, `seed4_override`, `seed5_override`, `seed6_override`, `seed7_override`, `clk_out_override`.
- `P_REPEATABILITY`: restore: With constant seed and enable history, the modulo-5 half-period sequence repeats every five output transitions; identical input histories also produce the same edge-time sequence on repeated runs. Required traces: `time`, `jitter_en_default`, `seed0_default`, `seed1_default`, `seed2_default`, `seed3_default`, `seed4_default`, `seed5_default`, `seed6_default`, `seed7_default`, `clk_out_default`, `jitter_en_override`, `seed0_override`, `seed1_override`, `seed2_override`, `seed3_override`, `seed4_override`, `seed5_override`, `seed6_override`, `seed7_override`, `clk_out_override`.
- `P_TIMING_BOUNDS`: restore: Every jitter-enabled half-period remains within the public modulation range from 8.4 ns through 11.6 ns. Required traces: `time`, `jitter_en_default`, `clk_out_default`, `jitter_en_override`, `clk_out_override`.
- `P_OUTPUT_LEVELS`: restore: clk_out uses 0 V and vdd levels with finite transition smoothing set by tr. Required traces: `time`, `vdd_ref_default`, `tr_ps_ref_default`, `clk_out_default`, `vdd_ref_override`, `tr_ps_ref_override`, `clk_out_override`.


The following canonical public behavior is normative for this derived form:

- Generate `clk_out` as a 0-to-`vdd` deterministic clock.
- With `jitter_en` low, use a constant 20 ns period, i.e. a 10 ns nominal half-period.
- With `jitter_en` high, sample `seed7:seed0` through `vth` at each output transition, interpret it as an unsigned seed, and apply repeatable edge-to-edge half-period modulation.
- A seed input change affects the next half-period computed after the next output transition; it must not move an already scheduled current edge.
- For edge index `k`, update the next half-period as `10 ns + (((seed + 3*k) % 5) - 2) * 0.8 ns`.
- With a constant seed and `jitter_en` state, the resulting modulo-5 half-period sequence repeats every five output transitions.
- Keep every resulting full clock period bounded and repeatable for the same seed.


## Modeling Constraints

- AMS role: deterministic jittered clock stimulus source for repeatable timing-margin and aperture-stress checks.
- Use deterministic timer-driven state and no random distribution functions.
- Decode seed inputs only through vth and preserve repeatability for identical input histories.
- Do not add undeclared ports, random state, or validation-only timing cases.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `deterministic_jittered_clock.va`.
Every supplied `.va` file is editable; do not add or omit files.
