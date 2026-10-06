# Evidence and retained assets

Read the relevant section when changing support claims, selecting retained assets,
or recording an experiment. Use [CONTRIBUTING](../../CONTRIBUTING.md) for delivery
and publication rules.

## Evidence and assets

For EVAS behavior or support/evidence changes, use stable capability IDs and update affected rows.
Keep implementation, evidence and review/release status separate; preserve known counterexamples.
EVAS semantic/numerical changes include the
[feature explanation](../../evas/docs/README.md#feature-documentation-contract) and independent checks.
Use the validation skill's [trigger table](../../.agents/skills/evas-validate/SKILL.md#revalidation-triggers)
when implementations, parents, inputs, checkers or measurement environments change.

Benchmark and repository-maintenance changes use their owning contracts and checks; they do not
require EVAS capability IDs or simulator evidence unless they also change EVAS behavior or claims.
Keep EVAS status in the register, actionable follow-ups in Issues and iteration history in PRs/commits;
do not duplicate those ledgers. Use the retention rules and receipt requirements below.
The [experiment index](../../experiments/README.md) identifies current assets and archived material.

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
