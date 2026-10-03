# r44 Release Certification

`r44` replaces the mutable `r43` campaign image as the final benchmarkv4
release. Release certification uses the Rust EVAS2 backend as the sole
executable evaluator. Spectre evidence is neither required nor inferred.

## Certification Gate

The canonical source contains 400 families and exactly five scored mutations
per family. A release candidate passes only when a fresh run proves all of the
following against the current source hashes:

The family-sharded `score_denominator_registry/NNN.json` files are the score
authority. Aggregate denominator and active-suite indexes are not maintained.

- 400/400 gold candidates compile and pass their private checker;
- 2000/2000 active mutations compile and fail the checker behaviorally;
- testbench gold and all five mutations retain their classification under
  `t' = 1.37 * t + 2 ns` for 398 families; families 361 and 362 use the affine
  translation `t' = t + 2 ns` because their DUTs contain fixed physical
  delay/frequency constants;
- insufficient excitation is explicitly rejected for 399 canonical families;
  the static encoder family 147 is marked not applicable;
- feedback and score profiles preserve the canonical harness semantics in all
  1200 materialized task forms;
- source certificates, task records, mutation bundle hashes, the family-sharded
  denominator registry, the materialized audit, and the release seal agree.

The 51 provenance-only mutations are retained for history but are outside the
2000-case score denominator and are not part of the r44 executable gate.

## Reproduction

Run executable certification with the Rust backend explicitly selected:

```bash
export VAEVAS_EVAS_REPO=/path/to/EVAS
export VAEVAS_EVAS_PERSISTENT_WORKER=0
export EVAS_ENGINE=evas2
export VAEVAS_DEFAULT_EVAS_ENGINE=evas2

python3 benchmark-vabench-release-v4/scripts/validate_v4_checker_batch.py \
  --family-range 001-400 \
  --output /tmp/r44-checker-batch.json \
  --work-root /tmp/r44-checker-work \
  --workers 8 --timeout-s 120 --force

python3 benchmark-vabench-release-v4/operations/tri_form_derivation_prep/refresh_rust_evas2_certifications.py \
  --source benchmark-vabench-release-v4/provenance/dut-base-v3-exact-five-hash-bound-v2 \
  --report /tmp/r44-checker-batch.json \
  --output benchmark-vabench-release-v4/evidence/r44/RUST_EVAS2_CERTIFICATION.json

python3 benchmark-vabench-release-v4/operations/tri_form_derivation_prep/audit_tri_form_release.py \
  --release-revision r44 \
  --output /tmp/r44-release-audit.json

python3 benchmark-vabench-release-v4/operations/tri_form_derivation_prep/run_v4_profile_parity_smoke.py \
  --family-range 001-400 \
  --output benchmark-vabench-release-v4/evidence/r44/PROFILE_PARITY.json
```

The final gate is `AUDIT_REPORT.json` with both `problems` and
`certification_problems` empty, plus `RELEASE_SEAL.json` with
`release_status=r44_immutable_rust_evas2_certified` and `immutable=true`.
