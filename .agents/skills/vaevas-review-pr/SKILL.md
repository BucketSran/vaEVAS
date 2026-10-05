---
name: vaevas-review-pr
description: >-
  Review a vaEVAS GitHub PR or local diff for actionable correctness,
  compatibility, validation, and evidence problems. Use when asked to review
  an EVAS checkpoint, benchmark change, or assess readiness. Review is read-only
  unless the user also requests fixes; it does not publish GitHub comments.
---

# Review a vaEVAS change

Resolve the requested diff, its actual base and head, and any stacked-PR
ancestry. Do not assume the base is `main`. Inspect the changed code and relevant
callers or consumers; keep findings attributable to the reviewed change.
Preserve the working tree. Perform fixes or publish review comments only when
the current task authorizes those actions.

Record resolved base/head commit IDs and the actual comparison. For branch changes,
use the merge-base with the PR's target; for an explicit pair of revisions, compare
those endpoints. For local work, include the requested staged, unstaged and relevant
untracked files as well as any committed range. A diff ending at HEAD alone does
not review uncommitted work; an empty committed diff does not end a local review.

Use the [project review policy](../../../CONTRIBUTING.md#reviewing-diffs) to determine
when a fresh-context independent review is required. The reviewer receives the
requirements, resolved diff and evidence, and checks relevant sources rather than
adopting the implementer's conclusions. An already independent reviewer performs
that review directly; this rule does not create recursive review delegation.

When the work used `show-me-your-work`, load its trail-review guidance and inspect
the existing canonical log and accessible evidence. Combine the applicable project
and trail-review requirements in one independent review when both are required.
Reuse an existing review only for the requirements, diff, evidence and trail it
actually covered; review any uncovered or changed scope. Keep the log format and
audit procedure in `show-me-your-work` rather than creating a second review log.

## Assess the relevant contracts

Use [workspace ownership](../../../README.md) and the affected component's contract:
[EVAS documentation](../../../evas/README.md) for simulator work or
[benchmark guidance](../../../benchmark/README.md) and the task contract for benchmark work.
Read only the owning protocol/sections. Review against the user's acceptance
criteria, rather than every possible future simulator feature.

Resolve requirements from the task, PR/Issue and owning component/task contract; no extra
specification file or issue-tracker setup is required. Assess three distinct questions:
whether the mathematics and requested semantics are implemented, whether architecture
and documented repository rules are respected, and whether independent evidence
supports the claims. A pass in one question does not answer the others. Treat code
smells as hypotheses requiring concrete impact, not automatic blockers.

For EVAS behavior or support/evidence changes, resolve affected
[capability rows](../../../evas/docs/CAPABILITIES.md) and
[handbook explanation](../../../evas/docs/README.md#feature-documentation-contract).
Check the three separate claims: what the reviewed commit implements, what the
identified evidence demonstrates, and whether the change is merged/released.
For stacked PRs, flag changed shared assumptions and evidence tied to an older
parent; do not treat a temporary integration test as proof of `main` support.
For EVAS claims, use the [revalidation triggers](../evas-validate/SKILL.md#revalidation-triggers)
to identify evidence invalidated by changed code, inputs, checkers or measurement conditions.

- For parser or binding changes, check full token consumption, unsupported syntax,
  parameter dependency and override rules, finite values, and instance isolation.
- For IR changes, trace Python/Rust serialization, version rejection, structured
  branch identity, endpoint orientation, and validation at both entry points.
- For assembly and solving, check contribution accumulation, independent instance
  constraints, ground/driven-node handling, singular systems, non-finite results,
  and residual acceptance. A small residual alone is not a forward-error bound.
- For EVAS stateful behavior, inspect the changed path and its consumers for
  initialization, call-site ownership, event order and candidate isolation.
  Check that reset/restart preserves other live histories, observation queries
  do not mutate accepted state, and rejected trials can retry in the same engine.
  Trace event-window/sample uncertainty into future history and voltage acceptance.
  Use [composition triggers](../evas-validate/SKILL.md#composition-triggers) when a
  shared mechanism changes; an operator-only pass does not verify feedback/reset.
- For benchmark changes, check the affected task instructions, environment,
  reference solution and grading contract. Require only assets that actually
  exist at that stage; a placeholder does not demonstrate executable tasks.
- For validation changes, compare case contracts, independent expected answers,
  checker calibration, fixed denominators, and requested versus effective
  settings. Inspect the source or derivation supporting a disputed expected answer,
  and distinguish the original program from a proposed corrected model. Follow
  the [evidence rules](../evas-validate/SKILL.md#preserve-independent-evidence) when
  interpreting negative controls or incomplete runs.
  Use `evas/validation/METHOD_QUALIFICATION.md` when present and a
  claim depends on it; missing qualification evidence remains a review gap.
- For documentation or reports, check that claims refer to the actual revision,
  build, and observations. Historical passes and static replay do not certify new
  code or transient semantics. Check current component contracts and the PR
  checkpoint rather than assuming a separate design or review-log file exists.
- For public experiment claims, follow the artifact links and provenance. A
  local-only archive may support a limited internal report, but cannot be called
  a publicly reproducible dataset. Preserve known counterexamples and distinguish
  LRM requirements, implementation choices and observations from other backends.

Assess whether a test could detect the relevant bug independently of the
implementation. Expected answers should come from a justified analytic or worked
reference, a qualified independent oracle, or a specified invariant. Preserve focused
kernel and rollback tests when they protect properties that outer tests do not expose.
Apply the [test selection rules](../../../CONTRIBUTING.md#behavior-first-tests): flag
self-derived oracles and duplicated fault coverage, but require a retained detector
before recommending regression deletion. For reusable development failures, check the
[candidate entry](../../../benchmark/CANDIDATES.md); recording one does not require
completing a benchmark task in this PR.
Run a focused reproduction when feasible and within task scope;
if it would alter shared state or require an unauthorized resource, explain the
verification gap instead of claiming it passed.

## Deliver the review

Use the [diff review format](../../../CONTRIBUTING.md#reviewing-diffs), including its
plain-language rules and publication dependency checks. Lead with actionable
findings ordered by severity. Identify which review question each finding concerns;
one passing category cannot hide a failure in another.
Avoid speculative architecture preferences and unrelated pre-existing issues.
Use this review format for findings; the shared `pr` skill applies when writing
a PR body, not when reporting a review. Include actionable trail findings and any
missing trail-review coverage in the same report when applicable.

If no actionable defects are found, say so and describe the review scope and
material verification limits. Complete one review unless new changes, a specific
unresolved question, or the user's request warrants another pass. Reuse review
that covers the same requirements and diff; changed behavior, dependencies or
claims require checking the affected scope again. There is no fixed reviewer
count or clean-round quota.
Describe direct and independently delegated review accurately; a readiness assessment
does not authorize merge or claim an independent review that did not happen.
