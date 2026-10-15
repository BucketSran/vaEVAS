# Task: vbr1_l1_pfd_up_dn_logic:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: PFD UP/DN logic
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_pfd_reset_race_buggy.scs`, `tb_pfd_reset_race_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `pfd_updn` with positional ports: `VDD`, `VSS`, `REF`, `DIV`, `UP`, `DN`.
- `dut_fixed.va` declares module `pfd_updn` with positional ports: `VDD`, `VSS`, `REF`, `DIV`, `UP`, `DN`.

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

## Public Behavior Checks

- `ref_leads_window_has_short_up_pulses_and_low_dn`
- `div_leads_window_has_short_dn_pulses_and_low_up`
- `both_high_overlap_fraction_is_bounded`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## PFD UP/DN Reset-Race Bugfix

The provided voltage-domain phase-frequency detector has a reset-race bug: one
input-edge branch does not clear both UP and DN when the opposite state is
already asserted. Fix the detector so either edge order produces only a short
UP or DN pulse and never leaves both outputs high.

The fixed module must be named `pfd_updn` and use electrical ports `VDD`, `VSS`,
`REF`, `DIV`, `UP`, and `DN`. A rising `REF` edge should set UP; a rising `DIV`
edge should set DN. Whenever both states would be high, both outputs must reset
low in the same event update.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
