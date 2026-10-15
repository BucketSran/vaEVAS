# Task: vbr1_l1_successive_approximation_calibration_search_fsm:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Successive-approximation calibration/search FSM
- Domain: `voltage`
- Target artifact(s): `successive_approximation_calibration_search_fsm.va`, `tb_successive_approximation_calibration_search_fsm.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `successive_approximation_calibration_search_fsm.va`, `tb_successive_approximation_calibration_search_fsm.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `successive_approximation_calibration_search_fsm.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "successive_approximation_calibration_search_fsm.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `successive_approximation_calibration_search_fsm.va` declares module `successive_approximation_calibration_search_fsm` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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
ahdl_include "successive_approximation_calibration_search_fsm.va"

XDUT (clk rst vin out metric) successive_approximation_calibration_search_fsm

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `step_size_halves`
- `trim_direction_follows_error`
- `done_after_search_window`

## Output Contract

Return exactly these source artifacts:

- `successive_approximation_calibration_search_fsm.va`
- `tb_successive_approximation_calibration_search_fsm.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Successive-approximation calibration/search FSM (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

Behavioral intent:

Run a clocked successive-approximation trim search with halving step size and completion flag.

Module name: `successive_approximation_calibration_search_fsm`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module successive_approximation_calibration_search_fsm(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is a signed calibration decision stimulus around 0.45 V. out is the bounded SAR trial trim voltage. metric is a voltage-coded done flag asserted after the search window.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
