# Task: vbr1_l2_adpll_lock_ratio_hop_timer_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: PLL Clock and Timing Systems
- Base function: ADPLL lock/ratio-hop/timer flow
- Domain: `voltage`
- Target artifact(s): `tb_adpll_ratio_hop_ref.scs`
- Supplied/reference support artifact(s): `adpll_ratio_hop_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for ADPLL lock/ratio-hop/timer flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `adpll_ratio_hop_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "adpll_ratio_hop_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `adpll_ratio_hop_ref.va` declares module `adpll_ratio_hop_ref` with positional ports: `VDD`, `VSS`, `ref_clk`, `ratio_ctrl`, `fb_clk`, `vout`, `vctrl_mon`, `lock`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=5u maxstep=5n
```

The release harness expects these exact public scalar observables:

- `ref_clk`
- `ratio_ctrl`
- `fb_clk`
- `vout`
- `vctrl_mon`
- `lock`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `ref_clk`
- `ratio_ctrl`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "adpll_ratio_hop_ref.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

IDUT (vdd vss ref_clk ratio_ctrl fb_clk vout vctrl_mon lock) adpll_ratio_hop_ref f_center=240e6 freq_step_hz=5e6 f_min=120e6 f_max=420e6 code_min=0 code_max=63 code_center=32 code_init=24 ratio_min=2 ratio_max=16 tedge=200p lock_tol=2n lock_count_target=5

tran tran stop=5u maxstep=5n
save ref_clk ratio_ctrl fb_clk vout vctrl_mon lock
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `adpll_ratio_hop_pre_ratio`
- `adpll_ratio_hop_post_ratio`
- `adpll_ratio_hop_feedback_divider_relation`
- `adpll_ratio_hop_feedback_tracks_reference`
- `adpll_ratio_hop_lock_reacquired`

## Public L2 Behavior Contract

This row is an ADPLL lock and ratio-hop flow. The testbench must expose the
pre-hop ratio, post-hop ratio, and reacquired lock:

1. Drive `ref_clk` as a stable 0 V/0.9 V periodic reference clock.
2. Drive `ratio_ctrl` initially near 4 and step it later to near 6.
3. Run long enough before the step for `lock` to assert and the pre-hop
   `vout`/`ref_clk` ratio to be visible.
4. Run long enough after the step for the loop to reacquire lock and the
   post-hop ratio to be visible.
5. Save `ref_clk ratio_ctrl fb_clk vout vctrl_mon lock` exactly.

Do not generate checker logic; the evaluator derives the pre-hop ratio,
post-hop ratio, `vout`/`fb_clk` divider relation, `fb_clk`/`ref_clk` tracking,
and lock reacquisition from these saved waveforms. The supplied DUT is expected
to use feedback timing in its control and lock decision, so the testbench should
not replace `fb_clk` with an independent source.

## Output Contract

Return exactly one source artifact named `tb_adpll_ratio_hop_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## ADPLL lock/ratio-hop/timer flow Testbench Companion

Write a Spectre transient testbench for the `ADPLL lock/ratio-hop/timer flow` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the checker
- include or instantiate the Verilog-A behavioral module under test
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
