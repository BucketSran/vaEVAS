# Task: vbr1_l1_sar_logic:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: SAR logic
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_sar_logic_4b_buggy.scs`, `tb_sar_logic_4b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `sar_logic_4b` with positional ports: `VDD`, `VSS`, `CLKS`, `DCOMP`, `DP_DAC_3`, `DP_DAC_2`, `DP_DAC_1`, `DP_DAC_0`, `RDY`.
- `dut_fixed.va` declares module `sar_logic_4b` with positional ports: `VDD`, `VSS`, `CLKS`, `DCOMP`, `DP_DAC_3`, `DP_DAC_2`, `DP_DAC_1`, `DP_DAC_0`, `RDY`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=260n maxstep=1n
```

The release harness expects these exact public scalar observables:

- `clks`
- `dcomp`
- `rdy`
- `dp_dac_3`
- `dp_dac_2`
- `dp_dac_1`
- `dp_dac_0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `rdy_low_after_third_decision_edge_at_126ns`
- `rdy_high_after_fourth_decision_edge_at_176ns`
- `final_dac_code_matches_comparator_sequence_1010`
- `rdy_clears_when_next_conversion_starts`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_sar_logic_4b_bugfix

The provided voltage-domain 4-bit SAR logic has an end-of-conversion timing bug:
it asserts `RDY` one clock before the LSB trial has been decided. Fix the
controller so `RDY` remains low through the MSB, next-bit, and LSB-trial setup
states, then asserts only after all four comparator decisions have been applied.

The fixed module must be named `sar_logic_4b` and use electrical ports `VDD`,
`VSS`, `CLKS`, `DCOMP`, `DP_DAC_3`, `DP_DAC_2`, `DP_DAC_1`, `DP_DAC_0`, and
`RDY`. It should start each conversion by trying the MSB, step through bits
3-to-0 on rising `CLKS` crossings, drive DAC decision outputs with voltage
contributions referenced to `VSS`, and clear `RDY` when the next conversion
starts.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
