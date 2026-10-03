# Windowed Event Rate Monitor Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Windowed Event Rate Monitor` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `windowed_event_rate_monitor.va`:
  - Module `windowed_event_rate_monitor` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `event_in` (input, electrical)
    - position 3: `gate` (input, electrical)
    - position 4: `rate` (output, electrical)
    - position 5: `average` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/windowed_event_rate_monitor.va`
- DUT instance: `XDUT (clk rst event_in gate rate average) windowed_event_rate_monitor`
- Required saved public traces: `average`, `clk`, `event_in`, `gate`, `rate`, `rst`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `windowed_event_rate_monitor.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `windowed_event_rate_monitor.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `windowed_event_rate_monitor.window_count` defaults to `5`; valid range: finite; overrides window_count.
- `windowed_event_rate_monitor.tr` defaults to `60p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIALIZE_EVENT_COUNT_SAMPLE_COUNT_RATE`: exercise and make observable: Initialize `event_count`, `sample_count`, `rate`, and `average` to zero. On each rising clock crossing, clear the measurement window and both observables when `rst` is high or `gate <= vth`. Otherwise increment `sample_count`, increment `event_count` when `event_in > vth`, and drive `rate = vhi * clip01(event_count / window_count)`. Required traces: `time`, `average`, `clk`, `event_in`, `gate`, `rate`, `rst`.
- `P_FOR_THE_SAME_GATED_SAMPLE_WINDOW`: exercise and make observable: For the same gated sample window, drive `average = vhi * clip01(event_count / sample_count)`. Hold the last observable values between rising clock crossings. Required traces: `time`, `average`, `clk`, `event_in`, `gate`, `rate`, `rst`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_INITIALIZE_EVENT_COUNT_SAMPLE_COUNT_RATE`: Initialize `event_count`, `sample_count`, `rate`, and `average` to zero. On each rising clock crossing, clear the measurement window and both observables when `rst` is high or `gate <= vth`. Otherwise increment `sample_count`, increment `event_count` when `event_in > vth`, and drive `rate = vhi * clip01(event_count / window_count)`.
- `P_FOR_THE_SAME_GATED_SAMPLE_WINDOW`: For the same gated sample window, drive `average = vhi * clip01(event_count / sample_count)`. Hold the last observable values between rising clock crossings.

The evaluator saves and may inspect these public trace signals: `time`, `average`, `clk`, `event_in`, `gate`, `rate`, `rst`.


The required trace names are: `time`, `average`, `clk`, `event_in`, `gate`, `rate`, `rst`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
