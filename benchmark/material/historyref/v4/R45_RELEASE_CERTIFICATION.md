# R45 Release Certification

R45 is a historical immutable vaBench V4 package at
`release/benchmarkv4-r45/`; the active operator-facing release is now r51.
R45's release audit and all three revision-specific evidence artifacts report
`pass`; `AUDIT_REPORT.json` contains no structural or certification problems.

## Certified Scope

- 1,200 tasks: 400 DUT, 400 testbench, and 400 bugfix forms.
- 7,200 prompt records.
- Direct EVAS runtime protocol: DUT and bugfix tasks expose one task-local
  visible test whose bytes are reused for trusted final replay. Testbench tasks
  expose the bound reference-plus-five-mutation suite without publishing the
  gold testbench candidate.
- Runtime identity: EVAS `0.8.3`, engine `evas2`, backend `evas-rust`; the
  certification policy is `rust_evas2_only` and has no compatibility fallback.

## Evidence

| Artifact | Verified result | SHA-256 |
| --- | --- | --- |
| `evidence/r45/RUST_EVAS2_CERTIFICATION.json` | 400/400 gold pass; 2,000/2,000 mutations killed; 399 insufficient-excitation rejections and 1 not-applicable case; 2,372 trace-axis invariants | `768d03bc818449e034f3658a95d24776c1f31d6877fd6a71589cacec195a3c55` |
| `evidence/r45/STIMULUS_METAMORPHIC.json` | 400/400 affine gold pass; 2,000/2,000 affine mutations killed; 0 infrastructure errors; 383 insufficient-excitation rejections and 17 not-applicable cases | `5c2b5eccd3d8f6de58cbc49efae8a87c5a2f5d0b1f5229d239dee827448f3871` |
| `evidence/r45/PROFILE_PARITY.json` | 1,200/1,200 task forms pass; 0 failures across families 001-400 | `5fb8ca4780f8b2cc4f1bd5be9c1c423dc08a0362d4421263ad003d90d8bf0425` |

Profile parity is a binding and semantic-hash check, not an additional
simulation campaign (`simulation_performed: false`). The gold/mutation and
affine results above are the fresh full-400-family Rust EVAS2 simulation
evidence.

## Release Seal

`release/benchmarkv4-r45/RELEASE_SEAL.json` repeats the three evidence hashes
above, declares `immutable: true`, and records the release status
`r45_immutable_rust_evas2_certified`. Its bound audit reports 1,200 tasks, 400
families, no stale certification inputs, and no problems.

The certification refresh was evidence-only:
`source_certifications_updated` is `false`. It produced R45 evidence without
rewriting the source certification shards or the frozen R44 release. R45
materialization instead binds those source inputs transitively by SHA-256 and
binds the fresh R45 evidence by the hashes listed above.

Immutability means the published R45 tree and its seal are not regenerated in
place after release. Any benchmark content, protocol, evidence, or input-hash
change requires a new release revision and a new seal.
