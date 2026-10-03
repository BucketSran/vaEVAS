# Task: vbr1_l1_calibration_deadband_controller:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Calibration deadband controller
- Domain: `voltage`
- Target artifact(s): `calibration_deadband_controller.va`
- Supplied/reference support artifact(s): `tb_calibration_deadband_controller.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `calibration_deadband_controller.va` declares module `calibration_deadband_controller` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `trim_holds_inside_deadband`
- `trim_moves_for_large_error`
- `trim_clamped_to_range`

## Output Contract

Return exactly one source artifact named `calibration_deadband_controller.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Calibration deadband controller (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Update a bounded trim code only when the signed error is outside a deadband.

Module name: `calibration_deadband_controller`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module calibration_deadband_controller(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is a signed calibration error around 0.45 V. out is a bounded trim voltage that holds inside the deadband and steps only outside it. metric is high only on an accepted trim update.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
