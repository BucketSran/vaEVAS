# Task: vbr1_l2_cppll_tracking_and_frequency_step_reacquire_flow:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: PLL Clock and Timing Systems
- Base function: CPPLL tracking and frequency-step reacquire flow
- Domain: `voltage`
- Target artifact(s): `cppll_timer_ref.va`, `ref_step_clk.va`, `tb_cppll_freq_step_reacquire_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for CPPLL tracking and frequency-step reacquire flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `cppll_timer_ref.va`, `ref_step_clk.va`, `tb_cppll_freq_step_reacquire_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `cppll_timer_ref.va`, `ref_step_clk.va` must be co-located with the generated Spectre testbench.
- Include each generated Verilog-A file exactly with a matching `ahdl_include "<file>.va"` line in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

This row is a CPPLL frequency-step reacquire flow. It must show a closed timing
loop, not just two unrelated clocks:

1. Reference step:
   - Use the public reference-clock source to create an early reference
     frequency and a later stepped frequency.

2. Loop tracking:
   - Drive `dco_clk` from a voltage-domain behavioral oscillator controlled by
     the loop state.
   - Drive `fb_clk` as the feedback clock that tracks the reference after loop
     settling.
   - Expose `vctrl_mon` as a bounded loop-control monitor.

3. Lock behavior:
   - Show that the loop can be locked or nearly tracking before the reference
     step.
   - Allow a visible disturbance after the frequency step.
   - Reacquire lock in the late transient window and track the new reference
     cadence.

The expected public relation is: reference step -> temporary tracking
disturbance -> bounded control response -> late-window feedback/reference
tracking with `lock` high.

## Output Contract

Return exactly these source artifacts:

- `cppll_timer_ref.va`
- `ref_step_clk.va`
- `tb_cppll_freq_step_reacquire_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `cppll_timer_ref`.

Create a voltage-domain charge-pump style PLL (CPPLL) behavioral
model in Verilog-A with a behavioral DCO timing loop, then produce a minimal Spectre transient testbench
that demonstrates unlock and reacquire behavior after a reference-frequency
step.

This L2 task is intentionally stronger than the steady
`vbr1_l2_pll_timing_slice`: it must show pre-step lock, disturbance-induced
unlock or lock drop, and late-window relock to the new reference frequency.

Behavioral intent:

- one reference clock input `ref_clk`
- one divided feedback clock output `fb_clk`
- one oscillator clock output `dco_clk`
- one monitor node `vctrl_mon` that reflects the loop control voltage
- one lock indicator output `lock`
- the loop should first lock to an initial reference, lose lock after a
  moderate reference-frequency change, then reacquire and track the new late
  frequency

Implementation constraints:

- pure voltage-domain Verilog-A only
- portable voltage-domain behavioral Verilog-A syntax
- use `@(timer(...))` for the DCO timing loop
- `fb_clk`, `dco_clk`, and `lock` should be driven as voltage outputs
- use the public `ref_step_clk` source artifact to create the reference step
- `ref_clk`, `fb_clk`, `lock`, and `vctrl_mon` must appear in the waveform CSV

Minimum simulation goal:

- the generated testbench should step the reference clock from 50 MHz to about
  51.28 MHz during the transient
- `lock` should show a pre-step lock event and at least one post-step relock
  event after the disturbance
- the late-window `fb_clk` frequency should match the stepped reference within a
  few percent
- `vctrl_mon` should stay bounded by the supply rails throughout the transient

Expected behavior:
- PLL should achieve lock before disturbance (lock goes high)
- After disturbance, PLL should re-lock within reasonable time
- Late frequency ratio (ref_period/fb_period) should be close to 1.0 when locked
Ports:
- `VDD`: inout electrical
- `VSS`: inout electrical
- `ref_clk`: input electrical
- `fb_clk`: output electrical
- `dco_clk`: output electrical
- `vctrl_mon`: output electrical
- `lock`: output electrical
