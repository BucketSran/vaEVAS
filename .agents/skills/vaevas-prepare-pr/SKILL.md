---
name: vaevas-prepare-pr
description: >-
  Prepare EVAS, benchmark, documentation or maintenance changes for a vaEVAS commit or PR,
  including scope inspection, verification evidence, and title/body drafting.
  Commit, push, and create a PR only when authorized by the current task.
  Do not treat preparation as permission to merge or include unrelated work.
---

# Prepare a vaEVAS PR

Produce a concrete reviewable result within the requested scope. Read
[repository guidance](../../../AGENTS.md),
[workspace ownership](../../../README.md), and any current repository
PR template. Use the actual checkout and remote; do not assume a machine-local
path, legacy repository, or branch name.

## Establish the change boundary

Inspect status, staged and unstaged changes, relevant untracked files, branch,
remote, and intended base/head. For stacked work, identify the parent branch and
the diff reviewers should see. Preserve unrelated or concurrent changes; do not
stash, switch branches, rebase, force-push, or merge as incidental cleanup.
Follow the [branch lifecycle](../../../CONTRIBUTING.md#branch-lifecycle); reuse the task's
existing PR for review fixes and related documentation/evidence. Record the
current parent/base and exact checkpoint; include capability IDs only for EVAS
behavior or support/evidence changes. Do not create an extra branch solely for
a review round, test report or commit.
Run the [workspace check](../../../scripts/README.md#本地工作区检查) when entering this
stage and at handoff. Resolve navigation gaps and report local changes and retained
evidence under the [workspace policy](../../../docs/contributing/workspaces.md#workspace-visibility-and-handoff).

Include only work belonging to the request. If commits are authorized, stage
explicit paths or hunks and inspect the staged diff. Do not split or commit
another contributor's in-progress work merely to tidy history.
For spec-driven delivery, check the [spec completion and PR boundaries](../../../CONTRIBUTING.md#spec-delivery-and-unattended-work).
Bind the PR's acceptance evidence to the included spec/tickets and reviewed head;
identify remaining criteria without presenting a partial implementation as complete.

## Make the evidence reviewable

- Confirm that changed behavior and compatibility limits agree with the owning
  component documentation and PR checkpoint. Keep unsupported behavior explicit.
- Use observed checks for the owning component: the [EVAS check mapping](../evas-validate/SKILL.md#select-the-necessary-checks),
  [benchmark/task contract](../../../benchmark/README.md), or document/link checks.
  EVAS regressions do not establish benchmark grading correctness. Do not rerun
  a full backend matrix solely to prepare a PR.
- Keep curated summaries and provenance according to
  [main retention rules](../../../docs/contributing/evidence.md#main-branch-contents) and the
  [experiment index](../../../experiments/README.md). Exclude raw waveforms,
  build products, credentials, and machine-specific configuration. An ignored
  directory is not proof that the files selected for commit are appropriate.
- Inspect the final diff and check formatting and links. Apply the
  [review format and publication dependency checks](../../../CONTRIBUTING.md#reviewing-diffs).
  Report checks not run or failures honestly; never present an old result as
  verification of this diff. Identify the revision or local diff actually checked
  and reviewed. Reuse matching review; after a change, identify affected claims
  and any review or verification still needed before calling the result ready.
- For EVAS behavior or support/evidence changes, verify that affected rows in the
  [support matrix](../../../evas/docs/COMPARISON.md), mathematical explanations
  and evidence links agree. Separate implementation,
  verification and review/release status. Link existing Issues for deferred work;
  avoid duplicating the register in a new progress document.

For work that used `show-me-your-work`, let that skill own the canonical decision
trail, its format and audit requirements. Link the existing trail and relevant
evidence instead of creating a second log or copying the trail into the PR body.
Keep its evidence accessible and follow the retention rules above when deciding
whether it belongs in the commit. Use [vaevas-review-pr](../vaevas-review-pr/SKILL.md)
to cover any required trail review together with the change review. The trail
supports review; it does not replace observed checks or independent review.

## Draft the PR description

When writing a PR body, load the shared `pr` skill for presentation. This skill
owns vaEVAS scope, evidence and publication requirements. Apply these project
adaptations to the generic `pr` template:

- Use the repository PR template when one exists; otherwise select useful sections
  from `pr`. A short PR can combine or omit headings while retaining the problem,
  resulting behavior, actual checks and material limits.
- Include a diagram, tree or diff sketch only when it helps explain the change.
- For a behavior fix, show observed before/after evidence when available. If the
  baseline was not run, say so and distinguish the reported or inferred prior
  behavior from observations.
- Describe affected callers and rollback constraints when material. Simple document
  changes need document checks, not a new simulator experiment to fill the template.

Write the title and body about the final change, including meaningful design or
compatibility decisions. Link the relevant contracts and evidence; omit abandoned
approaches and stale counts. Use the full skill names: `pr` formats the description;
`show-me-your-work` records decisions during execution.

Describe the component's changed behavior and actual checks. Benchmark-only work
and documentation edits that leave EVAS behavior, support and evidence claims
unchanged do not require EVAS capability IDs or a mathematical chapter. If a
documentation edit changes an EVAS support or evidence claim, update the affected
capability entry and its evidence links; use valid evidence or identify the gap.
For EVAS semantic/numerical changes, answer these questions as applicable:

- What input or model failed or was unsupported, and what happens after the change?
- Which equation, state transition or ordering rule explains the implementation?
  Use a small equation, diagram or pseudocode when useful and link the owning handbook.
- Which independent expected result and observed check demonstrate the behavior?
- What compatibility, precision, performance or composition limits remain, and which
  callers are affected? Describe material rollback constraints when they exist.

Keep the reviewed revision, effective settings and evidence identity clear. Distinguish
equation residual from output/timing error, and support speed claims with comparable
measurements. Reuse existing valid evidence links.

## Publish only within the requested scope

Use the [authorization defaults](../../../CONTRIBUTING.md#scope-and-authorization).
Preparation alone ends with the ready diff and proposed PR text. When the user
has authorized committing, pushing, or creating a PR for this task, complete
those authorized steps without asking again. Prefer a draft PR unless the user
requests otherwise, and use the verified base branch. Creation does not
authorize merging, reviewer messages, or unrelated repository changes.

Report what was actually prepared, committed, pushed, or opened. Include commit
identity and PR URL when applicable, the review base, verification limits, and
any relevant work still left locally.
Distinguish target-branch integration from synchronization of the daily checkout.
Keep temporary work discoverable until retired; record any pending integration or
retention reason and next action in its existing navigation entry.
After an authorized merge, account for unique commits, dirty files, running jobs
and ignored evidence before cleanup; a merged PR alone does not retire a worktree.
Dependent PRs need coordinated synchronization and affected checks before their
evidence can be claimed for the new base. Do not merge or clean up merely because
this preparation skill is being used.
