# Task: vbr1_l1_trim_calibration_controller:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Trim-voltage generator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_cdac_calibration_buggy.scs`, `tb_cdac_calibration_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `cdac_calibration` with positional ports: `clk`, `rst`, `err`, `trim`.
- `dut_fixed.va` declares module `cdac_calibration` with positional ports: `clk`, `rst`, `err`, `trim`.

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

- `reset_restores_nominal_trim`
- `high_err_windows_increase_trim`
- `low_err_windows_decrease_trim`
- `trim_stays_within_clamp_range`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Trim-voltage generator bugfix

The provided voltage-domain CDAC calibration trim controller updates its trim in
the wrong direction when the error input is asserted. Fix the controller so
rising clock edges increase the trim when `err` is high and decrease it when
`err` is low.

The fixed module must be named `cdac_calibration` and use electrical ports
`clk`, `rst`, `err`, and `trim`. Reset should restore `trim` to the nominal
mid-scale value. The trim output must remain bounded in the valid calibration
range and should be driven as a smoothed voltage.

Use voltage contributions and event-driven state updates. Do not use current
contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
