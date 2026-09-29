# vaEVAS collaboration guide

## Scope and current state

- This repository is the new shared workspace for a Verilog-A benchmark and the full EVAS simulator source.
- The research focus is benchmark quality and trustworthy evaluation. Harbor is the selected evaluation harness.
- The independent validation suite has 31 current development conditions and fixed four-backend evidence. Reviewed validation and EVAS implementation checkpoints are integrated into `main`; report only the support and checks documented for the revision being used.
- Read `README.md` and the README of the affected component before making structural changes. Current user instructions take precedence over this guide.

## Agent skills

Repository-local skills live in `.agents/skills/`. Load the skills relevant to the current request; these are independent entry points, not a mandatory pipeline.

- [evas-develop](.agents/skills/evas-develop/SKILL.md): implement or refactor EVAS language, IR, and execution behavior in a reviewable scope.
- [evas-validate](.agents/skills/evas-validate/SKILL.md): select and run appropriate checks, or reassess simulator evidence against independent contracts.
- [vaevas-review-pr](.agents/skills/vaevas-review-pr/SKILL.md): review a PR or local diff for correctness, contract, and evidence problems.
- [vaevas-prepare-pr](.agents/skills/vaevas-prepare-pr/SKILL.md): prepare a reviewable checkpoint and PR description; publish only within the user's authorization.

Skills route to the owning documentation and scripts. Current implementation scope, commands, and result counts belong in those sources rather than being duplicated in skill instructions. This guide owns collaboration policy; the [handbook](evas/docs/README.md) owns technical explanations, and the [capability register](evas/docs/CAPABILITIES.md) owns implementation/evidence status. Legacy global vaEvas skills must route this consolidated repository to these local entries rather than impose the old multi-repository workflow, interview rounds, or extra plan/KPI files.

## Branch lifecycle

- Use `main` as the shared reviewed baseline. Reuse a suitable task branch/worktree; otherwise start a short-lived branch for a defined task. Target `main` unless an actual dependency requires a different base. No permanent `develop` or integration branch is required.
- One reviewable change may include code, tests, mathematics and evidence. Record intermediate checkpoints as small commits within the same PR. Do not create branches for each review round or asset type; completed PRs are not permanent work queues.
- For dependent PRs, record the parent and exact reviewed base/head. One coordinator owns synchronization. After the parent lands, update the child against `main`, retarget it, and rerun checks affected by the changed base before claiming readiness. Preserve published checkpoints; prefer merge commits when integrating reviewed work. Do not rebase or force-push shared history as incidental cleanup.
- Temporary integration branches record the exact component commits and their own checks. They do not confer merged/released status on those components. Paused work records its checkpoint, remaining question and dependency in the existing PR/Issue.
- Complete the agreed scope and relevant checks, document unsupported behavior and evidence limits, and merge only within the user's authorization. A milestone does not require a complete simulator or universal backend passes.
- Close a task branch after merge only when publication/cleanup is authorized and unique commits, dirty files, running jobs and raw evidence have been accounted for. Preserve history through commits, PRs and intentional release tags. Subsequent work uses a new task PR; do not append it to a merged PR.
- Worktree and branch lifecycles are separate: reuse a free active checkout when useful. Before retiring one, preserve needed ignored runs outside it; use the host's managed archive tool where available. Never delete a checkout to hide pending work or merely because its name is old.

## Coordination and capability tracking

- Select the affected stable capability IDs from the [register](evas/docs/CAPABILITIES.md). Add an ID only for a distinct capability; implementation state, evidence state and review/release state are separate fields. Branch implementation is not `main` support, and matching backends are not an independent proof.
- Put the current scope, owner, dependencies and acceptance criteria in the task/PR or an existing Issue. Use Issues for remaining actionable work and the register for current status/links; do not create a duplicate project ledger or a mandatory Issue for every trivial edit.
- When parallel work is authorized, give each contributor a bounded responsibility and file ownership. One coordinator owns shared IR/scheduler interfaces, version changes, integration and publication; one writer per shared file/index at a time. A delegate's report does not authorize messaging another user thread or changing its checkout.
- Semantic/numerical changes deliver the behavior and mathematical explanation, implementation, independent checks, and known limits together. Follow the [feature documentation contract](evas/docs/README.md#feature-documentation-contract); routine documentation/tooling edits need only relevant consistency checks.
- Update affected capability rows when behavior, evidence or review status changes. On a base/implementation/checker change, identify which earlier conclusions need revalidation. Old results remain valid records of their original identities, not automatic evidence for the new revision.

## Ownership

- `tasks/`: benchmark tasks, reference solutions, and task-specific verification.
- `evas/`: simulator source, build configuration, and simulator regression tests.
- `evas/docs/`: public technical handbook and the capability register; `evas/validation/`: independent behavior contracts, fixtures, reference answers and checker qualification.
- `containers/`: shared container builds and dependency versions.
- `experiments/`: experiment configurations, analysis, and curated result summaries.
- `scripts/`: repository maintenance and validation helpers.
- Keep current usage and contracts with their owning component. Put stage plans, design discussion, and review logs in PRs and Git history, rather than parallel status documents.
- Add internal structure when an actual implementation requires it. Use the existing owning document instead of creating duplicate status trackers.

## Asset identity and retention

- Give each asset one owning location and link to it elsewhere. Code and docs use commits/tags; validation uses stable condition IDs and contract/checker revisions; runs use unique execution identities. A package version alone cannot distinguish development branches.
- Experiment receipts bind capability/condition IDs, implementation commit and dirty-source identity if applicable, binary hash, inputs/initial conditions, checker revision, commands, backend/toolchain, requested/effective settings, outputs, and result limits. The [experiment guide](experiments/README.md#实验资产与收据) defines the fields and availability labels; do not invent unavailable values or force unrelated container/Harbor fields into local simulator runs.
- New execution, reused evidence and reanalysis are distinct. Preserve prior inputs, raw records and conclusions; use a new run/analysis identity for changes. Keep independent conditions, configuration counts, histories and unit-test methods as separate denominators.
- Track compact public summaries and reproducible scripts in Git. Keep bulk runs/builds and private configuration outside tracked source. Public evidence needs a retrievable artifact plus manifest/hash; local-only paths/hashes must be labeled local-only. Asset archival/publication remains within user authorization.

## Migration and fixes

- Review legacy tasks, checkers, reference solutions, and EVAS code before importing them. Preserve source provenance and applicable license notices when material is migrated.
- Treat legacy pass records as historical evidence; verify the migrated behavior in the new repository.
- Diagnose whether a failure belongs to the specification, reference solution, checker, simulator, or execution environment.
- A coherent change may update tasks, grading, and EVAS together. Include a small reproducible regression for a behavioral fix when feasible and check the affected tasks.
- Validate specifications and scoring with independent evidence where appropriate. Do not weaken a checker merely to hide a simulator or candidate failure.
- Preserve unrelated work and existing source repositories. Migration does not authorize deleting old work.

## Verification and results

- Run checks appropriate to the changed behavior. Documentation and scaffold edits need link and diff checks, not a new test framework.
- Report what was actually checked and distinguish task failures from infrastructure failures.
- Record the task/repository revision, EVAS build and experiment budget with formal results; include image digests and Harbor/Agent configuration when used.
- If a fix changes grading, identify and rerun affected results before using them in a comparison.
- Keep raw runs, credentials, machine-specific configuration, and scratch files out of tracked content. `.gitignore` is not an access-control boundary.
- Public documentation must distinguish proposed behavior, implemented behavior, and verified results.
