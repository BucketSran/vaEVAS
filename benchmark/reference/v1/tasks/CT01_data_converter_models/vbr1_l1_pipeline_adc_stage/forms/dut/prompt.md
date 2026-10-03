# Task: vbr1_l1_pipeline_adc_stage:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Data Converter Models
- Base function: Pipeline ADC MDAC stage
- Domain: `voltage`
- Target artifact(s): `pipeline_stage.va`
- Supplied/reference support artifact(s): `tb_pipeline_stage_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

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

## Output Contract

Return exactly one source artifact named `pipeline_stage.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Implement a pure voltage-domain 1.5-bit pipeline ADC MDAC stage.

Public functional contract:

- On each rising edge of `PHI1`, sample `VIN`.
- On each rising edge of `PHI2`, compare the sampled input relative to
  `Vcm = V(VDD)/2` against `+VREF/4` and `-VREF/4`.
- Upper region: drive `D1=1`, `D0=0`, and
  `VRES = Vcm + 2*(VIN - Vcm) - VREF/2`.
- Lower region: drive `D1=0`, `D0=0`, and
  `VRES = Vcm + 2*(VIN - Vcm) + VREF/2`.
- Middle region: drive `D1=0`, `D0=1`, and
  `VRES = Vcm + 2*(VIN - Vcm)`.
- Clamp `VRES` to the supply range and drive all outputs with `transition(...)`.
- Avoid current-domain contributions, `ddt`, `idt`, transistor-level devices,
  AC/noise analysis, and KCL/KVL solver assumptions.
