# Element Shuffler Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Element Shuffler` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `element_shuffler.va`:
  - Module `element_shuffler` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst_n` (input, electrical)
    - position 2: `out0` (output, electrical)
    - position 3: `out1` (output, electrical)
    - position 4: `out2` (output, electrical)
    - position 5: `out3` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/element_shuffler.va`
- DUT instance: `XDUT (clk rst_n out0 out1 out2 out3) element_shuffler`
- Required saved public traces: `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `element_shuffler.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets clk and rst_n decision threshold.
- `element_shuffler.vdd` defaults to `0.9` V; valid range: vdd > 0; sets active output high level.
- `element_shuffler.tr` defaults to `3e-10` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_START`: exercise and make observable: Active-low reset establishes the state so the first rising clk edge after release selects out2. Required traces: `time`, `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.
- `P_PERMUTATION`: exercise and make observable: Rising clk edges advance the repeating out2, out0, out3, out1 permutation. Required traces: `time`, `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.
- `P_ONE_HOT`: exercise and make observable: Exactly one output is high in every stable released-reset state. Required traces: `time`, `rst_n`, `out0`, `out1`, `out2`, `out3`.
- `P_RAIL_LEVELS`: exercise and make observable: The selected output approaches vdd and all other outputs approach 0 V with finite smoothing. Required traces: `time`, `out0`, `out1`, `out2`, `out3`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Treat `clk` and `rst_n` as voltage-coded logic signals using threshold `vth`.

`rst_n` is active low. When `rst_n` is low, the shuffler must reset its internal state so the first valid rising edge of `clk` after reset release produces `out2` as the active output.

After reset is released, the active output must advance on each rising edge of `clk` through this repeating permutation:

```text
out2 -> out0 -> out3 -> out1 -> out2 -> ...
```

Exactly one of `out0`, `out1`, `out2`, and `out3` must be high in each stable state. Active outputs should be near `vdd`; inactive outputs should be near `0 V`.

The output sequence must be driven by `clk` and `rst_n` behavior, not by absolute simulation time.


The required trace names are: `time`, `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
