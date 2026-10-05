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

## Reviewing diffs

Fix the comparison before reviewing: base/head or a saved before/after snapshot, included
paths and relevant staged, unstaged and new files. For mixed local work, isolate the requested
change so earlier edits do not enter its review. Include affected consumers when needed.

Assess requirements, repository standards and correctness evidence separately. Report actionable
findings first, ordered by severity. For each finding, give the location, trigger, impact,
supporting evidence and focused repair. Label confirmed defects, inferences and pending checks.
State the reviewed scope, actual checks and remaining limits; do not invent findings to fill a format.

Use a fresh-context independent review for new numerical mechanisms, semantic behavior and grading
logic. Give the reviewer the agreed requirements, exact revision or local diff, and evidence to inspect.
The coordinator verifies findings, organizes fixes and reruns affected checks. New changes or unresolved
findings determine follow-up review; a fixed number of clean rounds is not required. Describe any missing
independent review as a limitation. Involve the user when scope changes, acceptance criteria are disputed,
an algorithm choice needs a research trade-off, or evidence overturns the agreed research direction.

Explain each material change with its before/after behavior, reason, observed verification and
limits. Scale detail to the change; a formatting-only diff does not need a mathematical explanation.

Use these plain-language rules for diff explanations, PR descriptions and review reports:

- Use short, active sentences. Give each sentence one action or claim. Put a condition before its action.
- Use the same term for the same concept. Keep code identifiers, necessary equations and technical terms.
- Use simple Chinese for user-facing explanations unless the user requests another language.
  Keep existing agent/skill files in their main language; these rules do not require translation.

These conventions borrow writing principles from ASD-STE100. The user's "80%" preference is
a style goal, not a measured compliance score or formal STE qualification.

Before publication, check new local references against the intended commit files and their base,
not only the working tree. Include an authorized new target in the change or point to an existing
published dependency. An untracked or omitted target is a publication gap even when local link
checks pass. Local installation changes outside the repository must be reported separately.

## Branch lifecycle

1. Reuse a suitable task branch/worktree. Otherwise branch from reviewed `main`; record a different parent only for a real dependency. No permanent `develop` branch is required.
2. Keep one reviewable outcome's code, tests, mathematics and evidence in one PR. Use small commits for iteration; do not branch for each review or asset type.
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

A spec is implemented when every required acceptance criterion has observed evidence,
the necessary tests and contracts are current, and required review findings are resolved.
Record any user-accepted scope change explicitly. Remaining required criteria keep the spec
incomplete; code written, tickets attempted or a passing test count alone does not finish it.
Report implementation and the requested delivery endpoint separately. PR bodies follow
`pr` through [vaevas-prepare-pr](.agents/skills/vaevas-prepare-pr/SKILL.md); a decision trail
links the evidence and does not replace the PR explanation or acceptance checks.

For authorized overnight or unattended execution, record the bounded scope, available
resources, agreed time/cost/tool budgets, delivery endpoint and stop conditions in the
existing task record. Reuse supplied limits and task context; clarify materially missing
limits before costly or remote execution. Use `show-me-your-work` throughout execution and audit its single trail
at handoff. Finish at the agreed outcome or resource limit; when a decision or dependency
blocks part of the work, record it and continue independent authorized work within the budget.
Scheduling a later run or recurring work is a separate request from running the present task.
