---
name: evas-validate
description: >-
  Select or run EVAS smoke checks, static regressions, independent semantic
  tests, checker calibration, or simulator-backend comparisons. Also use when
  reanalyzing archived evidence or reporting coverage and pass counts. Do not
  automatically launch a full remote matrix or implement new simulator features.
---

# Validate EVAS

Match the claim to the check. Start with [EVAS README](../../../evas/README.md)
and [experiment ownership](../../../experiments/README.md), then read
`evas/validation/README.md` and the relevant protocol or case cards if present.
The implementation and validation assets may live on development branches.
Confirm which of the entry points below exist in the current checkout; report
missing prerequisites without inventing commands or switching branches.
Resolve the affected [capability IDs](../../../evas/docs/CAPABILITIES.md) and the
claim being checked. Follow [asset ownership](../../../CONTRIBUTING.md#evidence-and-assets)
and the [receipt fields](../../../experiments/README.md#experiment-receipts). Documentation
changes only need relevant link/consistency/diff checks; this skill does not add
a simulator execution requirement to every task.

## Select the necessary checks

Run commands from the repository root. For simulator tests, first rebuild the debug
kernel using the [build command](../../../evas/README.md#构建与运行); tests use that binary.
Apply each row whose behavior/consumers change, and add the smallest regression that
detects the fix independently. This is a starting set, not proof of complete coverage.

| Changed area | Python test modules / check | Additional requirement |
| --- | --- | --- |
| Documentation or skills | `git diff --check`; local links/anchors; skill YAML frontmatter | No simulator run. Check staged diff before commit. |
| Syntax or parameter/instance binding | `test_affine test_contracts` | Accepted and rejected syntax/binding regression; include affected event/operator consumers. |
| Python/Rust IR or JSON transport | All Python tests, command below | Rust tests; version rejection, malformed input and public request/response coverage. |
| Shared assembly or linear algebra | `test_affine test_reuse test_accuracy test_nonlinear test_events` | Rust tests; compare original relation residuals, not just solved values. |
| Newton or polynomial evaluation | `test_nonlinear test_accuracy` | Rust tests; independent root, scaling, failure and tolerance checks. |
| PWL, cross or time/state scheduling | `test_events test_event_accuracy` | Rust commit/rollback tests; affected history contracts under `evas/validation/`. Static replay is insufficient. |
| Interval arithmetic | `test_interval test_event_accuracy` | Rust tests; exact-rational enclosure and uncertain/rejected cases. |
| A branch-specific timed operator | Its test module from that checkout's README, plus `test_events test_event_accuracy` | Rust tests and operator/history contract; do not invent a module absent from the checkout. |
| Checker or grading | Owning experiment's `test_*.py`, command below | Accept/reject calibration, then reanalysis of affected archived results. |
| Frozen validation identity | `python3 -B scripts/verify_validation_version.py` | Hash verification is not simulation validation. |

For a module set from the table, use this command with the listed module arguments:

```sh
PYTHONPATH=evas/src:evas/tests python3 -m unittest -v test_affine test_contracts
```

All-Python command for shared IR/transport changes:

```sh
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
```

For changes to Rust code, also run Rust tests (including private state rollback tests):

```sh
cargo test --locked --manifest-path evas/rust_core/Cargo.toml
```

For the Spectre checkers, the local calibration command is:

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_*.py' -v
```

For other checker directories, use their README command. When a static change can
alter the advertised replay support/results, run the [static replay](../../../evas/README.md#构建与运行)
with a fresh output directory. Backend comparisons use the owning
[Spectre](../../../experiments/dvs2-spectre-validation/README.md) or
[four-backend](../../../experiments/dvs2-four-backend-validation/README.md) protocol;
this table does not require a new remote matrix for every edit.

## Revalidation triggers

| Changed identity | Required action before reusing a conclusion |
| --- | --- |
| Documentation only, including a documentation-only parent update | Check links/syntax and claim consistency; no simulator execution. |
| Implementation or behavior-affecting parent code | Rebuild; run mapped tests and affected independent regressions. Check dependent capabilities at the new base/head. |
| Checker, threshold or result interpretation | Calibrate the checker and reanalyze affected raw evidence under a new analysis identity; preserve the prior verdict. Execute again only if required observations are missing. |
| Model, stimulus, initial conditions or solver settings | Freeze the revised inputs/expected answers and use a new execution identity for the affected configurations. |
| Compiler, flags, dependencies or simulator version | Record the new binary/tool identity; rerun affected correctness checks and any comparison claimed for that identity. |
| Hardware, timing boundary or performance methodology | Remeasure the affected performance claim; old timings describe the old setup. |

Record the changed identities and affected claims in the existing task/PR. If a
claim is unaffected, say why and link the original evidence. Keep any required but
unrun check visible; do not mark the new claim verified. These triggers select work
within authorization and do not grant extra remote compute or publication authority.

Reuse existing scripts and inspect their arguments before running them. Choose
the smallest scope that supports the request. Use remote resources, backends,
and budgets only within current authorization; access credentials alone do not
authorize a new experiment. Reuse authorization already given for this task.

## Preserve independent evidence

Before execution, fix case identities, stimuli, initial conditions, expected
answers, checker revision, tolerances, and the comparison denominator. Derive
answers independently of EVAS. Spectre results are comparison evidence and must
also satisfy the independent contract. Calibrate a changed checker with known
accept/reject controls; do not adjust thresholds to hide a DUT failure.

Use a new output directory and run identity; preserve old manifests and raw
records. Record source/build identity, relevant binaries or images, commands,
requested and effective settings, and input/output/checker hashes as required by
the protocol. Mark evidence as reused, reanalyzed, or newly executed.
Link the original execution when reanalyzing; preserve the earlier verdict and
explain checker corrections. Label artifacts public, repository-contained, or
local-only according to actual availability. A checksum without retrievable data
does not establish public reproducibility. If a shared base changes, rerun only
affected checks and state which historical evidence is still being reused.

Keep unsupported cases and compile, runtime, timeout, numerical, and
infrastructure failures visible. Do not remove them from the fixed denominator
or substitute missing settings with invented equivalents. A case used for
debugging is development evidence, not an untouched holdout.

## Report only the supported conclusion

Derive counts from the actual artifacts. Separate checker calibration, execution
success, numerical agreement, and formal qualification; preserve inconclusive
outcomes. State what ran, what failed or was unsupported, evidence paths, and
what the observations cannot establish. Keep curated summaries according to
[experiment ownership](../../../experiments/README.md), without tracking raw
runs or machine-specific configuration.
Update affected evidence/known-gap cells in the capability register separately
from implementation and review/release status. Backend differences such as
same-time event reads stay visible; do not label them LRM violations without a
supporting contract or silently rewrite the expected answer to match a backend.
