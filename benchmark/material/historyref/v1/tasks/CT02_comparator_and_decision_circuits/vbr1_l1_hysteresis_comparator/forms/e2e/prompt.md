# Task: vbr1_l1_hysteresis_comparator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Hysteresis comparator
- Domain: `voltage`
- Target artifact(s): `cmp_hysteresis.va`, `tb_cmp_hysteresis_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `cmp_hysteresis.va`, `tb_cmp_hysteresis_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `cmp_hysteresis.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "cmp_hysteresis.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `cmp_hysteresis.va` declares module `cmp_hysteresis` with positional ports: `VINN`, `VINP`, `OUTN`, `OUTP`, `VSS`, `VDD`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=100p
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `out_p`
- `out_n`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `gnd`
- `vinp`
- `vinn`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cmp_hysteresis.va"

Vvdd (vdd 0) vsource dc=0.9 type=dc

IDUT (vinn vinp out_n out_p gnd vdd) cmp_hysteresis vhys=10m tedge=50p

tran tran stop=80n maxstep=100p
save vinp vinn out_p out_n
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `output_shows_hysteresis_window`
- `upward_and_downward_trip_points_are_separated`

## Output Contract

Return exactly these source artifacts:

- `cmp_hysteresis.va`
- `tb_cmp_hysteresis_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain differential comparator with hysteresis and one
Spectre transient testbench.

DUT requirements:

- use module `cmp_hysteresis` with the public uppercase formal ports listed
  above
- expose `vhys` as a real parameter with default `10e-3`
- drive `OUTP` high and `OUTN` low only after
  `V(VINP)-V(VINN) > +vhys/2`
- drive `OUTP` low and `OUTN` high only after
  `V(VINP)-V(VINN) < -vhys/2`
- hold the previous decision between the two thresholds
- use directional crossing events and rail-referenced `transition()` outputs

Testbench requirements:

- include `cmp_hysteresis.va` via `ahdl_include`
- use a 0.9 V supply and 0 V reference
- instantiate the DUT by positional ports on scalar nodes `vinn`, `vinp`,
  `out_n`, `out_p`, `gnd`, and `vdd`
- drive the differential input through both hysteresis thresholds so both
  output states and the hold region are observable
- run `tran tran stop=80n maxstep=100p`
- save exactly `vinp`, `vinn`, `out_p`, and `out_n`
