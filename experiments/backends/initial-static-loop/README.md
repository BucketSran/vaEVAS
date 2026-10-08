# Initial static loop comparison

This checker owns the frozen 65-I probe in
[`evas/validation/cases/initial_static_loop`](../../../evas/validation/cases/initial_static_loop).
One Spectre configuration contains two instances. Initialization establishes
`[0,1]` and `[10,11,12]`; the timer establishes `[40,41]` and `[70,71,72]`;
the rising cross restores the initialization values. The hand sums are
`1 → 81 → 1` and `33 → 213 → 33`.

`check.py` checks every saved observer and sum against those independent
platforms. Each instance must show exactly two observed stage transitions.
Their exported time brackets must intersect the frozen timer/cross windows.
These brackets do not certify internal callbacks or repeated assignments whose
values are identical. Public EVAS regressions separately check non-idempotent
updates, duplicate OR leaves, and unique element initialization.

The voltage budget is the frozen `1e-7 + 1e-5 |independent expected voltage|`.
A boundary sample may contain either permitted stage. Different stages in
Spectre and EVAS are recorded as I; an outside-window stage difference is F.
Every same-stage voltage remains in the comparison denominator. There is no
interpolation across jumps. Exact decimal initial, stop, and nine requested
anchors are separate observation obligations; missing anchors remain I.
Empty, nonfinite, incomplete, or decreasing-time input is an error, not a
passing or failing numerical waveform.

Run checker calibration from the repository root:

```sh
python3 -B -m unittest discover -s experiments/backends/initial-static-loop -p 'test_*.py' -v
```

The calibration hand table is independent of the checker constants. Controls
cover wrong sums and each observer, mixed element stages, instance aliasing,
missing/repeated transitions, phase differences, exact-anchor omissions,
terminal decimal overshoot, malformed input, and absent candidate queries.

Actual Spectre evidence is pending. The first lane exhausted its 90-second
compilation limit before exporting a waveform. It establishes no numerical
verdict. A subsequent lane must retain its own execution identity, including
any reused compiler cache, and authenticate its fixed archive before reading
logs or PSF. No production behavior or frozen input is changed by this checker.
