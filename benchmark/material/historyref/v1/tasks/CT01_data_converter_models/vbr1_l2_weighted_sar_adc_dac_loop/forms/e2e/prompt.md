# Task: vbr1_l2_weighted_sar_adc_dac_loop:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Data Converter Models
- Base function: Weighted SAR ADC/DAC loop
- Domain: `voltage`
- Target artifact(s): `dac_weighted_8b.va`, `sar_adc_weighted_8b.va`, `sh_ideal.va`, `tb_sar_adc_dac_weighted_8b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Weighted SAR ADC/DAC loop. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `dac_weighted_8b.va`, `sar_adc_weighted_8b.va`, `sh_ideal.va`, `tb_sar_adc_dac_weighted_8b_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `dac_weighted_8b.va`, `sar_adc_weighted_8b.va`, `sh_ideal.va` must be co-located with the generated Spectre testbench.
- Include each generated Verilog-A file exactly with a matching `ahdl_include "<file>.va"` line in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `dac_weighted_8b.va` declares module `dac_weighted_8b` with positional scalar ports: `DIN7`, `DIN6`, `DIN5`, `DIN4`, `DIN3`, `DIN2`, `DIN1`, `DIN0`, `VOUT`.
- `sar_adc_weighted_8b.va` declares module `sar_adc_weighted_8b` with positional ports: `VIN`, `CLKS`, `RST_N`, `DOUT`, `BIT_INDEX`, `TRIAL_CODE_MON`, `TRIAL_VDAC`, `CMP_DECISION`, `CONV_DONE`, `VIN_SAMPLE`.
- `sh_ideal.va` declares module `sh_ideal` with positional ports: `vin`, `clk`, `vdd`, `vss`, `rst_n`, `vout`.

For `sar_adc_weighted_8b`, declare `DOUT` as an 8-bit electrical vector
output and let the Spectre positional instance map the eight scalar nodes
`dout_7 ... dout_0` onto that vector. Do not replace the vector with unrelated
private port names; `dout_7` is the MSB and `dout_0` is the LSB in the public
testbench connection.

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

- `sar_adc_code_range_sufficient`
- `sar_adc_unique_code_count`
- `sar_bit_trial_sequence_visible`
- `trial_dac_matches_trial_code_monitor`
- `comparator_decision_matches_sample_and_trial`
- `sar_code_matches_sampled_input`
- `dac_output_matches_weighted_code`
- `code_monotonic_with_sampled_input`
- `dac_output_in_range`

## Public L2 Behavior Contract

This row is a composed SAR ADC plus weighted DAC loop. The public behavior must
make the sample, conversion code, and reconstruction mutually consistent:

1. Sample/hold stage:
   - Sample `vin` onto `vin_sh` on the public sampling clock.
   - Keep the held sample stable long enough for conversion and reconstruction
     to be observed.

2. SAR conversion stage:
   - Drive `dout_7` through `dout_0` as an 8-bit voltage-coded final conversion
     result for the held input.
   - Expose the multi-cycle successive-approximation process on `bit_index`,
     `trial_code_mon`, `trial_vdac`, `cmp_decision`, `conv_done`, and `vin_sample`.
   - The ADC should consume the held `vin_sh` node, not the raw `vin` source,
     so the public chain is sample/hold -> SAR -> DAC.
   - The code should cover a broad range under the public full-swing input
     stimulus and should be monotonic with the sampled input.

3. Weighted DAC reconstruction:
   - Feed the saved SAR bits into the weighted DAC path.
   - Drive `vout` as the weighted reconstruction of the saved code in the 0 V
     to 0.9 V range.

The public relation is: sampled input `vin_sh`/`vin_sample` -> visible SAR trial
sequence -> final SAR code bits -> weighted DAC `vout`. The evaluator checks
trial-bit visibility, trial-DAC/comparator consistency, range, unique-code
coverage, monotonicity, and code-to-DAC consistency from saved waveforms.

Concrete public implementation guidance:

- A compact behavioral state machine is sufficient; do not build transistor
  devices, switched-capacitor physics, or an ideal mathematical lookup hidden
  from the public monitors.
- Use one public sampling phase and one MSB-to-LSB trial sequence. A practical
  pattern is: sample `VIN` into an internal held value on one `CLKS` edge while
  idle, then resolve one tentative SAR bit on each following rising edge.
- Test trial weights in this order: 128, 64, 32, 16, 8, 4, 2, 1. For each
  trial, compute `trial_vdac = trial_code / 255 * vdd`; keep the bit when the
  held sample is greater than or equal to that trial DAC value.
- Drive `trial_code_mon` as `trial_code / 255 * vdd`, `bit_index` as a
  voltage-coded public bit-position monitor, `cmp_decision` as 0 V or `vdd`,
  `vin_sample` as the held sample, and `conv_done` high only after the final
  LSB decision.
- Keep the implementation short and deterministic. The goal is observable
  behavioral consistency, not a full SAR controller with nonideal capacitor
  switching.

Public stimulus guidance for the generated testbench:

- Use `parameters vdd=0.9 fin=100e3`.
- Drive `clks` as a 50 MHz pulse clock with 0 V/`vdd` levels.
- Keep active-low `rst_n` low for the first few clock cycles, then high for the
  rest of the 20 us transient.
- Drive `vin` with a full-swing sine around mid-supply, for example
  `sinedc=0.45`, `ampl=0.45`, and `freq=fin`, so many post-reset samples cover
  the ADC range.

## Output Contract

Return exactly these source artifacts:

- `dac_weighted_8b.va`
- `sar_adc_weighted_8b.va`
- `sh_ideal.va`
- `tb_sar_adc_dac_weighted_8b_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a voltage-domain 8-bit SAR ADC, matching weighted DAC, sample/hold helper, and one voltage-domain Spectre transient testbench.

# Task: sar_adc_dac_weighted_8b_smoke

## Objective

Create a compact weighted SAR ADC/DAC round-trip system. The ADC samples a full-swing sine input,
uses an MSB-first weighted successive-approximation final-code update for each sample, the matching
weighted DAC converts the code back to an analog output, and the checker verifies code coverage,
sample-to-code consistency, DAC reconstruction from the code, and output range.

## Required Verilog-A Modules

Return these Verilog-A modules:

1. `sar_adc_weighted_8b`
   - Ports, all `electrical`, exactly in this order:
     - `vin`, `clks`, `rst_n`, `dout[7:0]`, `bit_index`, `trial_code_mon`, `trial_vdac`, `cmp_decision`, `conv_done`, `vin_sample`
   - On each conversion update after reset:
     - sample or use the held input voltage for the conversion decision
     - start from zero code and test weights MSB to LSB: 128, 64, 32, 16, 8, 4, 2, 1 over multiple clock edges
     - keep a tentative bit when the partial weighted DAC level does not exceed the sampled input
     - output the final 8-bit code clipped to `[0, 255]`
     - expose `bit_index`, `trial_code_mon`, `trial_vdac`, `cmp_decision`, `conv_done`, and `vin_sample` as voltage-coded monitor outputs
   - `dout_7` is MSB and `dout_0` is LSB in the scalar testbench connection.
2. `dac_weighted_8b`
   - Ports, all `electrical`, exactly in this order:
     - `din7`, `din6`, `din5`, `din4`, `din3`, `din2`, `din1`, `din0`, `vout`
   - Output:
     - `vout = weighted_code / 255 * vdd`
3. `sh_ideal`
   - Ports, all `electrical`, exactly in this order:
     - `vin`, `clks`, `vdd`, `vss`, `rst_n`, `vin_sh`
   - Tracks or samples `vin` so the checker can observe the sampled input as `vin_sh`.

## Behavioral Contract

- Use pure voltage-domain Verilog-A only.
- Use `@(cross(V(clks) - vth, +1))` for trial-bit clocked updates and an edge-triggered sampling phase for the held input.
- Use `transition(...)` for all driven outputs.
- Output HIGH should use `vdd`; output LOW should use `0`.
- The ADC code range should cover most of `[0, 255]` under the testbench sine input.
- The trial monitor outputs should show the MSB-to-LSB approximation sequence before `conv_done` asserts.
- The final output code should be monotonic with the sampled input voltage across the sine sweep.
- `vout` must stay within `[0, vdd]` and match `weighted_code / 255 * vdd`.

## Testbench Contract

- Use a 0.9 V supply and 0 V reference.
- Drive `clks` with a 50 MHz-class sampling clock.
- Use active-low `rst_n` and release reset early enough to leave many post-reset samples.
- Drive `vin` with a full-swing sine input around mid-supply so the sampled input covers most ADC codes.
- Instantiate `sar_adc_weighted_8b`, `dac_weighted_8b`, and `sh_ideal` by positional scalar ports.
- Save these exact scalar names:
  - `vin`, `vin_sh`, `clks`, `rst_n`, `vout`
  - `dout_7`, `dout_6`, `dout_5`, `dout_4`, `dout_3`, `dout_2`, `dout_1`, `dout_0`
  - `bit_index`, `trial_code_mon`, `trial_vdac`, `cmp_decision`, `conv_done`, `vin_sample`

## Expected Checker-Visible Behavior

- Many distinct post-reset output codes should appear.
- Trial monitor waveforms should expose every bit index from MSB to LSB.
- Comparator decisions should match `vin_sample` versus `trial_vdac`.
- Code range should span near the endpoints of the 8-bit range.
- Decoded output code should match the sampled input within quantization tolerance.
- `vout` should follow the code-derived DAC level and remain within the supply range.
