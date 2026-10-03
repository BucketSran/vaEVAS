# Task: vbr1_l1_thermometer_code_decoder:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: Thermometer-code decoder
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_thermometer_decoder_guarded_buggy.scs`, `tb_thermometer_decoder_guarded_ref.scs`, `thermometer_decoder_guarded.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `thermometer_decoder_guarded` with positional ports: `b0`, `b1`, `en`, `th0`, `th1`, `th2`, `th3`.
- `dut_fixed.va` declares module `thermometer_decoder_guarded` with positional ports: `b0`, `b1`, `en`, `th0`, `th1`, `th2`, `th3`.
- `thermometer_decoder_guarded.va` declares module `thermometer_decoder_guarded` with positional ports: `b0`, `b1`, `en`, `th0`, `th1`, `th2`, `th3`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=120n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `b0`
- `b1`
- `en`
- `th0`
- `th1`
- `th2`
- `th3`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `enable_low_forces_all_outputs_low`
- `enabled_codes_1_2_3_are_cumulative_thermometer`
- `th3_remains_low_for_two_bit_guarded_decode`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_thermometer_decoder_guarded_bugfix

Repair the provided Verilog-A guarded thermometer decoder. The DUT has
voltage-domain binary inputs `b0` and `b1`, enable input `en`, and
voltage-domain outputs `th0` through `th3`.

When `en` is low, all thermometer outputs must be low. When `en` is high,
decode the two-bit code into cumulative thermometer outputs: code `1` drives
only `th0`, code `2` drives `th0` and `th1`, and code `3` drives `th0`, `th1`,
and `th2`. `th3` remains low for this guarded two-bit task.

Keep the model purely voltage-domain and drive outputs with `transition`. Do
not use current contributions.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
