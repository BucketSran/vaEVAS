# Task: vbr1_l2_cppll_tracking_and_frequency_step_reacquire_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: PLL Clock and Timing Systems
- Base function: CPPLL tracking and frequency-step reacquire flow
- Domain: `voltage`
- Target artifact(s): `tb_cppll_freq_step_reacquire_ref.scs`
- Supplied/reference support artifact(s): `cppll_timer_ref.va`, `ref_step_clk.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for CPPLL tracking and frequency-step reacquire flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `cppll_timer_ref.va`, `ref_step_clk.va` will be co-located with the generated testbench by the evaluation harness.
- Include each supplied Verilog-A support file exactly with a matching `ahdl_include "<file>.va"` line in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `cppll_timer_ref.va` declares module `cppll_timer_ref` with positional ports: `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.
- `ref_step_clk.va` declares module `ref_step_clk` with positional ports: `VDD`, `VSS`, `CLK`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=6u maxstep=5n errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `ref_clk`
- `fb_clk`
- `dco_clk`
- `vctrl_mon`
- `lock`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cppll_timer_ref.va"
ahdl_include "ref_step_clk.va"

VDD_SRC (VDD 0) vsource type=dc dc=0.9
VSS_SRC (VSS 0) vsource type=dc dc=0

XREF (VDD VSS ref_clk) ref_step_clk period_pre=20n period_post=19.5n t_switch=2u tedge=100p
XDUT (VDD VSS ref_clk fb_clk dco_clk vctrl_mon lock) cppll_timer_ref div_ratio=8 f_center=800e6 kvco_hz_per_v=220e6 f_min=500e6 f_max=1.2e9 kp=2.5e6 ki=8.0e4 vctrl_init=0.45 tedge=1n lock_tol=1.2n lock_count_target=4

tran tran stop=6u maxstep=5n errpreset=conservative
save ref_clk fb_clk dco_clk vctrl_mon lock
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `cppll_reacquires_after_reference_step`
- `late_window_tracks_new_reference`
- `vctrl_stays_bounded`

## Public L2 Behavior Contract

This row is a CPPLL frequency-step reacquire flow. The testbench must expose a
reference step and enough time for the supplied loop to settle again:

1. Include both public support files `cppll_timer_ref.va` and `ref_step_clk.va`.
2. Instantiate the reference-step source and the CPPLL DUT with the public port
   order.
3. Run a transient long enough to include pre-step tracking, post-step
   disturbance, and late-window reacquisition.
4. Save `ref_clk fb_clk dco_clk vctrl_mon lock` exactly.

The expected public relation is: `ref_clk` changes cadence, `fb_clk` and
`dco_clk` temporarily deviate, `vctrl_mon` remains bounded, and `lock` is high
again in the late window. Do not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_cppll_freq_step_reacquire_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## CPPLL tracking and frequency-step reacquire flow Testbench Companion

Write a Spectre transient testbench for the `CPPLL tracking and frequency-step reacquire flow` behavioral
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
