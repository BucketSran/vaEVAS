# Variable Gain Differential Amplifier Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `variable_gain_differential_amplifier.va`:
  - Module `variable_gain_differential_amplifier` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigctrl_p` (input, electrical)
    - position 3: `sigctrl_n` (input, electrical)
    - position 4: `sigout` (output, electrical)

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_DIFFERENTIAL_SIGNAL_AND_CONTROL`: restore: Use `V(sigin_p, sigin_n)` as signal input and `V(sigctrl_p, sigctrl_n)` as gain-control input. Required traces: `time`, `sigin_p`, `sigin_n`, `sigctrl_p`, `sigctrl_n`, `sigout`.
- `P_VARIABLE_GAIN_MIDPOINT`: restore: Drive the unclamped target as `2.0 * V(sigctrl_p, sigctrl_n) * V(sigin_p, sigin_n) + 0.2`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigctrl_p`, `sigctrl_n`, `sigout`.
- `P_OUTPUT_CLAMP`: restore: Clamp the final output target to the inclusive interval `[-0.4 V, 0.8 V]`. Required traces: `time`, `sigout`.


The following canonical public behavior is normative for this derived form:

Use `V(sigctrl_p, sigctrl_n)` as the gain-control voltage and `V(sigin_p, sigin_n)` as the signal input. Multiply the two differential voltages by a gain constant of 2.0, center the output around 0.2 V, and clamp the final target to -0.4 V through 0.8 V.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `variable_gain_differential_amplifier.va`.
Every supplied `.va` file is editable; do not add or omit files.
