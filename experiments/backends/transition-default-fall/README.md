# Positive explicit transition rise, omitted fall

Frozen sources/decks and independent analytical segments for #66-T. Current candidate supports three arguments by binding omitted fall to the positive instance-constant rise, preserving the original Transition IR and callsite origin. Zero/unspecified rise, dynamic parameters and continuous voltage targets remain unsupported. This does not complete original va01/va02 or #66.

Normative rules: Verilog-AMS LRM2.4.0 §4.5.8, printed pages72–73, and Cadence Verilog-A Language Reference January2022/Product21.1, printed pages183–186. Only positive rise specified supplies both rise and fall. Interrupted edges remain continuous; same direction retains first origin, reversal uses previous destination. The new slope is computed between that origin and target over a full edge duration. Cadence explicitly describes equivalent falling behavior.

Each source has complete rise/fall, reverse, same-direction extension, reflected falling reversal and repeated unchanged target. Two instances have distinct fixed edge/delay settings and eight independent operator histories. Sparse/dense original three-argument cases differ only in strobetimes; explicit four-argument sparse is auxiliary equivalence evidence. `independent-segments.json` fixes exact rational affine tables and 71/407 queries. Tables derive from the manual rules, not EVAS execution or four-argument equality. Expected native-time values must evaluate those tables at exact binary64 query times.

Frozen waveform budget is1e-8V, timer window1e-18s; count/identity exact. Preserve actual raw times, required coverage and ordinary failures. Missing required times may not be replaced by nearby times. Held target outputs expose state, but nominal callback points require their allowed pre/post classification; a single callback trajectory must explain all samples. Actual controls and all retained failures are recorded in [evidence.json](evidence.json). Existing four-argument historical comparisons do not qualify this new source.

Development checks: `test_transition_defaults` tests complete edges, interruption/reflection, two instances/callsites, repeated targets and unsupported argument boundaries through the public compiler and Rust runtime. Main/default source origin is retained. Local independent replay of the frozen three cases has zero waveform difference at all requested points; this is local evidence only, not a Spectre result.


## Actual observations and retained gaps

Spectre21.1.0.509.isr12 executed the original sparse/dense three-argument sources and auxiliary four-argument source. All saved targets and outputs remained zero. Strict waveform failures are1320/2182/1320; sparse retains49/71 required points, dense385/407, each missing22. These failures are preserved; they do not establish a transition slope defect because the intended held targets never changed.

A separately frozen timer2×2 control changes only period/tolerance. Both period0 and period10 with explicit tolerance1e-12 produce correct held target sequences and identical252-row saved grids/values. Eight waveform outputs satisfy the original1e-8V budget against independent segments and EVAS at every actual native row; Spectre independent maximum is4.44e-16V, EVAS independent maximum0. Period10 with original1e-18 tolerance remains all zero. Within these controls the difference follows tolerance, not period or the absence of a supply. The internal reason or a universal timer minimum is unknown. No six-case timer-only proposal was executed.

Each1e-12 control still covers49/71 requested points, with22 missing. EVAS/Spectre raw targets differ at16 saved values inside the separately frozen1e-12 callback windows; their ordinary pairing failures remain recorded. Saved targets cannot certify hidden callback time or count the repeated unchanged-target callback. Callback window/count qualification staysI. Original1e-18 failures and budgets are unchanged, and belong to the existing timer alignment frontier (#108/#96); no total backend equality is claimed.

`check.py` binds fixed known archive identities and mandatory known source/deck/PSF/log/RESULT paths through the shared evidence helper before reading native rows. `test_check.py` calibrates reversed/extended edge equations, zero-output failures, missing/duplicate times, nonfinite refusal and absent target changes. `local_replay.py` reproduces all frozen71/407 anchors through the public compiler and Rust runtime. `native_replay.py` replays exact native grids and retains waveform/state ordinary failures separately. Run from repository root after building the kernel:

```sh
PYTHONPATH=evas/src:. python3 -B experiments/backends/transition-default-fall/local_replay.py evas/rust_core/target/debug/evas-kernel /tmp/transition-anchors.json
python3 -B -m unittest discover -s experiments/backends/transition-default-fall -p test_check.py
python3 -B -m unittest discover -s experiments/backends/evidence -p 'test_*.py'
python3 -B experiments/backends/transition-default-fall/check.py "$ORIGINAL_COLLECTION/spectre-output/runs" /tmp/transition-original.json
python3 -B experiments/backends/transition-default-fall/check.py "$TIMER_COLLECTION/spectre-output/runs" /tmp/transition-timer.json --mode timer-controls
```

The consumer calibration has 7 checks and the shared archive/PSF calibration has 12. `calibrate_collection.py COLLECTION OUTPUT` also verifies that disposable copies with an empty unpacked manifest or a replaced known PSF fail before parsing. The reviewed helper is included by normal merge of main `2e250c2d161324f151f27c3ca9e45ed32eff164a`. Both real archive analyses were rechecked and remain exactly equal, including failures and missing observations.

Raw archives remain local; this evidence is a bounded candidate comparison, not a public qualification receipt or completion of #66.
