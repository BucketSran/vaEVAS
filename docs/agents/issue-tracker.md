# Issue tracker

Project work is tracked in [vaEVAS GitHub Issues](https://github.com/BucketSran/vaEVAS/issues)
and its associated PRs. Resolve the actual repository from the checkout's remote
before using `gh`; repository access does not authorize a write.

Read the existing Issue/PR and relevant comments before creating a task record.
Reuse it for the same outcome, dependencies, acceptance criteria and handoff.
One-turn work can stay in the conversation under the
[scope policy](../../CONTRIBUTING.md#scope-and-authorization).

For EVAS accuracy or performance tasks, use the
[accuracy-recovery and performance acceptance rules](../contributing/validation.md#accuracy-recovery-and-performance-acceptance)
when defining the outcome and checks. Inspect existing mechanisms and the current task
status before proposing missing work or reopening a deferred optimization.

## Shared planning skills

`to-spec` and `to-tickets` use this tracker when publication is covered by the
current request. A local draft stays in the project's ignored task-output area
until publication is authorized. Use a body file for multiline `gh` writes.

Publish approved tickets by independently verifiable behavior, with real blocking
dependencies. Prefer existing native dependency support; otherwise link blockers
in the issue body. Reuse the existing parent rather than duplicating its scope.

Triage automation and its label vocabulary are not configured. Under this project
adaptation, spec/ticket work can proceed without triage labels; omit the shared
skills' default `ready-for-agent` label unless the user has selected a label policy.
Configure labels when adopting triage, rather than creating them for ordinary work.

**PRs as a request surface: no.** PRs remain review and delivery records; this flag
only excludes them from automatic feature-request triage.
