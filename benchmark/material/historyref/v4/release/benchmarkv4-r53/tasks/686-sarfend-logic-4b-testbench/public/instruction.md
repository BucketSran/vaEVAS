# SARFEND Logic 4b Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SARFEND Logic 4b` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sarfend_logic_4b.va`:
  - Module `sarfend_logic_4b` (entry)
    - position 0: `clks` (input, electrical)
    - position 1: `dcomp` (input, electrical)
    - position 2: `dcompb` (input, electrical)
    - position 3: `test` (input, electrical)
    - position 4: `dtest0` (input, electrical)
    - position 5: `dtest1` (input, electrical)
    - position 6: `dtest2` (input, electrical)
    - position 7: `dtest3` (input, electrical)
    - position 8: `clkc` (output, electrical)
    - position 9: `dp1` (output, electrical)
    - position 10: `dp2` (output, electrical)
    - position 11: `dp3` (output, electrical)
    - position 12: `dp4` (output, electrical)
    - position 13: `dm1` (output, electrical)
    - position 14: `dm2` (output, electrical)
    - position 15: `dm3` (output, electrical)
    - position 16: `dm4` (output, electrical)
    - position 17: `dout0` (output, electrical)
    - position 18: `dout1` (output, electrical)
    - position 19: `dout2` (output, electrical)
    - position 20: `dout3` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sarfend_logic_4b.va`
- DUT instance: `XDUT (clks dcomp dcompb test dtest0 dtest1 dtest2 dtest3 clkc dp1 dp2 dp3 dp4 dm1 dm2 dm3 dm4 dout0 dout1 dout2 dout3) sarfend_logic_4b`
- Required saved public traces: `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CONVERSION_RESET_AND_PREVIOUS_WORD`: exercise and make observable: Each rising `clks` crossing publishes the previous P-side state as dout3=dp4, dout2=dp3, dout1=dp2, and dout0=dp1, then initializes dp4=dm4=0 and every remaining undecided P/M pair to 1/1 for a new conversion. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_SAMPLE_AND_COMPARATOR_DECISIONS`: exercise and make observable: Decisions update dp4/dm4 through dp1/dm1 in MSB-to-LSB order. dcomp-high/dcompb-low selects P/M=1/0 and the opposite comparator polarity selects P/M=0/1; undecided trial pairs may remain equal-valued. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_TEST_OVERRIDE_BEHAVIOR`: exercise and make observable: When test is high, captured dtest3, dtest2, dtest1, then dtest0 replace the four live comparator decisions without changing their dp4-through-dp1 order. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_DOUT_BIT_MAPPING`: exercise and make observable: The previous P-side state is published with dout3=dp4, dout2=dp3, dout1=dp2, and dout0=dp1 before the new conversion state is initialized. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_LOGIC_OUTPUT_LEVELS`: exercise and make observable: Handshake, DAC-control, and data outputs use full voltage-coded low/high levels. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising `clks` crossing, publish the previous cycle DAC-P word,
reset the conversion pointer, initialize the DAC controls for a new conversion,
capture the test override word, and clear `clkc`.

- Publish the previous P-side state as `dout3=dp4`, `dout2=dp3`,
  `dout1=dp2`, and `dout0=dp1` before reinitializing the DAC controls.
- Initialize the new conversion to `dp4=dm4=0` and to
  `dp3=dm3=dp2=dm2=dp1=dm1=1`. These equal-valued pairs are intentional
  undecided/trial states; only an accepted decision makes that pair
  complementary.
- On falling `clks`, assert `clkc` to start comparison. While `clks` is low,
  comparator reset/recovery with both comparator outputs low reasserts `clkc`.
- Accept decisions in the order `dp4/dm4`, `dp3/dm3`, `dp2/dm2`, then
  `dp1/dm1`. A `dcomp`-high/`dcompb`-low decision produces P/M=`1/0`;
  `dcomp`-low/`dcompb`-high produces P/M=`0/1`.
- With `test` low, use the live comparator decision. With `test` high, use
  captured `dtest3`, `dtest2`, `dtest1`, then `dtest0` for the four decisions.
- Clear `clkc` when a decision is accepted and stop requesting comparisons
  after four decisions.


The required trace names are: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
