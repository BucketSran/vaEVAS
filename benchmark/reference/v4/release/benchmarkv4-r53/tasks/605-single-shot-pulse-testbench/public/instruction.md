# Single Shot Pulse Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Single Shot Pulse` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `source_single_shot.va`:
  - Module `source_single_shot` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/source_single_shot.va`
- DUT instance: `XDUT (vin vout) source_single_shot`
- Required saved public traces: `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `source_single_shot.pulse_width` defaults to `1e-08` s; valid range: pulse_width > 0; sets output high duration after a qualifying rising crossing.
- `source_single_shot.vlogic_high` defaults to `0.9` V; valid range: finite real; sets the asserted output level.
- `source_single_shot.vlogic_low` defaults to `0.0` V; valid range: finite real; sets the deasserted output level.
- `source_single_shot.vtrans` defaults to `0.45` V; valid range: finite real; sets the rising vin trigger threshold.
- `source_single_shot.tdel` defaults to `1e-09` s; valid range: tdel >= 0; sets output transition delay.
- `source_single_shot.trise` defaults to `2e-11` s; valid range: trise > 0; sets vout rise smoothing.
- `source_single_shot.tfall` defaults to `2e-11` s; valid range: tfall > 0; sets vout fall smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_CROSS_TRIGGER`: exercise and make observable: Each qualifying rising vin crossing through vtrans initiates an output pulse. Required traces: `time`, `vin`, `vout`.
- `P_NO_FALLING_TRIGGER`: exercise and make observable: Falling vin crossings do not initiate pulses. Required traces: `time`, `vin`, `vout`.
- `P_PULSE_WIDTH`: exercise and make observable: After a qualifying trigger, the output target remains high for pulse_width before returning low. Required traces: `time`, `vin`, `vout`.
- `P_OUTPUT_LEVELS`: exercise and make observable: The deasserted and asserted targets are vlogic_low and vlogic_high respectively. Required traces: `time`, `vin`, `vout`.
- `P_REPEATABLE_ONE_SHOTS`: exercise and make observable: Distinct qualifying rising edges produce corresponding pulses and vout returns low between sufficiently separated events. Required traces: `time`, `vin`, `vout`.
- `P_TRANSITION_TIMING`: exercise and make observable: Output changes use tdel delay with trise and tfall smoothing without altering the logical pulse duration contract. Required traces: `time`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT is a voltage-domain one-shot pulse generator.

Support these public parameters and legal overrides:

| Parameter | Default | Unit / range | Contract |
| --- | ---: | --- | --- |
| `pulse_width` | `10 ns` | time, `(0:inf)` | Output high duration after a qualifying input edge. |
| `vlogic_high` | `0.9` | V | Output high level. |
| `vlogic_low` | `0.0` | V | Output low level. |
| `vtrans` | `0.45` | V | Rising-edge threshold for `vin`. |
| `tdel` | `1 ns` | time, `[0:inf)` | Output transition delay. |
| `trise` | `20 ps` | time, `(0:inf)` | Output rise time. |
| `tfall` | `20 ps` | time, `(0:inf)` | Output fall time. |

Required observable behavior:

- Detect rising `vin` crossings at `vtrans`.
- On each qualifying rising edge, drive `vout` high.
- Use a timer to return `vout` low after the configured pulse width.
- Generate one output pulse per input rising edge.
- Drive `vout` through smoothed voltage contributions.

Use voltage contributions only. Do not use current contributions, `ddt()`,
`idt()`, transistor-level devices, AC/noise analysis, validation logic, validation-only
test hooks, or simulator-specific side channels.


The required trace names are: `time`, `vin`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
