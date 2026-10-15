# Task: vbr1_l1_vco_phase_integrator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: VCO phase integrator
- Domain: `voltage`
- Target artifact(s): `vco_phase_integrator.va`
- Supplied/reference support artifact(s): `tb_vco_phase_integrator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `vco_phase_integrator.va` declares module `vco_phase_integrator` with positional ports: `vctrl`, `phase`, `clk`.

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

- `phase_span_covers_nearly_full_wrap`
- `clock_toggles_on_phase_wrap`
- `late_edge_rate_exceeds_early_edge_rate`

## Output Contract

Return exactly one source artifact named `vco_phase_integrator.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## VCO Phase Integrator DUT

Write a pure voltage-domain Verilog-A module for a voltage-controlled VCO phase integrator with periodic phase updates.

The DUT module is `vco_phase_integrator` with ports `vctrl, phase, clk`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Use a 1 ns timer update and increment phase by `0.03 + 0.09 * V(vctrl)` at each update.
- Wrap phase at 1.0 and toggle `clk` on each wrap.
- Drive both `phase` and `clk` through `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `vco_phase_integrator.va`.
