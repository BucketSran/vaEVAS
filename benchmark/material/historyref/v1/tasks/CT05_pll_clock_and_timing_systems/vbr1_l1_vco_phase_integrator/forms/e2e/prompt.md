# Task: vbr1_l1_vco_phase_integrator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: VCO phase integrator
- Domain: `voltage`
- Target artifact(s): `tb_vco_phase_integrator_ref.scs`, `vco_phase_integrator.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `tb_vco_phase_integrator_ref.scs`, `vco_phase_integrator.va`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `vco_phase_integrator.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "vco_phase_integrator.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `vco_phase_integrator.va` declares module `vco_phase_integrator` with positional ports: `vctrl`, `phase`, `clk`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=180n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vctrl`
- `phase`
- `clk`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vctrl`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "vco_phase_integrator.va"

XDUT (vctrl phase clk) vco_phase_integrator

tran tran stop=180n maxstep=500p
save vctrl phase clk
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `phase_span_covers_nearly_full_wrap`
- `clock_toggles_on_phase_wrap`
- `late_edge_rate_exceeds_early_edge_rate`

## Output Contract

Return exactly these source artifacts:

- `tb_vco_phase_integrator_ref.scs`
- `vco_phase_integrator.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## VCO Phase Integrator End-to-End Task

Write both the Verilog-A DUT and Spectre testbench for a voltage-controlled VCO phase integrator with periodic phase updates.

The DUT module is `vco_phase_integrator` with ports `vctrl, phase, clk`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Use a 1 ns timer update and increment phase by `0.03 + 0.09 * V(vctrl)` at each update.
- Wrap phase at 1.0 and toggle `clk` on each wrap.
- Drive both `phase` and `clk` through `transition()`.

Required testbench behavior:
- Drive `vctrl` through low and higher-control intervals so the late clock edge rate is faster than the early edge rate.
- Save `vctrl`, `phase`, and `clk` across a long transient.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly two files: `vco_phase_integrator.va` and `tb_vco_phase_integrator_ref.scs`.
