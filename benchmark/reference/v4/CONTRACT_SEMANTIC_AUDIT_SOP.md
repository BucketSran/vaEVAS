# V4 Contract Semantic Audit SOP

## Purpose

This audit checks each canonical DUT family as an independent shard. It detects
broken bindings among the public instruction, public contract, family
properties, harness and profiles, checker registration, gold solution, and
recorded certification. It does not maintain a hand-edited 400-family table.

## Mechanical proof boundary

The tool can prove that the checked repository revision has consistent:

- family and task identifiers;
- target artifacts across the family spec, public contract, harness, task
  record, instruction, and gold bundle;
- property identifiers across the family spec, harness, and feedback/score
  profiles;
- required signals across properties, public observables, checker trace
  declarations, and saved traces;
- required-trace entries use physical scalar or indexed signal syntax rather
  than literals, thresholds, checker-derived values, or diagnostic labels;
- feedback/score stimulus semantics after profile resolution;
- checker IDs and loadable V4 registry entries;
- task-record hashes and gold-certification input hashes;
- active negative diagnostics that cite only declared public properties.

Lexical presence of an interface identifier in the instruction is evidence of
traceability, not proof that the prose defines its direction, units, range, or
behavior correctly. A missing identifier is therefore a `review` finding.
Likewise, an active five-mutation set that does not cite every property is a
coverage review, not proof that the checker omits that property.

The tool cannot prove:

- equivalence between natural-language requirements and checker mathematics,
  thresholds, windows, or event timing;
- completeness of stimulus or mutations;
- that every valid implementation is accepted or every invalid one rejected;
- absence of checker overfitting to the gold or current deck;
- independent simulator parity. A bound passing certification proves only the
  evaluator and evidence named by that certification.

These claims require human property-by-property review and, where relevant,
independent EVAS/Spectre evidence.

## Runbook

Create disposable shards outside the repository:

```bash
python3 benchmark-vabench-release-v4/scripts/audit_v4_contract_semantics.py \
  audit --shard-dir /tmp/v4-contract-audit-shards
```

Audit a repair batch without touching other shards:

```bash
python3 benchmark-vabench-release-v4/scripts/audit_v4_contract_semantics.py \
  audit --family-range 301-310 --shard-dir /tmp/v4-contract-audit-shards
```

Generate a disposable aggregate only when needed:

```bash
python3 benchmark-vabench-release-v4/scripts/audit_v4_contract_semantics.py \
  aggregate --shard-dir /tmp/v4-contract-audit-shards \
  --output /tmp/v4-contract-audit-summary.json
```

The aggregate command exits nonzero only for mechanical `error` findings.
`review` findings require inspection but do not claim a proven defect.

## Human review

For each reported family:

1. Read `public/task/instruction.md` and `evaluator/family_spec.json` together.
2. Map every property to the checker branch, thresholds, sampling window, and
   diagnostic property ID that enforce it.
3. Confirm the public stimulus excites the property without encoding a single
   implementation strategy.
4. Inspect the gold only after deriving expected behavior from the public
   contract; passing gold is a satisfiability witness, not the specification.
5. Classify the finding as instruction, family-spec, harness, checker, gold, or
   evidence debt. Repair families in focused batches and regenerate only their
   shards.

Do not edit a generated aggregate. Delete and regenerate it from shards.
