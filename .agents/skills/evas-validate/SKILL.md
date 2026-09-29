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
claim being checked. Follow [asset identity and retention](../../../AGENTS.md#asset-identity-and-retention)
and the [receipt fields](../../../experiments/README.md#实验资产与收据). Documentation
changes only need relevant link/consistency/diff checks; this skill does not add
a simulator execution requirement to every task.

## Select the necessary checks

| Requested evidence | Entry point and limit |
| --- | --- |
| Documentation or skill edits | Link, syntax, and diff checks; no simulator run needed. |
| Parser, binding, IR, or static solver changes | Affected tests and applicable static regression from the EVAS README. Static samples do not advance physical time. |
| Dynamic or event semantics | Applicable case cards and `evas/validation/METHOD_QUALIFICATION.md`; static replay is insufficient. |
| Frozen artifact identity | `scripts/verify_validation_version.py`; matching hashes do not certify simulation correctness. |
| Spectre or multiple backends | README and protocol in `experiments/dvs2-spectre-validation/` or `experiments/dvs2-four-backend-validation/`. |
| Reanalysis of existing event evidence | `experiments/dvs2-history-validation/README.md`; distinguish reanalysis from a new circuit execution. |

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
