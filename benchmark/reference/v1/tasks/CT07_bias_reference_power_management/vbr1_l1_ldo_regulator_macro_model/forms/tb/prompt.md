# Task: vbr1_l1_ldo_regulator_macro_model:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: LDO regulator macro model
- Domain: `voltage`
- Target artifact(s): `tb_ldo_regulator_macro_model.scs`
- Supplied/reference support artifact(s): `ldo_regulator_macro_model.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `ldo_regulator_macro_model.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "ldo_regulator_macro_model.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_ldo_regulator_macro_model.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.10 17.9n 0.10 18n 0.80 43.9n 0.80 44n 0.25 65.9n 0.25 66n 0.65 80n 0.65]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "ldo_regulator_macro_model.va"

XDUT (clk rst vin out metric) ldo_regulator_macro_model

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

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

Return exactly one source artifact named `tb_ldo_regulator_macro_model.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### LDO regulator macro model (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

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
