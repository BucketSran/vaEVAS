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
