# Task: vbr1_l1_dither_or_noise_like_deterministic_source:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Dither or noise-like deterministic source
- Domain: `voltage`
- Target artifact(s): `noise_gen.va`, `noise_gen_ref.va`, `tb_noise_gen_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `noise_gen.va`, `noise_gen_ref.va`, `tb_noise_gen_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `noise_gen.va`, `noise_gen_ref.va` must be co-located with the generated Spectre testbench.
- Include each generated Verilog-A file exactly with a matching `ahdl_include "<file>.va"` line in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

## Output Contract

Return exactly these source artifacts:

- `noise_gen.va`
- `noise_gen_ref.va`
- `tb_noise_gen_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `noise_gen`.

Create a voltage-domain Gaussian noise generator in Verilog-A,
then produce a minimal EVAS-compatible Spectre testbench and run a smoke simulation.

Behavioral intent:

- one analog input `vin_i` and one analog output `vout_o`
- parameter `sigma` (real, in Volts) controls the noise standard deviation
- output = input + zero-mean Gaussian noise: `vout_o = vin_i + sigma * $rdist_normal(...)`
- the noise is independent and added on every time step
- use `transition(...)` to drive `vout_o`

Implementation constraints:

- pure voltage-domain Verilog-A only
- EVAS-compatible syntax
- `$rdist_normal` is the correct EVAS-compatible call for Gaussian samples
- `vin_i` and `vout_o` must appear in the waveform CSV

Minimum simulation goal:

- DC input at 1.0 V, sigma=0.1 V, run for 500 ns with maxstep=0.5 ns
- `vout_o` mean must be within ±0.5 V of `vin_i` (zero-mean noise)
- noise standard deviation (std of `vout_o - vin_i`) must be between 0.01 V and 0.5 V
- `vout_o` must not be identical to `vin_i` (noise must be non-trivial)

Ports:
- `vin_i`: input electrical
- `vout_o`: output electrical
