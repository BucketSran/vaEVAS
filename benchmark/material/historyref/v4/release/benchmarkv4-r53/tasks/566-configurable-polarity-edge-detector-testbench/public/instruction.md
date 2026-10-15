# Configurable Polarity Edge Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Configurable Polarity Edge Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `configurable_polarity_edge_detector.va`:
  - Module `configurable_polarity_edge_detector` (entry)
    - position 0: `sig` (input, electrical)
    - position 1: `rise_en` (input, electrical)
    - position 2: `pulse` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/configurable_polarity_edge_detector.va`
- DUT instance: `XDUT (sig rise_en pulse) configurable_polarity_edge_detector`
- Required saved public traces: `sig`, `rise_en`, `pulse`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `configurable_polarity_edge_detector.vdd` defaults to `0.9` V; valid range: vdd > 0; sets the voltage-coded pulse high level.
- `configurable_polarity_edge_detector.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets the decision threshold for sig and rise_en.
- `configurable_polarity_edge_detector.tr` defaults to `2e-11` s; valid range: tr > 0; sets pulse rise and fall smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_SELECTION`: exercise and make observable: When rise_en is above vth, each rising crossing of sig through vth produces one output pulse. Required traces: `time`, `sig`, `rise_en`, `pulse`.
- `P_FALLING_SELECTION`: exercise and make observable: When rise_en is below vth, each falling crossing of sig through vth produces one output pulse. Required traces: `time`, `sig`, `rise_en`, `pulse`.
- `P_OPPOSITE_EDGE_REJECTION`: exercise and make observable: An edge opposite to the polarity selected by rise_en does not produce a pulse. Required traces: `time`, `sig`, `rise_en`, `pulse`.
- `P_BOUNDED_PULSE`: exercise and make observable: Each detected edge produces a bounded short pulse with nominal width about 2 ns rather than a latched high level. Required traces: `time`, `pulse`.
- `P_OUTPUT_LEVELS`: exercise and make observable: pulse uses 0 V and vdd levels with finite transition smoothing set by tr. Required traces: `time`, `pulse`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Treat `sig` and `rise_en` as voltage-coded logic using `vth`.
- When `rise_en` is high, generate a short pulse after each rising edge of `sig` and do not pulse on falling edges.
- When `rise_en` is low, generate a short pulse after each falling edge of `sig` and do not pulse on rising edges.
- The output pulse width should be a short support-timing pulse, nominally about 2 ns, with smooth edges.


The required trace names are: `time`, `sig`, `rise_en`, `pulse`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
