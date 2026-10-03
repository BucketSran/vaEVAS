# Task: vbr1_l1_digital_phase_accumulator_with_modulo_wrap:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Digital phase accumulator with modulo wrap
- Domain: `voltage`
- Target artifact(s): `phase_accumulator_timer_wrap_ref.va`, `tb_phase_accumulator_timer_wrap_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `phase_accumulator_timer_wrap_ref.va`, `tb_phase_accumulator_timer_wrap_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `phase_accumulator_timer_wrap_ref.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "phase_accumulator_timer_wrap_ref.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `phase_accumulator_timer_wrap_ref.va` declares module `phase_accumulator_timer_wrap_ref` with positional ports: `VDD`, `VSS`, `clk_out`, `phase_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=75n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `clk_out`
- `phase_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "phase_accumulator_timer_wrap_ref.va"

Vvdd (VDD 0) vsource dc=0.9 type=dc
Vvss (VSS 0) vsource dc=0.0 type=dc

IDUT (VDD VSS clk_out phase_out) phase_accumulator_timer_wrap_ref

tran tran stop=75n maxstep=20p errpreset=conservative
save clk_out phase_out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `phase_accumulator_timer_wrap`

## Output Contract

Return exactly these source artifacts:

- `phase_accumulator_timer_wrap_ref.va`
- `tb_phase_accumulator_timer_wrap_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

This entry is scoped as an ADPLL/NCO phase-timing primitive, not as a generic digital-logic benchmark. Model the wrapped phase state and derived voltage-domain timing outputs that a behavioral PLL loop would consume.

Write an ADPLL-style wrapped phase accumulator and matching transient testbench.

Module name: `phase_accumulator_timer_wrap_ref`.

Required DUT behavior:

- Ports are exactly `VDD`, `VSS`, `clk_out`, `phase_out`.
- Advance the internal phase state on a periodic `@(timer(...))` schedule.
- Wrap phase manually at 1.0 rather than relying on unsupported analog
  integration.
- Drive `phase_out` as a voltage-domain monitor of the wrapped phase state.
- Derive `clk_out` from the wrapped phase state so clock edges are observable
  across multiple wraps.
- Use voltage contributions and `transition()` only.

Required testbench behavior:

- Provide supply rails and save plain scalar observables `clk_out` and
  `phase_out`.
- Run long enough to show at least three phase wraps and corresponding clock
  transitions.
