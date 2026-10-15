# Task: vbr1_l1_digital_phase_accumulator_with_modulo_wrap:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Digital phase accumulator with modulo wrap
- Domain: `voltage`
- Target artifact(s): `phase_accumulator_timer_wrap_ref.va`
- Supplied/reference support artifact(s): `tb_phase_accumulator_timer_wrap_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `phase_accumulator_timer_wrap_ref.va` declares module `phase_accumulator_timer_wrap_ref` with positional ports: `VDD`, `VSS`, `clk_out`, `phase_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=75n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `clk_out`
- `phase_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `phase_accumulator_timer_wrap`

## Output Contract

Return exactly one source artifact named `phase_accumulator_timer_wrap_ref.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

This entry is scoped as an ADPLL/NCO phase-timing primitive, not as a generic digital-logic benchmark. Model the wrapped phase state and derived voltage-domain timing outputs that a behavioral PLL loop would consume.

## Digital phase accumulator with modulo wrap DUT

Write the Verilog-A DUT artifact(s) for `Digital phase accumulator with modulo wrap`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `phase_accumulator_timer_wrap_ref(VDD, VSS, clk_out, phase_out)`

Ports:

- `VDD`, `VSS`: electrical supply rails
- `clk_out`: output electrical derived clock
- `phase_out`: output electrical normalized phase monitor

## Behavioral Contract

- advance phase by `phase_step` every `dt` using `@(timer(...))`
- wrap phase manually into `[0, 1)` rather than letting it grow unbounded
- drive `phase_out` as a normalized monitor and toggle `clk_out` from the wrapped phase

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `time`
- `clk_out`
- `phase_out`
