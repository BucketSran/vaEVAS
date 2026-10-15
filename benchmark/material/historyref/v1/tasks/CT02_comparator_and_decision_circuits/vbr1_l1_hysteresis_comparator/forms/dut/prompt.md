# Task: vbr1_l1_hysteresis_comparator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Hysteresis comparator
- Domain: `voltage`
- Target artifact(s): `cmp_hysteresis.va`
- Supplied/reference support artifact(s): `tb_cmp_hysteresis_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `cmp_hysteresis.va` declares module `cmp_hysteresis` with positional ports: `VINN`, `VINP`, `OUTN`, `OUTP`, `VSS`, `VDD`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=100p
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `out_p`
- `out_n`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `output_shows_hysteresis_window`
- `upward_and_downward_trip_points_are_separated`

## Output Contract

Return exactly one source artifact named `cmp_hysteresis.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Hysteresis comparator DUT

Write the Verilog-A DUT artifact(s) for `Hysteresis comparator`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `cmp_hysteresis(vinn, vinp, out_n, out_p, vss, vdd)`

Ports:

- `vinn`, `vinp`: input electrical differential pair
- `out_n`, `out_p`: output electrical complementary decisions
- `vss`, `vdd`: electrical supply rails

## Behavioral Contract

- trip high when `V(vinp)-V(vinn)` exceeds `+vhys/2`
- trip low when `V(vinp)-V(vinn)` falls below `-vhys/2`
- hold the previous decision inside the hysteresis band
- drive complementary rail-referenced outputs with `transition(...)`

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `time`
- `out_p`
- `out_n`
