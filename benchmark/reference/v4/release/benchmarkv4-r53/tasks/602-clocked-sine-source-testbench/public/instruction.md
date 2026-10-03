# Clocked Sine Source Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Sine Source` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `vin_src.va`:
  - Module `vin_src` (entry)
    - position 0: `CLK` (input, electrical)
    - position 1: `RST_N` (input, electrical)
    - position 2: `VOUT_P` (output, electrical)
    - position 3: `VOUT_N` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/vin_src.va`
- DUT instance: `IVIN_SEED_A (clk rst_n vinp vinn) vin_src SEED=17 ampl=0.02 freq=fin sigma=VIN_NOISE vdd=vdd vth=0.45`
- DUT instance: `IVIN_SEED_B (clk rst_n vinp_seed_b vinn_seed_b) vin_src SEED=17 ampl=0.02 freq=fin sigma=VIN_NOISE vdd=vdd vth=0.45`
- DUT instance: `IVIN_SEED_ALT (clk rst_n vinp_seed_alt vinn_seed_alt) vin_src SEED=29 ampl=0.02 freq=fin sigma=VIN_NOISE vdd=vdd vth=0.45`
- DUT instance: `IVIN_SIGMA0 (clk rst_n vinp_sigma0 vinn_sigma0) vin_src SEED=17 ampl=0.02 freq=fin sigma=0 vdd=vdd vth=0.45`
- Required saved public traces: `clk`, `rst_n`, `vinp`, `vinn`, `vamp_p`, `vamp_n`, `vinp_seed_b`, `vinn_seed_b`, `vinp_seed_alt`, `vinn_seed_alt`, `vinp_sigma0`, `vinn_sigma0`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `vin_src.vdd` defaults to `0.9` V; valid range: vdd > 0; sets twice the output common-mode level.
- `vin_src.vth` defaults to `0.45` V; valid range: finite real; sets CLK and active-low reset decision thresholds.
- `vin_src.ampl` defaults to `0.15` V; valid range: ampl >= 0; sets sampled sine amplitude on VOUT_P.
- `vin_src.freq` defaults to `300000.0` Hz; valid range: freq >= 0; sets sampled sine frequency.
- `vin_src.sigma` defaults to `0.01` V; valid range: sigma >= 0; sets the scale of the optional deterministic seeded perturbation on VOUT_P.
- `vin_src.SEED` defaults to `0`; valid range: any integer accepted by the simulator random function; initializes the repeatable perturbation sequence.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_COMMON_MODE`: exercise and make observable: While RST_N is below vth, both outputs hold near vdd divided by two. Required traces: `time`, `rst_n`, `vinp`, `vinn`, `vinp_seed_b`, `vinn_seed_b`, `vinp_seed_alt`, `vinn_seed_alt`, `vinp_sigma0`, `vinn_sigma0`.
- `P_RISING_EDGE_SAMPLE`: exercise and make observable: After reset release, VOUT_P updates only on rising CLK crossings through vth. Required traces: `time`, `clk`, `rst_n`, `vinp`.
- `P_SAMPLED_SINE`: exercise and make observable: At each qualifying clock edge, VOUT_P samples vdd/2 plus ampl times sin(2*pi*freq*time), plus the optional seeded perturbation. Required traces: `time`, `clk`, `rst_n`, `vinp`.
- `P_REFERENCE_SIDE_COMMON_MODE`: exercise and make observable: VOUT_N remains at vdd divided by two during reset and active sampling. Required traces: `time`, `rst_n`, `vinn`.
- `P_INTEREDGE_HOLD`: exercise and make observable: Both outputs hold their sampled values between CLK events rather than continuously recomputing the sine or perturbation. Required traces: `time`, `clk`, `vinp`, `vinn`.
- `P_SEEDED_REPEATABILITY`: exercise and make observable: For fixed SEED, sigma, controls, and timing, the sampled perturbation sequence and outputs are repeatable; sigma zero removes the perturbation. Required traces: `time`, `clk`, `rst_n`, `vinp`, `vinn`, `vinp_seed_b`, `vinn_seed_b`, `vinp_seed_alt`, `vinn_seed_alt`, `vinp_sigma0`, `vinn_sigma0`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

This is an L2 measurement-flow stimulus macro, retained as an independent DUT
because it provides the clocked differential source used by composed gain and
linearity measurement flows. Implement `vin_src.va`, a clocked differential
sine stimulus source that can support composed measurement flows such as
gain-extraction benches.

On each rising crossing of `CLK`, if `RST_N` is high, update `VOUT_P` to a
sampled sine value around `vdd/2`. Keep `VOUT_N` at `vdd/2` as the reference
side. While reset is low, hold both outputs near `vdd/2`.

```text
VOUT_P = vdd/2 + ampl*sin(2*pi*freq*t) + optional deterministic perturbation
VOUT_N = vdd/2
```

Use the public parameters `vdd`, `vth`, `ampl`, `freq`, `sigma`, and `SEED`
where applicable. The important behavioral boundary is that the source is
clocked/sample-held rather than continuously recomputing random values at every
analog evaluation point.

Public parameters:

- `vdd = 0.9 V`: positive output common-mode supply parameter.
- `vth = 0.45 V`: voltage threshold for `CLK` and `RST_N`.
- `ampl = 0.15 V`: sine amplitude before any testbench override.
- `freq = 300 kHz`: sine frequency before any testbench override.
- `sigma = 0.01 V`: deterministic random perturbation scale.
- `SEED = 0`: seed used to initialize an instance-local integer RNG state.

Sample the sine and random perturbation only on rising `CLK` crossings after
reset release. Initialize a per-instance integer RNG state from `SEED`, and
pass that state to `$rdist_normal` so two independent instances with the same
seed produce the same sequence while different seeds select different
sequences. `VOUT_N` should remain at `vdd/2`; the perturbation is applied to
the positive side so the composed measurement flow sees a repeatable
single-ended stimulus component. With `sigma=0`, the sampled output must reduce
to the unperturbed sine even though the RNG state may still advance.

Use `vth` with a default near 0.45 V to interpret the voltage-coded `CLK` and
`RST_N` control inputs, and keep the model pure behavioral Verilog-A. Do not use
transistor-level devices, AC/noise analysis, waveform files, validation artifacts,
or simulator side channels.

Only `vin_src.va` is the source macro under review. The public harness supplies
`lfsr.va`, `dither_adder.va`, and `gain_amp_fixed.va` for composed-flow
evaluation; do not return or redefine those support modules.


The required trace names are: `time`, `clk`, `rst_n`, `vinp`, `vinn`, `vamp_p`, `vamp_n`, `vinp_seed_b`, `vinn_seed_b`, `vinp_seed_alt`, `vinn_seed_alt`, `vinp_sigma0`, `vinn_sigma0`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Include the supplied read-only support files only from
  `./dut/support/...`; do not reference `./support/...` or undeclared paths.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
