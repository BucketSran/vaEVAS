# Stateless nonlinear transient point-solve contract

This note records a confirmed boundary of the branch-only stateless nonlinear
transient entry. It is a diagnostic contract, not a regression that freezes a
preferred rounded output.

## Contract boundary

For programs with no states, events or history operators, transient execution
solves each requested output time as a point operating point:

```text
F(v; fl(PWL(t))) = 0
```

`fl(PWL(t))` is the kernel's binary64 representative produced by ordinary f64
PWL interpolation. The accepted tolerances apply to the resulting point problem:
original branch residual, row-scaled residual and full Newton correction. They do
not certify the exact-real interpolation of the submitted binary64 PWL knots, the
full arithmetic roundoff chain, or the amplification of input interpolation error
through linear gain or nonlinear sensitivity.

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
`u(1) = 4/3` and therefore `y = 10000000000000000/3`. The current kernel first
forms the rounded representative

```text
fl((1 - 1/3) * 1 + (1/3) * 2) = 1.3333333333333335
```

and accepts `y = 3333333333333334.0` with zero residual for that rounded point
problem. The absolute difference from the exact-PWL reference is `2/3 V`, far
larger than `vabstol = 1e-12` when `reltol = 0`.

This demonstrates a confirmed gap relative to the exact-PWL voltage budget.
Passing the current point residual contract does not close that gap or establish
the stronger total-accuracy claim. Providing that claim would require carrying input interpolation
uncertainty and a linear/nonlinear sensitivity budget through the solve, or a
conservative refusal policy for off-knot observations whose propagated input
uncertainty exceeds the requested voltage budget.
