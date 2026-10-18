# Validation and optimization acceptance

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

## Early integration checks

Before another task depends on a subtask's behavior, obtain the distinguishing
failure, relevant rejection and direct-consumer feedback on its fixed candidate.
Apply these additional triggers only when the change touches them:

- Representation, admission or dispatch changes: compare affected previously
  passing programs' IR or execution routes. Exercise changed routes in complete
  consumers, including surrounding state and internal drivers. An intentional
  representation change needs consumer evidence; identical IR is not a universal
  requirement and cannot validate a changed Rust consumer.
- New scans, searches, proof fallbacks or cache copies: preserve the existing
  budget owner and sublimits. Charge actual inner work and pass the authorized
  remainder to fallback attempts. Check an old successful route that does not need
  the new proof, and measure delegated child traversals or copies against the same
  ledger or a prepaid bound. Test exhaustion and same-request retry. A repeated
  cap constant does not establish an unchanged aggregate allowance.

CI passes its identified change plan with `--plan runs/ci-plan.json`: documentation
and workflow-only deltas skip simulator contracts; affected sources select their
contracts, and unknown EVAS source/build changes retain all available contracts.
A missing change identity retains all contracts. Draft incremental evidence covers
only that delta and does not close the full candidate's delivery obligations.

Use the local policy's `--early-checks` command for the recorded small-Select,
array-slot accounting and optional-initial-proof counterexamples. The same command
runs in the existing CI fast-checks job. Add `--kernel PATH` to check the two Select
consumers through the actual matching kernel; compilation-only evidence is labelled.
A changed small-Select route without a kernel returns exit2 and remains pending;
CI then builds the matching kernel and checks its consumers before wider regression.
Changes to the Rust consumer or build require this runtime check even when IR stays
the same.
An intentional representation change may pass those consumers without identical IR.
The initial-proof check enforces one production allocation owner, at most the
existing two allocation sites, and a sticky production Budget primitive. It does
not prove aggregate caller accounting or every loop's cost; review and relevant
private tests still establish those obligations. New or renamed mechanisms need
their own affected check instead of inheriting a pass from this starting set.
In particular, the generic initial-proof check does not cover a new Python
constant-math helper or a new DC/source-math audit. Their old-route admission and
inner-work counterexamples remain separate evidence under the same proof-budget
obligation. Repeated omissions may require shared accounting code; adding a skill
instruction does not fix that source defect or close its review finding.

Automatic checks report absent mechanisms as not applicable; an explicitly
requested absent check is blocked. Neither outcome verifies that mechanism.
Keep untested assumptions pending in the existing task entry.

| Feedback | Waiting boundary |
| --- | --- |
| Distinguishing failure, changed path, direct consumers, applicable representation/budget checks and review of their unresolved assumptions | Before dependent integration; other independent tasks may continue. |
| Full Python/Rust regression, stable-candidate original400, required CI and installation checks | Run against a fixed candidate in the background; finish before their delivery claims or merge. |
| Already matching execution, independent reference or review | Reuse by the affected claim and dependency identities; a new commit or PR stage alone does not invalidate it. |

Use the [candidate executor and batching rules](../../CONTRIBUTING.md#prepare-one-delivery-candidate)
to avoid running complete Python coverage both locally and remotely by default.
The chosen full executor retains all planned tests and reports skips and failures.
Pending remote coverage permits independent development, while the local direct
consumer feedback still gates work that depends on it. An unknown/shared mapping
keeps its full-coverage obligation and named executor.

Run changed-file formatting and metadata checks before expensive acceptance. Reuse
the same scoped checks and review through integration and publication. A focused
pass is not a new full400 score. Unknown/shared coverage remains conservative.

## Original request acceptance

For a behavioral repair, link the original failing request and its observed failure in the
existing task or PR. Preserve its model, stimulus, settings, checker and acceptance limits.
Reuse a recorded failure when its identities match; a reduced reproducer helps diagnosis but
does not replace acceptance of the original request. Benchmark repairs use their owning task
and grading contract.

Before claiming the repair complete, verify the original request on the final integrated
candidate through the supported public entry point, with the actual source and binary identified.
Select affected consumer and composition checks from [evas-validate](../../.agents/skills/evas-validate/SKILL.md#composition-triggers).
For EVAS behavior, apply [Spectre alignment acceptance](#spectre-alignment-acceptance) to the
changed behavior. A local unit-test pass or an author's earlier candidate does not establish
acceptance of the integrated version.

If the final candidate changes, follow the existing
[revalidation triggers](../../.agents/skills/evas-validate/SKILL.md#revalidation-triggers).
Reuse unaffected evidence with its identities and reason; rerun the affected obligations.
When the original request still fails or cannot be rerun within the task's resources, keep that
acceptance item open and state the blocker. Do not replace it with nearby passing cases or
expand the task to unrelated mechanisms without an agreed scope change.

## Accuracy recovery and performance acceptance

For EVAS accuracy or speed work, state the final observable requirement before choosing
an algorithm. Reuse the existing Issue/PR to name the model, affected consumers, voltage
and event budgets, observation scope, current failure or measured cost, and expected
improvement. Separate an incorrect accepted result from a conservative refusal.

### Carry accuracy through the consumer chain

Follow uncertainty through event time, sampled state, edge generation, filtering or
integration, and final voltage acceptance. Preserve inherited uncertainty across each
handoff. A precise new root does not erase an uncertain earlier sample or history.
Keep the external budget fixed; justify internal allocations by the affected consumer's
sensitivity and remaining budget. Do not assume equal shares or add/subtract interval
widths as if they were independent error contributions.

Choose a recovery action from evidence about the failing request:

| Dominant cause | Candidate action and required evidence |
| --- | --- |
| Current event-time uncertainty | Refine the current root and recompute its consumers from the same accepted state. Show that the downstream error bound decreases enough to meet the original request. |
| Inherited sample or accepted-history uncertainty | Retain and propagate it. Recovery needs a justified tighter source bound or supported replay; otherwise report the limit. Refining only the current root cannot remove it. |
| Error introduced by the new continuous segment | Use the applicable local step/order control. Show improvement after propagation to the required output, including earlier history. |
| Rounding, input uncertainty, or enclosure conservatism | Establish what can change and what limits recovery. Use a justified reformulation/control or report the unresolved limit; repeated shrinking alone is not evidence. |

Mixed or unknown causes remain explicit. An error code or a failed downstream filter
alone does not identify the source. Bound retries and preserve accepted state on failure;
strategy changes must pass the same final certification before committing.

An accuracy-recovery slice must demonstrate a recoverable case and a relevant case where
the selected action cannot help. Record the affected bound before/after, the unchanged
budget, independent output error, acceptance/refusal and work used. Reuse query-invariance
and same-controller failed-trial retry checks when those paths change. Check the declared
downstream scope beyond the event itself; finite observations do not prove a whole-trajectory
bound. Follow [Spectre alignment acceptance](#spectre-alignment-acceptance) separately.

The [sample-edge-filter root case](../../experiments/backends/sample-edge-filter/BOUNDARY.md#adaptive-root)
is an existing example. Its limited automatic input-root refinement already checks the
event and first physical history deadline. Later consumers, state/history-dependent roots
and general budget allocation are not established by that result. Reuse
[#119](https://github.com/BucketSran/vaEVAS/issues/119) for accuracy recovery and
[#96](https://github.com/BucketSran/vaEVAS/issues/96) for composition/alignment obligations.

### Compare speed at fixed accuracy

Profile a representative, validated workload before selecting matrix, history, certification,
memory or parallel-execution work. Freeze the model, final budgets and observation obligations
for the comparison. Record each algorithm's actual controls; identical parameter names alone
do not establish equal accuracy.

Select strategies from measured structural/numerical conditions, with declared applicability
and failure/fallback behavior. Every path must retain the same equations, event semantics,
history and acceptance rules. Compare complete requests, including preparation, certification,
retries and output costs. Report repeated timings, resource usage and regressions alongside
correctness, refusals and timeouts; fewer factorizations alone do not establish a speedup.
Use the existing [performance tools and measurement boundaries](../../experiments/performance/README.md).

The deferred [#57](https://github.com/BucketSran/vaEVAS/issues/57),
[#58](https://github.com/BucketSran/vaEVAS/issues/58) and
[#59](https://github.com/BucketSran/vaEVAS/issues/59) retain their measured-bottleneck reopening
conditions. These rules do not start those projects or require a new solver family.

This direction draws on the [ALPS product description](https://www.empyrean-tech.com/products/eda/analog-design-solution/spice-simulator.html)
of full-equation simulation, matrix-solving strategies and parallel execution. The error
accounting and recovery requirements above are EVAS design choices. The public description
does not disclose ALPS CS's internal error budgets or prove a speedup for EVAS.

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

### Qualify Spectre reference precision

Before attributing a discrepancy to EVAS, check whether the Spectre record meets the
case's independent voltage, event and observation requirements. Record the relevant
requested and effective tolerances, integration method, step limits and strobe settings.
A preset name or matching EVAS parameter values does not establish reference accuracy.

If reference accuracy is insufficient or uncertain, retain the baseline and compare a
tighter-tolerance run with a step-only refinement at fixed model, stimulus, initial state
and external budgets. Change one control group at a time; investigate integration-method
sensitivity when the trajectory or event sequence remains unstable. Reuse matching
qualified records rather than repeating a sweep for every code change. Report measured
errors against an independent answer, or the available invariants and refinement limits
when no such answer exists. Stable successive runs alone do not prove an error bound.

Keep reference precision, EVAS correctness, paired agreement and observation completeness
as separate results. A coarse Spectre run that exceeds the engineering budget remains a
failed configuration, not evidence that the feature is unsupported or EVAS is defective.
A reference with unbounded uncertainty remains explicitly unqualified for claims needing
that bound, even if it agrees with EVAS.

Verify required observation times against original output before reporting missing data.
Distinguish an absent observation, an output-time representation mismatch and a solver
failure to return a requested point. Exact-time obligations remain in force until a
reviewed matching rule accounts for timing error, waveform sensitivity and event sides;
changing that rule requires calibrated reanalysis with the old verdict retained.

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
problem, add or update [the candidate register](../../benchmark/material/draftbench/CANDIDATES.md) before handoff.
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
