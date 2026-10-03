# Task: vbr1_l1_ptat_ctat_reference_generator:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: PTAT/CTAT reference generator
- Domain: `voltage`
- Target artifact(s): `tb_ptat_ctat_reference_generator.scs`
- Supplied/reference support artifact(s): `ptat_ctat_reference_generator.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `ptat_ctat_reference_generator.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "ptat_ctat_reference_generator.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `ptat_ctat_reference_generator.va` declares module `ptat_ctat_reference_generator` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "ptat_ctat_reference_generator.va"

XDUT (clk rst vin out metric) ptat_ctat_reference_generator

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `ptat_branch_monotonic_with_temperature`
- `ctat_compensation_flattens_reference`
- `reference_common_mode_bounded`

## Public Behavioral Targets

- Treat vin as a voltage-coded temperature/control value in the 0-0.9 V range.
- Build opposing PTAT and CTAT internal trends; metric should expose a PTAT-like increasing branch.
- Combine PTAT and CTAT so out stays near a bounded reference around mid-scale instead of strongly tracking vin.
- Reset should initialize out near mid-scale and keep metric low until valid updates occur.
- Clamp out and metric to the public 0-0.9 V voltage-domain range.

## Output Contract

Return exactly one source artifact named `tb_ptat_ctat_reference_generator.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### PTAT/CTAT reference generator (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Generate PTAT and CTAT branch abstractions and combine them into a temperature-compensated voltage reference.

Module name: `ptat_ctat_reference_generator`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module ptat_ctat_reference_generator(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is a normalized temperature-code voltage. out is the compensated reference voltage. metric exposes the PTAT branch trend as a public observable without revealing hidden checker code.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
