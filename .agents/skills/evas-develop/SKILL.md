---
name: evas-develop
description: >-
  Implement, fix, or refactor EVAS simulator behavior, including Verilog-A
  parsing, parameter binding, Python/Rust IR, equation assembly, and solving.
  Use for source changes and semantic extensions, not validation-only runs,
  PR review alone, or unrelated repository documentation.
---

# Develop EVAS

Deliver the requested behavior as a coherent, reviewable change. The user's
scope and stopping point govern the work; this skill does not start subsequent
roadmap stages.

## Establish the contract

Start with [EVAS README](../../../evas/README.md), its current interface and
build guidance, and the relevant PR checkpoint. Confirm that the checkout
contains the intended implementation, then inspect affected code and callers.
Separate current behavior from proposals and historical verification.

For the requested change, identify accepted inputs, rejected inputs, observable
results, and compatibility implications. For new semantics, establish an
independent expected answer using the applicable language specification or
the validation contracts under `evas/validation/`, when present in this checkout.
Resolve only material ambiguities; use existing contracts for routine choices.

## Change the owning layer

- Parsing belongs in `syntax.py`; instance, parameter, and node binding belong
  in `frontend.py`. Keep syntax independent of IR.
- `src/evas/ir.py` and `rust_core/src/ir.rs` jointly define the transport contract.
  Trace format changes through both producers and consumers, version checks,
  malformed-input handling, runtime transport, and migration guidance.
- Rust `assembly.rs` owns IR validation and contribution assembly; `solver.rs`
  owns working-point solutions and residual acceptance; `linear.rs` owns the
  numerical linear solve. Verify these paths against the implementation branch
  and follow its documented ownership if the layout evolves.
- Preserve the Python compilation and Rust execution path. Unsupported
  semantics need an explicit diagnostic, not silent fallback, node assignment
  in place of equations, or model-name/test-family special cases.

Add files or abstractions when a concrete responsibility needs them. For stateful
extensions, define initialization and accepted/candidate state with commit and
rollback before implementation. Do not scaffold an unused state framework.

## Verify and hand off

Use independent expected values and the smallest regression that detects the
changed behavior, including a relevant rejection or compatibility case. Select
affected checks from the EVAS README; static replay cannot establish transient
or event correctness. Preserve the original validation cases and thresholds.

Update the owning component documentation when behavior or evidence changes;
keep stage discussion and review history in the PR, preparing text locally when
publication is outside the task's scope.
Report changed behavior, affected modules, observed verification, unsupported
scope, and remaining risks. Stop at an explicitly requested review boundary;
otherwise finish the requested implementation and checks without adding a new
approval gate.
