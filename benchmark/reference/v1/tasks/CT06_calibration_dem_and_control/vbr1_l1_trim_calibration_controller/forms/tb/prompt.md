# Task: vbr1_l1_trim_calibration_controller:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Trim-voltage generator
- Domain: `voltage`
- Target artifact(s): `tb_cdac_calibration_ref.scs`
- Supplied/reference support artifact(s): `cdac_calibration.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `cdac_calibration.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "cdac_calibration.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `err`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cdac_calibration.va"

XDUT (clk rst err trim) cdac_calibration

tran tran stop=220n maxstep=500p
save clk rst err trim
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `reset_trim_near_0p45`
- `trim_increments_decrements_and_recovers`
- `trim_clamped_to_0p05_0p85`

## Output Contract

Return exactly one source artifact named `tb_cdac_calibration_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Trim-voltage generator testbench

Write a Spectre testbench for a trim-voltage generator DUT.

The DUT module is `cdac_calibration` with ports `clk, rst, err, trim`. All ports are electrical; digital-control ports use 0/0.9 V logic levels. The candidate DUT file will be available as `cdac_calibration.va`; include it with `ahdl_include` and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- Implement a voltage-domain calibration accumulator that generates a trim voltage, not a capacitor-array CDAC model.
- Initialize `trim` to 0.45 V and reset it to 0.45 V when `rst` is high at a rising `clk` edge.
- When reset is low, add 0.06 V on high `err`, subtract 0.06 V on low `err`, clamp to 0.05 V to 0.85 V, and drive through `transition()`.

Stimulus and observability requirements:
- Use a 20 ns period clock, reset release near 16 ns, and an `err` waveform that is high, low, then high.
- Run to 220 ns with 500 ps maxstep and save `clk`, `rst`, `err`, and `trim`.

Review caveat: Historical naming can suggest a full capacitor-array CDAC; this public task is only the voltage-domain calibration accumulator that drives `trim`.

Return exactly one Spectre testbench file named `tb_cdac_calibration_ref.scs`.
