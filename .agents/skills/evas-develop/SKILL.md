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

Use the stable IDs in the [capability register](../../../evas/docs/CAPABILITIES.md)
to identify the change and its dependencies. Follow [repository coordination
policy](../../../CONTRIBUTING.md#parallel-work). Reuse suitable
in-progress work; when parallel work is authorized, agree file ownership and a
single owner for shared IR, scheduling and version changes before editing them.

For the requested change, identify accepted inputs, rejected inputs, observable
results, and compatibility implications. For new semantics, establish an
independent expected answer using the applicable language specification or
the validation contracts under `evas/validation/`, when present in this checkout.
Resolve only material ambiguities; use existing contracts for routine choices.

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

Use independent expected values and the smallest regression that detects the
changed behavior, including a relevant rejection or compatibility case. Select
checks from [the validation mapping](../evas-validate/SKILL.md#select-the-necessary-checks); static replay cannot establish transient
or event correctness. Preserve the original validation cases and thresholds.
When a shared mechanism changes, use the [composition triggers](../evas-validate/SKILL.md#composition-triggers)
to select affected feedback, event/reset, sampling and retry regressions. An
operator-only pass cannot establish those combinations.

Update the owning component documentation when behavior or evidence changes;
keep stage discussion and review history in the PR, preparing text locally when
publication is outside the task's scope.
For semantic/numerical work, update the relevant handbook chapter using the
[feature documentation contract](../../../evas/docs/README.md#feature-documentation-contract):
behavior, source/assumption distinction, mathematics, numerical method, code map,
independent evidence and limits. Update only affected capability rows; do not
promote branch work to merged support or an old run to verification of a new base.
Report changed behavior, affected modules, observed verification, unsupported
scope, and remaining risks. Stop at an explicitly requested review boundary;
otherwise finish the requested implementation and checks without adding a new
approval gate.
