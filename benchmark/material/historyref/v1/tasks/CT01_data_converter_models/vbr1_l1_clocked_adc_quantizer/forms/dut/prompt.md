# Task: vbr1_l1_clocked_adc_quantizer:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Data Converter Models
- Base function: Clocked ADC quantizer
- Domain: `voltage`
- Target artifact(s): `flash_adc_3b.va`
- Supplied/reference support artifact(s): `tb_flash_adc_3b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `flash_adc_3b.va` declares module `flash_adc_3b` with positional ports: `VDD`, `VSS`, `VIN`, `CLK`, `DOUT2`, `DOUT1`, `DOUT0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=820n maxstep=2n
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `dout2`
- `dout1`
- `dout0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `flash_adc_all_8_codes_present`
- `flash_adc_monotonic_with_ramp`

## Output Contract

Return exactly one source artifact named `flash_adc_3b.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Clocked ADC quantizer DUT

Write the Verilog-A DUT artifact(s) for `Clocked ADC quantizer`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `flash_adc_3b(vdd, vss, vin, clk, dout2, dout1, dout0)`

Ports:

- `vdd`, `vss`: electrical supply rails
- `vin`: input electrical analog voltage, clamped to the 0 V to 0.9 V conversion range
- `clk`: input electrical sampling clock
- `dout2`, `dout1`, `dout0`: output electrical code bits, MSB to LSB

## Behavioral Contract

- on each rising `clk` edge, quantize `V(vin)` into one of eight uniform bins
- clamp the converted code to `[0, 7]`
- drive output bits to `V(vdd)` for logic 1 and `V(vss)` for logic 0
- hold the sampled code between clock edges

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `vin`
- `clk`
- `dout2`
- `dout1`
- `dout0`
