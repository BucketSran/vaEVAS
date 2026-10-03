# Task: vbr1_l1_pipeline_adc_stage:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: Pipeline ADC MDAC stage
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `pipeline_stage.va`, `tb_pipeline_stage_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `pipeline_stage` with positional ports: `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.
- `dut_fixed.va` declares module `pipeline_stage` with positional ports: `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.
- `pipeline_stage.va` declares module `pipeline_stage` with positional ports: `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=300n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `phi1`
- `phi2`
- `vin`
- `vres`
- `d1`
- `d0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `upper_middle_lower_regions_exercised`
- `sub_adc_decisions_match_thresholds`
- `residue_follows_gain_two_mdac_formula`
- `residue_output_bounded`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Repair a pure voltage-domain 1.5-bit pipeline ADC MDAC stage.

The corrected model must sample `VIN` on `PHI1`, make the sub-ADC decision on
`PHI2`, and apply the proper sub-DAC correction term to the gain-of-2 residue:

- upper region: `VRES = Vcm + 2*(VIN - Vcm) - VREF/2`
- lower region: `VRES = Vcm + 2*(VIN - Vcm) + VREF/2`
- middle region: `VRES = Vcm + 2*(VIN - Vcm)`

Use `transition(...)`, stay voltage-domain only, and avoid `I(`, `ddt`, `idt`,
transistor-level devices, AC/noise analysis, and KCL/KVL solver assumptions.
