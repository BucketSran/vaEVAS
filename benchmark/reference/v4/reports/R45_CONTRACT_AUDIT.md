# R45 Contract Audit

Audit date: 2026-07-18
Source revision: `6608b94ebfeed60ef655888b435ea0b15122f83c`

The family-sharded contract audit ran across canonical DUT families 001-400.
The disposable shards and aggregate were generated with
`audit_v4_contract_semantics.py`; they are not a maintained registry.

## Result

| Classification | Families |
| --- | ---: |
| Mechanical binding error | 0 |
| Human review required | 33 |
| No finding | 367 |

The existing V4 repair gate also passed all 400 families with zero failures.
Together these checks found no broken ID, artifact, property, profile, trace,
checker-registry, task-record hash, or bound gold-certification relationship.
This is a structural consistency result, not proof that checker mathematics is
semantically equivalent to the public prose.

## Review Batch A: Public Interface Drift

Twenty-seven families declare entry-module ports or parameters in
`family_spec.json` that cannot be located in the public instruction:

- 088: bundled entry module `ref_step_clk` declares port `CLK`, but its exact
  interface is not stated.
- 303, 304, 310, 314, 315, 318, 319, 322, 323, 324, 326, 328, 334, 335, 336,
  339, 358, 368, 374, 381, 383, 392, 393, 398: `tick` is declared as a public
  parameter but is absent from the instruction.
- 330: `tap_limit` is declared but absent from the instruction.
- 332: `amp_tol` and `phase_tol` are declared but absent from the instruction.

These are real contract ownership decisions, not automatic edit requests.
Review whether each identifier is genuinely public. Then either document it in
the instruction or remove it from the public family spec and rebind evidence.

## Review Batch B: Negative Coverage

The five active negative certifications do not collectively cite every public
property for 21 families:

`322, 323, 324, 326, 328, 334, 335, 336, 337, 339, 350, 370, 374, 379, 381,
383, 384, 387, 392, 393, 398`.

This does not prove that the checker omits those properties. It proves only
that the named five-mutation evidence does not independently demonstrate them.
Review the checker branches first; add or retarget a mutation only where the
property is enforced but lacks negative evidence. Fix the checker or property
contract instead when no enforcement branch exists.

## Recommended Repair Order

1. Resolve 088 separately because it is a multi-artifact interface boundary.
2. Review 303-398 interface drift in small family batches, keeping instruction,
   family spec, gold, task record, and certification binding atomic.
3. Review the 21 negative-coverage families by checker/property mapping; the 15
   families shared with batch A can be handled in the same family PR.
4. Regenerate only affected family audit shards and certifications. Do not edit
   an aggregate or build a release as part of contract repair.

See `CONTRACT_SEMANTIC_AUDIT_SOP.md` for the proof boundary and runbook.
