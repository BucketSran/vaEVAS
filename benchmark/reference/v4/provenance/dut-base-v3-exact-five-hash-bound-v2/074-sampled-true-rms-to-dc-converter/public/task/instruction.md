# Sampled True-RMS-to-DC Converter

## Task Contract

Implement a sampled true-RMS-to-DC signal-conditioning core.

- Form: `dut`
- Level: `L1`
- Category: `baseband_signal_conditioning`
- Target artifact: `sampled_true_rms_to_dc.va`

The DUT converts differential voltage samples into a held DC voltage equal to
the true RMS of each non-overlapping four-sample window.

## Public Verilog-A Interface

```verilog
module sampled_true_rms_to_dc(vinp, vinn, clk, reset, enable, rms_out, valid);
```

Inputs:

- `vinp`, `vinn`: differential electrical input; the sampled value is `V(vinp,vinn)`.
- `clk`: electrical sampling clock.
- `reset`: active-high asynchronous reset.
- `enable`: active-high sample enable.

Outputs:

- `rms_out`: held true-RMS result in volts.
- `valid`: active-high completion indication for the most recently completed window.

## Public Parameter Contract

| Parameter | Default | Contract |
| --- | ---: | --- |
| `vth` | `0.45 V` | Logic threshold used for `clk`, `reset`, and `enable`. |
| `vhigh` | `0.9 V` | Logic-high level driven on `valid`. |
| `tr` | `100 ps` | Rise/fall smoothing for `rms_out` and `valid`; must be positive. |

The window length is fixed at four accepted samples and is not parameterized.

## Required Behavior

- On each rising `clk` crossing, accept `V(vinp,vinn)` only when `reset` is low
  and `enable` is high.
- Accumulate the square of each accepted sample. On the fourth accepted sample,
  update `rms_out` to `sqrt(sum(sample^2)/4)` and start a new empty window.
- Disabled clock edges do not advance or clear a partial window. They hold
  `rms_out` and deassert `valid`.
- `valid` is asserted for one sampling interval when a four-sample window
  completes, then deasserted at the next rising clock edge.
- Between update events, both outputs hold their state.
- A rising `reset` asynchronously clears the partial window, drives `rms_out`
  to `0 V`, and deasserts `valid`. While reset is high, clock edges keep the
  converter cleared.

## Modeling Constraints

Use deterministic, pure voltage-domain event-driven Verilog-A. Detect sampling
edges with `cross()`, smooth driven outputs with `transition()`, and use real
arithmetic for squaring, averaging, and `sqrt()`. Do not use file I/O, hidden
state ports, current contributions, transistor-level devices, or hard-coded
testbench timing or input values.

## Output Contract

Return exactly one complete Verilog-A file named `sampled_true_rms_to_dc.va`.
