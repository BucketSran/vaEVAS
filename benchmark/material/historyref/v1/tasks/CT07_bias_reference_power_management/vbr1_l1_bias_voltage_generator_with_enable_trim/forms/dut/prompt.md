# Task: vbr1_l1_bias_voltage_generator_with_enable_trim:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Bias voltage generator with enable/trim
- Domain: `voltage`
- Target artifact(s): `bias_voltage_generator_with_enable_trim.va`
- Supplied/reference support artifact(s): `tb_bias_voltage_generator_with_enable_trim.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `bias_voltage_generator_with_enable_trim.va` declares module `bias_voltage_generator_with_enable_trim` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `out`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `disable_forces_bias_low`
- `trim_code_moves_bias_voltage`
- `metric_marks_enabled_bias`

## Public Behavioral Targets

- Treat logic low/high as 0 V/0.9 V with a 0.45 V threshold.
- Treat vin as the combined enable/trim control. vin below about 0.25 V disables the bias: out near 0 V and metric low.
- When enabled, map vin from about 0.25-0.90 V to a bounded bias target around 0.28-0.82 V.
- out should move smoothly toward the trim target on clocked updates, not jump to rails.
- Higher trim/control voltage should increase out monotonically.
- metric should be high only while the bias generator is enabled and driving a valid bias.

## Output Contract

Return exactly one source artifact named `bias_voltage_generator_with_enable_trim.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Bias voltage generator with enable/trim (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Generate an enable-gated bias voltage with bounded trim response and disabled-state collapse.

Module name: `bias_voltage_generator_with_enable_trim`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module bias_voltage_generator_with_enable_trim(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is an enable/trim request voltage: low disables the bias, higher values select larger trim. out is the generated bias voltage. metric marks enabled bias operation.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
