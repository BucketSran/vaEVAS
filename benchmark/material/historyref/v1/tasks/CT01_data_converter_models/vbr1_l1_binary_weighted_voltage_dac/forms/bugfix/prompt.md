# Task: vbr1_l1_binary_weighted_voltage_dac:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: Simple 4-bit binary-coded DAC
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `simple_binary_voltage_dac_4b.va`, `tb_simple_binary_voltage_dac_4b_buggy.scs`, `tb_simple_binary_voltage_dac_4b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `simple_binary_voltage_dac_4b` with positional ports: `code_0`, `code_1`, `code_2`, `code_3`, `vref`, `vss`, `aout`.
- `dut_fixed.va` declares module `simple_binary_voltage_dac_4b` with positional ports: `code_0`, `code_1`, `code_2`, `code_3`, `vref`, `vss`, `aout`.
- `simple_binary_voltage_dac_4b.va` declares module `simple_binary_voltage_dac_4b` with positional ports: `code_0`, `code_1`, `code_2`, `code_3`, `vref`, `vss`, `aout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=165n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `code_0`
- `code_1`
- `code_2`
- `code_3`
- `aout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `all_16_binary_codes_match_ideal_levels`
- `code_bits_match_expected_sampled_sequence`
- `monotonic_output`
- `zero_and_full_scale_codes_reach_references`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_simple_binary_voltage_dac_4b_bugfix

Repair the provided Verilog-A simple 4-bit binary-coded DAC behavior model.
The circuit uses four binary-weighted voltage-domain code inputs `code_0`
through `code_3`, references `vref` and `vss`, and voltage-domain output `aout`.

Interpret the four code inputs as a 4-bit unsigned code. Drive `aout` linearly
from `vss` to `vref` so code `0` maps to `vss` and code `15` maps to `vref`.
Intermediate codes must be monotonic and use the ideal `code / 15` endpoint
scaling.

Keep the model purely voltage-domain and drive `aout` with `transition`. Do not
use current contributions.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
