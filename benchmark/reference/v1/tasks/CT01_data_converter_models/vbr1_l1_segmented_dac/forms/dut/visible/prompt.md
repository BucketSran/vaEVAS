# Task: vbr1_l1_segmented_dac:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Data Converter Models
- Base function: Segmented DAC
- Domain: `voltage`
- Target artifact(s): `segmented_dac.va`
- Supplied/reference support artifact(s): `tb_segmented_dac_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `segmented_dac.va` declares module `segmented_dac` with positional ports: `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=150n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `b0`
- `b1`
- `t0`
- `t1`
- `t2`
- `aout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `safe_time_output_levels_match_expected_segmented_codes`
- `output_is_monotonic_across_programmed_codes`
- `thermometer_segment_weight_is_four_lsb_steps`

## Output Contract

Return exactly one source artifact named `segmented_dac.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_segmented_dac_dut

Write a pure voltage-domain Verilog-A module named `segmented_dac`.

The module has electrical inputs `b0`, `b1`, `t0`, `t1`, `t2` and electrical
output `aout`. Treat `b0`/`b1` as binary LSB controls and `t0`/`t1`/`t2` as
thermometer segment controls. With `vref=0.72`, each binary LSB contributes
`vref/12`, and each thermometer segment contributes four LSB steps. Drive
`aout` with a smoothed voltage transition and use voltage contributions only.

Return exactly one complete Verilog-A file named `segmented_dac.va`.
