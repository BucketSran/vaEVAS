# Settling Time Measurement Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `settling_time_measurement_tb.va`:
  - Module `settling_time_measurement_tb` (entry)
    - position 0: `step` (input, electrical)
    - position 1: `vout` (output, electrical)
    - position 2: `done` (output, electrical)

## Public Parameter Contract

- `settling_time_measurement_tb.tr` defaults to `3e-10` s; valid range: finite real; use tr >= 0 for physical transition smoothing; sets smoothing for vout and done.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_INITIAL_ZERO_STATE`: restore: The settling-response state initializes to 0 V and vout begins from that state. Required traces: `time`, `vout`.
- `P_FIRST_ORDER_UPDATE`: restore: At each 1 ns update, the response advances by 0.04 times the difference between step and its previous value. Required traces: `time`, `step`, `vout`.
- `P_RESPONSE_CONVERGENCE`: restore: For a constant input step, vout approaches the step value monotonically without overshoot under the public recurrence. Required traces: `time`, `step`, `vout`.
- `P_DONE_TIME_GATE`: restore: Done remains low through 120 ns regardless of the response level. Required traces: `time`, `vout`, `done`.
- `P_DONE_SETTLED_GATE`: restore: After 120 ns, done is high only while the internal settled response is above 0.75 V and otherwise remains low. Required traces: `time`, `step`, `vout`, `done`.


The following canonical public behavior is normative for this derived form:

This is a measurement-helper DUT task, not a testbench-generation task.
Return only the Verilog-A source file `settling_time_measurement_tb.va`.

Use a 1 ns timer update to model a first-order settling response:

```text
y += 0.04 * (V(step) - y)
```

Drive `vout` from the internal state `y` using `tr` for transition smoothing.
Drive `done` low before the settling
boundary and high only after the simulation time is beyond 120 ns and the
settled state is above 0.75 V. The validation applies a step input, runs past
the 120 ns boundary, and saves `step`, `vout`, and `done`.

Use voltage-coded logic with a 0.45 V threshold where applicable. Drive high
logic outputs near 0.9 V and low outputs near 0 V. Keep the model pure
behavioral Verilog-A.

Do not generate a Spectre `.scs` file despite the historical `_tb` filename.
Do not use transistor-level devices,
AC/noise analysis, current contributions, waveform files, validation artifacts, or
simulator side channels.


## Modeling Constraints

- Implement the public 1 ns discrete-time first-order settling response and completion flag as a DUT measurement helper.
- Use smoothed voltage contributions only.
- Do not emit a Spectre deck or use current contributions, transistor-level devices, waveform files, validation artifacts, or simulator-specific side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `settling_time_measurement_tb.va`.
Every supplied `.va` file is editable; do not add or omit files.
