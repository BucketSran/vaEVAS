# Task: vbr1_l1_soft_hysteretic_limiter:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Soft/hysteretic limiter
- Domain: `voltage`
- Target artifact(s): `soft_hysteretic_limiter.va`
- Supplied/reference support artifact(s): `tb_soft_hysteretic_limiter.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `soft_hysteretic_limiter.va` declares module `soft_hysteretic_limiter` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `out`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `smooth_limiting`
- `hysteresis_state_memory`
- `bounded_output`

## Public Behavioral Targets

- After reset, keep `out` bounded in the 0 V to 0.9 V signal range.
- For high `vin` excursions, compress `out` toward a high limited level around
  0.75 V rather than passing the input directly.
- For low `vin` excursions, compress `out` toward a low limited level around
  0.15 V.
- Preserve hysteresis memory during mid-level hold windows: after a high
  excursion, the mid-level output/metric should remain in the high state; after
  a low excursion, they should remain in the low state.
- Drive `metric` as a voltage-coded hysteresis state observable, high for the
  high-memory state and low for the low-memory state.

## Output Contract

Return exactly one source artifact named `soft_hysteretic_limiter.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Soft/hysteretic limiter (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Limit a voltage signal with bounded compression and stateful hysteresis memory around high/low thresholds.

Module name: `soft_hysteretic_limiter`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module soft_hysteretic_limiter(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is an analog voltage stimulus. out is the bounded conditioned voltage. metric exposes the limiter hysteresis state: it goes high after upper-threshold excursions, low after lower-threshold excursions, and preserves that state during mid-level hold windows.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
