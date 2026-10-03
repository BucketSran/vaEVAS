# Clock Sample 1600n Sequencer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clock Sample 1600n Sequencer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clock_sample_1600n_sequencer.va`:
  - Module `clock_sample_1600n_sequencer` (entry)
    - position 0: `rst` (output, electrical)
    - position 1: `s` (output, electrical)
    - position 2: `nc` (output, electrical)
    - position 3: `res` (output, electrical)
    - position 4: `conv` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clock_sample_1600n_sequencer.va`
- DUT instance: `XDUT (rst s nc res conv) clock_sample_1600n_sequencer`
- Required saved public traces: `conv`, `nc`, `res`, `rst`, `s`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PERIODIC_16NS_FRAME`: exercise and make observable: Generate a repeating 16 ns ADC timing frame. Required traces: `time`, `conv`, `nc`, `res`, `rst`, `s`.
- `P_RESET_AND_SAMPLE_WINDOWS`: exercise and make observable: `rst` and `s` are high only in the declared frame windows, including both sample windows. Required traces: `time`, `conv`, `nc`, `res`, `rst`, `s`.
- `P_NONOVERLAP_AND_RESIDUE_WINDOWS`: exercise and make observable: `nc` and `res` use the declared non-overlap and residue windows without swapping outputs. Required traces: `time`, `conv`, `nc`, `res`, `rst`, `s`.
- `P_CONVERSION_OUTPUT_TIMING`: exercise and make observable: `conv` is asserted in the declared conversion windows with valid timing and level. Required traces: `time`, `conv`, `nc`, `res`, `rst`, `s`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Generate a repeating 16 ns ADC timing frame with these high windows: `rst` from 0 to 0.2 ns; `s` from 1.0 to 1.8 ns and 9.0 to 9.8 ns; `nc` from 2.0 to 2.25 ns and 10.0 to 10.25 ns; `res` from 3.0 to 3.25 ns, 4.5 to 4.75 ns, 6.0 to 6.25 ns, and 7.5 to 7.75 ns; and `conv` from 3.0 to 7.0 ns and 11.0 to 15.0 ns. All outputs should return low between their public windows and repeat every 16 ns.


The required trace names are: `time`, `conv`, `nc`, `res`, `rst`, `s`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
