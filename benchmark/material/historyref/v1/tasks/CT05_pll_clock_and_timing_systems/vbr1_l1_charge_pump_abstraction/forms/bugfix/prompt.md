# Task: vbr1_l1_charge_pump_abstraction:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Voltage-domain charge-pump control abstraction
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_charge_pump_abstraction.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `charge_pump_abstraction` with positional ports: `clk`, `rst`, `up`, `dn`, `vctrl`, `metric`.
- `dut_fixed.va` declares module `charge_pump_abstraction` with positional ports: `clk`, `rst`, `up`, `dn`, `vctrl`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `up`
- `dn`
- `vctrl`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `up_pulse_increases_control`
- `down_pulse_decreases_control`
- `control_voltage_clamped`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Voltage-domain charge-pump control abstraction (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

Behavioral intent:

Represent UP/DN pulse effects as a voltage-domain control-node update without current contributions.

Module name: `charge_pump_abstraction`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module charge_pump_abstraction(clk, rst, up, dn, vctrl, metric);
input clk, rst, up, dn;
output vctrl, metric;
electrical clk, rst, up, dn, vctrl, metric;
```

Signal contract:

clk, rst, up, and dn are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. A sampled UP-only pulse increases vctrl, a sampled DN-only pulse decreases vctrl, simultaneous or absent pulses hold the control voltage, and rst high resets vctrl to midscale. metric is a voltage-coded UP/DN/hold status observable.

Saved waveform columns:

```text
clk rst up dn vctrl metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
