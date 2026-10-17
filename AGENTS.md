# vaEVAS agent guide

This repository owns the Verilog-A benchmark and EVAS voltage-domain simulator.
Circuit execution orchestration belongs to the separate circuit harness. Component
READMEs own support, versions and result counts; history supplies evidence when needed.

## Start and resume

1. Recover the current request and task record; inspect `git status -sb`. Identify the
   outcome, owning paths and acceptance checks. Carry forward valid decisions and
   [authorization](CONTRIBUTING.md#scope-and-authorization); review remains read-only.
2. For edits, check ownership and reuse `current` under the
   [workspace rules](docs/contributing/workspaces.md#creating-and-handing-off-work).
   Run `python3 -B scripts/check_workspaces.py` at start/resume, after creating a
   worktree and at handoff. Independent work starts from reviewed `main`; review
   fixes stay in the open task PR. Preserve other writers' files and shared history.
3. Load the matching entry below and only the sections needed for the next decision.
   Search headings before reading large files. Expand tool output for a failure or
   concrete question; save complete results once in the task's existing `runs/` area
   using [compact output and evidence](scripts/README.md#compact-tool-output).
4. For behavior changes, load [behavior-first tests](docs/contributing/validation.md#behavior-first-tests).
   Make the smallest coherent change and run the owning acceptance checks. Report
   the checked revision/local diff, failures and limits. Keep one main conversation and fixed
   [current-task entry](docs/contributing/workspaces.md#workspace-visibility-and-handoff).
   Compaction alone does not trigger a transfer; necessary
   [handoffs](docs/contributing/workspaces.md#conversation-handoff-triggers) retain links in both directions.

## Load by task

| When | Entry and obligations |
| --- | --- |
| Work spans components/stages, a spec or unattended delivery | [vaevas-workflow](.agents/skills/vaevas-workflow/SKILL.md); shared-skill routing and delivery boundaries |
| Implement/refactor EVAS behavior | [evas-develop](.agents/skills/evas-develop/SKILL.md); capability IDs, behavior-first tests, handbook and actual Spectre alignment |
| Select/run checks or report EVAS evidence | [evas-validate](.agents/skills/evas-validate/SKILL.md); affected regressions, revalidation and evidence identity |
| Build or grade benchmark tasks | [benchmark contract](benchmark/README.md); task and checker acceptance |
| Review a diff, including GLM review | [vaevas-review-pr](.agents/skills/vaevas-review-pr/SKILL.md); fixed scope, complete evidence and one concise summary |
| Prepare a commit/PR or publish | [vaevas-prepare-pr](.agents/skills/vaevas-prepare-pr/SKILL.md); final delta, reuse of matching checks and publication authority |
| Edit human docs / agent instructions | [documentation rules](CONTRIBUTING.md#documentation-language); `technical-writing` / `writing-for-agents` |
| Manage checkouts, parallel writers or cross-repository work | [workspaces](docs/contributing/workspaces.md); ownership, visibility and preservation before retirement |
| Retain/report experiment material or select main assets | [evidence policy](docs/contributing/evidence.md); receipts, retention and timing; [experiment index](experiments/README.md) |
| Capture a reusable development failure | [candidate policy](docs/contributing/validation.md#development-bench-candidates); recording does not authorize task construction |

Known component tasks can enter their skill directly. Name skills briefly and report
checks actually run. No mandatory interview, plan, KPI or separate workflow file.
For EVAS build/run commands, use [evas/README](evas/README.md#构建与运行).
EVAS behavior or support claims require the component's capability/evidence gates;
documentation-only changes need no simulator run. Keep failing cases and denominators,
source identities and local/published status truthful. Publishing, merging and cleanup
require authorization for that action and target.

## Ownership

- `evas/`: simulator, build and developer tests.
- `evas/docs/`: mathematics and capability status; `evas/validation/`: independent contracts, fixtures and checkers.
- `benchmark/`: Harbor tasks, reference solutions, scoring and shared task environments.
- `experiments/`: execution/analysis tools and compact evidence; ignored `runs/`: temporary/bulk output.
- `scripts/`: repository maintenance.
