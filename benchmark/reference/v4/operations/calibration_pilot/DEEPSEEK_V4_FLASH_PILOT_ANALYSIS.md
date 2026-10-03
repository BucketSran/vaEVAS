# DeepSeek V4 Flash Calibration Pilot

This is a historical exploratory calibration report, not a benchmark result.
Its materialization counts used an earlier recovery policy. Under the current
strict V4 runner, noncompliant direct envelopes and normalized agentic layouts
remain `invalid_submission` and are not score-eligible.

## Scope

This calibration run covers ten preregistered circuit families, all three task
forms, and G0-G5: 180 cells in total. The 65,536-token episode cap counts
provider completion tokens, including hidden reasoning and visible completion.
Tool output is recorded separately. Sixty-six uncensored 4,096-token episodes
were reused after a mechanical hash and truncation audit; the remaining 114
cells were rerun.

EVAS feedback results below are provisional diagnostics. Spectre remains the
final judge for paper-facing benchmark scores.

## Budget Effect

| Metric | 4,096 diagnostic | 65,536 calibrated | Change |
|---|---:|---:|---:|
| Materialized candidates under historical recovery policy | 95/180 | 178/180 | +83 |
| No complete submission | 85/180 | 2/180 | -83 |
| EVAS feedback pass | 50/180 | 92/180 | +42 |
| Overall pass rate | 27.8% | 51.1% | +23.3 pp |
| Pass among complete submissions | 52.6% | 51.7% | -0.9 pp |

The large overall improvement primarily comes from removing output truncation,
not from making the checker easier. Conditional correctness among complete
submissions changes only modestly.

## G0-G5 Results

| Mode | Pass | Fail | No submission | Overall pass | Submission rate | Pass given submission |
|---|---:|---:|---:|---:|---:|---:|
| G0 | 12 | 18 | 0 | 40.0% | 100.0% | 40.0% |
| G1 | 11 | 18 | 1 | 36.7% | 96.7% | 37.9% |
| G2 | 14 | 16 | 0 | 46.7% | 100.0% | 46.7% |
| G3 | 17 | 12 | 1 | 56.7% | 96.7% | 58.6% |
| G4 | 18 | 12 | 0 | 60.0% | 100.0% | 60.0% |
| G5 | 20 | 10 | 0 | 66.7% | 100.0% | 66.7% |

These are one-repetition descriptive results. They do not establish a causal
skill or feedback effect. G4/G5 also consume substantially more output tokens,
model calls, tool calls, feedback calls, and wall time.

## Results By Form

| Form | Pass | Fail | No submission | Pass rate |
|---|---:|---:|---:|---:|
| DUT | 33 | 25 | 2 | 55.0% |
| Bugfix | 49 | 11 | 0 | 81.7% |
| Testbench | 10 | 50 | 0 | 16.7% |

Testbench construction remains the primary capability bottleneck even after
submission truncation is largely removed.

## Token And Tool Telemetry

| Mode | Median output tokens | Total output tokens | Reasoning tokens | Model calls | Feedback calls |
|---|---:|---:|---:|---:|---:|
| G0 | 3,372.5 | 153,029 | 124,459 | 30 | 0 |
| G1 | 3,403.0 | 139,079 | 107,728 | 30 | 0 |
| G2 | 10,028.0 | 651,816 | 456,629 | 324 | 42 |
| G3 | 8,150.5 | 468,438 | 322,084 | 287 | 50 |
| G4 | 11,891.5 | 801,386 | 537,362 | 596 | 193 |
| G5 | 11,458.0 | 859,728 | 590,937 | 697 | 249 |

Across all cells, median output use is 6,178 tokens and mean use is 17,074.9.
Twenty-three cells reached 65,536 tokens after already materializing a complete
submission; four of those submissions passed EVAS feedback. No cell ended as a
file-less `budget_exhausted` result.

## Direct Output Protocol Audit

Only 13/60 direct responses followed the exact artifact envelope. An offline
diagnostic normalizer could mechanically materialize 59/60 without inspecting
or editing code semantics: 23 single-artifact fenced blocks, 16 uniquely
labeled multi-block responses, one uniquely labeled multi-file block, six
malformed but unambiguous envelopes, and 13 exact envelopes. That recovery is
useful for transport diagnosis only. The 47 non-exact responses remain invalid
under the current V4 protocol and cannot enter formal scoring.

Of nine historically recovered candidates, three passed EVAS behavior checks
and six failed compilation or behavior checks. Those behavior results may be
reported separately as exploratory analysis, not as benchmark outcomes.

## Original Cells Without Complete Submission

- G0: none
- G1: `v4-342` (diagnostically recoverable, not score-eligible)
- G2: none
- G3: `v4-307` (diagnostically recoverable, not score-eligible)
- G4: none
- G5: none

The aggregate tables above preserve the historical pilot accounting. Both
cells remain transport-protocol noncompliant; their Verilog-A behavior can be
inspected separately but must not alter the formal denominator or score.

## Decision

Freeze 65,536 provider output tokens as the pilot episode ceiling for G0-G5.
Count hidden reasoning in the same budget, stop immediately on normal
completion, retain actual token and wall-time telemetry, and classify provider
or judge timeouts as infrastructure errors rather than benchmark failures.

The formal multi-model campaign must use a frozen runner and provider adapter,
record the exact provider model identifier and timestamp, and use Spectre as
the final judge. Hosted aliases without a pinned snapshot require a fresh run
within one controlled campaign window.

## Artifact Digests

- 4,096 campaign: `c428aba9067f27250318fd4c1d5cf77ceb102250bdbf183199e76453fa55f63c`
- 65,536 campaign: `d171b087db082c0b3777f792bdb6bb30191057ce2e2b69ce5820307b8968989d`
- Reuse manifest: `c89bf1f9515dff166e990faca78d52d48002d6b3efc1efa19b56b5911c417a5b`
- Original EVAS score report before path repair: `5ad3a4f565750a9152a6884e300913c695a9250884a9018803960a85ab1f1f68`

## Submission-Path Repair

Five agentic Testbench episodes wrote the requested artifact under the literal
prompt path `public/submission/testbench.scs`. The original file tool treated
that public path as relative to the submission root and therefore nested it a
second time. A hash-preserving diagnostic repair promoted those five files and
recorded an audit entry without invoking the model again. All five then failed
EVAS feedback: three on deck syntax and two on insufficient stimulus or
observation windows. The repairs are not score-eligible under the current
strict runner.

- Layout-repair report: `db86dbf38e9dd9166e3810547ba258166d724dd16c6ba3b067de76d9b3501606`
- Direct-protocol audit: `4e1ff93ac1d94b32838bd34dd0f82bb5e5790c0cb14b4cdb8db6beee2089ba67`
- Final rescored EVAS report: `436c89e8748b9ab5bec98690b491e0bb5fbe4523c468d2517dc37620f5235ae4`
