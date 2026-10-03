# Task: vbr1_l1_uvlo_brownout_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: UVLO/brownout detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_uvlo_brownout_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `uvlo_brownout_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `uvlo_brownout_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `power_good_has_hysteresis`
- `brownout_clears_power_good`
- `recovery_requires_upper_threshold`

## Public Behavioral Targets

- Treat vin as the supply. Assert power-good out high only after vin rises above about 0.65 V.
- Keep out high while vin remains between about 0.55 V and 0.65 V; this is the UVLO hysteresis band.
- Clear out low on brownout below about 0.55 V or reset.
- metric should distinguish fault/lockout from the valid power-good state.

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### UVLO/brownout detector (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

Behavioral intent:

Implement an undervoltage-lockout power-good detector with separate rising and falling supply thresholds.

Module name: `uvlo_brownout_detector`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module uvlo_brownout_detector(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the supply monitor voltage. out is a power-good voltage with UVLO hysteresis. metric is high during undervoltage/brownout and low during power-good operation.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
