# Task: vbr1_l1_capacitive_weighted_sar_feedback_dac:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Data Converter Models
- Base function: Capacitive/weighted SAR feedback DAC
- Domain: `voltage`
- Target artifact(s): `cdac_cal.va`
- Supplied/reference support artifact(s): `tb_cdac_cal_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `cdac_cal.va` declares module `cdac_cal` with positional ports: `VDD`, `VSS`, `CLK`, `D9`, `D8`, `D7`, `D6`, `D5`, `D4`, `D3`, `D2`, `D1`, `D0`, `CAL0`, `CAL1`, `VDAC_P`, `VDAC_N`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=68n maxstep=20p
```

The release harness expects these exact public scalar observables:

- `CLK`
- `CAL0`
- `CAL1`
- `VDAC_P`
- `VDAC_N`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `binary_code_sets_nominal_dac_level`
- `calibration_bits_shift_feedback_level`
- `differential_outputs_move_complementarily`

## Output Contract

Return exactly one source artifact named `cdac_cal.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Implement a pure voltage-domain behavioral 10-bit capacitive feedback DAC for a
SAR ADC.

Public port roles:

- `VDD`, `VSS`: supply/reference nodes.
- `CLK`: sampling clock input.
- `D9`...`D0`: binary DAC control inputs, with `D9` as MSB and `D0` as LSB.
- `CAL0`, `CAL1`: redundant calibration control inputs.
- `VDAC_P`, `VDAC_N`: complementary differential voltage outputs.

Public functional contract:

- On each rising transition of `CLK`, sample `D9`...`D0`, `CAL0`, and `CAL1`
  against the mid-supply logic threshold.
- Convert `D9`...`D0` into an unsigned 10-bit `main_code`.
- Convert the calibration inputs into `cal_code = CAL0 + 2*CAL1`.
- For this benchmark, model the redundant calibration contribution as
  `effective_code = main_code + 32*cal_code`.
- Drive complementary outputs around a 0.45 V common-mode under the public
  0.9 V supply. The intended differential behavior is
  `VDAC_P - VDAC_N = 0.6 * ((effective_code / 1023.0) - 0.5)`.
- Higher `effective_code` should raise `VDAC_P` relative to `VDAC_N`; lower
  `effective_code` should lower it.
- Use smooth voltage transitions for the output levels.

Avoid current-domain contributions, transistor-level devices, AC/noise
analysis, and KCL/KVL solver assumptions.
