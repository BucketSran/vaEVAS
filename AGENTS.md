# vaEVAS agent guide

This repository contains a Verilog-A benchmark and the EVAS voltage-domain simulator.
Current user instructions govern scope; support, versions and result counts live in component docs.

## Quick workflow

1. Read the current task, `git status -sb`, and the affected component README. Select the relevant skill below; they are independent entry points.
2. Identify the requested outcome, affected [capability IDs](evas/docs/CAPABILITIES.md), and acceptance checks. Keep scope and dependencies in the conversation or existing PR/Issue; no mandatory plan/KPI/task file.
3. For edits, reuse a suitable task branch/worktree. New independent work starts from reviewed `main`; use a parent branch only for an actual dependency. Keep review fixes in the existing open PR.
4. Make the smallest coherent change. Select checks and revalidation triggers from [evas-validate](.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks); documentation-only changes need no simulator run.
5. Update affected contracts, capability rows and evidence links. Report the exact commit, checks, failures and limits; prepare/publish through the PR skill within the requested scope.

Carry existing task authorization forward without asking again. A request to implement permits necessary local edits and checks; review alone stays read-only. Publishing, merging and cleanup need authorization covering that action. If absent, finish independent work and ask once about the concrete action. See [examples](CONTRIBUTING.md#scope-and-authorization).

## Skills

| Task | Repository entry |
| --- | --- |
| Implement/refactor | [evas-develop](.agents/skills/evas-develop/SKILL.md) |
| Check behavior/evidence | [evas-validate](.agents/skills/evas-validate/SKILL.md) |
| Review | [vaevas-review-pr](.agents/skills/vaevas-review-pr/SKILL.md) |
| Prepare/publish a checkpoint | [vaevas-prepare-pr](.agents/skills/vaevas-prepare-pr/SKILL.md) |

Global vaEvas skills route here; legacy interview, KPI and multi-repository workflows do not apply.

## Ownership

- `evas/`: simulator code, build and developer tests.
- `evas/docs/`: mathematics and capability status; `evas/validation/`: independent contracts, fixtures and checkers.
- `tasks/`: benchmark tasks, reference solutions and task verification.
- `experiments/`: protocols, execution receipts and curated results; ignored `runs/`: temporary/bulk output.
- `containers/`: shared build environments; `scripts/`: repository maintenance.

## Build and checks

Use Python 3.10+ and Rust/Cargo. From the repository root:

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
```

Then use [compile/solve/transient smoke commands](evas/README.md#构建与运行) or the
[change-to-check mapping](.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks).
Run the relevant regression after a behavioral fix; do not substitute static replay for event validation.

## Guardrails

- Do not rebase/force-push shared history, merge, or delete branches as incidental cleanup.
- Do not overwrite another contributor's work or share file/index writes concurrently; [assign ownership first](CONTRIBUTING.md#parallel-work).
- Do not weaken a checker or remove failures from the denominator to improve results.
- Do not invent receipt fields, claim unrun checks, or treat branch/local evidence as merged support or public reproducibility.
- Do not commit credentials, machine-private configuration, raw bulk runs or build products.
- Do not retire a checkout before completing the [preservation checklist](CONTRIBUTING.md#retiring-work).

## Detailed references

- [CONTRIBUTING](CONTRIBUTING.md): task scope, branch dependencies, coordination and cleanup.
- [Technical handbook](evas/docs/README.md#feature-documentation-contract): behavior, mathematics, references, implementation and limits.
- [Experiment receipts](experiments/README.md#experiment-receipts): source/input/checker identities, reanalysis and artifact availability.
