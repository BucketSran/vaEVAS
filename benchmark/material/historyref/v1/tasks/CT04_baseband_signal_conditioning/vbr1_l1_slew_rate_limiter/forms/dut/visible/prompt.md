# Task: vbr1_l1_slew_rate_limiter:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Slew-rate limiter
- Domain: `voltage`
- Target artifact(s): `slew_rate_limiter.va`
- Supplied/reference support artifact(s): `tb_slew_rate_limiter_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `slew_rate_limiter.va` declares module `slew_rate_limiter` with positional ports: `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `input_up_down_steps_exercised`
- `rising_slew_is_limited`
- `high_level_eventually_reached`
- `falling_slew_is_limited`
- `low_level_eventually_reached`
- `lagged_response_not_passthrough`

## Output Contract

Return exactly one source artifact named `slew_rate_limiter.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain Verilog-A module for a discrete slew-rate limiter.

The DUT module is `slew_rate_limiter` with ports `vin, vout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Use a 1 ns timer update and move the internal output toward `vin` by at most 0.015 V per update.
- Limit both rising and falling changes and drive `vout` with `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.
