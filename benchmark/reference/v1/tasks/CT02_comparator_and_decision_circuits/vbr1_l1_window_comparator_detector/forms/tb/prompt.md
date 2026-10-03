# Task: vbr1_l1_window_comparator_detector:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Window comparator/detector
- Domain: `voltage`
- Target artifact(s): `tb_window_comparator_ref.scs`
- Supplied/reference support artifact(s): `window_comparator_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `window_comparator_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "window_comparator_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `window_comparator_ref.va` declares module `window_comparator_ref` with positional ports: `VDD`, `VSS`, `vin`, `out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `vin`
- `out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "window_comparator_ref.va"

Vvdd (VDD 0) vsource dc=0.9 type=dc
Vvss (VSS 0) vsource dc=0.0 type=dc

IDUT (VDD VSS vin out) window_comparator_ref

tran tran stop=90n maxstep=20p errpreset=conservative
save vin out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `true_window_comparator`

## Output Contract

Return exactly one source artifact named `tb_window_comparator_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Window comparator/detector Testbench Companion

Write a Spectre transient testbench for the `Window comparator/detector` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include `window_comparator_ref.va` via `ahdl_include`
- instantiate `window_comparator_ref` with scalar nodes `VDD`, `VSS`, `vin`,
  and `out`
- include `tran tran stop=90n maxstep=20p errpreset=conservative`
- save `vin` and `out`
- drive `vin` with a triangular PWL waveform that visits below `0.3 V`,
  between `0.3 V` and `0.6 V`, above `0.6 V`, then back through the window
- make `out` high only inside the `0.3 V < vin < 0.6 V` window and low
  outside it on both the rising and falling ramps
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
