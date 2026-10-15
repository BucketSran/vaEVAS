# r53 release qualification

r53 preserves the current 400-family, 1,200-task benchmark content and binds
the active runtime to `evas-sim==0.8.7`. It also binds the release manifest to
the repository's single authoritative experiment policy, which gives every
agent episode 1,800 seconds and scores the latest complete declared submission
when that limit is reached.

## Certification scope

The canonical gold and exact-five negative certifications are reused by their
transitive source hashes. r53 does not claim a fresh local full-400 simulation:
no task, checker, denominator, gold, or mutation content changed solely for the
runtime promotion.

The new runtime is qualified at the deployment boundary:

1. build and verify the EVAS 0.8.7 wheel;
2. build and push an immutable shared image;
3. record the Harbor digest;
4. run the pushed-image golden smoke;
5. warm the image in Vela;
6. complete a one-task Vela smoke with submission persistence and private
   final evaluation enabled.

Spectre is not part of the r53 gate and is not run.

## Release artifacts

`release/benchmarkv4-r53/` contains the 400-family, 1,200-task materialization,
runtime-ingestion evidence, structural audit, and immutable release seal. The
seal status is `r53_immutable_source_certification_reused`; its
`runtime_requirements` object binds EVAS 0.8.7 and the exact
`EXPERIMENT_POLICY.json` hash.
