# Task: vbr1_l1_bang_bang_phase_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Bang-bang phase detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_bbpd_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `bbpd_ref` with positional ports: `data`, `clk`, `retimed_data`, `up`, `down`.
- `dut_fixed.va` declares module `bbpd_ref` with positional ports: `data`, `clk`, `retimed_data`, `up`, `down`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=60n maxstep=50p
```

The release harness expects these exact public scalar observables:

- `data`
- `clk`
- `retimed_data`
- `up`
- `down`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `up_pulse_when_data_lags_clock`
- `down_pulse_when_data_leads_clock`
- `outputs_clear_on_next_clock_edge`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Bang-bang phase detector Bugfix

Repair the supplied buggy Verilog-A implementation for `Bang-bang phase detector`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
