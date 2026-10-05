---
name: vaevas-workflow
description: >-
  Select or resume the vaEVAS workflow for work spanning benchmark, EVAS, or
  several development stages. Resolve scope, component ownership, acceptance
  and handoff, then route to the needed project or shared skills. A known
  single-component task can use its skill directly.
---

# Coordinate vaEVAS work

Use this entry to select the next necessary step. Existing component skills
remain independent entry points; small fixes and document edits need no full
grill, specification or ticket sequence.

## Recover the task boundary

Read the current request, accepted decisions, `git status -sb`, and the affected
component contract linked from [AGENTS.md](../../../AGENTS.md). For resumed work,
read its existing Issue/PR and relevant evidence before asking for missing context.
When starting/resuming edits or creating a worktree, run the
[workspace check](../../../scripts/README.md#本地工作区检查) and resolve missing visible
entries under the [workspace policy](../../../CONTRIBUTING.md#workspace-visibility-and-handoff).
Identify the requested operation, deliverable, owning component and acceptance
checks. Discussion, review, check selection and execution have different outcomes;
carry forward the user's scope and [authorization](../../../CONTRIBUTING.md#scope-and-authorization).

Use [domain docs](../../../docs/agents/domain.md) for terminology and decisions,
and [tracker conventions](../../../docs/agents/issue-tracker.md) for task records.
Reuse a settled acceptance criterion or specification. Ask only about unresolved
decisions that affect the requested outcome; inspect available facts yourself.

## Select the component entry

| Requested work | Entry and owning acceptance |
| --- | --- |
| Implement or fix EVAS behavior | [evas-develop](../evas-develop/SKILL.md); simulator semantics and independent behavior checks |
| Select/run EVAS checks or reanalyze evidence | [evas-validate](../evas-validate/SKILL.md); preserve the requested operation and evidence identity |
| Design/build benchmark tasks or grading | [benchmark contract](../../../benchmark/README.md); task requirements, reference solutions and checker calibration |
| Review a change | [vaevas-review-pr](../vaevas-review-pr/SKILL.md); requirements, repository rules and supporting evidence |
| Prepare a commit or PR | [vaevas-prepare-pr](../vaevas-prepare-pr/SKILL.md); reviewable scope, evidence and authorized publication |

For work crossing components, state each component's deliverable and the check
that connects them. Benchmark-only work does not inherit EVAS capability gates.
Record reusable failures through the [candidate policy](../../../CONTRIBUTING.md#development-bench-candidates);
formal task construction remains a separate scope decision.

## Use shared skills when needed

Load only the skills matching the current work. Resolve them from the client's
available skills and respect explicit-invocation settings. If a shared skill is
unavailable, use the project contracts for work they cover and report any actual
gap; do not claim the skill ran or require a library-wide setup for a small task.

| Condition | Shared skill |
| --- | --- |
| Write user-facing prose | `unslop` |
| Write technical docs for people / agent instructions | `technical-writing` / `writing-for-agents` |
| Unsettled goals or acceptance need discussion | `grilling`; use `grill-with-docs` when requested, with `domain-modeling` for resolved terms or decisions |
| An agreed design needs a specification or dependent work needs tickets | `to-spec` / `to-tickets` when requested; reuse existing records and the project adaptations below |
| The user invokes `implement` for a single bounded task | `implement`, with the owning component entry |
| The user invokes `implement-spec` for a spec with dependent tickets | `implement-spec` for the task graph and integration; component entries own implementation and acceptance |
| Authorized long-running, unattended or multi-phase execution | `show-me-your-work`; maintain one canonical decision trail during execution |
| Diagnose a failure / evaluate a consequential shared change | `diagnosing-bugs` / `blast-radius` |
| Measure or report performance / prevent an evidenced recurring error | `benchmark-checklist` / `correct` |
| Write a PR body | `pr`, through the adaptations in `vaevas-prepare-pr` |

For shared planning skills, scale the specification to the agreed behavior and
acceptance criteria instead of filling an exhaustive template. Follow the
[project test policy](../../../CONTRIBUTING.md#behavior-first-tests), including
independent numerical answers and distinct kernel checks. Reuse agreed test
boundaries; take unresolved choices back to the user. Publishing specs or tickets
uses the tracker conventions and existing task authorization.

When `implement` or `implement-spec` is invoked, apply these project adaptations:

- Reuse the spec, tickets and configured tracker. Resolve missing acceptance or
  blocking relationships before dependent work; a small task need not acquire
  artificial tickets or subagents to fit a template.
- Use the [spec delivery criteria](../../../CONTRIBUTING.md#spec-delivery-and-unattended-work)
  to choose integration/PR boundaries and the requested endpoint. Commit, PR,
  issue closure, merge and cleanup steps remain within that authorization.
- Reuse a suitable branch and visible worktrees under the project ownership rules.
  Inspect an unexpected base or existing changes before reconciliation; a shared
  recipe's reset step does not permit discarding work. Keep research notes and
  task evidence in the owning project's existing output area.
- Component contracts and the project test mapping select checks. A generic
  full-suite step does not require an unrelated simulator/backend matrix.
  Reuse matching independent review through `vaevas-review-pr`.

For overnight or unattended work, establish the bounds in the linked delivery
policy before execution. `show-me-your-work` records the run; it does not schedule
another run. Preparation and publication continue through `vaevas-prepare-pr`,
with `pr` formatting the PR body and the canonical trail linked where needed.

Use the project review skill for the required review scope, including any
decision-trail review. Reuse review of the same requirements and evidence;
several matching skills do not by themselves require several review rounds.

## Complete the requested stage

Keep maintained results in their [owning component](../../../AGENTS.md#ownership).
Update existing contracts and evidence links when the task changes their claims.
Use the existing Issue/PR for cross-session scope, dependencies and deferred work;
if publication is not authorized, preserve the local handoff as described in
CONTRIBUTING. A decision trail records execution choices, not a second task tracker.

Report the deliverable, checks actually run, unresolved findings and next dependency.
Rerun the workspace check at handoff. State what is integrated, what is visible in
the primary checkout, and why any temporary worktree remains; update its existing
navigation entry. A visibility pass does not establish integration or permit cleanup.
Finish at the requested stage. Reopen settled design only when new evidence or a
scope change requires a decision, using the [review policy](../../../CONTRIBUTING.md#reviewing-diffs).
