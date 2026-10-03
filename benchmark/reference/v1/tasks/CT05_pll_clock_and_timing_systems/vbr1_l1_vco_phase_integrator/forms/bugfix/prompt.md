# Task: vbr1_l1_vco_phase_integrator:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: VCO phase integrator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_vco_phase_integrator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `vco_phase_integrator` with positional ports: `vctrl`, `phase`, `clk`.
- `dut_fixed.va` declares module `vco_phase_integrator` with positional ports: `vctrl`, `phase`, `clk`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=180n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vctrl`
- `phase`
- `clk`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `phase_increments_with_control_voltage`
- `phase_wraps_modulo_one`
- `clock_toggles_when_phase_wraps`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## VCO phase integrator Bugfix

Repair the supplied buggy Verilog-A implementation for `VCO phase integrator`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
