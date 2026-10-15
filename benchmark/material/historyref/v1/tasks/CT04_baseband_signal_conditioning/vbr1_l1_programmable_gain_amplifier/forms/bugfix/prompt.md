# Task: vbr1_l1_programmable_gain_amplifier:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Programmable gain amplifier
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_programmable_gain_amplifier.scs`, `tb_programmable_gain_amplifier_buggy.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `programmable_gain_amplifier` with positional ports: `clk`, `rst`, `gain_sel`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `programmable_gain_amplifier` with positional ports: `clk`, `rst`, `gain_sel`, `vin`, `out`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `gain_sel`
- `vin`
- `out`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `gain_select_changes_slope`
- `sampled_gain_holds_between_clock_edges`
- `common_mode_is_preserved`
- `rail_clamps_with_clip_metric`
- `reset_returns_to_unity_gain`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

Representative public mismatch scenarios:

| Scenario | Expected behavior | Faulty behavior to repair |
| --- | --- | --- |
| `gain_sel` changes before a rising `clk` edge | gain changes only after the sampling edge and then holds | output gain changes asynchronously or ignores sampled gain |
| reset asserted | output returns to common mode and gain returns to unity/default behavior | stale gain or output state survives reset |
| large input excursion under high gain | output clamps to the rail and `metric` marks clipping | output exceeds rails or clipping metric is missing |
| common-mode input | output remains near common mode regardless of gain | amplifier shifts common mode incorrectly |

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain Verilog-A programmable gain amplifier.

The gain code is sampled on rising `clk` edges:
- reset selects unity gain and returns the output to the common-mode voltage.
- `gain_sel=0` selects a low gain.
- `gain_sel=1` selects a high gain.
- The output is `vcm + gain * (V(vin)-vcm)` with rail clamps.
- `metric` is high when the unclamped target clips to either rail.

Module name: `programmable_gain_amplifier`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL solving assumptions.

Public port contract:

```verilog
module programmable_gain_amplifier(clk, rst, gain_sel, vin, out, metric);
```

Saved waveform columns:

```text
clk rst gain_sel vin out metric
```

Public transient contract:

```spectre
tran tran stop=90n maxstep=250p
```
