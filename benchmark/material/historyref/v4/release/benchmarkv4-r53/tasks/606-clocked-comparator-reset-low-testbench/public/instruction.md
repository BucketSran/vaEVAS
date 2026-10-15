# Clocked Comparator Reset Low Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Comparator Reset Low` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clocked_comparator_reset_low.va`:
  - Module `clocked_comparator_reset_low` (entry)
    - position 0: `CMPCK` (input, electrical)
    - position 1: `VINN` (input, electrical)
    - position 2: `VINP` (input, electrical)
    - position 3: `DCMPN` (output, electrical)
    - position 4: `DCMPP` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clocked_comparator_reset_low.va`
- DUT instance: `XDUT (cmpck vinn vinp dcmpn dcmpp) clocked_comparator_reset_low`
- Required saved public traces: `cmpck`, `vinn`, `vinp`, `dcmpn`, `dcmpp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `clocked_comparator_reset_low.vdd` defaults to `0.9` V; valid range: vdd > 0; sets logic-high level and twice the CMPCK decision threshold.
- `clocked_comparator_reset_low.td_cmp` defaults to `1e-10` s; valid range: td_cmp >= 0; sets output decision delay.
- `clocked_comparator_reset_low.tr` defaults to `1e-11` s; valid range: tr >= 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_RESET_LOW`: exercise and make observable: Both decision outputs initialize low. Required traces: `time`, `dcmpn`, `dcmpp`.
- `P_FALLING_EDGE_RESET_LOW`: exercise and make observable: Each falling CMPCK crossing through vdd/2 resets both DCMPN and DCMPP low. Required traces: `time`, `cmpck`, `dcmpn`, `dcmpp`.
- `P_POSITIVE_DIFFERENTIAL_DECISION`: exercise and make observable: On a rising CMPCK crossing with VINP greater than VINN, DCMPP is high and DCMPN is low. Required traces: `time`, `cmpck`, `vinp`, `vinn`, `dcmpn`, `dcmpp`.
- `P_NEGATIVE_DIFFERENTIAL_DECISION`: exercise and make observable: On a rising CMPCK crossing with VINP less than VINN, DCMPN is high and DCMPP is low. Required traces: `time`, `cmpck`, `vinp`, `vinn`, `dcmpn`, `dcmpp`.
- `P_EQUAL_INPUT_RESET_STATE`: exercise and make observable: On a rising CMPCK crossing with equal inputs, both outputs remain low. Required traces: `time`, `cmpck`, `vinp`, `vinn`, `dcmpn`, `dcmpp`.
- `P_LATCHED_HOLD_AND_TIMING`: exercise and make observable: The reset or decided state holds between CMPCK events and output changes use td_cmp delay and tr smoothing. Required traces: `time`, `cmpck`, `dcmpn`, `dcmpp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize both decision outputs low.
- Whenever `CMPCK` falls through `vdd/2`, reset both decision outputs low.
- Whenever `CMPCK` rises through `vdd/2`, latch a differential decision:
  `DCMPP` high for `VINP > VINN`, `DCMPN` high for `VINP < VINN`, and both
  outputs remain low for an equal-input decision.
- Hold the latched or reset state until the next clock event.
- Drive outputs as smooth voltage-domain levels using the configured delay and
  transition time.


The required trace names are: `time`, `cmpck`, `vinn`, `vinp`, `dcmpn`, `dcmpp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
