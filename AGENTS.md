# vaEVAS collaboration guide

## Scope and current state

- This repository is the new shared workspace for a Verilog-A benchmark and the full EVAS simulator source.
- The research focus is benchmark quality and trustworthy evaluation. Harbor is the selected evaluation harness.
- Initialization defines workspace ownership only. Task types, counts, scoring, simulator coverage, packaging, and internal architecture remain open.
- Read `README.md` and `docs/workspace.md` before making structural changes. Current user instructions take precedence over this guide.

## Ownership

- `tasks/`: benchmark tasks, reference solutions, and task-specific verification.
- `evas/`: simulator source, build configuration, and simulator regression tests.
- `containers/`: shared container builds and dependency versions.
- `experiments/`: experiment configurations, analysis, and curated result summaries.
- `scripts/`: repository maintenance and validation helpers.
- `docs/`: design proposals, settled decisions, and usage documentation.
- Add internal structure when an actual implementation requires it. Use the existing owning document instead of creating duplicate status trackers.

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
- Record the task/repository revision, EVAS build, image digest, Harbor/Agent configuration, and experiment budget with formal results.
- If a fix changes grading, identify and rerun affected results before using them in a comparison.
- Keep raw runs, credentials, machine-specific configuration, and scratch files out of tracked content. `.gitignore` is not an access-control boundary.
- Public documentation must distinguish proposed behavior, implemented behavior, and verified results.
