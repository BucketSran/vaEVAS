---
name: evas-develop
description: >-
  Implement, fix, or refactor EVAS compiler and voltage-domain simulator
  behavior, including continuous dynamics, histories, and events. Use for
  behavioral source changes, not benchmark authoring, validation-only runs,
  PR review alone, or unrelated repository documentation.
---

# Develop EVAS

Deliver the requested behavior as a coherent, reviewable change. The user's
scope and stopping point govern the work; this skill does not start subsequent
roadmap stages.

## Establish the contract

Use the relevant interface/build guidance in [EVAS README](../../../evas/README.md)
and the task's existing PR checkpoint when present. Confirm that the checkout
contains the intended implementation, then inspect affected code and callers.
Separate current behavior from proposals and historical verification.

Use the stable IDs in the [evidence index](../../../evas/docs/development/capability-evidence.md)
to identify the change and its dependencies. Follow [repository coordination
policy](../../../docs/contributing/workspaces.md#parallel-work). Reuse suitable
in-progress work; when parallel work is authorized, agree file ownership and a
single owner for shared IR, scheduling and version changes before editing them.

For the requested change, identify accepted inputs, rejected inputs, observable
results, and compatibility implications. For new or disputed semantics, distinguish
the intended engineering behavior from what the supplied VA program expresses.
Derive the expected answer from the applicable language specification or independent
validation contract. Preserve the original model and verdict when proposing a
corrected model; a correction answers a different compatibility question.
Resolve only material ambiguities; use existing contracts for routine choices.

For accuracy recovery or speed optimization, follow the
[accuracy and performance acceptance rules](../../../docs/contributing/validation.md#accuracy-recovery-and-performance-acceptance).
Identify the error source or measured bottleneck and the observable evidence that the
chosen action improves it. Reuse existing recovery mechanisms before extending them.

Before changing behavior, follow the [behavior-first test rules](../../../docs/contributing/validation.md#behavior-first-tests).
Use an independent failing case, reusing an existing regression when it exposes
the fault. Trace the affected public entry through its actual compiler/kernel path;
a Python helper result alone does not establish the default Rust path's behavior.
Distinguish inspected code from an observed run and keep an unexecuted baseline
unconfirmed. Preserve focused lifecycle/numerical tests with distinct obligations.

## Change the owning layer

Use the current [module/interface map](../../../evas/README.md#模块与接口), then the
owning handbook chapter for code responsibilities: [voltage solving and sparse
paths](../../../evas/docs/math/solving.md), [event settlement](../../../evas/docs/math/events.md),
[operator histories](../../../evas/docs/math/operators.md), or [continuous dynamics,
derivatives and DAE](../../../evas/docs/math/continuous.md). Read only the affected
sections and verify their entries against the checkout rather than copying a
second code map into this skill.

Preserve the Python compilation and Rust execution path. For IR changes, trace
both producers and consumers, version checks, malformed-input handling, runtime
transport, and migration guidance. Unsupported semantics need an explicit
diagnostic, not silent fallback or model-name/test-family special cases.

When the change touches these mechanisms, preserve their shared invariants:

- Contributions accumulate in one equation system; program assignments retain
  their statement order. Equivalent encodings preserve shared IR semantics.
- Operator history belongs to the instantiated call site, not the receiving
  variable. Initialization, feedback and reset must preserve other live states.
- Each trial starts from accepted history. Keep candidate changes isolated;
  commit state, error bounds, queues and event records only after acceptance.
  Rejected trials leave accepted state intact; same-time input changes require
  reevaluation. History queries and output sampling must not mutate it.
- Check equation residual, history accuracy and event-time uncertainty at their
  owning stages. Propagate applicable uncertainty through sampling, future
  history and voltage amplification; a small residual alone is insufficient.

Add files or abstractions when a concrete responsibility needs them. For stateful
extensions, define initialization and accepted/candidate state with commit and
rollback before implementation. Do not scaffold an unused state framework.

## Verify and hand off

Rerun the independent case through the affected path after the change and explain
the distinct fault each added regression detects. Include a relevant rejection or
compatibility case. Select
checks from [the validation mapping](../evas-validate/SKILL.md#select-the-necessary-checks); static replay cannot establish transient
or event correctness. Preserve the original validation cases and thresholds.
When a shared mechanism changes, use the [composition triggers](../evas-validate/SKILL.md#composition-triggers)
to select affected feedback, event/reset, sampling and retry regressions. An
operator-only pass cannot establish those combinations.

Update the owning component documentation when behavior or evidence changes;
keep stage discussion and review history in the PR, preparing text locally when
publication is outside the task's scope.
If the failure can become a reusable modeling task, update the
[benchmark candidate register](../../../benchmark/CANDIDATES.md) with its trigger,
evidence, proposed task and unresolved questions. Capture first; do not start formal
benchmark construction unless it is part of the requested scope.
For semantic/numerical work, update the relevant handbook chapter using the
[feature documentation contract](../../../evas/docs/README.md#feature-documentation-contract):
behavior, source/assumption distinction, mathematics, numerical method, code map,
independent evidence and limits. Update affected support summaries and evidence-index entries; do not
promote branch work to merged support or an old run to verification of a new base.
Hand off the requirements, actual diff and evidence for the independent review
required by the [review policy](../../../CONTRIBUTING.md#reviewing-diffs).
Report changed behavior, affected modules, observed verification, unsupported
scope, and remaining risks. Stop at an explicitly requested review boundary;
otherwise finish the requested implementation and checks without adding a new
approval gate.
