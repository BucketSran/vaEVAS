# Task: vbr1_l1_debounce_latch:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Comparator debounce latch
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `debounce_latch.va`, `dut_buggy.va`, `tb_debounce_latch_buggy.scs`, `tb_debounce_latch_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `debounce_latch.va` declares module `debounce_latch` with positional ports: `sig`, `rst_n`, `out`.
- `dut_buggy.va` declares module `debounce_latch` with positional ports: `sig`, `rst_n`, `out`.
- `dut_fixed.va` declares module `debounce_latch` with positional ports: `sig`, `rst_n`, `out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=140n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `sig`
- `rst_n`
- `out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `short_pulse_window_stays_low`
- `stable_high_window_latches_high`
- `reset_low_clears_state`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Comparator Debounce Latch Bugfix

Repair the provided Verilog-A comparator decision qualification latch. The DUT
has voltage-domain input `sig`, active-high reset release input `rst_n`, and
voltage-domain output `out`.

When reset is asserted low, clear the latched state. After reset is released,
only latch `out` high if the comparator-style `sig` decision rises above
threshold and stays high for the configured qualification interval. Short
glitches before the interval expires must not set the latch.

Keep the model purely voltage-domain and drive `out` with `transition`. Do not
use current contributions.
