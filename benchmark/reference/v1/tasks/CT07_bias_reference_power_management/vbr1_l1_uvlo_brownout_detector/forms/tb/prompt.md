# Task: vbr1_l1_uvlo_brownout_detector:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: UVLO/brownout detector
- Domain: `voltage`
- Target artifact(s): `tb_uvlo_brownout_detector.scs`
- Supplied/reference support artifact(s): `uvlo_brownout_detector.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `uvlo_brownout_detector.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "uvlo_brownout_detector.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `uvlo_brownout_detector.va` declares module `uvlo_brownout_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

Public schedule source: `tb_uvlo_brownout_detector.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.50 9.9n 0.50 10n 0.70 27.9n 0.70 28n 0.58 42.9n 0.58 43n 0.52 54.9n 0.52 55n 0.62 66.9n 0.62 67n 0.68 80n 0.68]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "uvlo_brownout_detector.va"

XDUT (clk rst vin out metric) uvlo_brownout_detector

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `power_good_has_hysteresis`
- `brownout_clears_power_good`
- `recovery_requires_upper_threshold`

## Public Behavioral Targets

- Treat vin as the supply. Assert power-good out high only after vin rises above about 0.65 V.
- Keep out high while vin remains between about 0.55 V and 0.65 V; this is the UVLO hysteresis band.
- Clear out low on brownout below about 0.55 V or reset.
- metric should distinguish fault/lockout from the valid power-good state.

## Output Contract

Return exactly one source artifact named `tb_uvlo_brownout_detector.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### UVLO/brownout detector (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

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
