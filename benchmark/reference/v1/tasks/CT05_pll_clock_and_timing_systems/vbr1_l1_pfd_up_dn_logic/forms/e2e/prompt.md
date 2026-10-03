# Task: vbr1_l1_pfd_up_dn_logic:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: PFD UP/DN logic
- Domain: `voltage`
- Target artifact(s): `pfd_updn.va`, `tb_pfd_reset_race_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `pfd_updn.va`, `tb_pfd_reset_race_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `pfd_updn.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "pfd_updn.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `pfd_updn.va` declares module `pfd_updn` with positional ports: `VDD`, `VSS`, `REF`, `DIV`, `UP`, `DN`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=300n maxstep=5n errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `ref`
- `div`
- `up`
- `dn`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `ref`
- `div`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "pfd_updn.va"

Vvdd (vdd 0) vsource dc=0.9 type=dc
Vvss (vss 0) vsource dc=0.0 type=dc

IDUT (vdd vss ref div up dn) pfd_updn vth=0.45 tedge=20p

tran tran stop=300n maxstep=5n errpreset=conservative
save ref div up dn
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `up_and_dn_pulses_exist`
- `overlap_window_is_bounded`
- `outputs_clear_after_race`

## Output Contract

Return exactly these source artifacts:

- `pfd_updn.va`
- `tb_pfd_reset_race_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## PFD UP/DN Reset-Race End-to-End Task

Write both the Verilog-A DUT and Spectre testbench for a PFD reset-race UP/DN generator.

The DUT module is `pfd_updn` with ports `VDD, VSS, REF, DIV, UP, DN`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Set `UP` high on a rising `REF` edge and set `DN` high on a rising `DIV` edge.
- If the opposite output is already high when an edge arrives, clear both outputs to model the reset-race behavior.
- Drive `UP` and `DN` as smoothed voltage-domain logic levels.

Required testbench behavior:
- Use close REF/DIV edge timing and a small maxstep so reset-race ordering is observable.
- Save `REF`, `DIV`, `UP`, and `DN`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly two files: `pfd_updn.va` and `tb_pfd_reset_race_ref.scs`.
