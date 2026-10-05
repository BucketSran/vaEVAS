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
5. Merge the agreed scope after relevant checks and authorized review; universal simulator support is not a gate. End that task after merge and use a new PR for later work. Apply the retirement checklist separately before cleanup.

## Workspace visibility and handoff

The primary checkout is the daily human entry, named `current` in this local workspace.
Temporary worktrees isolate conflicting or parallel work; their results must remain discoverable
from that entry's project directory. Reuse a suitable checkout before creating another one.
Keep concurrent writes in the primary checkout within the [ownership rules](#parallel-work).

Place temporary checkouts under the primary checkout's sibling `worktrees/` directory when the
host supports that location. For a host-managed checkout elsewhere, create a visible directory
symlink there pointing to the actual checkout; keep the host's managed path intact. In the local
`worktrees/README.md`, link each entry using a relative path and record its purpose, current
handoff state and next action. Link this index from the surrounding project README. This is local
workspace navigation, not a second issue tracker; link the existing task record when available.

Run `python3 -B scripts/check_workspaces.py` at the checkpoints in AGENTS.md. The check discovers
the primary checkout through Git, then inspects its linked worktrees. Resolve missing or stale
navigation before continuing ordinary edits. It reports tracked/untracked changes, ignored paths
and commits not reachable from the selected local base. A passing visibility check does not mean
the work is integrated or safe to delete. See [commands and limits](scripts/README.md#本地工作区检查).

At handoff, distinguish implementation, review, integration into the target branch, and visibility
in the daily checkout. If integration or cleanup is pending, keep the visible entry with the reason
and next action. Complete already-authorized integration and retirement when their conditions are
met; otherwise report the concrete remaining step without treating local work as merged support.
After [preserving needed material](#retiring-work) and retiring a worktree, remove its navigation
entry and rerun the check. Changing the index never authorizes merging or deleting files.

The sibling `local/` directory holds archived evidence, recovery snapshots and local presentation
materials; it is not an active development checkout. Archive records keep their source identities.
Maintain current source and contracts in the repository, and use Git's worktree inventory to
identify active checkouts rather than recursively treating archived code copies as live projects.

<a id="behavior-first-tests"></a>

## Behavior-first tests

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

<a id="development-bench-candidates"></a>

## Development failures as benchmark candidates

When development exposes a reusable modeling mistake, semantic trap or compatibility
problem, add or update [the candidate register](benchmark/CANDIDATES.md) before handoff.
Record the concrete trigger, observed versus required behavior, evidence and proposed
modeling task. Separate confirmed causes from hypotheses; a simulator bug or infrastructure
failure must not be mislabeled as a VA model defect. Reuse the existing candidate for the
same failure family. Link code, Issue/PR and compact receipts instead of copying run logs.

Capture is part of the current work. Formal task design, variant generation, scoring and
Harbor integration are a separate work item; a new candidate does not trigger them by
default. Existing prototypes stay labeled as prototypes until that work is reviewed.
The register owns candidate status; Issues and PRs own implementation work and history.

## Parallel work

- Before authorized delegation, the coordinator posts each worker's owner, writable paths, base and expected result in task messages. That assignment is the ownership record; no separate lock file is required.
- Workers report path overlap before editing it. The coordinator serializes access or reassigns responsibility; workers do not resolve overlap by reverting others' changes.
- One coordinator controls shared IR/scheduler interfaces, versions, integration and publication. Only the coordinator stages/commits in a shared checkout; independent worktrees have separate indexes.
- Explicitly hand off a path before changing writers. Inspect status before integration; assignments coordinate people/agents but are not OS locks against uncoordinated processes.

<a id="cross-repository-work"></a>

## Cross-repository work

For a task involving vaEVAS and the circuit harness, one coordinator records both actual checkouts,
source revisions, existing local changes and the shared acceptance outcome. Explicitly read each
repository's `AGENTS.md` and relevant skills; attaching another folder does not automatically load
its project instructions. Apply each repository's rules to its own files.

Keep engine algorithms and independent validation in `evas/`, task definitions and scoring in
`benchmark/`, and reusable execution/job/evidence collection in the harness. Preserve pinned historical
backends; a new engine adapter must identify the current source and kernel it actually executes.
Record the request/result/error contract with its owner and verify a complete consumer-to-backend run
in addition to component checks. Integration success does not establish a published benchmark score.

Use the ownership rules above for each checkout. A worktree for one repository does not isolate the
other. Keep commits and PRs separate, linking their exact dependencies and merge order. Handoffs carry
the outcome, identities, checks, limits and remaining work through the existing task record; start the
next independent task in a new conversation rather than replaying the full implementation discussion.

## Evidence and assets

For EVAS behavior or support/evidence changes, use stable capability IDs and update affected rows.
Keep implementation, evidence and review/release status separate; preserve known counterexamples.
EVAS semantic/numerical changes include the
[feature explanation](evas/docs/README.md#feature-documentation-contract) and independent checks.
Use the validation skill's [trigger table](.agents/skills/evas-validate/SKILL.md#revalidation-triggers)
when implementations, parents, inputs, checkers or measurement environments change.

Benchmark and repository-maintenance changes use their owning contracts and checks; they do not
require EVAS capability IDs or simulator evidence unless they also change EVAS behavior or claims.
Keep EVAS status in the register, actionable follow-ups in Issues and iteration history in PRs/commits;
do not duplicate those ledgers. Use the retention rules and receipt requirements below.
The [experiment index](experiments/README.md) identifies current assets and archived material.

## Main branch contents

`main` is the maintained source and evidence entry point for the benchmark and EVAS.
Each added file must serve a current use, validation obligation or published claim.

| Keep on main | Owner |
| --- | --- |
| Simulator source, build/dependency files, examples and developer regressions | `evas/` |
| Current mathematics, behavior, support boundaries and user instructions | `evas/docs/` and component READMEs |
| Independent models, stimuli, contracts, reusable input generators/checkers and their calibration | `evas/validation/` |
| Benchmark candidate register, Harbor-format tasks, reference solutions, scoring and shared task environments | `benchmark/` |
| Reusable execution/analysis tools and compact evidence needed for current or published comparisons | `experiments/` |
| Repository maintenance, contribution instructions and agent/skill entry points | `scripts/`, root files, `.agents/` |

Label construction-only entries in their component README until usable assets exist.
Some reusable validation tools still live in historical experiment directories. Keep their current paths
until their imports, callers, commands and source-identity recording have been migrated together.
The experiment index records these exceptions; do not add new shared checkers to PR-named directories.

Archive completed audits, superseded stage reports and one-off diagnostics through a **published fixed
commit**, with a short link from the owning index when still useful. Keep compact historical baselines
on main when they support a published comparison; preserve failures, settings and the full denominator.
PR numbers, run dates and a former branch name alone are not reasons to retain an entire directory.
Do not keep duplicate progress/design/review logs, raw bulk output, build products, credentials or
machine-private configuration on main. Durable mathematical explanations belong in the handbook.

Before removing an asset: inspect code imports, commands, documentation links and frozen manifests;
retain reachable source/evidence identities; update current links; run the affected checks.
A checker move changes the identity of future analyses, not the identity or verdict of old receipts.
Git preserves tracked history, not ignored raw data: retain and verify needed raw archives separately.
Do not rewrite frozen snapshots, overwrite old verdicts or turn local-only data into a public-data claim.

## Execution receipts

Use the owning experiment's existing manifest/result format; no duplicate record is required.

| Required information | What the record must identify |
| --- | --- |
| Purpose and execution | Capability/condition, run or analysis ID, new execution versus reuse/reanalysis, and the original run for the latter |
| Implementation and build | DUT/EVAS commit, dirty state plus retrievable source snapshot/patch and hash, kernel identity; a version or `dirty=true` alone is insufficient |
| Inputs and judgment | Model, stimulus, initial state, observation grid, independent answer, tolerances and checker identity/hash |
| Environment and command | Backend/toolchain, command, requested and effective settings, budget; performance claims also need hardware, timing boundary and repetitions |
| Results | Execution status, compilation/runtime/numerical/environment failures, fixed denominator, protocol verdict and limits |
| Availability | Archive location, inventory/hash and whether a reader can actually retrieve the material |

Do not invent missing fields; mark unknown or inapplicable items explicitly. Record container/image/agent
identity only when used. Changed parameters or checkers require a new execution/analysis identity;
reanalysis is not a new simulator run. Report cases, backend configurations, event histories and test
methods separately. Keep counterexamples and inconclusive results; development cases are not unseen holdouts.

Label availability as **repository-contained**, **public archive**, or **local-only**. Public archives need
a working retrieval address and inventory/hash; machine paths and checksums alone are not download links.
Publication still requires task authorization. Before workspace cleanup, preserve needed ignored evidence
and its verified old-to-new path mapping. Package versions alone do not identify development branches.

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
