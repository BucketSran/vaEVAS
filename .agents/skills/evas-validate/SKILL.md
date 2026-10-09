---
name: evas-validate
description: >-
  Select or run EVAS smoke checks, static regressions, independent semantic
  tests, checker calibration, or simulator-backend comparisons. Also use when
  reanalyzing archived evidence or reporting coverage and pass counts. Do not
  automatically launch a full remote matrix, implement simulator features, or
  apply EVAS capability requirements to benchmark-only work.
---

# Validate EVAS

Match the claim to the check. For simulator behavior, use the relevant sections
of [EVAS README](../../../evas/README.md) and [validation guidance](../../../evas/validation/README.md).
For archived evidence or backend comparisons, use [experiment ownership](../../../experiments/README.md)
and the owning protocol or case cards.
For test independence and deduplication, use the
[behavior-first test rules](../../../docs/contributing/validation.md#behavior-first-tests).
Choose tests by the faults they can detect, not test counts; do not remove distinct
kernel/rollback obligations or rewrite frozen evidence during cleanup.
The implementation and validation assets may live on development branches.
Confirm which of the entry points below exist in the current checkout; report
missing prerequisites without inventing commands or switching branches.
Resolve the claim being checked and, for EVAS behavior or support/evidence
changes, the affected [capability IDs](../../../evas/docs/development/capability-evidence.md).
Follow [asset ownership](../../../docs/contributing/evidence.md#evidence-and-assets); use the
[receipt fields](../../../docs/contributing/evidence.md#execution-receipts) for experiment evidence.
Documentation changes only need relevant link/consistency/diff checks.

## Match the requested operation

Use the request and existing authorization to choose the operation; a known mode
does not require another confirmation.

- **Select checks:** inspect contracts and affected consumers, then return the
  proposed commands, prerequisites and reasons. Stop with that plan; selection
  alone does not authorize building or running the checks.
- **Execute checks:** run the selected checks within the agreed resources and
  report observed outcomes, identities and limits.
- **Reanalyze evidence:** inspect the archived inputs, outputs and checker identity
  before deciding what can be reused. Recalibrate a changed checker and record the
  new analysis identity. Execute again only when needed observations are missing
  and the run is within the task's resource authorization; otherwise report the gap.

## Select the necessary checks

Select rows by changed behavior and affected consumers, not just the edited file.
For broad shared changes, select the listed module sets; a narrow fix may use
focused test classes/methods with its scope stated. Behavioral changes follow
the [behavior-first test order](../../../docs/contributing/validation.md#behavior-first-tests);
this mapping selects coverage, not when to write the failing case. It is a
starting set, not proof of complete coverage or a requirement to run every row.

When executing, run commands from the repository root. Before simulator tests,
rebuild the debug kernel using the [build command](../../../evas/README.md#构建与运行);
those tests use that binary. Checks that do not invoke the kernel need no build.

| Changed area | Python test modules / check | Additional requirement |
| --- | --- | --- |
| Documentation or skills | `git diff --check`; local links/anchors; skill YAML frontmatter | No simulator run. Check staged diff before commit. |
| Syntax or parameter/instance binding | `test_affine test_contracts` | Accepted and rejected syntax/binding regression; include affected event/operator consumers. |
| Python/Rust IR or JSON transport | All Python tests, command below | Rust tests; version rejection, malformed input and public request/response coverage. |
| Shared assembly or voltage relations | `test_affine test_reuse test_accuracy test_nonlinear test_events` | Rust tests; original relation residuals and affected continuous/settlement consumers. |
| Dense/sparse dispatch, factorization or reuse | `test_affine test_reuse test_accuracy test_sparse test_sparse_transient` | Rust tests; singular/scaled systems, changing sparsity and original relations. |
| Newton or point polynomial evaluation | `test_nonlinear test_accuracy test_precision_chain` | Rust tests; independent roots, scaling, failure and forward voltage error. |
| Continuous relations, feedback or derivative lowering | `test_continuous_dynamics test_dynamic_closure` | Rust tests; joint states, initialization, derivative/impulse boundaries and affected event/reset consumers. |
| Implicit DAE continuation | `test_implicit_dynamics` | Initial root, algebraic branch/singularity, history accuracy and query-grid invariance. |
| Nonlinear integral/filter composition | `test_dynamic_closure test_mixed_dynamics` | Preserve every live state, DC/direct terms and precision through event restarts. |
| History ownership, initialization or commit/rollback | `test_lifecycle_closure test_semantic_invariants` | Rust lifecycle/rollback tests; same-engine rejected-trial retry and unaffected state preservation. |
| PWL or cross localization | `test_events test_event_accuracy` | Add `test_dynamic_cross` for internal/operator trajectories and affected sampling consumers. |
| Scheduling or prediction horizons | `test_timer test_event_horizons` | Known events must bound propagation; adding observations must not change physical history. |
| Same-time settlement, event conditions, writers or OR | `test_settlement`; affected `test_event_conditions test_event_writers test_event_or` | Program order, selected writers, original relations and rejected ambiguous solutions. |
| Event-window sampling or reset observation | `test_event_window_sampling test_lifecycle_closure` | Certify all possible root times and retain sample uncertainty in future history. |
| Error propagation or voltage acceptance | `test_precision_chain`; affected operator accuracy tests | Check history/time error after amplification, not only equation residual. |
| Interval arithmetic | `test_interval test_event_accuracy`; affected dynamic/sampling consumers | Rust tests; exact-rational enclosure, non-finite inputs and uncertain/rejected cases. |
| An individual timed operator | Its semantic/accuracy modules in the checkout; affected `test_timed_composition` | Use its handbook/validation contract; select shared-path tests below when it changes history, feedback or events. |
| EVAS checker or grading | Owning validation/experiment's `test_*.py`, command below | Accept/reject calibration, then reanalysis of affected archived results. Benchmark grading follows its own task contract. |
| Frozen validation identity | `python3 -B scripts/verify_validation_version.py` | Hash verification is not simulation validation. |

For GUARDS tags, capability/evidence navigation or the traceability generator,
run `python3 -B scripts/traceability.py --check`. Regenerate the matrix after
reviewing the changed declarations. Generator behavior changes also require
`python3 -B -m unittest discover -s scripts/tests -v`; this checks the maintenance
tool, not EVAS semantics or qualification. Preserve frozen identities when moving files.

For a Python module set from the table:

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
python3 -B -m unittest discover -s experiments/backends/dvs2-spectre-validation -p 'test_*.py' -v
```

For other checker directories, use their README command. When a static change can
alter the advertised replay support/results, run the [static replay](../../../evas/README.md#构建与运行)
with a fresh output directory. Backend comparisons use the owning
[Spectre](../../../experiments/backends/dvs2-spectre-validation/README.md) or
[four-backend](../../../experiments/backends/dvs2-four-backend-validation/README.md) protocol;
this table does not require a new remote matrix for every edit.

## Composition triggers

Trace changed data through its consumers. Select only applicable obligations:

- State construction or initialization: check call-site/instance isolation,
  nonzero initial values and preservation of unrelated dynamic states.
- Continuous relations or nonlinear evaluation: check the affected integral,
  derivative, filter or DAE feedback path with an independent answer.
- Scheduling, settlement or reset: check the event boundary, preserved history,
  post-event closure and future propagation together.
- Sampling or error bounds: check uncertainty over the root window, its storage
  in sampled state and later voltage amplification. Include a justified rejection.
- Query, interpolation or caching: check extra output samples and equivalent
  encodings against the same physical history.
- Candidate mutation or acceptance: inspect and run the relevant Rust lifecycle
  checks for rejected-trial retry in the same engine. Restarting a process does
  not establish rollback correctness.

State which consumers and obligations selected the checks in the task/PR report;
no separate checklist or new experiment is required. Keep unsupported combinations
explicit rather than treating an operator-only pass as joint support.

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
or substitute missing settings with invented equivalents. A reference pass does
not complete negative-control calibration. If the contract requires a scored
waveform, an engine diagnostic without that waveform leaves the check incomplete;
an expected rejection needs the contract's specified rejection evidence. A case used for
debugging is development evidence, not an untouched holdout.
Record reusable modeling or compatibility discoveries in the
[candidate register](../../../benchmark/CANDIDATES.md), linking the original failure
and distinguishing model intent, language semantics and backend observations.

## Report only the supported conclusion

Derive counts from the actual artifacts. Separate checker calibration, execution
success, numerical agreement, and formal qualification; preserve inconclusive
outcomes. State what ran, what failed or was unsupported, evidence paths, and
what the observations cannot establish. Keep curated summaries according to
[experiment ownership](../../../experiments/README.md), without tracking raw
runs or machine-specific configuration.
Update affected entries in the [evidence index](../../../evas/docs/development/capability-evidence.md)
and support conclusions in the [capability overview](../../../evas/docs/CAPABILITIES.md)
separately from review/release status. Backend differences such as
same-time event reads stay visible; do not label them LRM violations without a
supporting contract or silently rewrite the expected answer to match a backend.
