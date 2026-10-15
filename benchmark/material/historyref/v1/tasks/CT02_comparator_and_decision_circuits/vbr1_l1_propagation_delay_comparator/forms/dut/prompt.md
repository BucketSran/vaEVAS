# Task: vbr1_l1_propagation_delay_comparator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Propagation-delay comparator
- Domain: `voltage`
- Target artifact(s): `cmp_delay.va`, `edge_interval_timer.va`
- Supplied/reference support artifact(s): `tb_cmp_delay_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `cmp_delay.va` declares module `cmp_delay` with positional ports: `CLK`, `VINN`, `VINP`, `DCMPN`, `DCMPP`, `LP`, `LM`, `VSS`, `VDD`.
- `edge_interval_timer.va` declares module `edge_interval_timer` with positional ports: `CLK_1`, `CLK_2`, `OUT_PS`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=16n maxstep=10p
```

The release harness expects these exact public scalar observables:

- `clk`
- `vinp`
- `vinn`
- `out_p`
- `out_n`
- `delay_ps`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `output_goes_high_in_each_phase`
- `clk_to_output_delay_increases_as_diff_shrinks`

## Output Contract

Return exactly these source artifacts:

- `cmp_delay.va`
- `edge_interval_timer.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Propagation-delay comparator DUT

Write the Verilog-A DUT artifact(s) for `Propagation-delay comparator`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `cmp_delay(CLK, VINN, VINP, DCMPN, DCMPP, LP, LM, VSS, VDD)`

Ports:

- `CLK`: input electrical decision clock
- `VINN`, `VINP`: input electrical differential pair
- `DCMPN`, `DCMPP`: output electrical complementary decisions
- `LP`, `LM`: output electrical compatibility monitor ports
- `VSS`, `VDD`: electrical supply rails

## Behavioral Contract

- on rising `CLK`, resolve the positive input polarity to `DCMPP` high
- reset the public decision outputs low between decisions
- model a longer clock-to-output delay as `abs(V(VINP)-V(VINN))` shrinks
- keep the delay bounded by public minimum and maximum delay parameters

## Public Evaluation Observables

The companion validation testbench saves these waveform columns through scalar
testbench aliases:

- `time`
- `clk`
- `vinp`
- `vinn`
- `out_p`
- `out_n`
- `delay_ps`
