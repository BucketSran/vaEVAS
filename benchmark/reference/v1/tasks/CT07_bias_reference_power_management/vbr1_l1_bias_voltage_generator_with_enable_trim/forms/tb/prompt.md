# Task: vbr1_l1_bias_voltage_generator_with_enable_trim:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Bias voltage generator with enable/trim
- Domain: `voltage`
- Target artifact(s): `tb_bias_voltage_generator_with_enable_trim.scs`
- Supplied/reference support artifact(s): `bias_voltage_generator_with_enable_trim.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `bias_voltage_generator_with_enable_trim.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "bias_voltage_generator_with_enable_trim.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `bias_voltage_generator_with_enable_trim.va` declares module `bias_voltage_generator_with_enable_trim` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

Public schedule source: `tb_bias_voltage_generator_with_enable_trim.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.10 11.9n 0.10 12n 0.35 31.9n 0.35 32n 0.75 53.9n 0.75 54n 0.10 65.9n 0.10 66n 0.55 80n 0.55]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "bias_voltage_generator_with_enable_trim.va"

XDUT (clk rst vin out metric) bias_voltage_generator_with_enable_trim

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `disable_forces_bias_low`
- `trim_code_moves_bias_voltage`
- `metric_marks_enabled_bias`

## Public Behavioral Targets

- Treat logic low/high as 0 V/0.9 V with a 0.45 V threshold.
- Treat vin as the combined enable/trim control. vin below about 0.25 V disables the bias: out near 0 V and metric low.
- When enabled, map vin from about 0.25-0.90 V to a bounded bias target around 0.28-0.82 V.
- out should move smoothly toward the trim target on clocked updates, not jump to rails.
- Higher trim/control voltage should increase out monotonically.
- metric should be high only while the bias generator is enabled and driving a valid bias.

## Output Contract

Return exactly one source artifact named `tb_bias_voltage_generator_with_enable_trim.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Bias voltage generator with enable/trim (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Generate an enable-gated bias voltage with bounded trim response and disabled-state collapse.

Module name: `bias_voltage_generator_with_enable_trim`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module bias_voltage_generator_with_enable_trim(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is an enable/trim request voltage: low disables the bias, higher values select larger trim. out is the generated bias voltage. metric marks enabled bias operation.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
