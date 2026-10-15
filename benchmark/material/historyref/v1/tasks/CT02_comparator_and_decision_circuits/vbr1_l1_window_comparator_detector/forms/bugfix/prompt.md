# Task: vbr1_l1_window_comparator_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Window comparator/detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_window_comparator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `window_comparator_ref` with positional ports: `VDD`, `VSS`, `vin`, `out`.
- `dut_fixed.va` declares module `window_comparator_ref` with positional ports: `VDD`, `VSS`, `vin`, `out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `vin`
- `out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `inside_window_high_on_rising_and_falling_sweeps`
- `below_lower_threshold_low`
- `above_upper_threshold_low`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Window comparator/detector Bugfix

Repair the supplied buggy Verilog-A implementation for `Window comparator/detector`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.

Intended behavior:

- Use lower threshold `vlow = 0.3 V` and upper threshold `vhigh = 0.6 V`.
- Output HIGH only when `vlow < V(vin,VSS) < vhigh`.
- Output LOW below the lower threshold and above the upper threshold.
- The buggy source incorrectly treats all `vin > vlow` values as in-window;
  repair the upper-threshold exit behavior without changing the module name,
  port order, or testbench observable names.
