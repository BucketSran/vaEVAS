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

## Maintain the existing record

Use the [task template](../../.github/ISSUE_TEMPLATE/task.md) as optional prompts.
A small issue can use a few sentences for the problem and completion condition.
For larger work, explain the problem, outcome and acceptance, then the approach,
current result, blocker and next checkpoint. Include a decision with a recommendation
only when a real choice remains. Record agreed dates; use dependencies and checkpoints
when a completion date is unknown.

Keep the title about the stable outcome. Maintain one dated current summary at the
top, linking the existing progress table, owner and evidence instead of starting
another tracker. Summaries of that table retain its revision and scope. Keep
current-candidate observations separate from older accepted totals; partial passes,
successful execution and reference qualification are different claims.

Preserve prior results, failures, costs and acceptance obligations under dated
history or a `<details>` block. Label their checkpoint so an old "current" does not
read as the latest state. When a conclusion changes, mark the earlier summary as
superseded and link its correction while retaining the original observations.
Update only the authorized records; if an earlier record is outside scope, identify
the stale claim and link the correction from the record being updated.

PR descriptions explain the cumulative delivery using
[the PR skill](../../.agents/skills/vaevas-prepare-pr/SKILL.md#draft-the-pr-description).
Experiment reports keep the question, setup, source identity, execution owner,
results, limits and supported next action together. PRs and issues link those
reports and retain only the conclusions needed for review or the next decision.

## Stage and area labels

Every open issue carries one `stage:*` label and at least one `area:*` label.
A project board groups issues by these labels; GitHub's open/closed state and
close reason record the outcome, so a closed issue needs no stage label.

| Label | Meaning |
| --- | --- |
| `stage:idea` | Recorded; not yet discussed |
| `stage:design` | Goal, approach or acceptance under discussion |
| `stage:planned` | Agreed to do; waiting for an owner or a slot |
| `stage:active` | In progress on a branch, workspace or PR |
| `stage:paused` | Stopped; the body states the reason and the resume condition |
| `area:evas`, `area:benchmark`, `area:project` | Owning line; `project` covers workflow, documentation, repository and site |

For EVAS issues linked to the [unified feature list](../../evas/docs/COMPARISON.md#engineering-status),
the stage label is a coarse board view. Status, priority, dependencies and acceptance
stay in that list; when the two disagree, correct the label.

The user authorized every session to create `stage:idea` issues and to change
`stage:*` and `area:*` labels without asking (2026-10-22). Closing an issue, changing
another record's scope, merging and publishing still follow
[scope and authorization](../../CONTRIBUTING.md#scope-and-authorization).

<a id="record-a-new-idea"></a>

### Record a new idea

1. Search open and closed issues for the same outcome. When one exists, add the idea
   there as a comment and stop.
2. Otherwise write the [idea template](../../.github/ISSUE_TEMPLATE/idea.md) sections
   into a body file and create the issue:
   `gh issue create --title "<stable outcome>" --label stage:idea --label area:<line> --body-file <file>`.
   Use a title prefix such as `feat(evas):` and name the outcome, as for any issue.
3. Move the stage label when the decision changes: `idea` → `design` → `planned` →
   `active`. Set `paused` together with a dated note of the reason. The delivering PR
   links the issue, with `Closes #N` only when it delivers the whole outcome.

## Shared planning skills

`to-spec` and `to-tickets` use this tracker when publication is covered by the
current request. A local draft stays in the project's ignored task-output area
until publication is authorized. Use a body file for multiline `gh` writes.

Publish approved tickets by independently verifiable behavior, with real blocking
dependencies. Prefer existing native dependency support; otherwise link blockers
in the issue body. Reuse the existing parent rather than duplicating its scope.

Triage uses the [stage and area labels](#stage-and-area-labels). Published tickets
take `stage:planned` and an area label; the shared skills' default `ready-for-agent`
label is not part of this vocabulary.

**PRs as a request surface: no.** PRs remain review and delivery records; this flag
only excludes them from automatic feature-request triage.
