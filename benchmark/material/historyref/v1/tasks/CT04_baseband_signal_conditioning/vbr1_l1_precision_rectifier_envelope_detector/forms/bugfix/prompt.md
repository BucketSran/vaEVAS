# Task: vbr1_l1_precision_rectifier_envelope_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Precision rectifier/envelope detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_precision_rectifier_envelope_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `precision_rectifier_envelope_detector` with positional ports: `clk`, `rst`, `vin`, `rect`, `env`, `metric`.
- `dut_fixed.va` declares module `precision_rectifier_envelope_detector` with positional ports: `clk`, `rst`, `vin`, `rect`, `env`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `rect`
- `env`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `full_wave_rectification_around_common_mode`
- `envelope_peak_hold_and_decay`
- `negative_half_cycle_rectifies`
- `hold_metric_marks_envelope_memory`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

Representative public mismatch scenarios:

| Scenario | Expected behavior | Faulty behavior to repair |
| --- | --- | --- |
| `vin` rises above common mode | `rect` follows the positive deviation and `env` can update its peak | positive half-cycle is not reflected correctly |
| `vin` falls below common mode | `rect` still reports the absolute deviation from common mode | negative half-cycle is ignored or has the wrong sign |
| after a peak | `env` holds the recent envelope and decays gradually | envelope drops immediately or never decays |
| envelope memory active | `metric` marks the held-envelope state | metric does not indicate envelope memory |

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a voltage-domain precision rectifier with an envelope output.

The module rectifies the absolute deviation around the common-mode voltage rather than around
ground. It also tracks a peak envelope: the envelope updates quickly to new rectified peaks and
decays slowly when the rectified input falls. The metric output is high when the envelope is
holding above the instantaneous rectified value.

Public port contract:

```verilog
module precision_rectifier_envelope_detector(clk, rst, vin, rect, env, metric);
input clk, rst, vin;
output rect, env, metric;
electrical clk, rst, vin, rect, env, metric
```

Signal contract:

All logic controls are voltage-coded, low=0 V and high=0.9 V with threshold 0.45 V. The design remains pure voltage-domain behavioral Verilog-A: no current contributions, transistor devices, AC/noise analysis, or KCL/KVL solving assumptions.

Saved waveform columns:

```text
clk rst vin rect env metric
```

Public transient contract:

```spectre
tran tran stop=96n maxstep=0.25n
```
