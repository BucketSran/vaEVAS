# Flash: cold solve regresses despite lower transient CPU

The existing 100 MHz, 10,000-conversion bank workload is **slower from solver launch to exit** for the sampled binary-search reference. Five alternating measured pairs all favor the baseline for process elapsed time. All twelve archived jobs (two designated warmups plus ten measured solves) pass the frozen functional checker with zero native errors and the same 152,093 accepted steps. These are actual archived solves, not new simulations. The designated warmups do not warm subsequent jobs' compilation caches: every log explicitly creates its AHDL library and compiles it.

`quiet_phase_analysis.json` retains each native log/archive hash and separates its phase measurements. `analyze_phases.py` reproduces the extraction from the parent actual-evidence JSON, checks both immutable hashes, and rejects missing or duplicate compilation/phase records.

| Timing (seconds; median [min, max], five measured solves per side) | Baseline | Reference |
| --- | --- | --- |
| Cold AHDL compilation elapsed | 0.779 [0.771, 0.798] | 1.160 [1.150, 1.160] |
| Intrinsic transient CPU | 4.22635 [4.19897, 4.24477] | 3.54706 [3.53225, 3.61508] |
| Intrinsic transient elapsed | 2.26523 [2.25874, 2.29920] | 1.98773 [1.97095, 2.03189] |
| Native last accumulated CPU | 5.18019 [5.15565, 5.21404] | 4.88729 [4.88171, 4.95473] |
| Native last accumulated elapsed | 3.18022 [3.16933, 3.23813] | 3.28547 [3.27124, 3.76652] |
| Solver process elapsed | 3.271827 [3.271664, 3.522277] | 3.419368 [3.372037, 3.872896] |
| Process minus last accumulated elapsed | 0.102497 [0.091447, 0.333787] | 0.100797 [0.087193, 0.133898] |

The native transient CPU decreases by 16.1%, and its elapsed time by 12.3%. The cold compiler adds 381 ms at the median, exceeding the 277.5 ms transient elapsed saving. The final accumulated native CPU falls only 5.65%; process elapsed rises 4.51%. Differences of medians are descriptive, not an additive causal decomposition of each job. Per-job phase values are retained for that purpose. Native aggregate-audit elapsed duplicates aggregate CPU in this environment and is deliberately excluded. CPU is reported as native CPU accounting; `+mt=1` does not justify treating it as process wall time (native transient utilization is about 180–190%).

**Disposition: no admission yet.** This result does not establish a faster user workflow. A narrowly named transient-CPU objective would need both a demonstrated scan limiter and evidence that the production workflow amortizes compilation; neither warm caching nor a longer useful characterization is established by these fresh jobs. Network upload/remote launch are outside the solver process timer, and the comparable process-minus-native residual does not support blaming network startup for the regression.

Next diagnostic work already has exact source requests in `REQUEST.json`: compare event-only linear scan against continuous-only binary search, and count callback/comparison/sample work in separate, explicitly instrumented profiles. The event-only linear scan uses the same fixed comparator loop at the actual sampling event; it may preserve the useful reduction in repeated callback work while avoiding the binary-search compiler cost. This is an untested hypothesis. Counts with `$strobe` are excluded from formal scoring and timing claims. Keep current load, tolerances and all failed/old evidence. Do not extend duration solely to amortize compiler overhead.
