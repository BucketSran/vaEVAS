# ADC Sample Clock Sequencer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `ADC Sample Clock Sequencer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `adc_sample_clock_sequencer.va`:
  - Module `adc_sample_clock_sequencer` (entry)
    - position 0: `rst` (output, electrical)
    - position 1: `s` (output, electrical)
    - position 2: `ss` (output, electrical)
    - position 3: `nc_az` (output, electrical)
    - position 4: `nc` (output, electrical)
    - position 5: `conv` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/adc_sample_clock_sequencer.va`
- DUT instance: `XDUT (rst s ss nc_az nc conv) adc_sample_clock_sequencer`
- Required saved public traces: `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PERIODIC_18NS_FRAME`: exercise and make observable: Generate a repeating 18 ns timing frame. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_RESET_SAMPLE_AND_SS_WINDOWS`: exercise and make observable: `rst`, `s`, and `ss` are high only in the declared frame windows. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_NONOVERLAP_AND_AUTOZERO_WINDOWS`: exercise and make observable: `nc` and `nc_az` use the declared non-overlap and autozero windows without swapping outputs. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_CONVERSION_WINDOW_TIMING`: exercise and make observable: `conv` is asserted in the declared conversion windows with the correct phase. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_TIMING_OUTPUT_LEVELS`: exercise and make observable: All timing outputs drive valid voltage-coded low/high levels. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Generate a repeating 18 ns ADC timing frame with these high windows: `rst` from 0 to 0.25 ns; `s` from 0.6 to 1.0 ns, 6.6 to 7.0 ns, and 12.6 to 13.0 ns; `ss` from 0.6 to 1.2 ns, 6.6 to 7.2 ns, and 12.6 to 13.2 ns; `nc_az` from 1.35 to 1.55 ns, 7.35 to 7.55 ns, and 13.35 to 13.55 ns; `nc` from 1.7 to 2.05 ns, 7.7 to 8.05 ns, and 13.7 to 14.05 ns; and `conv` from 2.4 to 5.4 ns, 8.4 to 11.4 ns, and 14.4 to 17.4 ns. All outputs should return low between their public windows and repeat every 18 ns.


The required trace names are: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
