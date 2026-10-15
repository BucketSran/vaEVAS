# Task: vbr1_l1_ldo_regulator_macro_model:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: LDO regulator macro model
- Domain: `voltage`
- Target artifact(s): `ldo_regulator_macro_model.va`
- Supplied/reference support artifact(s): `tb_ldo_regulator_macro_model.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `ldo_regulator_macro_model.va` declares module `ldo_regulator_macro_model` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `regulated_output_bounded`
- `load_step_causes_droop`
- `output_recovers_after_load_reduction`

## Public Behavioral Targets

- Treat vin as a voltage-coded load/disturbance control, not as the regulator supply rail.
- Regulated out should remain bounded near about 0.60 V under light load.
- Higher load/disturbance should cause visible droop from the nominal target, not rail-to-rail tracking.
- After a load reduction, out should recover gradually toward the regulation target over clocked updates.
- metric should be high when regulation error is small and lower during droop/recovery.
- Keep all outputs in the 0-0.9 V voltage-domain range.

## Output Contract

Return exactly one source artifact named `ldo_regulator_macro_model.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### LDO regulator macro model (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Approximate an LDO output-voltage macro model with bounded load droop and recovery behavior.

Module name: `ldo_regulator_macro_model`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module ldo_regulator_macro_model(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is a bounded load/disturbance-control voltage. out is the regulated output-voltage macro-model response. metric marks regulation error/recovery quality.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
