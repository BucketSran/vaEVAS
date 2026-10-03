# Task: vbr1_l1_clocked_adc_quantizer:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: Clocked ADC quantizer
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_flash_adc_3b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `flash_adc_3b` with positional ports: `VDD`, `VSS`, `VIN`, `CLK`, `DOUT2`, `DOUT1`, `DOUT0`.
- `dut_fixed.va` declares module `flash_adc_3b` with positional ports: `VDD`, `VSS`, `VIN`, `CLK`, `DOUT2`, `DOUT1`, `DOUT0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=820n maxstep=2n
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `dout2`
- `dout1`
- `dout0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `all_eight_codes_reachable`
- `code_monotonic_with_input`
- `top_code_saturates_at_7`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Clocked ADC quantizer Bugfix

Repair the supplied buggy Verilog-A implementation for `Clocked ADC quantizer`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
