# Tests and benchmark candidates

For behavior changes, read the test rules below and select checks with the owning
component skill. Read candidate capture or migration rules only when that work applies.
See [CONTRIBUTING](../../CONTRIBUTING.md) for the contribution workflow.

## Behavior-first tests

<a id="behavior-first-tests"></a>

Use TDD for behavior changes: choose a contract and observable failure, run the smallest
meaningful failing test, implement the fix, then refactor within scope. Reuse an existing
case if it already exposes the defect. Report an observed red run; do not imply tests
written after the fix were run before it. Independent validation design can precede
implementation; it is not constrained to one test at a time.

Before adding a test, identify its required behavior, independent answer and distinct
failure mode in its name/comment or the existing PR. No separate test-plan file is needed.

- Derive expected values from the specification, a worked analytic example, an independent
  qualified reference or an invariant. Do not call or copy the computation under test to
  obtain its own expected answer. A literal copied from a current output is not independent.
- Prefer a stable behavior interface. Keep focused kernel tests when they expose interval
  enclosure, state isolation or failed-trial retry that a process-level test cannot observe.
  Do not mock the computation being tested or assert incidental helper layout/call counts.
- Distinguish tautology from repetition. A tautological oracle needs replacement. Tests with
  the same model may still protect different layers or failure modes. A source/copy identity
  check verifies packaging, not mathematical correctness; label that claim accordingly.
- Reuse or parameterize cases when contract, failure mode, observation boundary and evidence
  source are the same. Keep distinct sign, scale, boundary, composition and rollback cases
  when they detect distinct faults; parameterization alone does not reduce execution cost.
- Before deleting a regression, identify the retained test and show it still catches the
  original defect or a targeted wrong implementation. If equivalence is uncertain, retain
  it and report the question. Preserve frozen suites, denominators and historical receipts;
  update current traceability when test locations change. Never prune solely to cut counts.

This adapts the behavioral and independent-oracle guidance in
[Matt Pocock's TDD skill](https://github.com/mattpocock/skills/blob/d1caf1e952fe395014ae729445d43ea7c1b40fa0/skills/engineering/tdd/SKILL.md).
Its mandatory interface confirmations, blanket ban on internal tests and review-only
refactoring are not repository rules. Existing authorization, numerical evidence and
independent validation contracts govern those choices here.

## Spectre alignment acceptance

For changes to accepted VA/SCS behavior, initialization, events, history operators or
numerical execution, identify the changed observable behavior and compare it with actual
Spectre execution before recommending merge or claiming alignment. Select the smallest
cases that expose that behavior and its affected consumers; a full backend matrix is not
required. Documentation, packaging identity, result storage and diagnostics alone need no
new Spectre run when they leave simulated behavior unchanged.

Use the same physical model, instance parameters, stimulus and initial conditions. Preserve
each backend's requested/effective settings, observation conventions and relevant version
identity. Solver controls need not have identical names or values; explain their mapping
and choose voltage/time tolerances from the contract before inspecting results. Include
initial values and relevant event boundaries, signs, instance isolation or compositions,
not only a DC point when the changed behavior is dynamic.

Link retrievable inputs, both backend outputs, commands and source/kernel/Spectre identities
to the actual comparison and its tolerances. Separate EVAS-to-Spectre agreement from each
backend's independent analytical/invariant checks; local unit tests, an nd equivalent of
an np operator, model reviews or an unrelated comparison-table row do not establish the
new behavior's Spectre compatibility. A Spectre-only probe supports only its stated scope.

Reuse an existing Spectre execution when its physical inputs and relevant semantics match;
link its frozen identity and explain applicability to the changed implementation. Rebuild
and recheck the affected EVAS behavior at the new head. State whether a change was newly
paired, compared against reusable reference data, or remains without alignment evidence.
Do not require re-execution just to replace a valid evidence link with a newer timestamp.

Spectre remains the project's compatibility reference, while independent contracts still
check mathematical correctness. Investigate disagreement before accepting a result:
distinguish VA semantics, settings, tolerances, simulator-version behavior and EVAS defects.
Retain a justified, version-specific exception explicitly; do not change the model or widen
tolerances merely to conceal disagreement. An unavailable run or unexplained discrepancy
keeps the affected alignment/merge recommendation pending unless the user accepts that
specific partial scope. Record the gap in the existing PR/capability evidence, independently
of GitHub's ready flag or the code-review outcome.

These are acceptance requirements, not additional resource authorization. Prepare missing
cases and commands using existing tools, and run within the current task's server/time/case
budget. An expired run's unused allocation does not authorize a fresh remote experiment.

### Classify differences before selecting a repair

The engineering target is correct VA behavior within declared voltage, event-time, count,
ordering and downstream-output requirements, verified against actual Spectre runs.
Bitwise equality or the same internal accepted time grid is not the default target.
Independent mathematics must describe the actual source and language semantics, including
permitted event tolerances; an idealized replacement circuit is not an oracle.

| Finding | Disposition |
| --- | --- |
| Different event points within the permitted window, with correct samples, counts/order and downstream outputs within fixed budgets | May be accepted as a scoped known difference with evidence and the applicable scope decision. |
| Different continuous values satisfying independent and paired engineering budgets | Engineering pass; do not require the same numerical algorithm. |
| Wrong initialization, lost/duplicated events, violated ordering, stale reads/history, observation-dependent trajectories, or events outside permitted windows | EVAS defect when attributable to EVAS; preserve a failing case and repair the responsible rule. |
| Accepted output exceeds its requested error, or a claimed enclosure excludes the correct result | EVAS correctness defect; do not widen the checker or suppress uncertainty. |
| Unsupported legal composition or unnecessarily conservative refusal | Capability/accuracy-recovery gap, distinct from a wrong accepted result. |
| Small time shifts change final codes, event sequences or feedback trajectories; or evidence is missing | Investigate model sensitivity, semantics and each backend. Not automatically acceptable and not automatically an EVAS defect. |

Keep separate verdicts for independent correctness, engineering comparison, strict same-time
diagnostics and evidence availability. Do not delete event-window rows, shift waveforms to
fit, or relax a budget after seeing a failure. In a window, still check event timing/counts,
sample values and effects on all affected downstream consumers. Exact-boundary obligations
explicitly required by an existing contract remain until individually reclassified.

A known-difference record names its inputs/settings, backend and candidate identities,
original observations/verdicts, unchanged budgets, reason, authorization, and reopening
conditions. Retain old F/I results. The current acceptance decision can supersede their
blocking role without pretending the old strict test passed or that a candidate is merged.

The accepted **SEF-TIMER-18** record is owned by
[#96](https://github.com/BucketSran/vaEVAS/issues/96) and the
[sample-edge-filter decision](../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18).
Its unchanged 18 strict phase mismatches are not an EVAS repair target. Reopen on new evidence
of invalid timing, lost/reordered events, incorrect state/history, failed error bounds or
downstream budget failures. Changed models, settings, consumers or versions require affected
revalidation, not automatic inheritance. C1, original #79, VCO, Spec B and zero-tolerance
timer probes are outside this decision. Do not add an epsilon or imitate a Spectre grid merely
to clear the diagnostic. Future tasks must name the failed engineering or semantic property
before changing a solver rule.

## Development failures as benchmark candidates

<a id="development-bench-candidates"></a>

When development exposes a reusable modeling mistake, semantic trap or compatibility
problem, add or update [the candidate register](../../benchmark/CANDIDATES.md) before handoff.
Record the concrete trigger, observed versus required behavior, evidence and proposed
modeling task. Separate confirmed causes from hypotheses; a simulator bug or infrastructure
failure must not be mislabeled as a VA model defect. Reuse the existing candidate for the
same failure family. Link code, Issue/PR and compact receipts instead of copying run logs.

Capture is part of the current work. Formal task design, variant generation, scoring and
Harbor integration are a separate work item; a new candidate does not trigger them by
default. Existing prototypes stay labeled as prototypes until that work is reviewed.
The register owns candidate status; Issues and PRs own implementation work and history.

## Migration

Inspect source contracts, checkers and reference solutions before importing legacy code/tasks. Preserve
provenance and license notices. Historical passes retain their original revision; verify migrated behavior
with affected checks. Importing material does not authorize deleting its source repository.
