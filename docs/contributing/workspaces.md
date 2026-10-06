# Workspaces and coordination

Read the relevant section when managing worktrees, coordinating writers, integrating
repositories, or retiring work. Start with [CONTRIBUTING](../../CONTRIBUTING.md) for
scope, branch lifecycle and delivery rules.

## Workspace visibility and handoff

The primary checkout is the daily human entry, named `current` in this local workspace.
Temporary worktrees isolate conflicting or parallel work; their results must remain discoverable
from that entry's project directory. Reuse a suitable checkout before creating another one.
Keep concurrent writes in the primary checkout within the [ownership rules](#parallel-work).

Place temporary checkouts under the primary checkout's sibling `worktrees/` directory when the
host supports that location. For a host-managed checkout elsewhere, create a visible directory
symlink there pointing to the actual checkout; keep the host's managed path intact. In the local
`worktrees/README.md`, link each entry using a relative path and record its purpose, current
handoff state and next action. Link this index from the surrounding project README. This is local
workspace navigation, not a second issue tracker; link the existing task record when available.

Run `python3 -B scripts/check_workspaces.py` at the checkpoints in AGENTS.md. The check discovers
the primary checkout through Git, then inspects its linked worktrees. Resolve missing or stale
navigation before continuing ordinary edits. It reports tracked/untracked changes, ignored paths
and commits not reachable from the selected local base. A passing visibility check does not mean
the work is integrated or safe to delete. See [commands and limits](../../scripts/README.md#本地工作区检查).

At handoff, distinguish implementation, review, integration into the target branch, and visibility
in the daily checkout. If integration or cleanup is pending, keep the visible entry with the reason
and next action. Complete already-authorized integration and retirement when their conditions are
met; otherwise report the concrete remaining step without treating local work as merged support.
After [preserving needed material](#retiring-work) and retiring a worktree, remove its navigation
entry and rerun the check. Changing the index never authorizes merging or deleting files.

The sibling `local/` directory holds archived evidence, recovery snapshots and local presentation
materials; it is not an active development checkout. Archive records keep their source identities.
Maintain current source and contracts in the repository, and use Git's worktree inventory to
identify active checkouts rather than recursively treating archived code copies as live projects.

## Parallel work

- Before authorized delegation, the coordinator posts each worker's owner, writable paths, base and expected result in task messages. That assignment is the ownership record; no separate lock file is required.
- Workers report path overlap before editing it. The coordinator serializes access or reassigns responsibility; workers do not resolve overlap by reverting others' changes.
- One coordinator controls shared IR/scheduler interfaces, versions, integration and publication. Only the coordinator stages/commits in a shared checkout; independent worktrees have separate indexes.
- Explicitly hand off a path before changing writers. Inspect status before integration; assignments coordinate people/agents but are not OS locks against uncoordinated processes.

## Cross-repository work

<a id="cross-repository-work"></a>

For a task involving vaEVAS and the circuit harness, one coordinator records both actual checkouts,
source revisions, existing local changes and the shared acceptance outcome. Explicitly read each
repository's `AGENTS.md` and relevant skills; attaching another folder does not automatically load
its project instructions. Apply each repository's rules to its own files.

Keep engine algorithms and independent validation in `evas/`, task definitions and scoring in
`benchmark/`, and reusable execution/job/evidence collection in the harness. Preserve pinned historical
backends; a new engine adapter must identify the current source and kernel it actually executes.
Record the request/result/error contract with its owner and verify a complete consumer-to-backend run
in addition to component checks. Integration success does not establish a published benchmark score.

Use the ownership rules above for each checkout. A worktree for one repository does not isolate the
other. Keep commits and PRs separate, linking their exact dependencies and merge order. Handoffs carry
the outcome, identities, checks, limits and remaining work through the existing task record; start the
next independent task in a new conversation rather than replaying the full implementation discussion.

## Retiring work

Before authorized branch deletion or worktree retirement:

1. Check the task owner and running jobs; an active task/process using the checkout prevents retirement.
2. Inspect status, unique commits and upstream differences. Preserve needed uncommitted/unpushed work in reachable commits or a recoverable snapshot; zero unpushed commits is not required for managed archival.
3. List needed ignored runs/build inputs and move them to retained storage. Verify manifest/hash and retrieval path; keep historical receipts unchanged and record old-to-new paths in the archive inventory. Git snapshots do not preserve ignored files.
4. Use the host's managed archive tool when available. A merged PR alone does not require archival; reuse free active worktrees. Delete a branch only after its needed history remains reachable.
