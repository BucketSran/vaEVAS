# Dither Noise Like Deterministic Source Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Dither Noise Like Deterministic Source` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `noise_gen_ref.va`:
  - Module `noise_gen` (entry)
    - position 0: `vin_i` (input, electrical)
    - position 1: `vout_o` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/noise_gen_ref.va`
- DUT instance: `IDUT_DEFAULT (vin_i vout_default) noise_gen`
- DUT instance: `IDUT_OVERRIDE (vin_i vout_override) noise_gen dt=0.8n sigma=0.037`
- Required saved public traces: `vin_i`, `vout_default`, `vout_override`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `noise_gen.sigma` defaults to `0.01` V; valid range: sigma >= 0; scales the held deterministic perturbation added to vin_i.
- `noise_gen.dt` defaults to `5e-10` s; valid range: dt > 0; sets the periodic interval between perturbation-sample updates.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PERIODIC_UPDATE`: exercise and make observable: The deterministic perturbation sample updates once every dt seconds. Required traces: `time`, `vin_i`, `vout_default`, `vout_override`.
- `P_SAMPLE_HOLD`: exercise and make observable: Between update events, the perturbation vout_o minus vin_i remains piecewise constant. Required traces: `time`, `vin_i`, `vout_default`, `vout_override`.
- `P_ADDITIVE_OUTPUT`: exercise and make observable: At all times after the first update, vout_o equals vin_i plus sigma times the currently held normalized perturbation sample. Required traces: `time`, `vin_i`, `vout_default`, `vout_override`.
- `P_DETERMINISTIC_SEQUENCE`: exercise and make observable: The normalized perturbation sample repeats the public eight-sample sequence [-1.0, -0.5, 0.0, 0.5, 1.0, 0.5, 0.0, -0.5], advancing by one entry at each dt update. Required traces: `time`, `vin_i`, `vout_default`, `vout_override`.
- `P_ZERO_MEAN_DITHER`: exercise and make observable: Every complete eight-sample sequence period is exactly zero mean, and every perturbation is bounded within [-sigma, +sigma]. Required traces: `time`, `vin_i`, `vout_default`, `vout_override`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Generate a sampled, zero-mean, noise-like deterministic perturbation and add it
to `V(vin_i)`. The output is piecewise constant between sample events:

```text
vout_o = V(vin_i) + sigma * sample
```

The normalized perturbation `sample` must repeat this public eight-sample sequence, advancing by one entry at each `dt` update:

```text
[-1.0, -0.5, 0.0, 0.5, 1.0, 0.5, 0.0, -0.5]
```

Every complete eight-sample period is exactly zero mean, and every perturbation must remain bounded within `[-sigma, +sigma]`.

Use a periodic timer-driven sample-and-hold style, such as `@(timer(0, dt))`,
so the perturbation is updated once per sample interval rather than recomputed
at every analog evaluation point or sampled only once. The task models a
bounded dither/noise-like stimulus source for transient behavioral benches; it
does not require physical noise analysis.


The required trace names are: `time`, `vin_i`, `vout_default`, `vout_override`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
