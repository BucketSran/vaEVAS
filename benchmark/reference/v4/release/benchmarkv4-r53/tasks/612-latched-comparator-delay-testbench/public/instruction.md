# Latched Comparator Delay Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Latched Comparator Delay` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `latched_comparator_delay.va`:
  - Module `latched_comparator_delay` (entry)
    - position 0: `DOUT` (output, electrical)
    - position 1: `GND` (inout, electrical)
    - position 2: `VDD` (inout, electrical)
    - position 3: `CLK` (input, electrical)
    - position 4: `VINN` (input, electrical)
    - position 5: `VINP` (input, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/latched_comparator_delay.va`
- DUT instance: `XDUT (dout 0 vdd clk vinn vinp) latched_comparator_delay td=500p tr=100p vn=0`
- Required saved public traces: `vdd`, `clk`, `vinn`, `vinp`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `latched_comparator_delay.td` defaults to `1e-09` s; valid range: td >= 0; sets DOUT delay after a latch event.
- `latched_comparator_delay.tr` defaults to `1e-10` s; valid range: tr >= 0; sets DOUT transition smoothing.
- `latched_comparator_delay.vos` defaults to `0.0` V; valid range: finite real; sets deterministic input-referred decision offset.
- `latched_comparator_delay.vn` defaults to `0.001` V; valid range: vn >= 0; sets standard deviation of the input-referred random decision term; zero disables it.
- `latched_comparator_delay.seed_init` defaults to `0.0`; valid range: finite integer-valued real accepted as a random seed; initializes the repeatable random decision sequence.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SUPPLY_REFERENCED_THRESHOLD`: exercise and make observable: The latch clock threshold is the midpoint of VDD and GND, and DOUT low and high levels use those same rails. Required traces: `time`, `vdd`, `clk`, `dout`.
- `P_RISING_EDGE_LATCH`: exercise and make observable: Each rising CLK midpoint crossing latches one comparison result; falling crossings do not resample the input. Required traces: `time`, `vdd`, `clk`, `vinn`, `vinp`, `dout`.
- `P_OFFSET_DECISION`: exercise and make observable: With vn zero, DOUT latches high exactly when VINP minus VINN exceeds vos and low otherwise. Required traces: `time`, `clk`, `vinn`, `vinp`, `dout`.
- `P_SEEDED_RANDOM_TERM`: exercise and make observable: With vn nonzero, each latch decision includes a normal input-referred term scaled by vn from the sequence initialized by seed_init. Required traces: `time`, `clk`, `vinn`, `vinp`, `dout`.
- `P_INTEREDGE_HOLD`: exercise and make observable: The latched decision holds between rising CLK events even if VINP or VINN changes. Required traces: `time`, `clk`, `vinn`, `vinp`, `dout`.
- `P_DELAY_AND_SMOOTHING`: exercise and make observable: DOUT applies td delay and tr transition smoothing after each latch event. Required traces: `time`, `clk`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- At `initial_step`, derive `vh`, `vl`, and the clock threshold from `VDD` and
  `GND`, and initialize the random seed from `seed_init`.
- On each rising crossing of `CLK` through the midpoint of the supply rails,
  latch whether `VINP - VINN` exceeds `vos` plus the random decision term.
- When `vn` is zero, the random term is deterministic zero; when `vn` is
  nonzero, draw it from a normal distribution using the initialized seed.
- Hold the latched value between clock events.
- Drive `DOUT` to the derived supply rails with the configured delay and
  transition time.


The required trace names are: `time`, `vdd`, `clk`, `vinn`, `vinp`, `dout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
