# Contributing to vaEVAS

[AGENTS.md](AGENTS.md) is the agent quick reference. This guide owns detailed collaboration procedures;
the [handbook](evas/docs/README.md) owns technical explanations and the
[capability register](evas/docs/CAPABILITIES.md) owns implementation/evidence status.
Read the relevant section; these sections are not a mandatory pipeline.

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

## Branch lifecycle

1. Reuse a suitable task branch/worktree. Otherwise branch from reviewed `main`; record a different parent only for a real dependency. No permanent `develop` branch is required.
2. Keep one reviewable outcome's code, tests, mathematics and evidence in one PR. Use small commits for iteration; do not branch for each review or asset type.
3. For dependent PRs, record parent PR and exact base/head. The coordinator updates the child after the parent lands, retargets it to `main`, and selects [affected checks](.agents/skills/evas-validate/SKILL.md#revalidation-triggers). Preserve published checkpoints; prefer merges over rewriting shared history.
4. Temporary integration work records its component commits and separate evidence; it does not mark components merged or released. Paused work records the remaining question in its existing PR/Issue.
5. Merge the agreed scope after relevant checks and authorized review; universal simulator support is not a gate. End that task after merge and use a new PR for later work. Apply the retirement checklist separately before cleanup.

## Parallel work

- Before authorized delegation, the coordinator posts each worker's owner, writable paths, base and expected result in task messages. That assignment is the ownership record; no separate lock file is required.
- Workers report path overlap before editing it. The coordinator serializes access or reassigns responsibility; workers do not resolve overlap by reverting others' changes.
- One coordinator controls shared IR/scheduler interfaces, versions, integration and publication. Only the coordinator stages/commits in a shared checkout; independent worktrees have separate indexes.
- Explicitly hand off a path before changing writers. Inspect status before integration; assignments coordinate people/agents but are not OS locks against uncoordinated processes.

## Evidence and assets

Use stable capability IDs and update affected rows. Keep implementation, evidence and review/release
status separate; preserve known counterexamples. Semantic/numerical changes include the
[feature explanation](evas/docs/README.md#feature-documentation-contract) and independent checks.
Use the validation skill's [trigger table](.agents/skills/evas-validate/SKILL.md#revalidation-triggers)
when implementations, parents, inputs, checkers or measurement environments change.

[experiments/README.md](experiments/README.md#experiment-receipts) owns receipt fields, asset identities,
availability labels and retention. Store compact summaries/scripts in Git and bulk evidence in an identified
archive. Keep status in the register, actionable follow-ups in Issues and iteration history in PRs/commits;
do not duplicate those ledgers. Package versions alone do not identify development branches.

## Retiring work

Before authorized branch deletion or worktree retirement:

1. Check the task owner and running jobs; an active task/process using the checkout prevents retirement.
2. Inspect status, unique commits and upstream differences. Preserve needed uncommitted/unpushed work in reachable commits or a recoverable snapshot; zero unpushed commits is not required for managed archival.
3. List needed ignored runs/build inputs and move them to retained storage. Verify manifest/hash and retrieval path; keep historical receipts unchanged and record old-to-new paths in the archive inventory. Git snapshots do not preserve ignored files.
4. Use the host's managed archive tool when available. A merged PR alone does not require archival; reuse free active worktrees. Delete a branch only after its needed history remains reachable.

## Migration

Inspect source contracts, checkers and reference solutions before importing legacy code/tasks. Preserve
provenance and license notices. Historical passes retain their original revision; verify migrated behavior
with affected checks. Importing material does not authorize deleting its source repository.
