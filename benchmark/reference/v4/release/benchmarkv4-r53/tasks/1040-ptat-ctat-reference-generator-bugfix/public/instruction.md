# PTAT CTAT Reference Generator Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `ptat_ctat_reference_generator.va`:
  - Module `ptat_ctat_reference_generator` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

## Public Parameter Contract

- `ptat_ctat_reference_generator.tr` defaults to `1e-10` s; valid range: tr > 0; sets output and metric transition smoothing.
- `ptat_ctat_reference_generator.vth` defaults to `0.45` V; valid range: 0 < vth < 0.9; sets clk and rst logic threshold.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RESET_REFERENCE`: restore: Reset initializes out to 0.45 V and metric to 0 V until a valid rising-clock update. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_INPUT_CLAMP`: restore: Each rising clk update with reset inactive samples vin and clamps the temperature/control value to 0 V through 0.9 V. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_PTAT_TREND`: restore: Metric reports the PTAT branch 0.18 V plus 0.34 times the clamped sampled input and therefore increases monotonically with vin. Required traces: `time`, `clk`, `vin`, `metric`.
- `P_CTAT_PTAT_AVERAGE`: restore: Out is the equal-weight average of PTAT = 0.18 V + 0.34*vin_clamped and CTAT = 0.78 V - 0.34*vin_clamped. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_REFERENCE_BOUNDS`: restore: Out remains within the public 0 V through 0.9 V voltage range with finite transition smoothing. Required traces: `time`, `out`.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals.
- Treat `vin` as a normalized temperature/control voltage in the 0 V to 0.9 V range.
- Reset should initialize `out` to 0.45 V and drive `metric` to 0 V until
  valid updates occur.
- On each rising `clk` crossing with reset low, clamp the sampled temperature
  input to `[0 V, 0.9 V]`.
- Compute the PTAT branch as `0.18 V + 0.34 * vin_clamped` and the CTAT branch
  as `0.78 V - 0.34 * vin_clamped`.
- Drive the reference output as the equal-weight branch average:
  `out = 0.5 * ptat + 0.5 * ctat`.
- Drive `metric` as the PTAT branch voltage so it increases with the
  temperature/control input.
- Clamp the driven `out` voltage to the public 0 V to 0.9 V voltage-domain
  range.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


## Modeling Constraints

- Use deterministic sampled voltage-domain behavior.
- Do not use current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.
- Do not add undeclared ports, validation hooks, or simulator-specific side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `ptat_ctat_reference_generator.va`.
Every supplied `.va` file is editable; do not add or omit files.
