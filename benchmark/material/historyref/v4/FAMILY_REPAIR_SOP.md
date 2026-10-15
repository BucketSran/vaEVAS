# V4 Family Repair SOP

## Scope

The canonical score denominator is maintained as one registry shard per family:

```text
provenance/dut-base-v3-exact-five-hash-bound-v2/
  score_denominator_registry/
    _meta.json
    001.json
    ...
    400.json
```

`_meta.json` contains only stable release-wide metadata. Each numbered file owns
one canonical family and its DUT, testbench, bugfix, mutation, and hash bindings.
There is no aggregate denominator file or aggregate-generation workflow.

## Repair PR

1. Rebase the branch onto the latest `origin/main` before making evidence claims.
2. Edit only the selected canonical family directories, their checker code, and
   the matching `score_denominator_registry/<family>.json` shards.
3. Regenerate harness/profile data with `migrate_v4_profile_parity.py`. The tool
   refreshes only the selected family shards.
4. Do not edit or commit `release/benchmarkv4`, `AUDIT_REPORT.json`,
   `MANIFEST.json` or `RELEASE_SEAL.json` in a family repair PR.
5. Run the source repair gate for the exact family range:

   ```bash
   python3 benchmark-vabench-release-v4/scripts/validate_v4_repair_gate.py \
     --family-range 001-010 --output /tmp/v4-repair-gate.json
   ```

6. Validate registry completeness and determinism:

   ```bash
   python3 benchmark-vabench-release-v4/operations/tri_form_derivation_prep/score_denominator_registry.py \
     --source benchmark-vabench-release-v4/provenance/dut-base-v3-exact-five-hash-bound-v2
   ```

7. Materialize a temporary release, then run reference, five-mutation, affine,
   and insufficient-excitation checks with pinned Rust EVAS2 0.8.2. Every case
   must bind `output/evas.log` to `Version 0.8.2` and
   `evas_engine = evas-rust`. Spectre is unavailable and is not a gate.
8. Submit compact, repository-relative evidence. Do not commit raw simulator
   output, machine-local paths, or claims not bound to runtime logs.

## Integration Release

After family PRs merge, one release-maintainer job runs on the latest `main`:

1. Validate all 400 registry shards.
2. Materialize the complete 1,200-task release from the registry.
3. Run the release audit and rebuild `MANIFEST.json`, `AUDIT_REPORT.json`, and
   `RELEASE_SEAL.json` once.
4. Commit generated release artifacts in a dedicated integration PR.

Family repair PRs must never carry global release rebuilds. This keeps family
ownership independent and prevents unrelated batches from conflicting.

## No Aggregate Registry

Do not generate or maintain a repository-wide denominator table. The metadata
file and the 400 family shards are the complete source of truth. Consumers must
read the shards directly. `TASK_INDEX.json` and `MANIFEST.json` are generated
immutable release artifacts, not maintenance registries.
