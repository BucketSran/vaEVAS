# Voltage-domain precision breadth qualification

Approved scope: user request on 2026-10-12. Integration base: 4448253a15ea8cf566d88e62be54c3819060648a. Integrate on codex/precision-breadth-night; deliver reviewed PRs without merging. PR #131 remains unchanged.

## Outcome

Replace unknown coverage with calibrated, reproducible measurements for 20 basic feature groups F01-F20 and 24 engineering composition groups EC01-EC24 from the accompanying inventories. These are development-informed validation cases, not a held-out benchmark. A group passes only when all mandatory variants, outputs, initialization, events and critical observations pass. Variants, settings and backends do not inflate the group denominator. Semantics-pending groups remain visible; they cannot acquire a passing label by omission.

Keep all previous cards, criteria, results and denominators immutable. New cards, references, observations and configuration identities are versioned separately. Numerical accuracy, behavior, evidence completeness and actual effective settings are separate results.

## Acceptance

Use the existing Q1/Q2/Q3 budgets: B=(10 nV + 1 ppm*A)*factor with factors 10,1,0.1. Same mathematical answer and external budget for all four backends. Input error and independent numerical-reference uncertainty are each <= B/100; unresolved reference, timing and export uncertainty <= B/10, with amplification propagated. Actual error plus unresolved uncertainty must fit B. Counter channels require integer states within 1 uV and exact event count/order.

Keep start, stop, input corners, event windows, edge endpoints, reset boundaries, catch-up points and wrap boundaries. No cross-jump interpolation, excluded fixed-width boundary windows, post-hoc threshold relaxation or per-point event-time fitting. One common event history explains all consumers. Undefined mathematical derivative points receive explicit undefined-point records and mandatory one-sided checks, not fabricated exact answers. Timer/cross source tolerances are part of each frozen case identity.

Each reference is independent of EVAS code. Include handwritten anchors and positive/negative calibration controls for wrong state, omitted/repeated events, wrong order, excessive error, missing rows and NaN. Counter-derived callback brackets must fit the full legal window without clipping. Unknown observation/setting evidence stays unknown. Raw phase and continuous phase consumers are separate obligations.

## Task graph

T0 freeze scope, interface, baseline hashes and decision trail.
T1 foundation cards and independent references, depends T0.
T2 engineering cards and independent references, depends T0.
T3 shared grading, observation qualification and calibration, depends T0; integrate T1/T2.
T4 bounded four-backend runner, settings/identity/attempt receipts, depends T0; official runs depend T3 calibration.
T5 execute all ready groups at frozen candidate settings; isolate compiler/interface/configuration/numerical/evidence failures, depends T1-T4. Preserve failed and unrun slots.
T6 repair evidenced EVAS defects, one coherent root cause at a time, depends actual T5 failure; red/green regression and relevant actual Spectre run are required. Changes to shared scheduler/IR coordinated by root.
T7 Astra and actual GLM independently audit significant reference, checker and numerical changes, then final validation on included revision. Review may start before all runs complete.
T8 concise comparison/methodology/evidence update, full decision trail audit, reviewed PR delivery. Broad parent issues stay open for remaining obligations.

EC05/22/23/24 need support or semantic analysis; record explicit current behavior and independent equations, do not silently redesign the DUT. Exclude filtered-output cross near-root recovery owned by #131. Continue other tasks if one group is unresolved.

## Resources and termination

Use existing local and thu-sui resources. Remote execution serial under the shared lock. Per compiler/simulator stage 90 seconds, license wait 30 seconds, 4 GiB process/container memory, 32 MiB file and 256 MiB condition output limits; cleanup receipt after timeout. Emergency ceiling: 1000 Spectre and 2000 combined open-backend attempts, including failures and reruns. No overall time cutoff; stop when ready tasks and required review are complete, or the specific external blocker is documented. No repeated identical run without a causal reason.

Deliver actual outcomes, not a promised all-pass matrix. A genuine unsupported composition may remain a documented defect if repairing it requires an unsettled semantic contract. Such an unresolved leaf must be reported explicitly, never marked implemented.

## Configuration revision before the second execution batch

The first frozen batch at f9ff6017 remains immutable. Actual Spectre deep logs and PSF headers render maxstep with about six significant digits, so the requested 4.8828125e-10 s appears as 4.88281e-10 s. This is a configuration-evidence gap, not proof of numerical failure.

For breadth-v2, Spectre Q3 uses the existing named deep_bound candidate: step_units=0.0004, with deep reltol/vabstol/iabstol unchanged. This gives a readable 0.4 ns cap for the 1 us unit. Every affected Q3 claim requires a new execution. Other backends and Q1/Q2 keep their original candidates. The Q budgets, event windows, actual-time grading and required observations are unchanged.

F03 logic and EC05 edge are reserved identifiers in the reference language; the current fixtures use logic_out and edge_v. Original sources and failures remain in the first batch. These corrections retain the logical group/variant denominator and require new source/execution identities.

The official attempt mapping is fixed before the second batch in batch-v2/SELECTION.json. It does not choose the best result among profiles.
