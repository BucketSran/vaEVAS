# Task: vbr1_l2_flash_adc_mini_array:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Data Converter Models
- Base function: Flash ADC mini-array
- Domain: `voltage`
- Target artifact(s): `tb_flash_adc_3b_ref.scs`
- Supplied/reference support artifact(s): `flash_adc_3b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Flash ADC mini-array. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `flash_adc_3b.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "flash_adc_3b.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `flash_adc_3b.va` declares module `flash_adc_3b` with positional ports: `VDD`, `VSS`, `VIN`, `CLK`, `CMP0`, `CMP1`, `CMP2`, `CMP3`, `CMP4`, `CMP5`, `CMP6`, `DOUT2`, `DOUT1`, `DOUT0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=86n maxstep=200p
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `cmp0`
- `cmp1`
- `cmp2`
- `cmp3`
- `cmp4`
- `cmp5`
- `cmp6`
- `dout2`
- `dout1`
- `dout0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `vin`
- `clk`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "flash_adc_3b.va"

Vvdd (vdd 0) vsource dc=0.9 type=dc
Vvss (vss 0) vsource dc=0.0 type=dc

IDUT (vdd vss vin clk cmp0 cmp1 cmp2 cmp3 cmp4 cmp5 cmp6 dout2 dout1 dout0) flash_adc_3b vrefp=0.9 vrefn=0.0 vth=0.45 tedge=100p

tran tran stop=86n maxstep=200p
save vin clk cmp0 cmp1 cmp2 cmp3 cmp4 cmp5 cmp6 dout2 dout1 dout0
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `all_8_flash_codes_present`
- `comparator_threshold_ladder_matches_vin_bins`
- `comparator_outputs_form_thermometer_prefix`
- `binary_code_matches_comparator_count`

## Public L2 Behavior Contract

This row is a small flash ADC array, so the testbench must make both comparator
and encoder behavior observable:

1. Drive `vin` through one stable midpoint in each of the eight quantization
   bins across the 0 V to 0.9 V range.
2. Place each midpoint before a rising `clk` edge and hold it stable across the
   sampling window.
3. Save `cmp0` through `cmp6` so the evaluator can check the thermometer prefix.
4. Save `dout2 dout1 dout0` so the evaluator can check that the binary output
   equals the number of high comparator decisions.

Use 0 V/0.9 V logic levels, a 0.45 V logic threshold, and a transient schedule
long enough to show all eight codes. Do not generate checker logic; the hidden
evaluator derives code coverage and thermometer/binary consistency from the
saved scalar waveforms.

## Output Contract

Return exactly one source artifact named `tb_flash_adc_3b_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Flash ADC mini-array Testbench Companion

Write a Spectre transient testbench for a 3-bit flash ADC mini-array. The
supplied DUT exposes seven comparator decisions as a thermometer vector and
encodes that vector into a 3-bit binary output after clocked sampling.

Public requirements:

- use a 0.9 V supply and 0 V reference
- drive `vin` through the midpoint of each of the 8 quantization bins, using
  stable windows before each clock edge
- drive `clk` so the checker can sample one stable conversion for every code
  from `0` through `7`
- instantiate `flash_adc_3b` by positional ports
- save exactly these scalar names: `vin`, `clk`, `cmp0`, `cmp1`, `cmp2`,
  `cmp3`, `cmp4`, `cmp5`, `cmp6`, `dout2`, `dout1`, `dout0`
- include a transient `tran` analysis
- avoid transistor-level devices, AC/noise analysis, and current-domain solver assumptions
