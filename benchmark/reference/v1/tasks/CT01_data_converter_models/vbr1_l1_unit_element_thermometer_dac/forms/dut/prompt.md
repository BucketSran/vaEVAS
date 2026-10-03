# Task: vbr1_l1_unit_element_thermometer_dac:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Data Converter Models
- Base function: Unit-element thermometer DAC
- Domain: `voltage`
- Target artifact(s): `thermometer_dac_15seg.va`
- Supplied/reference support artifact(s): `tb_thermometer_dac_15seg_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `thermometer_dac_15seg.va` declares module `thermometer_dac_15seg` with positional ports: `seg0`, `seg1`, `seg2`, `seg3`, `seg4`, `seg5`, `seg6`, `seg7`, `seg8`, `seg9`, `seg10`, `seg11`, `seg12`, `seg13`, `seg14`, `vref`, `vss`, `aout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=180n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `seg0`
- `seg1`
- `seg2`
- `seg3`
- `seg4`
- `seg5`
- `seg6`
- `seg7`
- `seg8`
- `seg9`
- `seg10`
- `seg11`
- `seg12`
- `seg13`
- `seg14`
- `aout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `safe_time_output_levels_match_15_segment_thermometer_count`
- `full_scale_counts_all_15_segments`
- `output_is_monotonic_across_programmed_segment_counts`

## Output Contract

Return exactly one source artifact named `thermometer_dac_15seg.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_thermometer_dac_15seg_dut

Write a pure voltage-domain Verilog-A DUT for a 4-bit-equivalent, 15-segment
unit-element thermometer DAC.

Return exactly one complete Verilog-A file named
`thermometer_dac_15seg.va`.

## Module Contract

Implement this module declaration and port order:

```verilog
module thermometer_dac_15seg(
    seg0, seg1, seg2, seg3, seg4, seg5, seg6, seg7,
    seg8, seg9, seg10, seg11, seg12, seg13, seg14,
    vref, vss, aout
);
```

All ports are `electrical`. `seg0` through `seg14`, `vref`, and `vss` are
inputs; `aout` is the output. Segment pins use 0 V / 0.9 V logic levels with a
threshold parameter near 0.45 V.

## Required Behavior

- Treat every segment pin above threshold as one active unit element.
- Count all fifteen unary segment pins, including `seg14`.
- Drive `aout` from `vss` to `vref` with endpoint scaling:

```text
aout = vss + (vref - vss) * active_segment_count / 15
```

- Smooth the output contribution with `transition`.
- Stay in the pure voltage-domain behavioral subset. Do not use current
  contributions, `ddt`, or `idt`.

## Public Evaluation Observables

The public checker samples `aout` away from input transitions for active segment
counts 0, 1, 2, 7, 14, and 15. It checks monotonicity, endpoint scaling, and
full-scale behavior when all fifteen segments are active.
