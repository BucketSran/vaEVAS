# SARFEND Logic 4b Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

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

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_CONVERSION_RESET_AND_PREVIOUS_WORD`: restore: Each rising `clks` crossing publishes the previous P-side state as dout3=dp4, dout2=dp3, dout1=dp2, and dout0=dp1, then initializes dp4=dm4=0 and every remaining undecided P/M pair to 1/1 for a new conversion. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_SAMPLE_AND_COMPARATOR_DECISIONS`: restore: Decisions update dp4/dm4 through dp1/dm1 in MSB-to-LSB order. dcomp-high/dcompb-low selects P/M=1/0 and the opposite comparator polarity selects P/M=0/1; undecided trial pairs may remain equal-valued. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_TEST_OVERRIDE_BEHAVIOR`: restore: When test is high, captured dtest3, dtest2, dtest1, then dtest0 replace the four live comparator decisions without changing their dp4-through-dp1 order. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_DOUT_BIT_MAPPING`: restore: The previous P-side state is published with dout3=dp4, dout2=dp3, dout1=dp2, and dout0=dp1 before the new conversion state is initialized. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.
- `P_LOGIC_OUTPUT_LEVELS`: restore: Handshake, DAC-control, and data outputs use full voltage-coded low/high levels. Required traces: `time`, `clkc`, `clks`, `dcomp`, `dcompb`, `dm1`, `dm2`, `dm3`, `dm4`, `dout0`, `dout1`, `dout2`, `dout3`, `dp1`, `dp2`, `dp3`, `dp4`, `dtest0`, `dtest1`, `dtest2`, `dtest3`, `test`.


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


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `sarfend_logic_4b.va`.
Every supplied `.va` file is editable; do not add or omit files.
