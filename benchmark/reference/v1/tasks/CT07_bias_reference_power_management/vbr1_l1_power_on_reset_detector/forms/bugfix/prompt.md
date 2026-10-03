# Task: vbr1_l1_power_on_reset_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Power-on-reset detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_power_on_reset_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `power_on_reset_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `power_on_reset_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Power-on-reset detector (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

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
