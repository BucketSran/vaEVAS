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
Spectre and EVAS are recorded as strict phase F. Window compatibility remains
separate: an in-window difference is I, an outside-window difference is F.
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

The [compact evidence](evidence.json) records one actual Spectre configuration
with two instances. Under the original stop=1 request, 80 native rows and 720
paired voltages pass the frozen budget. The final raw row lies beyond that stop.
The explicit supplemental stop+1ULP request pairs all 81 rows and 729 voltages;
that full pairing has a different request identity. All 81 raw rows separately
satisfy the independent formula budget. No cross-backend stage difference
was observed. EVAS canonical/sparse/dense common outputs and states agree, and
event records agree; internal accepted step counts differ between query grids.

Strict native observation remains I. Five of nine exact decimal requested
anchors are present; the terminal token is `1.0000000000000002`. The supplemental
EVAS request explicitly extends stop and holds the original input endpoint over
that one-ULP interval solely to query every exported row. It does not certify the
canonical request's exact endpoint. No jump interpolation is used.

The original source/deck/manifest hashes are unchanged. Spectre completed in
25.837658 seconds under the same 90-second limit. A compiler-cache input from the
first timeout lane was retained, but Spectre actually compiled N2 and N3 again
in 11.5 and 11.3 seconds. The reason for the shorter compilation is unknown.
The first lane's immutable timeout archive remains separately identified; it
contains no waveform and establishes no numerical failure.

The shared archive helper authenticates all 64 regular archive members before
reading the output manifest or waveform. The output manifest lists 36 files.
[Negative controls](archive-negative-controls.json) mutate copies of that
manifest and PSF: both exit ERROR 2 before writing analysis evidence.
The original RESULT's ms readback I is preserved. PR109 readback reparses the
original log and PSF successfully: effective stop 1 s, maxstep 0.025 s, traponly,
reltol 1e-6, voltage absolute tolerance 1e-7 V. The global requested reltol is
1e-5, distinct from the conservative transient effective value.

Reanalysis from the repository root, using retained local-only raw:

```sh
PYTHONPATH=evas/src:. python3 -B experiments/backends/initial-static-loop/analyze.py \
  --collection /absolute/path/to/initial-loop-reference-v2/collected/spectre \
  --readback experiments/backends/paper/settings_readback.py \
  --output runs/initial-event-static-loop/fresh-analysis \
  --evidence runs/initial-event-static-loop/fresh-evidence.json
```

The raw is local-only; compact identities do not establish public replay.
[Review adjudication](review-notes.md) explains F1–F4 and the stricter frozen
Spectre timer window. This slice leaves general runtime loops, dynamic indices,
and complete #65/SAR support unresolved.

## Offline settings qualification repair

The original shared reader verifies log/PSF internal consistency. The additional
`settings_contract.py` now checks frozen requested globals, stop/maxstep/method,
PSF metadata, and this probe's declared effective conservative profile. Its P
comes from successful checks rather than an unconditional report field. The
20 calibrations include a synthetic log/PSF pair that agrees on a wrong maxstep:
the shared reader accepts its consistency and the frozen contract rejects it.
They also reject wrong requested controls, consistent wrong effective controls,
missing/nonfinite controls, and preserve the 15 waveform/phase controls.

This metadata reanalysis reuses the four original EVAS requests/responses from
`actual-native-analysis-v4`, authenticates every prior artifact against fixed
a6a1b0c7 evidence, authenticates the original Spectre archive again, and verifies
exact JSON Program equality with source dc177010 after the resource diagnostic
fix and normal merge of main PR114. It executes no simulator. Original numerical
production/kernel identities and original RESULT remain preserved in evidence;
the current source/kernel identity is recorded separately for reuse assessment.
Both raw-copy tamper controls also reject through this offline entry with ERROR2.

```sh
PYTHONPATH=evas/src:. python3 -B experiments/backends/initial-static-loop/reanalyze_settings.py \
  --collection /absolute/path/to/initial-loop-reference-v2/collected/spectre \
  --prior-analysis runs/initial-event-static-loop/actual-native-analysis-v4 \
  --output runs/initial-event-static-loop/fresh-settings-analysis \
  --evidence runs/initial-event-static-loop/fresh-settings-evidence.json
```
