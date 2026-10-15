# Task: vbr1_l2_weighted_sar_adc_dac_loop:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Data Converter Models
- Base function: Weighted SAR ADC/DAC loop
- Domain: `voltage`
- Target artifact(s): `tb_sar_adc_dac_weighted_8b_ref.scs`
- Supplied/reference support artifact(s): `dac_weighted_8b.va`, `sar_adc_weighted_8b.va`, `sh_ideal.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Weighted SAR ADC/DAC loop. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `dac_weighted_8b.va`, `sar_adc_weighted_8b.va`, `sh_ideal.va` will be co-located with the generated testbench by the evaluation harness.
- Include each supplied Verilog-A support file exactly with a matching `ahdl_include "<file>.va"` line in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `dac_weighted_8b.va` declares module `dac_weighted_8b` with positional scalar ports: `DIN7`, `DIN6`, `DIN5`, `DIN4`, `DIN3`, `DIN2`, `DIN1`, `DIN0`, `VOUT`.
- `sar_adc_weighted_8b.va` declares module `sar_adc_weighted_8b` with positional ports: `VIN`, `CLKS`, `RST_N`, `DOUT`, `BIT_INDEX`, `TRIAL_CODE_MON`, `TRIAL_VDAC`, `CMP_DECISION`, `CONV_DONE`, `VIN_SAMPLE`.
- `sh_ideal.va` declares module `sh_ideal` with positional ports: `vin`, `clk`, `vdd`, `vss`, `rst_n`, `vout`.

The supplied SAR ADC exposes `DOUT` as an 8-bit electrical vector. In the
Spectre positional instance, list the public scalar nodes `dout_7 ... dout_0`
in the `DOUT` position so they map to the vector bits. `dout_7` is the MSB and
`dout_0` is the LSB.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=20u maxstep=5n
```

The release harness expects these exact public scalar observables:

- `vin`
- `vin_sh`
- `clks`
- `rst_n`
- `vout`
- `dout_7`
- `dout_6`
- `dout_5`
- `dout_4`
- `dout_3`
- `dout_2`
- `dout_1`
- `dout_0`
- `bit_index`
- `trial_code_mon`
- `trial_vdac`
- `cmp_decision`
- `conv_done`
- `vin_sample`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clks`
- `rst_n`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "dac_weighted_8b.va"
ahdl_include "sar_adc_weighted_8b.va"
ahdl_include "sh_ideal.va"

Vvdd (vdd 0) vsource dc=vdd
Vvss (vss 0) vsource dc=0

IADC (vin_sh clks rst_n dout_7 dout_6 dout_5 dout_4 dout_3 dout_2 dout_1 dout_0 bit_index trial_code_mon trial_vdac cmp_decision conv_done vin_sample) sar_adc_weighted_8b vdd=vdd
IDAC (dout_7 dout_6 dout_5 dout_4 dout_3 dout_2 dout_1 dout_0 vout) dac_weighted_8b vdd=vdd
ISH (vin clks vdd vss rst_n vin_sh) sh_ideal

tran tran stop=20u maxstep=5n
save vin vin_sh clks rst_n vout dout_7 dout_6 dout_5 dout_4 dout_3 dout_2 dout_1 dout_0 bit_index trial_code_mon trial_vdac cmp_decision conv_done vin_sample
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `transient_analysis_present`
- `public_observables_saved`
- `dut_or_system_instantiated`
- `sar_bit_trial_sequence_visible`
- `trial_dac_matches_trial_code_monitor`
- `comparator_decision_matches_sample_and_trial`
- `sar_adc_code_range_sufficient`
- `sar_adc_unique_code_count`
- `sar_code_matches_sampled_input`
- `dac_output_matches_weighted_code`
- `code_monotonic_with_sampled_input`
- `dac_output_in_range`

## Public L2 Behavior Contract

This row is a composed SAR ADC plus weighted DAC loop. The testbench must make
the sample, conversion code, and reconstruction visible:

1. Drive a full-swing analog input that produces broad 8-bit code coverage
   after reset.
2. Drive the sampling/conversion clock long enough for many completed
   conversions.
3. Save the held sample `vin_sh`, the ADC's `vin_sample`, all eight SAR output
   bits, the trial monitor outputs, and the weighted DAC output `vout`.
4. Feed `vin_sh` into the SAR ADC input, then connect the SAR output bits into
   the weighted DAC path so `vout` is reconstructable from the saved code.

The expected public relation is: `vin` is sampled to `vin_sh`/`vin_sample`, the
SAR trial monitors show an MSB-to-LSB approximation sequence, the final SAR bits
encode that held input, and `vout` follows the weighted reconstruction of the
same saved code. Do not generate checker logic; the evaluator checks trial
visibility, comparator/trial-DAC consistency, coverage, monotonicity, and
code-to-DAC consistency.

Concrete public stimulus guidance:

- Use `parameters vdd=0.9 fin=100e3`.
- Drive `clks` as a 50 MHz pulse clock with 0 V/`vdd` levels.
- Keep active-low `rst_n` low for the first few clock cycles, then high for the
  rest of the 20 us transient.
- Drive `vin` with a full-swing sine around mid-supply, for example
  `sinedc=0.45`, `ampl=0.45`, and `freq=fin`, so many post-reset samples cover
  the ADC range.
- The testbench should instantiate all three supplied modules in the chain:
  `vin -> sh_ideal -> sar_adc_weighted_8b -> dac_weighted_8b -> vout`.

## Output Contract

Return exactly one source artifact named `tb_sar_adc_dac_weighted_8b_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Weighted SAR ADC/DAC loop Testbench Companion

Write a Spectre transient testbench for the `Weighted SAR ADC/DAC loop` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the checker
- include or instantiate the Verilog-A behavioral module under test
- drive enough full-swing input samples after reset for broad 8-bit code coverage
- save `bit_index`, `trial_code_mon`, `trial_vdac`, `cmp_decision`, `conv_done`, and `vin_sample` so the approximation loop is observable
- connect the SAR ADC output bits into the weighted DAC so `vout` is reconstructable from the saved code
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
