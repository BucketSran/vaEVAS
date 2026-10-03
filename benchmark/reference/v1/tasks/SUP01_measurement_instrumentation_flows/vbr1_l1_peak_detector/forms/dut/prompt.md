# Task: vbr1_l1_peak_detector:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Measurement Instrumentation Flows
- Base function: Peak detector
- Domain: `voltage`
- Target artifact(s): `peak_detector.va`
- Supplied/reference support artifact(s): `tb_peak_detector_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `peak_detector.va` declares module `peak_detector` with positional ports: `vin`, `rst`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=180n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `rst`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `first_peak_is_held`
- `reset_clears_peak`
- `second_peak_updates_to_larger_value`

## Output Contract

Return exactly one source artifact named `peak_detector.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_peak_detector_dut

Write a pure voltage-domain Verilog-A module for a resettable peak detector.

The DUT module is `peak_detector` with ports `vin, rst, vout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Track the maximum observed `vin` value using a timer-sampled internal peak.
- High `rst` clears the peak to 0 V.
- Drive `vout` from the peak value through `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `peak_detector.va`.
