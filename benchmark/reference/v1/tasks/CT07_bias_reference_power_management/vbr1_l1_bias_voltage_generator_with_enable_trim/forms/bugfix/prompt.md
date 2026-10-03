# Task: vbr1_l1_bias_voltage_generator_with_enable_trim:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Bias voltage generator with enable/trim
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_bias_voltage_generator_with_enable_trim.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `bias_voltage_generator_with_enable_trim` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `bias_voltage_generator_with_enable_trim` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Bias voltage generator with enable/trim (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

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
