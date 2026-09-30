# Stateless nonlinear transient waveform-accuracy contract

This note records the precision boundary and the branch-local repair for the
stateless nonlinear transient entry. It is a diagnostic contract, not a frozen
preferred rounded output.

## Proof object

For programs with no states, events or history operators, transient execution
first solves each requested output time as a nominal point operating point:

```text
F(v; fl(PWL(t))) = 0
```

`fl(PWL(t))` is the kernel's binary64 representative produced by ordinary f64
PWL interpolation. The existing Newton acceptance still applies to this point
problem: original branch residual, row-scaled residual and full Newton
correction.

The transient path then performs a separate waveform-accuracy certification. It
builds an interval for each driven input using the existing PWL interval
operation, which encloses the exact real interpolation of the submitted binary64
knots at that output time. Holding the accepted unknown voltages fixed as point
intervals, it replays each original branch relation with interval arithmetic over
that input box. The sample is accepted only if every residual interval is inside
the same voltage budget used by the nominal residual check:

```text
[-B_i, B_i], where B_i = vabstol + reltol * max(abs(lhs_i), abs(rhs_i)).
```

If the interval cannot be made finite or does not fit the budget, the kernel
returns `waveform_accuracy`. This is a conservative refusal, not a relaxed
comparison threshold.

This certification is distinct from a Krawczyk or interval-Newton proof. It does
not prove global root uniqueness, all possible rounded arithmetic paths, or a
complete forward-error bound for arbitrary ill-conditioned polynomials. It does
cover the concrete failure mode where exact-PWL input uncertainty is amplified by
linear gain or by the local sensitivity of an accepted nonlinear relation while
the nominal point residual remains small.

## High-gain diagnostic

Verilog-A body:

```verilog
V(y,r) <+ 1e16 * (V(u,r) - 1);
```

Minimal request shape:

```json
{
  "driven": ["u"],
  "transient": {
    "pwl": [[[0.0, 1.0], [3.0, 2.0]]],
    "output_times": [1.0],
    "stop": 3.0,
    "max_step": 3.0
  },
  "vabstol": 1e-12,
  "reltol": 0.0
}
```

At `t = 1.0`, exact rational arithmetic over the submitted binary64 knots gives
`u(1) = 4/3` and therefore `y = 10000000000000000/3`. The nominal f64 point uses

```text
fl((1 - 1/3) * 1 + (1/3) * 2) = 1.3333333333333335
```

and solves `y = 3333333333333334.0` with zero nominal residual. Relative to the
exact-PWL reference this is `2/3 V` away, far larger than `vabstol = 1e-12` when
`reltol = 0`.

The repaired contract rejects this request with `waveform_accuracy`. The same
model can pass only when the requested voltage budget covers the propagated input
uncertainty; the regression uses `vabstol = 8 V` for that positive control because
the outward interval residual is conservatively bounded by roughly `[-4, 6] V`.

## Remaining scope

The current branch still rejects nonlinear events, state/history/operator
coupling, and non-affine transient dynamics. It also does not implement a general
interval Newton or sensitivity matrix certificate for moving the unknown voltages
over an interval. If a future feature needs to certify root movement itself, it
must add an explicit interval solve or Krawczyk-style proof rather than relying on
nominal residuals.
