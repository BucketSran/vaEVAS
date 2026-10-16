# Workspaces and coordination

Read the relevant section when managing worktrees, coordinating writers, integrating
repositories, or retiring work. Start with [CONTRIBUTING](../../CONTRIBUTING.md) for
scope, branch lifecycle and delivery rules.

## Workspace visibility and handoff

The primary checkout, named `current` in this local workspace, is the default development
directory. Switch task branches there after the previous task has handed it over; `current`
does not stay permanently on `main`. One task or benchmark batch owns its checked-out branch
at a time. Preserve unfinished changes and required evidence before switching branches.
Temporary worktrees isolate work that must proceed simultaneously. Their results remain
discoverable from the project entry. Reuse a suitable checkout before creating another one,
and follow the [ownership rules](#parallel-work) for concurrent writes.

Place temporary checkouts under the primary checkout's sibling `worktrees/` directory when the
host supports that location. For a host-managed checkout elsewhere, create a visible directory
symlink there pointing to the actual checkout; keep the host's managed path intact. In the local
`worktrees/README.md`, link each entry using a relative path and record its purpose, current
handoff state and next action. Link this index from the surrounding project README. This is local
workspace navigation, not a second issue tracker; link the existing task record when available.
The surrounding project README is the single current-task entry: keep its outcome, owning
checkout, stage and next action together, linking the existing PR/Issue or evidence. The
worktree index records locations, purposes and dispositions, and points back to that task.
Distinguish current work, retained delivery candidates and historical evidence. Do not turn
every retained checkout into an active task or copy a historical handoff's execution instructions
into the current queue. A missing target stays explicitly unresolved until its recovery location
is verified; removing an active navigation link does not establish safe archival.

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

## Creating and handing off work

Before creating a checkout, inspect the current task and worktree index for the same problem
and acceptance outcome. Reuse its checkout across conversations and review rounds. Record the
owner, writable paths, base, destination and acceptance outcome in that existing entry or task
record before writing. If another conversation owns those paths, assist read-only or wait for
an explicit handoff; changing conversations does not create a new implementation task.

Each task or benchmark batch has one coordinating conversation. It assigns writable paths,
controls shared Git operations, and coordinates validation and delivery. Another conversation
joins through an explicit assignment or takes over through a handoff. Read-only analysis and
review can use a fixed revision or saved diff without another checkout.

The normal project limit is three active writing workspaces: `current`, one additional EVAS
workspace, and one additional benchmark workspace. `current` can host either development line.
These are available slots, not required permanent directories. Retained candidates and historical
evidence do not occupy an active writing slot and do not resume automatically. Discuss a changed
scope or priority before exceeding this limit or using another development line's extra slot.

Use this table to decide whether to reuse a checkout, queue work, or isolate it:

| Situation | Decision | Action |
| --- | --- | --- |
| Start an independent task and `current` is available | Reuse | Check the prior handoff and retained assets, then create a task branch from updated, reviewed `main`. Record a different parent only for a real dependency. |
| Continue a task, fix review findings, or resume in another conversation | Reuse | Keep the task branch and checkout. Hand off coordination explicitly when its owner changes. |
| Accelerate an existing EVAS task | Reuse and assign | Identify the bottleneck, then delegate analysis, reproduction, review, or a bounded implementation subtask. Keep one implementation lead. |
| Discuss future features or benchmark scope | Discuss first | Resolve ownership, acceptance and implementation timing before allocating a branch or checkout. |
| Implement several tasks in one benchmark batch | Reuse in parallel | Share the batch branch and checkout. Assign task directories and coordinate shared files, generation and acceptance. |
| Writers need the same core interface, scoring rule or shared generator | Queue conflicting writes | Give the shared change one owner or an explicit order. Independent work can continue. |
| Start an independent task while `current` is occupied, without a need for simultaneous implementation | Queue | Prepare through discussion or read-only analysis, then wait for handoff. |
| Implement independent outcomes simultaneously with clear file, acceptance and runtime boundaries | Isolate | Use the owning development line's extra slot. Reuse a suitable idle checkout before creating one. |
| Validation must retain one source/environment while another version changes | Isolate if necessary | First check whether a fixed binary or existing snapshot is sufficient. Use the owning line's extra slot only when two source checkouts are needed. |
| The owning development line's extra slot is occupied | Queue or reprioritize | Resolve the active task or agree on a scope change before allocating more workspaces. |
| A task or batch has merged into `main` | End the task and assess reuse | Check remaining changes, required evidence and running processes. Start later independent work on a new task branch; physical cleanup follows the retirement rules separately. |

Create a worktree only when simultaneous work needs an independent source state or branch,
an appropriate slot is available, and no suitable idle checkout can be reused. A new branch
does not require a new directory. A dirty or occupied `current` remains intact while its owner
resolves the handoff; its status does not authorize reset, stash or an incidental branch switch.

At handoff or suspension, record the resulting revision or local diff, remaining acceptance
checks, destination and reason to retain the checkout in the existing task/index. Transfer
ownership explicitly before another writer starts. Run the visibility check; use its opt-in
[asset report](../../scripts/README.md#只读资产报告) when deciding reuse or retirement.
Its overlap and duplicate candidates narrow review; they do not establish semantic equivalence,
integration or an inactive owner. Incomplete observations require follow-up, not a clean bill.

## Conversation handoff triggers

Move coordination to a fresh main conversation at these checkpoints:

| Trigger | Handoff point |
| --- | --- |
| A complete task reaches its agreed delivery endpoint | Start the next independent task in a new conversation. |
| The same task reaches its second observable context compaction in the current conversation | Hand off at the next safe checkpoint before taking another implementation step. |
| Repeated evidence reads, confused authorization or omitted settled decisions show lost context | Correct the immediate ambiguity, preserve work and hand off early. |

Count only observed compaction events in the existing task record. Preserve the count across
summaries; if earlier events cannot be recovered, mark the count unknown rather than inventing
it. Repeated reads needed for new evidence are not themselves a context failure. A fresh
review subagent does not replace the coordinating conversation.

A safe checkpoint has saved edits, fixed evidence identities and explicit ownership of running
jobs. Finish or identify an in-flight Git operation; do not interrupt it blindly. The handoff
in the existing PR/Issue or local current-task entry states the outcome, checkout/branch and
revision or local diff, reusable checks, remaining work, running jobs, authorization and limits.
Keep it within 300 visible characters and link detailed evidence; add no separate process file.
The receiving conversation reads that entry and the affected contract, then resumes the first
unfinished step without rereading the entire history or repeating matching checks.

Reuse `current`. Continue the same task on its existing branch; for a new independent task,
create a task branch from reviewed, updated `main` after the prior owner releases the checkout.
A new conversation does not require a new worktree, branch for an ongoing task, or cleanup.
After handoff, the old conversation stops writing. Preparing a handoff does not itself create
or message another task; follow the user's requested transition.

## Asset lifetime

Keep source changes recoverable through commits or snapshots. Preserve each required raw
evidence set once and refer to its fixed source/binary identities from other tasks. New task
outputs use one designated run directory; do not copy bulk runs into every worker checkout.
Existing evidence paths remain valid until an authorized move has a verified recovery mapping.

Keep build directories for active tasks rather than all retained checkouts. Before proposing
cache removal, identify binaries required by existing receipts and retain those artifacts.
Share dependency downloads where suitable; concurrent writers must not replace one another's
executable through a common writable target directory. A validation result names the binary
actually executed. Cache measurements are candidates for review, not reclaimable-space promises.

## Parallel work

- EVAS defaults to one implementation lead with read-only collaborators. Assign a bounded writing subtask only when its paths and interfaces can be separated; shared IR and scheduler changes have one owner.
- Benchmark batches normally allow parallel writes to assigned task directories. The coordinator handles overlaps and serializes shared indexes, scoring rules, common sources and generators that rewrite multiple tasks. A task directory alone does not establish independent ownership of those shared assets.
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

At the end of each task, state whether the checkout remains active, is retained for a named
delivery blocker, or is a retirement candidate. A completed review alone is not a reason to
keep another writing checkout indefinitely. Preserve unfinished integration at the project
entry; perform physical cleanup only under the following checklist and its authorization.

Before authorized branch deletion or worktree retirement:

1. Check the task owner and running jobs; an active task/process using the checkout prevents retirement.
2. Inspect status, unique commits and upstream differences. Preserve needed uncommitted/unpushed work in reachable commits or a recoverable snapshot; zero unpushed commits is not required for managed archival.
3. List needed ignored runs/build inputs and move them to retained storage. Verify manifest/hash and retrieval path; keep historical receipts unchanged and record old-to-new paths in the archive inventory. Git snapshots do not preserve ignored files.
4. Use the host's managed archive tool when available. A merged PR alone does not require archival; reuse free active worktrees. Delete a branch only after its needed history remains reachable.
