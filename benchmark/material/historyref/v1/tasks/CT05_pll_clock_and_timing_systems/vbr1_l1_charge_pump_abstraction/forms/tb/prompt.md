# Task: vbr1_l1_charge_pump_abstraction:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Voltage-domain charge-pump control abstraction
- Domain: `voltage`
- Target artifact(s): `tb_charge_pump_abstraction.scs`
- Supplied/reference support artifact(s): `charge_pump_abstraction.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `charge_pump_abstraction.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "charge_pump_abstraction.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `charge_pump_abstraction.va` declares module `charge_pump_abstraction` with positional ports: `clk`, `rst`, `up`, `dn`, `vctrl`, `metric`.

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `up`
- `dn`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "charge_pump_abstraction.va"

XDUT (clk rst up dn vctrl metric) charge_pump_abstraction

tran tran stop=80n maxstep=0.5n
save clk rst up dn vctrl metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `up_pulse_increases_control`
- `down_pulse_decreases_control`
- `control_voltage_clamped`

## Output Contract

Return exactly one source artifact named `tb_charge_pump_abstraction.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Voltage-domain charge-pump control abstraction (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

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
