# Task: vbr1_l1_bandgap_reference_macro_model:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Bandgap reference macro model
- Domain: `voltage`
- Target artifact(s): `bandgap_reference_macro_model.va`
- Supplied/reference support artifact(s): `tb_bandgap_reference_macro_model.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `bandgap_reference_macro_model.va` declares module `bandgap_reference_macro_model` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `startup_threshold_blocks_reference`
- `reference_settles_near_nominal`
- `line_regulation_is_bounded`

## Public Behavioral Targets

- Treat logic low/high as 0 V/0.9 V with a 0.45 V threshold.
- Treat vin as a sub-1 V supply ramp. Start regulation above about 0.65 V and reset below about 0.50 V.
- During reset or below-threshold supply, hold out near 0 V and keep metric low.
- After startup, regulate out near a supply-insensitive reference around 0.55 V.
- During higher supply, keep the reference nearly constant instead of supply-tracking.
- During brownout, reset out near 0 V and mark the output invalid.

## Output Contract

Return exactly one source artifact named `bandgap_reference_macro_model.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Bandgap reference macro model (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Model a startup-gated voltage reference that settles to a supply-insensitive reference after VDD exceeds the startup threshold.

Module name: `bandgap_reference_macro_model`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module bandgap_reference_macro_model(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is the public sub-1 V supply-ramp stimulus. out is the generated reference voltage, held low below the roughly 0.65 V startup threshold and regulated near 0.55 V after startup. metric is a voltage-coded reference-valid observable, low near 0 V before startup/brownout and high near 0.9 V while valid.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
