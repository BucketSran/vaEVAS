# vaBench Release Package v1

This directory is the clean paper-facing benchmark package for the 86-entry L1/L2
vaBench release target: 73 core circuit entries plus 13 auxiliary
measurement/stimulus support entries. The current scored denominator is the
certified 73-entry / 265-form core circuit slice; the 13-entry / 35-form support
suite is certified and reported separately but excluded from the core score.
Certification, score denominators, speed/debug measurements, and model baselines
are reported as separate surfaces so paper claims cannot mix their evidence.

The current 300-task benchmark management surface is
`vabench-300-expansion/`. It uses form-level tasks as benchmark tasks: 271
inherited certified v1 forms plus 29 fresh-certified v1.1 forms. All 300 forms
are simulator-certified assets after the v1.1 score-admission audit; the scored
model-evaluation denominator is the 265 core forms after support-suite
exclusions. Use `vabench-300-expansion/VABENCH_300_MANIFEST.json` for 300-task
asset-management statistics and `reports/score_denominator_manifest.json` for
entry/form score-boundary claims.

This package is the current vaBench release target. It can be cited only through
the current reports in `reports/`. A row
is not part of the scored benchmark until its score-denominator report marks it
as counted, and no pending or blocked simulator run is certification evidence.

## Layout

- `tasks/`: release L1/L2 task directories after materialization; only
  `track=core` rows marked counted by the score denominator enter the main
  circuit score.
- `conformance/`: non-scored L0 EVAS/Spectre diagnostic cases.
- `evidence/`: certification bundles and simulator logs referenced by tasks.
- `reports/`: coverage, parity, speed/debug, baseline, completion, artifact
  index, claim gate, and paper table summaries.
- `vabench-300-expansion/`: 300 form-level task management surface with
  partial-pass negative manifests and 29 fresh-certified v1.1 task assets.
- `rerun_staging/`: staged runnable bundles used for EVAS/Spectre dual reruns.
- `vabench-300-expansion/`: v1.1 expansion assets for the 300 form-level task
  plan. This includes the existing 271 certified v1 tasks, 29 proposed v1.1
  tasks, and 5 partial-pass near-miss negatives per task. The proposed tasks
  remain pending certification until static, EVAS, and Spectre evidence exists.

Rows are planned in `../docs/VABENCH_RELEASE_TRACKER.csv`. A row is not part of
the scored benchmark until its task assets and EVAS/Spectre evidence are
complete.

Current seed rows may contain `forms/<form>/` directories copied from reviewed
source tasks. These copied assets are release-materialized and enter the score
only when `reports/score_denominator_manifest.json` marks them counted.

L0 conformance assets are synchronized from `../conformance/evas-spectre/`.
They are simulator diagnostics and do not count toward L1/L2 benchmark coverage,
model capability, bugfix claims, or broad parity denominators.

## Current Claim Boundary

The current local package is source-complete, statically certified, and
EVAS/Spectre dual-certified for all 300 release forms. The main scored benchmark
denominator is the 73 core entries / 265 core forms marked counted in
`reports/score_denominator_manifest.json`; the 13 support entries / 35 support
forms are certified but excluded from the core circuit score. EVAS speed/debug
measurements and model baselines remain separate gated claims.

Use these reports as the source of truth:

- `reports/claim_gate.json`: allowed and blocked paper claims with safe wording.
- `reports/paper_tables.json`: CSV/Markdown table exports for paper drafting.
- `reports/completion_audit.json`: requirement-by-requirement completion gate.
- `reports/artifact_index.json`: traceability index for artifacts and commands.
- `reports/score_denominator_manifest.json`: only source of truth for scored
  entries/forms.
- `reports/external_blockers.json`: external bridge/rerun/import blocker chain.
- `reports/finish_readiness.json`: preflight gate for safely starting,
  importing, and finishing the fresh EVAS/Spectre release rerun.
- `MANIFEST.json`: package-level machine-readable index for entries, forms,
  assets, evidence links, certification status, and score inclusion.
- `EVALUATOR.json`: machine-readable evaluator contract for task selection,
  backend roles, result/evidence schemas, score gates, and baseline lanes.

Task-local `checks.yaml` parity blocks are checker-contract metadata, not the
certification source of truth. If a task-local parity note disagrees with
`reports/dual_certification.json` or `reports/score_denominator_manifest.json`,
use the report files for paper claims and treat the task-local note as stale
metadata to refresh.

Current safe wording is intentionally narrow:

- The package defines an 86-entry L1/L2 coverage target split into core circuit
  coverage and auxiliary measurement/stimulus support coverage.
- The main scored denominator is the certified 73-entry / 265-form core circuit
  slice; the certified 13-entry / 35-form support suite is reported separately.
- All materialized release forms pass static/integrity checks.
- Current dual reports certify all 300 release forms with zero EVAS PASS /
  Spectre FAIL mismatches.
- L0 conformance is separate from the benchmark denominator.

Do not claim EVAS speedup, debug advantage, or model baselines until the
corresponding claim gate is allowed.

## L2 Background Conditions

Level-2 core rows count as composed behavioral circuit flows only when the
public prompt, gold behavior, and checker expose more than a final scalar output:
they must show intermediate state, multi-stage behavior, measurement state, or
closed-loop response. L2 rows remain voltage-domain/event-driven behavioral
Verilog-A tasks. They do not claim transistor-level implementation, layout,
current-domain regulation, RF S-parameters, AC/noise analysis, PSRR,
jitter/noise performance, or full silicon characterization unless those
properties are explicitly modeled and checked.

Level-2 support rows are certified release assets for measurement or stimulus
infrastructure, but they are excluded from the core circuit score and must be
reported separately from analog/mixed-signal circuit-function coverage.

## Reproducible Commands

Regenerate the local release package, reports, schema validation, checksums, and
tests:

```bash
python3 runners/run_vabench_release_longrun.py
```

After the external Virtuoso bridge is reachable, finish the fresh dual rerun,
import only complete results, and refresh downstream reports:

```bash
python3 runners/finish_vabench_release_after_bridge.py
```

The direct rerun command is:

```bash
./scripts/run_with_bridge.sh python3 runners/run_vabench_release_dual_rerun.py \
  --output-root results/vabench-release-v1-dual-rerun \
  --timeout-s 180
```

Blocked or dry-run summaries must not be imported as certification evidence.
Use `reports/bridge_profile_diagnostics.json` and
`reports/external_blockers.json` to decide whether the bridge is ready. Use
`reports/finish_readiness.json` before importing any fresh rerun summary.
