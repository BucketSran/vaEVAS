# IQ Downconversion Chain Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `IQ Downconversion Chain` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `iq_downconversion_chain.va`:
  - Module `iq_downconversion_chain` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)
    - position 5: `lo_i` (output, electrical)
    - position 6: `lo_q` (output, electrical)
    - position 7: `mix_i` (output, electrical)
    - position 8: `mix_q` (output, electrical)
    - position 9: `phase_mon` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/iq_downconversion_chain.va`
- DUT instance: `XDUT (clk rst vin out metric lo_i lo_q mix_i mix_q phase_mon) iq_downconversion_chain`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`, `lo_i`, `lo_q`, `mix_i`, `mix_q`, `phase_mon`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `iq_downconversion_chain.tr` defaults to `8e-11` s; valid range: tr > 0; sets output transition smoothing.
- `iq_downconversion_chain.vth` defaults to `0.45` V; valid range: finite real; sets clock and reset logic threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_COMMON_MODE`: exercise and make observable: Active-high reset returns I/Q baseband outputs, LO monitors, and mixer monitors to 0.45 V and phase_mon to 0.9 V. Required traces: `time`, `rst`, `out`, `metric`, `lo_i`, `lo_q`, `mix_i`, `mix_q`, `phase_mon`.
- `P_QUADRATURE_SEQUENCE`: exercise and make observable: Successive non-reset rising clk edges cycle the I/Q coefficient pairs through (1,0), (0,1), (-1,0), and (0,-1), then wrap. Required traces: `time`, `clk`, `rst`, `lo_i`, `lo_q`, `phase_mon`.
- `P_LO_MONITORS`: exercise and make observable: Lo_i and lo_q equal 0.45 V plus 0.40 V times their current quadrature coefficients. Required traces: `time`, `lo_i`, `lo_q`, `phase_mon`.
- `P_MIXER_MONITORS`: exercise and make observable: Each mixer monitor equals 0.45 V plus 1.25 times the vin deviation times its LO coefficient, clamped to 0.02 V through 0.88 V. Required traces: `time`, `vin`, `lo_i`, `lo_q`, `mix_i`, `mix_q`.
- `P_BASEBAND_UPDATES`: exercise and make observable: On each valid edge, out and metric apply the public 0.85 first-order update toward mix_i and mix_q respectively and remain clamped to 0.02 V through 0.88 V. Required traces: `time`, `clk`, `mix_i`, `mix_q`, `out`, `metric`.
- `P_PHASE_MONITOR`: exercise and make observable: Phase_mon exposes the current four-state phase as phase/3 times 0.9 V. Required traces: `time`, `clk`, `phase_mon`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On reset, return the I/Q baseband outputs, LO monitors, and mixer monitors to
the 0.45 V common-mode level. Drive `phase_mon` to 0.9 V on reset and
initialize the phase state so the first post-reset rising `clk` crossing
advances to phase 0.

After reset releases, advance a four-state quadrature LO sequence on each
rising `clk` crossing and wrap from phase 3 back to phase 0. Use this
coefficient table:

| Phase | I coefficient | Q coefficient |
| ---: | ---: | ---: |
| 0 | 1.0 | 0.0 |
| 1 | 0.0 | 1.0 |
| 2 | -1.0 | 0.0 |
| 3 | 0.0 | -1.0 |

For each phase, drive `lo_i` and `lo_q` as
`0.45 V + 0.40 V * coefficient`. Compute each mixer monitor as
`0.45 V + 1.25 * (vin - 0.45 V) * coefficient`, then clamp each mixer monitor
to `[0.02 V, 0.88 V]`.

Update each I/Q baseband state once per valid clock edge using
`state_next = state_prev + 0.85 * (mixer_value - state_prev)`, then clamp the
state to `[0.02 V, 0.88 V]`. Drive `out` from the I-path state and `metric`
from the Q-path state. Drive `phase_mon` as `phase / 3.0 * 0.9 V`.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`, `lo_i`, `lo_q`, `mix_i`, `mix_q`, `phase_mon`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
