# Task: vbr1_l1_trim_calibration_controller:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Trim-voltage generator
- Domain: `voltage`
- Target artifact(s): `cdac_calibration.va`
- Supplied/reference support artifact(s): `tb_cdac_calibration_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `cdac_calibration.va` declares module `cdac_calibration` with positional ports: `clk`, `rst`, `err`, `trim`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=220n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `err`
- `trim`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `reset_trim_near_0p45`
- `trim_increments_decrements_and_recovers`
- `trim_clamped_to_0p05_0p85`

## Output Contract

Return exactly one source artifact named `cdac_calibration.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Trim-voltage generator DUT

Write a pure voltage-domain Verilog-A module for a trim-voltage generator.

The DUT module is `cdac_calibration` with ports `clk, rst, err, trim`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Implement a voltage-domain calibration accumulator that generates a trim voltage, not a capacitor-array CDAC model.
- Initialize `trim` to 0.45 V and reset it to 0.45 V when `rst` is high at a rising `clk` edge.
- When reset is low, add 0.06 V on high `err`, subtract 0.06 V on low `err`, clamp to 0.05 V to 0.85 V, and drive through `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Review caveat: Historical naming can suggest a full capacitor-array CDAC; this public task is only the voltage-domain calibration accumulator that drives `trim`.

Return exactly one complete Verilog-A file named `cdac_calibration.va`.
