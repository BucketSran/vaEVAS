# Task: vbr1_l1_dither_or_noise_like_deterministic_source:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Dither or noise-like deterministic source
- Domain: `voltage`
- Target artifact(s): `tb_noise_gen_ref.scs`
- Supplied/reference support artifact(s): `noise_gen.va`, `noise_gen_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `noise_gen.va`, `noise_gen_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include each supplied Verilog-A support file exactly with a matching `ahdl_include "<file>.va"` line in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `noise_gen.va` declares module `noise_gen` with positional ports: `vin_i`, `vout_o`.
- `noise_gen_ref.va` declares module `noise_gen` with positional ports: `vin_i`, `vout_o`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=500n maxstep=1n
```

The release harness expects these exact public scalar observables:

- `vin_i`
- `vout_o`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vin_i`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "noise_gen.va"
ahdl_include "noise_gen_ref.va"

IDUT (vin_i vout_o) noise_gen sigma=0.1 dt=0.5n

tran tran stop=500n maxstep=1n
save vin_i vout_o
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `noise_is_nontrivial`
- `noise_std_in_range`

## Public L1 Testbench Stimulus Contract

This TB row should expose deterministic noise-like variation:

- Drive the source input as a stable DC value.
- Instantiate the supplied deterministic noise-like source with public
  parameters that produce visible but bounded output variation.
- Run long enough to collect many update intervals.
- Save `vin_i` and `vout_o` exactly.

The expected public relation is: `vout_o` should not be stuck at a constant
value, and its variation should stay within the intended range. Do not generate
checker logic.

## Output Contract

Return exactly one source artifact named `tb_noise_gen_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Dither or noise-like deterministic source Testbench Companion

Write a Spectre transient testbench for the `Dither or noise-like deterministic source` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the public behavior checks
- include or instantiate the Verilog-A behavioral module under test
- satisfy the named behavior checks using only public waveforms and side outputs
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
