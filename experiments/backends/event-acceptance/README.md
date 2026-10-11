# Spec B 验收记录

## 当前如何判读

**结构重构已交付；旧的跨后端精确验收仍未全部完成。**
2026-10-11 在近邻 strobe 修复版本重新执行原 E1–E6 × base/fine 共 12 个 EVAS 请求，
冻结 checker 不变，数值与事件检查均为 12/12 P；资格仍为 12/12 I。
[当前运行身份](20261011-current.json)与历史参考分开保存。这次没有重跑 Spec B 的 Spectre，
不能把新 strobe 三例的结论替代这些旧模型。

| 旧记录 | 现在有证据支持的判断 | 剩余工作 |
| --- | --- | --- |
| E1/E2/E4 的基础档 | 原有限数值和事件通过，但导出资格 I | 补合格观测，不能仅改写结论 |
| 其余七个数值 I | 原生导出终点未精确命中科学域终点 | 保留原 I；若新增工程验收须另记时间误差依据 |
| E6 两个数值 F | Spectre 原误差 7.85/4.67 µV，超过原 1 µV；收紧容差后降至 0.334/0.020 µV | 保留原 F；新增参考仍有资格或端点义务 |
| E3/E4 精确边界 | 原记录中计数相差 1，窗外未见差异 | 未纳入 SEF-TIMER-18；不能自动宣布已接受 |
| E5 的 1/3 | binary64 无法精确表示该有理时刻 | 分开精确数学时刻与实际可观察时刻，不用最近点冒充 |

本页只管理 Spec B。原 C1、#79 stop=3、VCO 和源驱动局部历史由
[#96](https://github.com/BucketSran/vaEVAS/issues/96)按原模型继续跟踪；
非阻断提示不解决这些严格差异。下面完整保留原数据、预算和历史检查点。

## 原始对照与判据

P102 baseline `56473944` and candidate `5e38bdf882f41ad17f2a704268907ae0e36600d9` each executed all twelve frozen requests. All twelve requests and responses are byte-identical between revisions. Both pass the independent finite mathematical and event tests; maximum EVAS error across continuous and stored-sample channels is 2.9109159527251904e-11 V. There is no new candidate-only discrepancy. This is preservation evidence, not compatibility acceptance.

The coordinator's actual Spectre reference contains twelve successful executions and 306 verified collected files. Source identities match the original frozen VA inputs. The derived decks add seventeen significant digits to PSF output precision. All twelve actual log and PSF controls match reltol 1e-8, vabstol 1e-10, iabstol 1e-14, traponly, and their declared base/fine maxstep 0.02/0.002 s. Saved waveform rows equal accepted transient steps plus the initial row in every case. These facts support native computed-grid provenance but do not establish rounded-export enclosure bounds or exact rational callback semantics.

The frozen independent checker remains SHA `4a80e6cc91c553ae40d5d635c81ee0d11fd4436bc6fd96d88d1b1a51a13e28ff`; its 1 uV, 200 ns and exact count/order contracts are unchanged.

| Configuration | Spectre independent numeric | Spectre event observation | Qualification | Continuous max error V | Limitation |
| --- | --- | --- | --- | ---: | --- |
| E1-base | P | P | I | 1.8645e-14 | Export qualification remains I |
| E1-fine | I | I | I | 1.914e-14 | Final time token 1.0000000000000004 |
| E2-base | P | P | I | 1.8450e-14 | Export qualification remains I |
| E2-fine | I | I | I | 1.858e-14 | Final time token 1.0000000000000004 |
| E3-base | I | I | I | 1.0000e-8 | Final time token 2.0000000000000013 |
| E3-fine | I | I | I | 1.0000e-8 | Final time token 2.0000000000000013 |
| E4-base | P | P | I | 7.1552e-14 | Export qualification remains I |
| E4-fine | I | I | I | 7.4668e-14 | Final time token 2.0000000000000009 |
| E5-base | I | I | I | 2.0000e-9 | Final time token 2.0000000000000013 |
| E5-fine | I | I | I | 2.0000e-9 | Final time token 2.0000000000000013 |
| E6-base | F | P | F | 7.85259115986e-6 | Exceeds original 1 uV |
| E6-fine | F | I | F | 4.67175138126e-6 | Exceeds 1 uV; final time token 2.0000000000000009 |

Ten configurations' saved-record errors are below 1 uV; strict complete-domain numeric verdicts are P for three, I for seven and F for two. Event verdicts are P for four and I for eight. No failed or incomplete configuration is removed from the denominator.

E6's numerical discrepancy already exceeds 1 uV before the edit at 0.25 s. Its largest drift occurs at 0.49999998000000001 s, before the mode-change timer. The timer brackets are approximately [0.24999998, 0.25] and [0.49999998, 0.5], each 20 ns wide, proving finite observed deadline behavior within the original 200 ns budget. This is an actual baseline/reference numerical discrepancy, retained in the original comparison. Separate convergence diagnostics keep the source and external 1 µV budget unchanged: tightening Spectre to reltol=1e-10, vabstol=1e-12 and iabstol=1e-16 reduces the error to 0.334291 µV at maxstep=0.002 s and 0.019991 µV at maxstep=0.0001 s. This supports a reference numerical-convergence explanation without establishing Spectre’s internal algorithm. The strict-0.002 finite numerical/event checks pass; the strict-0.0001 record lacks the exact endpoint. Both retain qualification I and neither replaces an original F.

At exact rational time 0.5 in E3 and 0.75 in E4, Spectre count is 1 and EVAS count is 0, in both profiles and both EVAS revisions. These exact-boundary differences are retained separately. There are no count differences outside the event uncertainty windows among the matched finite pairs. E5's exact rational 1/3 is not representable in binary64; no nearest or rounded point is assigned exact-center status.

`finite_pairs` in the actual summary uses the same reference for both EVAS revisions. Rows are matched by explicit numeric binary64 time projection. The comparison subtracts the exact Fraction formula difference between the retained decimal time coordinate and the EVAS binary64 coordinate. It records both raw differences and correction magnitudes. Ten such continuous pair checks pass and both E6 pair checks fail for each EVAS revision. This numeric residual comparison does not qualify the exported time origin or prove exact simultaneous observation.

The original settings reader rejected Spectre's `ms`, `pV`, and `fA` display units. The failed first analysis remains in `spectre-reference-actual/`. `settings_readback_si.py` adds only those SI units, with twelve positive/reject calibration controls in `SETTINGS_SI_CALIBRATION.json`; the rerun remains separate in `spectre-reference-actual-si/`. The original acceptance checker is unchanged. Raw reference data, original failures and prior outputs remain retained. No further remote call was performed by this worker.

The frozen checker’s `failures` array records diagnostics and coverage problems; it does not list every numerical threshold violation. Read its numeric status and maximum errors together. The public receipt adds `numeric_failure_reasons` derived from the unchanged 1 µV threshold, preserving all original fields.

Compact identities and outcomes are in [receipt.json](receipt.json). Frozen shared models, input plans and the unchanged checker are [repository-contained](../../../evas/validation/event_acceptance/README.md). Complete raw outputs and execution logs remain local-only under `current/runs/event-closure-20261008/`; checksums alone do not establish public reproducibility.

## Single-batch preparation checkpoint

The small refactor from `bb89c830` to `cacc8550` gives the first event and each
subsequent microevent one `prepare_changed_batch` entry. It preserves static
calendar truncation, causal-loop budgets, phase queries and atomic publication.
It changes no root policy, numerical budget, supported model or checker.

[The checkpoint receipt](batch-refactor.json) binds the two binaries, tests and
frozen reference reuse. The selected 251 Python tests retain their original
assertions. Their 706 captured model requests compare return codes and complete
stdout/stderr text without numerical tolerances, including rejected requests.
This is a finite same-host numerical preservation check, not proof for every
possible input or subprocess entry point. Diagnostic timings are not compared.
Existing Rust production-entry tests retain same-Controller rollback/retry
coverage; final-stage helper tests remain a separate obligation.

To repeat the response check, build the baseline and candidate separately with
the same Rust toolchain/profile, preserve the baseline binary, then run from the
candidate checkout:

```sh
python3 -B experiments/backends/event-acceptance/check_batch_refactor.py \
  /path/to/baseline/evas-kernel evas/rust_core/target/debug/evas-kernel \
  runs/batch-refactor-recheck --expected-requests 706
```

The output directory must be new. The 706 count is for the pinned test revision.
The verifier isolates diagnostic files and fails on a request-count mismatch,
response difference or timeout. All existing test assertions still run.

Seven frozen engineering models and twelve Spec B requests were also executed
on both binaries. The engineering responses were compared with the same actual
Spectre 21.1.0.509.isr12 records in both EVAS runs. All fourteen base/tight paired
analyses are unchanged. Exact time-key pairing still has missing observations;
M1-base still fails its original independent check. C1, #79 and VCO strict
differences and observation-qualification limits remain open. This checkpoint
does not constitute new Spectre execution or broader compatibility acceptance.

Raw requests, responses, failed verifier attempts and independent reviews are
local-only in the visible `worktrees/spectre-event-alignment/runs/event-candidate-step-20261009/`
entry. The repository retains the comparator and compact receipt, not a public
Spectre waveform archive. The user accepted this stage; the following section records the wider refactor.


## Whole event-cluster transaction checkpoint

The next structural checkpoint is runtime commit `7f091d3d`, based on the accepted
small checkpoint `521a4a57`. Its [receipt](cluster-refactor.json) records identities
and results. It changes ownership, with no new event or numerical policy.

```text
accept_changed_events
  PreparedEvents::prepare, immutable Controller and calendar
    prepare_changed_batch for each connected event batch
    check microevent budgets and prepare physical-phase outputs
    return frame, records, outputs and typed calendar update
  PreparedEvents::publish, consume the completed result
    publish frame, cursor, records, outputs and calendar without fallible work
```

Static calendars keep their storage and advance their cursor. Held/history
calendars are replaced and restart at cursor zero. The existing batch arithmetic,
root certificates, history algorithms, budget checks and error order are retained.
An added production-entrance regression samples a held timer from `.1*.3` and
requests an uncertifiable `.03` output. It verifies that two failed attempts keep
previously stored outputs and accepted state intact, then retries the same
Controller after removing that query. The clean run and retry agree. This test
passes on the original implementation too; it protects existing rollback behavior.

The candidate passes 218 Rust tests with one ignored. The fixed event test set
passes 251 tests; all 706 baseline/candidate responses agree exactly, including
140 rejections. The two captured diagnostic sidecars also match in a separate
post-analysis; only `stages.*.nanos` is excluded. Records, their order, counters
and errors are compared. Other requests did not enable sidecar capture.
Twelve frozen Spec B responses and seven engineering-model
responses are also byte-identical. The same fourteen actual Spectre base/tight
comparisons retain their original results. The original archive's 371 files and
fourteen PSF traces were rebound and checked. No new remote Spectre run was made;
models, stimuli, settings, checker and reference data are unchanged.

These finite preservation checks do not resolve C1, #79, VCO, M1 or incomplete
observation qualification. PR117 was merged into main `c2ca32ee` on 2026-10-09 after user approval.
The remaining strict Spec B reference obligations continue in [Issue96](https://github.com/BucketSran/vaEVAS/issues/96);
integration does not upgrade the original F/I. Raw
runs, the scope and complete independent reports remain local-only under the
visible `worktrees/spectre-event-alignment/runs/event-cluster-transaction-20261009/`
entry. The diagnostic inventory was regenerated because code movement changed
its source-function references; the preceding checkpoint's CI failed that freshness check.
