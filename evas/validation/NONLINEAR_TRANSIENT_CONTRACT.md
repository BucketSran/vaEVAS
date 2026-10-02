# Stateless nonlinear transient waveform-accuracy contract

This note records the precision boundary for the stateless nonlinear transient
entry introduced in the IR v15 checkpoint and retained in IR16. Its proof and
independent answers define the contract; no preferred rounded output is frozen.
Joint nonlinear integration and implicit DAE use the separate
[continuous-dynamics contract](../docs/CONTINUOUS.md); the stateless restriction
below applies to this entry, not every nonlinear solver path.

## Proof object

For polynomial programs with no states, events or history operators, transient execution
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

Residual replay alone is insufficient for both point and off-knot inputs: a tiny
residual or arithmetic/input uncertainty can be amplified by feedback or nonlinear
sensitivity. Both now require a restricted root-box certificate: a scalar
monotonicity proof where possible, otherwise the Krawczyk proof below. An exact
input does not imply an exact root.

The residual and interval-Jacobian calculations use the original RHS expression
trees saved by assembly for each branch equation, not the collapsed affine row
used by the fast nominal solve. This preserves cancellation across a legal raw IR expression tree for the certificate; duplicate-node terms inside one affine expression remain invalid IR. The implementation builds an
inner representable voltage box around the accepted nominal solution:

```text
X_j ⊂ [x_j - B_j, x_j + B_j]
B_j = lower(vabstol + reltol * abs(x_j))
```

The inner endpoints ensure the certified box itself does not exceed the requested
voltage budget because of outward-rounded endpoint arithmetic. It then evaluates
`F(x,U)` and the interval Jacobian `J(X,U)` over the original branch relation
available to the solver. Both paths require a square system. Assembly retains
every summed contribution in `original_rhs`; residuals and interval derivatives
sum all of these trees. Splitting or reordering independent contributions does
not itself disable certification. The nominal Jacobian still only supplies an
arbitrary preconditioner, so its collapsed coefficients are not proof objects.
If the scalar proof below succeeds, no preconditioner is constructed. Otherwise
the local floating-point inverse-like matrix `C` is used
only as a preconditioner; it is not treated as an exact inverse. The Krawczyk image
is constructed with outward interval operations:

```text
K(X) = x - C F(x,U) + (I - C J(X,U)) (X - x)
```

The sample is accepted only when `K(X)` is strictly inside `X` and the interval
operator row-sum bound, accumulated with outward interval arithmetic, satisfies:

```text
||I - C J(X,U)||∞ < 1
```

If the system is not square, the residual or Jacobian intervals are nonfinite, or neither
root-box proof succeeds, the kernel returns
`waveform_accuracy`. This is a conservative refusal, not a relaxed comparison
threshold.

In the integrated entry, affine systems retain the existing original-IR affine
forward-error map, including consistent redundant constraints and summed
contributions. They do not use the polynomial Krawczyk shape restrictions.
Input-selected branches remain restricted to affine leaves. For polynomial systems the root-box check certifies a root
inside the requested voltage box under the stated restricted conditions. It
is still not a general-purpose interval solver for arbitrary coupled dynamics;
nonlinear events, state/history/operator coupling and unsupported non-square
cases remain outside this supported subset. Non-square polynomial systems are refused at
point inputs too; the public static `solve` keeps its existing local Newton
contract and does not acquire this transient forward-error proof.

## Scalar monotonicity certificate

The local optimization checkpoint `ddfd379` adds a sufficient scalar proof before
Krawczyk. For a single unknown, suppose the derivative interval on `X × U`
excludes zero. Its sign is constant, with a conservative lower bound
`m = inf(abs(dF/dx)) > 0`. At the accepted representative `x`, define

```text
R = sup(abs(F(x,U)))
E = upper(R / m)
d_left  = lower(x - X.lo)
d_right = lower(X.hi - x)
```

Accept this proof only when `E < d_left` and `E < d_right`. For each fixed input
in `U`, the mean value theorem implies opposite signs at the two endpoints;
continuity gives a root, and the nonzero derivative gives uniqueness within `X`.
The proof uses the original expression tree and outward interval derivatives,
with inward distances and an outward error radius. A small derivative therefore
enlarges `E` instead of allowing a small residual to hide a large voltage error.

If the derivative contains zero, or the strict distance test fails, execution
uses the original Krawczyk path with the already evaluated interval Jacobian.
Multi-unknown systems use Krawczyk. The later precision-chain repair also applies
these proofs at point inputs, closing the earlier residual-only boundary.
This is an EVAS derivation from the mean value theorem, not a claim about another
simulator's internal algorithm. Independent high-precision positive/negative
slope roots, the feedback-amplification rejection and strict-boundary tests are
in `test_nonlinear_transient.py` and `solver.rs`. `test_precision_chain.py` adds
100-digit quadratic roots near the fold `y=u+y²`, exact-input and off-knot
contribution-splitting controls, and acceptance under a provable looser budget.
At `u=.25`, a nominal error around `3.725e-9 V` can coexist with zero rounded
residual and correction. A `1e-12 V` request must not accept that result; the
multiple root cannot pass either nonsingularity-based certificate.

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
uncertainty; the regression retains `vabstol = 8 V` as its positive control. The integrated
affine map and the polynomial interval-residual check both propagate the original
input uncertainty; their conservative bounds need not be numerically identical.

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

The joint candidate still rejects nonlinear events, state/history/operator
coupling, and non-affine transient dynamics. The root-box certificate is limited
to square branch systems at point and off-knot stateless samples. It uses all
saved original RHS trees within each branch, including summed contributions and
legal nested expression cancellation. Duplicate-node terms inside one affine
expression remain invalid IR. It does not replace a future general interval solve for broader
nonlinear dynamic features.
