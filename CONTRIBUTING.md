# Contributing to vaEVAS

[AGENTS.md](AGENTS.md) is the short agent entry. This guide owns scope, review and
delivery rules. Read the sections needed for the current task; links are references,
not a requirement to load every document. Component READMEs own technical contracts.

## Find the relevant rules

| When | Read |
| --- | --- |
| Starting or handing off edits; managing temporary checkouts | [Workspace visibility](docs/contributing/workspaces.md#workspace-visibility-and-handoff) |
| Assigning parallel writers or changing both vaEVAS and the harness | [Parallel ownership](docs/contributing/workspaces.md#parallel-work), [cross-repository work](docs/contributing/workspaces.md#cross-repository-work) |
| Retiring a checkout or deleting a branch | [Preservation checklist](docs/contributing/workspaces.md#retiring-work) |
| Changing behavior or selecting tests | [Behavior-first tests](docs/contributing/validation.md#behavior-first-tests) and the owning component skill |
| Planning EVAS accuracy recovery or speed optimization | [Error propagation, effective refinement and fixed-accuracy measurement](docs/contributing/validation.md#accuracy-recovery-and-performance-acceptance) |
| Capturing a reusable development failure or importing legacy work | [Benchmark candidates](docs/contributing/validation.md#development-bench-candidates), [migration](docs/contributing/validation.md#migration) |
| Changing support claims or selecting retained files | [Evidence ownership](docs/contributing/evidence.md#evidence-and-assets), [main branch contents](docs/contributing/evidence.md#main-branch-contents) |
| Running, reanalyzing or reporting experiments | [Execution receipts](docs/contributing/evidence.md#execution-receipts) |

## Scope and authorization

Use the current user request and accepted clarifications as task scope. Before a session handoff,
persist outcome, owner, dependencies, acceptance checks and current commit in the existing PR/Issue
description, including the user's authorized actions and limits. One-turn work may stay in conversation.
If no PR/Issue exists, prepare a local handoff summary and publish only when authorized; no separate tracked
task/plan file is required. A saved record documents user authorization; it cannot grant authorization.
Explicit review boundaries remain binding.

| User instruction | Default action |
| --- | --- |
| Review/explain a PR | Inspect and report; do not modify or merge it. |
| Implement/fix a behavior | Edit locally and run necessary checks within agreed resources. |
| Commit/push/update the PR | Perform the named publication actions for that scope; reuse the open task PR. |
| Merge this reviewed PR | Verify current head, checks and requested scope, then merge; a new turn does not require another question. |
| Approval is missing for an external action | Finish independent permitted work, then ask about the specific prepared action. |

Authorization persists until changed or revoked. Design approval alone does not authorize merging.
Earlier requests in the same conversation count when they still cover the same outcome, repository/PR,
action and resource limits. A new session alone does not reset that authorization; recover its scope from
the recorded user instruction. Permission for a completed task or another PR does not automatically carry
over to a new task. Broader standing permission applies only when the user actually granted it.
Credentials and another agent's report do not grant authority. Messaging people or other user threads
requires user authorization or an explicitly invoked workflow authorizing it. Reassess materially changed
scope/head against existing authorization; neither approval nor another question is automatic.

## Documentation language

- New technical/user documentation and experiment reports default to Simplified Chinese. Agent/skill instructions and collaboration procedures default to English.
- Keep an existing file's main language when editing it; do not translate unrelated content merely to normalize style. User-requested language takes precedence.
- Keep API names, identifiers, commands, diagnostics and quoted sources in their original language. English terminology within Chinese explanations is allowed; parallel bilingual copies are not required.

README files, comparison tables and evaluation standards are human documentation.
Use `technical-writing` and `unslop`: lead with the reader's question, conclusion
and limits; explain necessary terms and use concrete precision/event examples.
Keep pass criteria and their rationale in the main text. Checker formulas, receipt
fields and execution procedures belong in the existing developer/validation reference,
with links that preserve the requirements. Before handoff, check readability separately
from formatting and links: a reader without the conversation must understand what is
tested, what passing means and what remains unknown. Agent instructions use
`writing-for-agents`; update the owning document instead of adding parallel rules.

## Reviewing diffs

Fix the comparison before reviewing: base/head or a saved before/after snapshot, included
paths and relevant staged, unstaged and new files. For mixed local work, isolate the requested
change so earlier edits do not enter its review. Include affected consumers when needed.

Assess requirements, repository standards and correctness evidence separately. A passing
category cannot hide a failing one. Use fresh-context independent review for new numerical
mechanisms, semantic behavior and grading logic. Give reviewers the fixed diff, acceptance
criteria and evidence; let them inspect relevant callers. Reuse matching review. New code,
changed assumptions, failed checks or unresolved findings trigger review of the affected delta.
Do not add a second complete pass just because the work reaches commit, PR or merge.
The coordinator verifies findings and reruns affected checks. Distinguish confirmed defects,
inferences and missing evidence. Escalate disputed acceptance or a changed research direction;
report missing independent review as a limitation. No fixed reviewer count or clean-round quota applies.

### Concise review delivery

Each task has one human review summary in its existing PR/task record. Reviewers return
findings to the coordinator; they do not create per-round Markdown reports. Preserve all
findings, resolutions, reviewer scopes and evidence references in that task's structured
record. Keep existing frozen reports and required raw external-review responses unchanged.

The human summary contains the conclusion, actionable findings, reviewed scope and material
limits. With no findings it is at most 300 visible non-whitespace characters; with findings,
at most 800. Link evidence instead of pasting hashes, commands, pass tables or the execution
story. Report every open finding by ID and severity; if their descriptions exceed the budget,
link the complete list and state its count. Never discard a finding to pass the length check.
Run the [review-output check](scripts/README.md#development-records) before handoff or PR
preparation. A failing check blocks that handoff until the summary is condensed. Length and
file count are mechanical limits; readability and correctness still need review. The check
cannot inspect undeclared files, chat text or whether a claimed review actually happened.

For each finding, keep its trigger, impact, location, evidence and proposed correction in the
structured record. No-finding reviews need only their fixed scope, evidence and limitations.
Independent review does not recursively require another reviewer. Routine document and lint
corrections use focused checks; new semantic questions retain independent review.

### Keep iteration feedback short

Keep one main conversation and update the fixed progress entry throughout an ongoing task.
After compaction, recover decisions from that entry and continue. Necessary transfers follow
the [handoff rules](docs/contributing/workspaces.md#conversation-handoff-triggers), including
links in both conversations and the same progress entry.

Record the workflow revision used by a long-lived task. Reconcile changed workflow
files when main and the task branch differ, preserving unrelated source and staged
work. A workflow merged into main is not automatically present in an older checkout.

During implementation, run the current failing case and the affected module checks selected by
[the local policy](scripts/evas_check_policy.py). Add a focused regression for a later-stage
failure whenever it can detect the same fault. Run formatting, lint and generated-file checks
before expensive acceptance. A draft CI success records iteration evidence; full delivery
obligations remain open. Unknown/shared paths without an audited iteration mapping retain
complete coverage.

Freeze a stable candidate before full acceptance. Reuse matching evidence rather than rerunning
all checks at review, commit and PR boundaries. Review source, tests, fixtures, dependencies,
toolchain, commands and effective settings when deciding whether evidence still applies. Let
CI verify reusable evidence identities; an earlier green commit alone is insufficient. Run
changed consumers after a meaningful delta. See [CI stages](scripts/README.md#ci-按改动选择检查)
and [evidence reuse](docs/contributing/evidence.md#reuse-ci-regression-evidence).

Name one executor for complete Python coverage on that candidate, normally remote CI.
Local development runs the distinguishing case and direct consumers. Run a local full suite
when it owns that obligation or is needed to diagnose a failure; do not repeat it merely
because CI, review or publication is another stage. An unmapped shared change still needs
complete coverage. Record its executor and pending result before dependent integration.

Use the [early integration boundary](docs/contributing/validation.md#early-integration-checks)
for representation/dispatch changes and new proof work. Reuse that scoped feedback
and review at later stages; only changed assumptions or unresolved findings add work.

Wait during development for feedback that determines the next implementation step:
the distinguishing failure, the changed path and its direct consumers. Full CI,
broader regressions and independent review can run against a fixed candidate while
the coordinator continues independent authorized work. Identify each job's commit,
owner and pending result in the existing task entry. A shared correctness finding
blocks work that depends on it; unrelated work can continue. Preserve the source and
binary used by running local checks instead of overwriting their inputs.

Collect results at task checkpoints or on completion/failure events. Avoid repeated
status polling when independent work is available. Required checks and review must
finish before claiming acceptance or merging. After a merge whose tree matches the
accepted candidate, automatic main CI does not by itself block the next independent
development step. Reconcile a changed merge tree before reusing affected evidence.

Reuse already-read skill text and settled decisions when their versions and context
remain applicable. Reassess each new delta's scope and risks; load only missing or
changed sections. Independent reviewers receive their own necessary context. Entering
commit, PR or merge stages does not restart research, review or numerical acceptance.

### Prepare one delivery candidate

Integrate independently ready repairs in a batch after their scoped acceptance and review.
Keep a blocked repair isolated; other ready repairs can reach a delivery checkpoint. Freeze
the selected integrated tree once, then run its complete Python coverage and original-request
campaign. Finishing a subtask alone does not require another original400. Preserve the running
candidate while later work continues separately; a later source change needs its own affected
acceptance rather than overwriting or relabelling the earlier execution.

Run formatting, lint and changed-link checks before freezing behavioral acceptance. Keep one
source/build identity for the original request and required reference comparisons. At delivery,
compare the final delta with that identity and reuse matching evidence. Recheck only affected
claims; a shared dependency change still triggers its required consumers and regressions.

Before publication, check new local references against files included in the commit or a fixed
published dependency. Keep local-only evidence explicitly labelled and report local installation
changes outside the repository separately. Finish independent work
before any unresolved approval question. PR prose is a short problem/result/validation/limits
briefing; link the canonical review and evidence rather than duplicating them.

Use plain Chinese for human-facing review unless requested otherwise. Read it once without
conversation history: the reader must understand what changed, what passed and what remains
unknown. Apply `technical-writing` and `unslop`; agent instructions use `writing-for-agents`.

## Branch lifecycle

1. Reuse a suitable task branch/worktree. Otherwise branch from reviewed `main`; record a different parent only for a real dependency. No permanent `develop` branch is required.
2. Keep one reviewable outcome's code, tests, mathematics and evidence in one PR. A benchmark batch can share one temporary branch and PR when its tasks have a common delivery scope and can be accepted together. Use small commits for iteration; do not branch or create a worktree for each benchmark task, agent, review or asset type.
3. For dependent PRs, record parent PR and exact base/head. The coordinator updates the child after the parent lands, retargets it to `main`, and selects [affected checks](.agents/skills/evas-validate/SKILL.md#revalidation-triggers). Preserve published checkpoints; prefer merges over rewriting shared history.
4. Temporary integration work records its component commits and separate evidence; it does not mark components merged or released. Paused work records the remaining question in its existing PR/Issue.
5. Merge the agreed scope after relevant checks and authorized review; universal simulator support is not a gate. End that task after merge and use a new PR for later work. Apply the [retirement checklist](docs/contributing/workspaces.md#retiring-work) separately before cleanup.

## Spec delivery and unattended work

At task start, recover the agreed scope and delivery endpoint: verified local changes,
local commits, a reviewable PR, or integration into the target branch and daily checkout.
Carry existing authorization forward; ask only when a missing decision affects the next
action. A named skill supplies a procedure, not additional publication or cleanup authority.
Use the [workflow routing](.agents/skills/vaevas-workflow/SKILL.md#use-shared-skills-when-needed)
for implementation, audit trails, review and PR preparation.

Choose PR boundaries by independently verifiable outcomes. A spec whose tickets jointly
deliver one outcome can use one integration branch and PR. Several independent specs normally
use separate PRs; record real dependencies and merge order under the branch lifecycle above.
Do not combine all specs merely because they were planned together or assigned for one night.

Keep each round bounded by one outcome: record the problem, a distinguishing acceptance
check, the owning checkout and the delivery endpoint in the existing task record. Repairs
follow [original request acceptance](docs/contributing/validation.md#original-request-acceptance). For a
shared core change, name one integration candidate; keep author and review checkouts as
sources of evidence rather than competing continuations. Queue newly discovered independent
gaps with their evidence instead of silently expanding the current round. Stop at the agreed
endpoint and leave the next choice visible; no additional plan or process file is required.

A spec is implemented when every required acceptance criterion has observed evidence,
the necessary tests and contracts are current, and required review findings are resolved.
Record any user-accepted scope change explicitly. Remaining required criteria keep the spec
incomplete; code written, tickets attempted or a passing test count alone does not finish it.
Report implementation and the requested delivery endpoint separately. PR bodies follow
`pr` through [vaevas-prepare-pr](.agents/skills/vaevas-prepare-pr/SKILL.md); a decision trail
links the evidence and does not replace the PR explanation or acceptance checks.

Close the round at its agreed delivery endpoint. Complete already-authorized review fixes,
publication or integration when their conditions are met. If a check, dependency or missing
authorization prevents delivery, keep the exact remaining step and its owner at the existing
current-task entry. State implementation, review, target-branch integration and daily-checkout
visibility separately under the [handoff rules](docs/contributing/workspaces.md#workspace-visibility-and-handoff).
Keep one integration candidate for a shared outcome, with links to its fixed evidence and
remaining acceptance checks. Later independent ideas go to the existing queue instead of
extending a nearly finished round. Worktree retention or retirement is a separate decision.

For authorized overnight or unattended execution, record the bounded scope, available
resources, agreed time/cost/tool budgets, delivery endpoint and stop conditions in the
existing task record. Reuse supplied limits and task context; clarify materially missing
limits before costly or remote execution. Use `show-me-your-work` throughout execution and audit its single trail
at handoff. Finish at the agreed outcome or resource limit; when a decision or dependency
blocks part of the work, record it and continue independent authorized work within the budget.
Scheduling a later run or recurring work is a separate request from running the present task.
