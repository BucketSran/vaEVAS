# Task: vbr1_l1_lfsr_prbs_generator:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: PRBS stimulus/dither generator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_prbs7_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `prbs7_ref` with positional ports: `clk`, `rst_n`, `en`, `serial_out`, `state_0`, `state_1`, `state_2`, `state_3`, `state_4`, `state_5`, `state_6`.
- `dut_fixed.va` declares module `prbs7_ref` with positional ports: `clk`, `rst_n`, `en`, `serial_out`, `state_0`, `state_1`, `state_2`, `state_3`, `state_4`, `state_5`, `state_6`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=120n maxstep=50p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst_n`
- `en`
- `serial_out`
- `state_0`
- `state_1`
- `state_2`
- `state_3`
- `state_4`
- `state_5`
- `state_6`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `reset_loads_nonzero_seed`
- `enabled_clock_edges_advance_lfsr_state`
- `feedback_uses_prbs7_taps`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# PRBS stimulus/dither generator Bugfix

Repair the supplied buggy Verilog-A implementation for the `PRBS stimulus/dither
generator`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
