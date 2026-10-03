# Vargain Diffamp Clip Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Vargain Diffamp Clip` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `vargain_diffamp_clip.va`:
  - Module `vargain_diffamp_clip` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigctrl_p` (input, electrical)
    - position 3: `sigctrl_n` (input, electrical)
    - position 4: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/vargain_diffamp_clip.va`
- DUT instance: `XDUT (sigin_p sigin_n sigctrl_p sigctrl_n sigout) vargain_diffamp_clip`
- Required saved public traces: `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `vargain_diffamp_clip.gain_const` defaults to `3.0`; valid range: finite; overrides gain_const.
- `vargain_diffamp_clip.sigout_high` defaults to `1.0`; valid range: finite; overrides sigout_high.
- `vargain_diffamp_clip.sigout_low` defaults to `-1.0`; valid range: finite; overrides sigout_low.
- `vargain_diffamp_clip.sigin_offset` defaults to `0.05`; valid range: finite; overrides sigin_offset.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_COMPUTE_THE_DIFFERENTIAL_SIGNAL_AS_V`: exercise and make observable: Compute the observable input signal as `V(sigin_p, sigin_n)`. Required traces: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.
- `P_COMPUTE_THE_DIFFERENTIAL_CONTROL_AS_V`: exercise and make observable: Compute the gain-control term as `V(sigctrl_p, sigctrl_n)` with the documented polarity. Required traces: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.
- `P_SUBTRACT_SIGIN_OFFSET_FROM_THE_DIFFERENTIAL`: exercise and make observable: Subtract `sigin_offset` from the differential input before gain multiplication. Required traces: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.
- `P_MULTIPLY_THE_OFFSET_CORRECTED_SIGNAL_BY`: exercise and make observable: Multiply the offset-corrected signal by the differential control and `gain_const`. Required traces: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.
- `P_CLAMP_THE_RESULT_TO_THE_PUBLIC`: exercise and make observable: Clamp the amplified target to the public positive and negative output limits. Required traces: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.
- `P_DRIVE_SIGOUT_WITH_THE_CLIPPED_TARGET`: exercise and make observable: Drive `sigout` with the clipped target transfer and correct output scale. Required traces: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Compute the differential signal as `V(sigin_p, sigin_n)`.
- Compute the differential control as `V(sigctrl_p, sigctrl_n)`.
- Subtract `sigin_offset` from the differential signal.
- Multiply the offset-corrected signal by the differential control and `gain_const`.
- Clamp the result to the public output limits.
- Drive `sigout` with the clipped target.


The required trace names are: `time`, `sigctrl_n`, `sigctrl_p`, `sigin_n`, `sigin_p`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
