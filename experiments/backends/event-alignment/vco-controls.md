# Constant VCO: four controlled Spectre observations

These controls diagnose the ordinary phase mismatch from #108/#100. They do not establish general VCO support or resolve the missing observation coverage required by #96. The original constant model remains unchanged; the second model adds an independent `idt` output. No production code or comparison budget changed.

The independent reference is exact rational arithmetic on each binary64 query time: `q = 1/8 + 2^19*t`, `phase = q - floor(q)`. The four roots are `(7 + 8*k)/2^22`, `k=0..3`. Each case requests 22 times: start/stop and, around each root, the root itself, its immediately adjacent binary64 times, and root ± `2^-40` seconds. Inputs, independent expectations and budgets are frozen in [vco-controls](vco-controls/MANIFEST.json).

## Actual controls

Spectre `21.1.0.509.isr12` ran the four configurations serially. The parent controller collected 82 files and verified their hashes; archive SHA256 is `287bf5bd018082e8928da9063de532e688080df4d47a85c135e0cf4e2e4d1613`. The raw archive remains local. This compact evidence is not a public receipt or a qualification of exact endpoints.

All four collected VA/deck hashes match the frozen cases. Actual transient settings read from each Spectre log are `method=traponly`, `errpreset=conservative`, `maxstep=232.831 ps` (rounded log display). Baseline transient `reltol=1e-6`, voltage/current abstol `100 nV`/`1 pA`; tight `reltol=1e-9`, abstol `100 pV`/`1 fA`. Requested global reltol was `1e-5`/`1e-8`; conservative changes the effective transient value. Decks retain `%24.17g` export precision and `strobeoutput=all`; neither export precision nor a strobe request certifies internal integration state.

| Control | Native rows | Exact requested times present | Spectre vs independent ordinary phase failures |
|---|---:|---:|---:|
| original baseline | 32805 | 11/22 | 0 |
| independent raw baseline | 32805 | 11/22 | 0 |
| original tight | 32811 | 11/22 | 1 |
| independent raw tight | 32811 | 11/22 | 1 |

At each tolerance setting, adding raw preserves the entire saved native time sequence and every original `ctl/freq/phase/out` value exactly. There is no observed output/grid perturbation in these four cases. Baseline and tight have different native sequences. Every case still misses the same 11 requested times, including all exact roots and right-adjacent ULP points. No interpolation, nearest-point substitution or removal from the denominator is used.

## Boundary evidence and limit

At `t=1.6689300537109373e-6` (first root's immediate binary64 predecessor), exact `q=1-2^-53` and phase `0.9999999999999999`. Baseline exports that phase; tight exports `1.1102230246251565e-16`. Ordinary phase difference is `0.9999999999999998`, exceeding the unchanged `1e-3` cycle budget. Tight's maximum circular phase difference across native rows is `4.440892098500626e-16`; sine error against the analytical expression is at most `1.6091572518917019e-12 V`. Thus this failure is localized to the modulo side at a boundary, with no comparable full-amplitude sine discrepancy. Its ordinary phase failure remains recorded.

The raw `idt` export at that tight point is exactly `1.0`, an error of `+1/2` ULP measured using the exported value's binary64 ULP. At the second/third/fourth root predecessors, raw exports `2.0/3.0/4.0`, errors `+1/2,+1,+1/2` ULP, while phase remains close to 1. Consequently applying modulo to exported raw does **not** reproduce the observed `idtmod` phase. This is direct evidence against treating independent raw output as the hidden `idtmod` accumulator. It does not isolate Spectre's internal rounding, modulo algorithm, integration state, or observation conversion.

EVAS uses an exact-source certificate when its enclosure crosses a wrap boundary. Its exact rational integration of the dyadic input chooses the mathematical half-open modulo side at the actual binary64 time. Four local native-time replays of the frozen sources are recorded in [the compact evidence](evidence/vco-controls.json). Baseline pairing has zero ordinary failures; tight pairing retains the first-root predecessor failure. The previous original g17 fourth-root predecessor failure is not superseded: the requested strobes/control grid changed, and the new baseline no longer exports the same failing phase there. This sensitivity prevents a claim of resolved Spectre ordinary-phase compatibility.

The next decision is the observation contract near wrap: do consumers require exact half-open phase at binary64 time, or Spectre's finite observed phase? Keep the current ordinary failure and coverage gap until that contract is chosen and validated. No epsilon, threshold increase or waveform relabeling is justified by these controls. The minimal next probe, if internal side attribution is required, is a separate exact-dyadic source that exposes a bounded manual wrap of one `idt` history beside `idtmod`, with original/source controls and its own actual observation grid; that would still require proving the shared-state relationship rather than assuming it.

## Reproduce analysis

From the repository root, with the four collected case folders under `$VCO_RUNS`:

```sh
python3 experiments/backends/event-alignment/vco-controls/analyze.py "$VCO_RUNS" /tmp/vco-controls-analysis.json
python3 -m unittest discover -s experiments/backends/event-alignment/vco-controls -p test_analyze.py
```

The diagnostic checks source/deck identity, preserves native rows/tokens through the existing PSF normalizer, rejects nonfinite or duplicate/nonincreasing times, evaluates exact rational expectations, retains ordinary failures, reports missing exact anchors and compares original/raw on common actual times. Six calibration tests cover the dyadic side, ordinary-vs-circular distinction, nonfinite export, missing signal refusal, duplicate/nonincreasing times and missing-anchor preservation. It is a bounded diagnostic, not a replacement alignment checker.

[最终两个最小探针](final-probes.md)保留原失败并列出完整有限 M1 对齐及原 VCO 返回量的定位结果。
