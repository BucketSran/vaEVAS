# Task: vbr1_l1_bandgap_reference_macro_model:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Bandgap reference macro model
- Domain: `voltage`
- Target artifact(s): `bandgap_reference_macro_model.va`, `tb_bandgap_reference_macro_model.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `bandgap_reference_macro_model.va`, `tb_bandgap_reference_macro_model.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `bandgap_reference_macro_model.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "bandgap_reference_macro_model.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `bandgap_reference_macro_model.va` declares module `bandgap_reference_macro_model` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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
ahdl_include "bandgap_reference_macro_model.va"

XDUT (clk rst vin out metric) bandgap_reference_macro_model

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `startup_threshold_blocks_reference`
- `reference_settles_near_nominal`
- `line_regulation_is_bounded`

## Public Behavioral Targets

- Treat logic low/high as 0 V/0.9 V with a 0.45 V threshold.
- Treat vin as a sub-1 V supply ramp. Start regulation above about 0.65 V and reset below about 0.50 V.
- During reset or below-threshold supply, hold out near 0 V and keep metric low.
- After startup, regulate out near a supply-insensitive reference around 0.55 V.
- During higher supply, keep the reference nearly constant instead of supply-tracking.
- During brownout, reset out near 0 V and mark the output invalid.

## Output Contract

Return exactly these source artifacts:

- `bandgap_reference_macro_model.va`
- `tb_bandgap_reference_macro_model.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Bandgap reference macro model (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

Behavioral intent:

Model a startup-gated voltage reference that settles to a supply-insensitive reference after VDD exceeds the startup threshold.

Module name: `bandgap_reference_macro_model`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module bandgap_reference_macro_model(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the public supply-ramp stimulus. out is the generated reference voltage, held low below startup threshold and regulated near nominal after startup. metric is a voltage-coded reference-valid observable.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
