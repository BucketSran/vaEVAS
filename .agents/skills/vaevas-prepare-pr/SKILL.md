---
name: vaevas-prepare-pr
description: >-
  Prepare a vaEVAS change or EVAS checkpoint for a reviewable commit or PR,
  including scope inspection, verification evidence, and title/body drafting.
  Commit, push, and create a PR only when authorized by the current task.
  Do not treat preparation as permission to merge or include unrelated work.
---

# Prepare a vaEVAS PR

Produce a concrete reviewable result within the requested scope. Read
[repository guidance](../../../AGENTS.md),
[workspace ownership](../../../README.md), and any current repository
PR template. Use the actual checkout and remote; do not assume a machine-local
path, legacy repository, or branch name.

## Establish the change boundary

Inspect status, staged and unstaged changes, relevant untracked files, branch,
remote, and intended base/head. For stacked work, identify the parent branch and
the diff reviewers should see. Preserve unrelated or concurrent changes; do not
stash, switch branches, rebase, force-push, or merge as incidental cleanup.
Follow the [branch lifecycle](../../../AGENTS.md#branch-lifecycle); reuse the task's
existing PR for review fixes and related documentation/evidence. Record the
affected capability IDs, current parent/base and exact checkpoint; do not create
an extra branch solely for a review round, test report or commit.

Include only work belonging to the request. If commits are authorized, stage
explicit paths or hunks and inspect the staged diff. Do not split or commit
another contributor's in-progress work merely to tidy history.

## Make the evidence reviewable

- Confirm that changed behavior and compatibility limits agree with the owning
  component documentation and PR checkpoint. Keep unsupported behavior explicit.
- Use observed checks appropriate to the change. Follow
  [EVAS commands](../../../evas/README.md) and the relevant validation protocol;
  do not rerun a full backend matrix solely to prepare a PR.
- Keep curated summaries and provenance according to
  [experiment ownership](../../../experiments/README.md). Exclude raw waveforms,
  build products, credentials, and machine-specific configuration. An ignored
  directory is not proof that the files selected for commit are appropriate.
- Inspect the final diff and check formatting and links. Report checks not run
  or failures honestly; never present an old result as verification of this diff.
- Verify that affected [capability rows](../../../evas/docs/CAPABILITIES.md),
  mathematical explanations and evidence links agree. Separate implementation,
  verification and review/release status. Link existing Issues for deferred work;
  avoid duplicating the register in a new progress document.

Write a title and body about the final change: the concrete problem, resulting
behavior, meaningful design or compatibility decisions, actual checks and their
outcomes, and remaining limits. Link the relevant contracts and evidence. Use the
repository template if one exists; omit abandoned approaches and stale counts.

## Publish only within the requested scope

Preparation alone ends with the ready diff and proposed PR text. When the user
has authorized committing, pushing, or creating a PR for this task, complete
those authorized steps without asking again. Prefer a draft PR unless the user
requests otherwise, and use the verified base branch. Creation does not
authorize merging, reviewer messages, or unrelated repository changes.

Report what was actually prepared, committed, pushed, or opened. Include commit
identity and PR URL when applicable, the review base, verification limits, and
any relevant work still left locally.
After an authorized merge, account for unique commits, dirty files, running jobs
and ignored evidence before cleanup; a merged PR alone does not retire a worktree.
Dependent PRs need coordinated synchronization and affected checks before their
evidence can be claimed for the new base. Do not merge or clean up merely because
this preparation skill is being used.
