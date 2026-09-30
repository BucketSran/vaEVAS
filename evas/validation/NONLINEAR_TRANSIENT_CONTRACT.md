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
intervals, it first replays each original branch relation with interval
arithmetic over that input box. Every residual interval must fit the same voltage
budget used by the nominal residual check:

```text
[-B_i, B_i], where B_i = vabstol + reltol * max(abs(lhs_i), abs(rhs_i)).
```

That residual check is not enough when a small input/residual perturbation is
amplified by feedback. The second certification step builds the local Jacobian
`J = ∂F/∂v` at the accepted point, factors it, and propagates residual intervals
into node-voltage error bounds:

```text
|δv_j| <= Σ_i |(J^{-1})_{j i}| · max(abs(R_i.lo), abs(R_i.hi))
```

Each unknown node error bound must fit `vabstol + reltol * abs(V_j)`. If the
residual interval, Jacobian factorization or forward propagation cannot be made
finite, or if the propagated voltage bound exceeds the requested budget, the
kernel returns `waveform_accuracy`. This is a conservative refusal, not a relaxed
comparison threshold.

For affine networks this is a fixed-coefficient linear forward-error bound over
the existing exact-PWL input interval. For polynomial networks it remains a local
fixed-Jacobian certificate; it is useful for refusing high-gain and ill-conditioned
accepted points, but it is not a Krawczyk or interval-Newton proof. It does not
prove global root uniqueness, all possible rounded arithmetic paths, or a complete
forward-error bound for arbitrary nonlinear polynomials. Cases outside that proof
must stay rejected or receive a future interval solve certificate.

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

## Feedback diagnostic

Verilog-A body:

```verilog
V(y,r) <+ a * V(y,r) + (V(u,r) - 1);
```

with `a = 0.99999999999999`, source knots
`[[0, 1], [3, nextafter(1, +inf)]]`, `t = 1`, `vabstol = 1e-12`, and
`reltol = 0` has a nominal f64 solution `y = -0.0` and a zero nominal residual.
Exact rational arithmetic over the submitted binary64 values gives

```text
u(1) = (2 * 1 + nextafter(1, +inf)) / 3
exact_y = (u(1) - 1) / (1 - a) = 1 / 135 V
```

within the exact binary64 value of `a`. The residual interval is only around one
ulp, but the feedback gain `1 / (1 - a)` amplifies it to millivolts, so the
request must fail `waveform_accuracy` under a `1e-12 V` absolute budget. This is
the counterexample that distinguishes residual replay from forward-error
certification.

## Remaining scope

The current branch still rejects nonlinear events, state/history/operator
coupling, and non-affine transient dynamics. It also does not implement a general
interval Newton or Krawczyk certificate for moving the unknown voltages over an
interval. If a future feature needs to certify nonlinear root movement itself, it
must add an explicit interval solve or Krawczyk-style proof rather than relying on
nominal residuals or the local fixed-Jacobian forward check alone.
