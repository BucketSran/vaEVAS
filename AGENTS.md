# vaEVAS agent guide

This repository contains a Verilog-A benchmark and the EVAS voltage-domain simulator.
Current user instructions govern scope; support, versions and result counts live in component docs.
EVAS and benchmark development share this repository; circuit execution orchestration belongs
to the separate circuit harness. Course content and prior-stage papers are external references.
Start from current code and component contracts; read historical material when its evidence is needed.

## Quick workflow

1. Read the current task, `git status -sb`, and the affected component README. Select the relevant skill below; they are independent entry points.
2. Identify the outcome, owning component and acceptance checks. For EVAS behavior or support/evidence changes, identify affected [capability IDs](evas/docs/CAPABILITIES.md). For work spanning sessions or handoffs, persist scope/dependencies in the existing PR/Issue; one-turn work may stay in the conversation. No mandatory plan/KPI/task file.
3. For edits, keep the primary checkout (`current` in this workspace) as the daily entry. Reuse a suitable task branch/worktree; temporary checkouts need a visible project entry. Run `python3 -B scripts/check_workspaces.py` when starting/resuming edits, after creating a worktree, and at handoff; follow [workspace visibility](CONTRIBUTING.md#workspace-visibility-and-handoff). New independent work starts from reviewed `main`; use a parent branch only for an actual dependency. Keep review fixes in the existing open PR.
4. Make the smallest coherent change. Use [behavior-first TDD and test selection](CONTRIBUTING.md#behavior-first-tests); for EVAS, select checks and revalidation triggers from [evas-validate](.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks). Documentation-only changes need no simulator run.
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
Shared planning skills use the [issue tracker](docs/agents/issue-tracker.md) and
[domain documentation](docs/agents/domain.md). A full interview/spec/ticket sequence is not mandatory.
Global vaEvas skills route here; legacy interview, KPI and multi-repository workflows do not apply.
Use the actual checkout as the command working directory. If the host session points to another
project and these skills are absent from its catalog, read the relevant declared `SKILL.md` through
the resolved checkout path; this is manual loading, not confirmation of automatic discovery.
When using a skill, name it briefly and report the checks actually run; no separate usage log is required.

## Ownership

- `evas/`: simulator code, build and developer tests.
- `evas/docs/`: mathematics and capability status; `evas/validation/`: independent contracts, fixtures and checkers.
- `benchmark/`: Harbor-format tasks, reference solutions, scoring and shared task environments.
- `experiments/`: reusable execution/analysis tools and compact evidence; legacy checker paths are listed in its index. Ignored `runs/`: temporary/bulk output.
- `scripts/`: repository maintenance.

## Build and checks

Use Python 3.10+ and Rust/Cargo. From the repository root, build the kernel when needed:

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
```

Validation-only Python entries need no kernel:

```sh
python3 -B evas/validation/check_design_math.py
python3 -B scripts/verify_validation_version.py
```

These check draft mathematics and frozen artifact identity, respectively; neither runs a simulator.
Then use [compile/solve/transient smoke commands](evas/README.md#构建与运行) or the
[change-to-check mapping](.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks).
Run the relevant regression after a behavioral fix; do not substitute static replay for event validation.

## Guardrails

- Do not rebase/force-push shared history, merge, or delete branches as incidental cleanup.
- Do not overwrite another contributor's work or share file/index writes concurrently; [assign ownership first](CONTRIBUTING.md#parallel-work).
- Do not weaken a checker or remove failures from the denominator to improve results.
- Do not invent receipt fields, claim unrun checks, or treat branch/local evidence as merged support or public reproducibility.
- Do not commit credentials, machine-private configuration, raw bulk runs or build products.
- Keep main assets within the [retention rules](CONTRIBUTING.md#main-branch-contents); link completed reports to fixed published history.
- Do not retire a checkout before completing the [preservation checklist](CONTRIBUTING.md#retiring-work).
- Report integration and worktree retention separately from implementation completion; keep unfinished integration visible at the project entry.

## Detailed references

- [CONTRIBUTING](CONTRIBUTING.md): task scope, branch dependencies, coordination, cleanup and [documentation language](CONTRIBUTING.md#documentation-language).
- [Cross-repository work](CONTRIBUTING.md#cross-repository-work): explicit checkout/instruction loading, ownership and end-to-end acceptance for harness integration.
- [Diff review format](CONTRIBUTING.md#reviewing-diffs): separate review questions, plain-language explanations and publication dependencies.
- [Technical handbook](evas/docs/README.md#feature-documentation-contract): behavior, mathematics, references, implementation and limits.
- [Execution receipts](CONTRIBUTING.md#execution-receipts): source/input/checker identities, reanalysis and artifact availability; [experiment index](experiments/README.md): current and archived assets.
