# r52 release certification

This promotion binds the benchmark release to the Rust EVAS2 runtime at
EVAS 0.8.5 and makes the Testbench public/private boundary explicit.

## Public asset boundary

For every Testbench task, both direct one-shot and agentic runs receive the
same public task view and the same correct reference DUT. The public runtime
does not generate, copy, mount, name, or hash any `mutation_01`--`mutation_05`
asset. Agentic EVAS feedback is reference-DUT-only. The evaluator keeps the
reference DUT plus five hidden faults in `trusted_replay_fixtures`; the final
private Spectre judge uses that private suite for scoring.

## Promotion evidence

The revision-scoped evidence is stored under `evidence/r52/`:

- `RUST_EVAS2_CERTIFICATION.json`: 400/400 gold, 2,000/2,000 mutation kills,
  and 2,400/2,400 timing-invariant cases under EVAS 0.8.5;
- `STIMULUS_METAMORPHIC.json`: 400/400 Testbench families pass affine
  stimulus checks and all 2,000 hidden faults remain killed;
- `PROFILE_PARITY.json`: all 1,200 task forms pass profile parity.

The canonical source contains fresh EVAS 0.8.5 recertification for the 15
families whose public contracts changed. `release/benchmarkv4-r52/` contains
the 400-family, 1,200-task materialization, runtime-ingestion evidence,
release audit, and immutable seal.

## Reproduction

```bash
EVAS_ENGINE=evas2 \
VAEVAS_DEFAULT_EVAS_ENGINE=evas2 \
VAEVAS_EVAS_REPO=/path/to/EVAS \
python3 benchmark-vabench-release-v4/operations/tri_form_derivation_prep/audit_tri_form_release.py \
  --release-revision r52 \
  --release benchmark-vabench-release-v4/release/benchmarkv4-r52 \
  --output /tmp/r52-audit.json
```

The audit must report empty `problems` and `certification_problems`, and the
release seal must declare `r52_immutable_rust_evas2_certified`.
