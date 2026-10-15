# Soft Hysteretic Limiter Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Soft Hysteretic Limiter` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `soft_hysteretic_limiter.va`:
  - Module `soft_hysteretic_limiter` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/soft_hysteretic_limiter.va`
- DUT instance: `XDUT (clk rst vin out metric) soft_hysteretic_limiter`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `soft_hysteretic_limiter.tr` defaults to `1e-10` s; valid range: tr > 0; sets out and metric transition smoothing.
- `soft_hysteretic_limiter.gain` defaults to `1.8`; valid range: gain > 0; sets the sampled small-signal gain about 0.45 V common mode.
- `soft_hysteretic_limiter.hys_step` defaults to `0.08` V; valid range: hys_step >= 0; sets the signed remembered offset after upper or lower threshold excursions.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_NEUTRAL`: exercise and make observable: Initialization or active reset sets out and metric to 0.45 V and clears the remembered hysteresis offset. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_HYSTERESIS_STATE_UPDATE`: exercise and make observable: On rising clk crossings, vin above 0.62 V stores +hys_step, vin below 0.38 V stores -hys_step, and vin within the middle band preserves the prior offset. Required traces: `time`, `clk`, `rst`, `vin`, `metric`.
- `P_GAINED_LIMITER_TRANSFER`: exercise and make observable: The held output target is 0.45 V plus gain times vin minus 0.45 V plus the remembered hysteresis offset. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_OUTPUT_LIMITS`: exercise and make observable: Out is clamped to 0.10 V through 0.82 V with finite transition smoothing. Required traces: `time`, `out`.
- `P_STATE_METRIC`: exercise and make observable: Metric equals 0.45 V plus twice the remembered offset, producing 0.61 V and 0.29 V for the default high- and low-memory states. Required traces: `time`, `clk`, `vin`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Implement a clocked soft limiter with hysteresis memory around the `0.45 V`
  common-mode level.
- Initialize the held output and state monitor to `0.45 V`, with neutral
  hysteresis offset `0 V`.
- On each rising `clk` crossing, update the held limiter state. While `rst` is
  active high, reset the output and hysteresis state to their neutral
  common-mode values.
- When reset is low, set the hysteresis offset to `+hys_step` after a sampled
  input above `0.62 V`, set it to `-hys_step` after a sampled input below
  `0.38 V`, and otherwise preserve the previous hysteresis offset.
- Compute the held output target as
  `gain * (vin - 0.45 V) + 0.45 V + hysteresis_offset`.
- Clamp the driven `out` voltage to `[0.10 V, 0.82 V]`.
- Drive `metric` as a voltage-coded state monitor:
  `0.45 V + 2.0 * hysteresis_offset`, so the default high- and low-memory
  states produce 0.61 V and 0.29 V respectively.

The public example harness is a public verification scenario for wiring and saved
observables. Do not hard-code its runtime horizon, waveform breakpoints, or
sample windows into the DUT.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
