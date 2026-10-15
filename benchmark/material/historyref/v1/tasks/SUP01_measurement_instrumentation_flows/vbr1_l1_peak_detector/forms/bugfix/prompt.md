# Task: vbr1_l1_peak_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Measurement Instrumentation Flows
- Base function: Peak detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_peak_detector_buggy.scs`, `tb_peak_detector_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `peak_detector` with positional ports: `vin`, `rst`, `vout`.
- `dut_fixed.va` declares module `peak_detector` with positional ports: `vin`, `rst`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=180n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `rst`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `first_peak_window_tracks_input_peak`
- `reset_window_clears_stored_peak`
- `post_reset_window_tracks_new_higher_peak`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_peak_detector_bugfix

The provided voltage-domain peak detector has a reset bug: reset does not clear
the stored peak value. Fix the model so it tracks the highest input voltage
observed while reset is low, clears promptly when reset is high, and can capture
a new peak after reset is released.

The fixed module must be named `peak_detector` and use electrical ports `vin`,
`rst`, and `vout`. On periodic update events, if `rst` is above the logic
threshold the stored peak and output should clear near zero. Otherwise, the
stored peak should update only when `vin` exceeds the current stored peak. The
output should be driven through a smoothed voltage contribution.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
