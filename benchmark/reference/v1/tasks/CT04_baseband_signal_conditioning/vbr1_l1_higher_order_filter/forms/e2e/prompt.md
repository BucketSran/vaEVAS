# Task: vbr1_l1_higher_order_filter:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Higher-order filter
- Domain: `voltage`
- Target artifact(s): `higher_order_filter.va`, `tb_higher_order_filter.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `higher_order_filter.va`, `tb_higher_order_filter.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `higher_order_filter.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "higher_order_filter.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `higher_order_filter.va` declares module `higher_order_filter` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

Public schedule source: `tb_higher_order_filter.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 8n 0.45 12n 0.9 28n 0.9 31n 0.45 37n 0.45 42n 0.1 58n 0.1 61n 0.45 67n 0.45 72n 0.85 80n 0.85]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "higher_order_filter.va"

XDUT (clk rst vin out metric) higher_order_filter

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `two_filter_states`
- `step_response_is_smoothed`
- `reset_clears_states`

## Output Contract

Return exactly these source artifacts:

- `higher_order_filter.va`
- `tb_higher_order_filter.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Higher-order filter (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

Behavioral intent:

Approximate a second-order low-pass response with two sampled internal filter states.

Module name: `higher_order_filter`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module higher_order_filter(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is an analog voltage stimulus. out is the bounded conditioned voltage. metric exposes the filter/settling internal response.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
