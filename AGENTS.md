# vaEVAS agent guide

This repository contains a Verilog-A benchmark and the EVAS voltage-domain simulator.
Current user instructions govern scope; support, versions and result counts live in component docs.
EVAS and benchmark development share this repository; circuit execution orchestration belongs
to the separate circuit harness. Course content and prior-stage papers are external references.
Start from current code and component contracts; read historical material when its evidence is needed.

## Quick workflow

1. Read the current task, `git status -sb`, and the affected component README. Select the relevant skill below; they are independent entry points.
2. Identify the outcome, owning component and acceptance checks. For EVAS behavior or support/evidence changes, identify affected [capability IDs](evas/docs/CAPABILITIES.md). For work spanning sessions or handoffs, persist scope/dependencies in the existing PR/Issue; one-turn work may stay in the conversation. No mandatory plan/KPI/task file.
3. For edits, keep the primary checkout (`current` in this workspace) as the daily entry. Reuse a suitable task branch/worktree; temporary checkouts need a visible project entry. Run `python3 -B scripts/check_workspaces.py` when starting/resuming edits, after creating a worktree, and at handoff; follow [workspace visibility](docs/contributing/workspaces.md#workspace-visibility-and-handoff). New independent work starts from reviewed `main`; use a parent branch only for an actual dependency. Keep review fixes in the existing open PR.
4. Make the smallest coherent change. Use [behavior-first TDD and test selection](docs/contributing/validation.md#behavior-first-tests); for EVAS, select checks and revalidation triggers from [evas-validate](.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks). Documentation-only changes need no simulator run.
5. Update affected component contracts and evidence links; update capability rows only when EVAS support/evidence changes. Report the reviewed revision or local diff, checks, failures and limits; prepare/publish through the PR skill within the requested scope.

Capture reusable development failures in [benchmark candidates](benchmark/CANDIDATES.md), linking existing evidence. Recording a candidate does not add a scored task or authorize benchmark construction.

Carry authorization forward for the same task, target and action within its resource limits; it does not automatically extend to another PR. Implementation permits necessary local edits/checks; review alone stays read-only. Publishing, merging and cleanup need authorization covering that action. If absent, finish independent work and ask once about the concrete action. See [boundaries and examples](CONTRIBUTING.md#scope-and-authorization).

## Skills

| Task | Repository entry |
| --- | --- |
| Select/resume work across components or stages | [vaevas-workflow](.agents/skills/vaevas-workflow/SKILL.md) |
| Implement/refactor EVAS behavior | [evas-develop](.agents/skills/evas-develop/SKILL.md) |
| Check EVAS behavior/evidence | [evas-validate](.agents/skills/evas-validate/SKILL.md) |
| Review | [vaevas-review-pr](.agents/skills/vaevas-review-pr/SKILL.md) |
| Prepare/publish a checkpoint | [vaevas-prepare-pr](.agents/skills/vaevas-prepare-pr/SKILL.md) |

Use the project entry and shared skills on demand; known component tasks can enter directly.
For spec implementation, unattended work and PR delivery, follow the
[skill routing](.agents/skills/vaevas-workflow/SKILL.md#use-shared-skills-when-needed) and
[delivery criteria](CONTRIBUTING.md#spec-delivery-and-unattended-work).
Shared planning skills use the [issue tracker](docs/agents/issue-tracker.md) and
[domain documentation](docs/agents/domain.md). A full interview/spec/ticket sequence is not mandatory.
Global vaEvas skills route here; legacy interview, KPI and multi-repository workflows do not apply.
Use the actual checkout as the command working directory. If the host session points to another
project and these skills are absent from its catalog, read the relevant declared `SKILL.md` through
the resolved checkout path; this is manual loading, not confirmation of automatic discovery.
When using a skill, name it briefly and report the checks actually run; no separate usage log is required.

For GLM reviews, prioritize a complete, scoped report; the user has ample GLM quota.
Default to USD 5 per CLI call, process-local `CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000`
and a 15-minute timeout; size the task total to its review obligations. A user's explicit ceiling prevails.
Retain complete changed functions, relevant callers and evidence when reducing duplicate
context. After budget/output truncation, adjust the limiting resource before retrying;
count actual reported turns and preserve failed responses. Archived USD 1/call and fixed
call-count limits are historical run settings, not project defaults. A missing report stays pending.

For EVAS behavior changes, require relevant actual Spectre comparisons before recommending
merge or claiming behavioral alignment. Record a justified reuse or explicit alignment gap;
local regressions, analytical answers and model reviews do not replace this evidence.
Follow [Spectre alignment acceptance](docs/contributing/validation.md#spectre-alignment-acceptance)
for scope, tolerances, version identity and exceptions.

## Ownership

- `evas/`: simulator code, build and developer tests.
- `evas/docs/`: mathematics and capability status; `evas/validation/`: independent contracts, fixtures and checkers.
- `benchmark/`: Harbor-format tasks, reference solutions, scoring and shared task environments.
- `experiments/`: reusable execution/analysis tools and compact evidence; legacy checker paths are listed in its index. Ignored `runs/`: temporary/bulk output.
- `scripts/`: repository maintenance.

## Build and checks

When building or running EVAS, use Python 3.10+, Rust/Cargo and the
[build and smoke commands](evas/README.md#构建与运行). Select validation with the
[change-to-check mapping](.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks);
static mathematics and artifact-identity checks do not run a simulator.
Run the relevant regression after a behavioral fix; do not substitute static replay for event validation.

## Guardrails

- Do not rebase/force-push shared history, merge, or delete branches as incidental cleanup.
- Do not overwrite another contributor's work or share file/index writes concurrently; [assign ownership first](docs/contributing/workspaces.md#parallel-work).
- Do not weaken a checker or remove failures from the denominator to improve results.
- Do not invent receipt fields, claim unrun checks, or treat branch/local evidence as merged support or public reproducibility.
- Do not commit credentials, machine-private configuration, raw bulk runs or build products.
- Keep main assets within the [retention rules](docs/contributing/evidence.md#main-branch-contents); link completed reports to fixed published history.
- Do not retire a checkout before completing the [preservation checklist](docs/contributing/workspaces.md#retiring-work).
- Report integration and worktree retention separately from implementation completion; keep unfinished integration visible at the project entry.

## Detailed references

Read only the sections needed for the task. [CONTRIBUTING](CONTRIBUTING.md#find-the-relevant-rules)
routes to collaboration, test and evidence rules. For EVAS behavior documentation, use the
[technical handbook contract](evas/docs/README.md#feature-documentation-contract);
for retained experiment material, use the [experiment index](experiments/README.md).
