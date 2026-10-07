# Ordered event source comparisons

These are development comparisons for bounded event closure. Sources, observation plans and thresholds were frozen before each execution. The source revisions form separate groups; later diagnostics do not replace earlier failures.

| Source group | Actual Spectre result | Interpretation |
| --- | --- | --- |
| Three original sources | Three compilation failures | Spectre rejected leading-decimal Verilog-A tokens. Original sources and errors are retained. |
| Three value-preserving lexical corrections | Mixed and hidden-loose fail the finite contract; hidden-tight ends with SPECTRE-18 | Adding a leading zero preserves each numeric value. A partial waveform from the runtime failure is not accepted as complete evidence. |
| Two separate sources with timer tolerance changed from 1 µs to 1 fs | Mixed passes finite voltage checks but has insufficient callback bracketing; hidden-loose fails voltage and callback checks | Cross declarations and external criteria are unchanged. |

In the 1 fs hidden-loose run, every saved record after the first timer retains n=1, q=h=m=0, including the numeric stop. The source and deck match the frozen inputs. There are 35 saved rows and 132 accepted steps, so these records do not expose all calculated-step states. The final retained output is wrong under the independent criterion. Whether a callback was untriggered, reverted, or affected by saving remains unknown.

[Three single-factor diagnostics](diagnostics-v5/README.md) distinguish timer tolerance, cross association and sampling density. With 1 ps timer tolerance the hidden state recovers. With 1 fs tolerance and only the cross callback removed, timer/integrator state also recovers. Denser output strobes make the mixed case's finite callback check pass. These observations establish an association with the tested combination, not the simulator's internal cause.

[summary.json](summary.json) retains all five executable source configurations and their original finite and full verdicts. [receipt.json](receipt.json) identifies sources, decks, checker, normalization and actual settings. [Frozen sources and checker](../../../evas/validation/ordered_event_sources/README.md) allow new executions. Actual log and PSF settings were read without substituting requested values. Exact endpoint and close callback order remain inconclusive.

The [candidate phase comparison](candidate-phase/README.md) records the final 709a4376 implementation and earlier failing checkpoints. Each of the two 16-request suites passes its fixed contract: fourteen complete finite outputs and two prescribed rejections. Extra phase probes check actual returned states and direct outputs against exact Fraction answers; event metadata alone is insufficient. Two separate scope cases each pass both grids: an isolated timer with forced flow, and a held timer replanned by the current callback. These are independently counted mathematical diagnostics, not new matched Spectre configurations.

The actual Spectre sources, decks, settings, observation plans and independent checkers are unchanged by these EVAS-only repairs. The reference results are therefore reused at their recorded identities. Extra EVAS phase probes are mathematical checks; they are not new matched Spectre samples. Spectre's runtime failure does not establish EVAS's required `cross_ttol_unrepresentable` rejection. Raw waveforms, logs and binaries remain local-only under `current/runs/event-closure-20261008/`; hashes do not make them publicly retrievable. None of these development counts is a paper qualification count.

The `EVAS_candidate_status` in `summary.json` records the status at the time of the reference analysis. It is retained as historical context. Current versioned EVAS executions and their verdicts are in the [candidate receipts](candidate-phase/README.md).
