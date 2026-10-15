# Task: vbr1_l1_power_on_reset_detector:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Power-on-reset detector
- Domain: `voltage`
- Target artifact(s): `power_on_reset_detector.va`
- Supplied/reference support artifact(s): `tb_power_on_reset_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `power_on_reset_detector.va` declares module `power_on_reset_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `reset_asserted_below_supply_threshold`
- `release_delay_after_power_good`
- `brownout_reasserts_reset`

## Public Behavioral Targets

- Treat vin as a supply ramp. Keep out reset-asserted high while reset input is high or vin is below about 0.62 V.
- After vin is power-good and reset is released, wait about four rising clock updates before deasserting out low.
- During the release delay, metric may indicate partial release; after release, metric should be high.
- If supply falls below threshold or reset asserts again, immediately assert out high and clear the release delay.

## Output Contract

Return exactly one source artifact named `power_on_reset_detector.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Power-on-reset detector (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Detect a supply ramp, hold reset asserted through a release-delay window, and reassert reset on brownout.

Module name: `power_on_reset_detector`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module power_on_reset_detector(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the supply-ramp/brownout stimulus. out is an active-high reset voltage that releases only after a power-good delay and reasserts on brownout. metric marks released/reset-valid status.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
