# PR6 E1（CI 40584762318）原始证据接收与十角色 bundle 组合

执行成功、结构完整、预期拒绝、语义资格分开表述。本批只做数据核验与组合：没有运行任何测试 body、科学回归、compiler、kernel、DUT、backend、SSH、Spectre 或 Harbor，没有 fetch、没有写真实 Git、没有写授权/baseline/review，也没有新增科学阈值。

| 维度 | 结果 |
|---|---|
| 执行成功 | 是：raw_verify 0 个发现、0 个未闭合项；prepare_bundle 通过；verify 通过 |
| 结构完整 | 是：十角色齐全；verify.py 43 项检查全部 ok |
| 预期拒绝 | 已复现：可信 gate 对 E1 报告给出 `expected exactly one matching trusted baseline context`（merge_allowed=false）；7 项篡改探针与 6 项输出路径拒绝探针均按预期被拒 |
| 语义资格 | false；raw_successful=false；merge_allowed=false；科学资格 false；映射仅为 DRAFT，独立精确 context 验收 PENDING |

## 来源事实

### 身份与终态

- PR6 <https://github.com/BucketSran/vaEVAS/pull/269>：head `fa5556de20de4fecbf9db4e3630cd5d6754b07c2`（tree `470ad588ddeb848b7c05d3f23656a96f085f8bfd`），base `4d6ebc71efea35822a28f2861f2b0a2a6db17e59`（tree `33a1a097624a24d46dda3ec289b1d899280d7e18`）。保存的 pr-initial.json 为扁平结构，核对的是 `headRefOid/baseRefOid`。
- E1 = run 40584762318 attempt 1，event pull_request，status completed / conclusion failure，开始 2026-10-27T21:12:09Z，最后更新 2026-10-27T21:27:08Z（<https://github.com/BucketSran/vaEVAS/actions/runs/40584762318>）。
- 作业 21 个全部终态：{"success": 19, "failure": 2}。失败的两个是 `regression-admission` 与 `ci-result`；四个 `regression (n)` 分片与 `regression-coverage` 均 success。
- `host_job_success_is_scientific_qualification=false`：作业 success 不等于科学资格。
- CI 实际检出对象 `253082c49e6b37155becf8ed2e40a899bf99c130`（refs/pull/269/merge）：**本 worker 首次检查（约 2026-10-27T21:33Z，早于 start.json 的 21:34:53Z）时本地缺该对象；raw 校验运行时它已在共享对象库中，对象文件时间 2026-10-27T21:48:25.644335+00:00，不是本 worker fetch 的**（全程未 fetch）。现已读取该对象：parents `['4d6ebc71efea35822a28f2861f2b0a2a6db17e59', 'fa5556de20de4fecbf9db4e3630cd5d6754b07c2']`，tree `470ad588ddeb848b7c05d3f23656a96f085f8bfd`，提交信息 `Merge fa5556de20de4fecbf9db4e3630cd5d6754b07c2 into 4d6ebc71efea35822a28f2861f2b0a2a6db17e59`，committer GitHub <noreply@github.com> 1793135525 +0800；与预期完全一致。GitHub 签名头存在，**未验证签名**。库存 source_tree 与该 tree 相同。
- 可信 base 的 gate 与登记代码（regression_gate.py、regression_context_registration.py、run_trusted_regression_gate.py）在 02dee32b、4d6ebc71、fa5556de 三处字节相同，且与源码导出 S 相同：gate sha256 `65e3542fa4989b35d31ee6998c9dc14f8975524e4b30a23b76539abf7317b38e`，登记 `138ca3036008c8f0616d0e21019f1e434ab1cd1b6498694cd2613c275c261a22`，loader `30cb19e469db4ea26b00ca4959e68c4aa1196be15a9051452ff491210619aa63`。

### 13 个 artifact（逐个按 GitHub digest 核验 zip 原字节）

| artifact | id | zip 字节 | sha256 | 成员 |
|---|---|---|---|---|
| git-fixture-isolation | 12772716921 | 112937 | `8cd4a3972aced783…` | 180 |
| ngspice-comparison | 12772490800 | 136726 | `7ead0cd5b27ff840…` | 79 |
| fast-feedback | 12772445653 | 9879 | `a4c80aff04c52313…` | 2 |
| python-regression-shard-2 | 12772381449 | 24368180 | `4630dfd584f4e3eb…` | 9 |
| python-regression-shard-3 | 12772256432 | 27095930 | `ee55be3a10247293…` | 9 |
| python-regression-shard-0 | 12772006414 | 24502572 | `8c539cc920211b54…` | 9 |
| python-regression-shard-1 | 12771427081 | 24604303 | `bcbbd714cecd2872…` | 9 |
| rust-test-listing | 12771362618 | 78018 | `3e3ccc893fd79689…` | 29 |
| python-regression-admission | 12771312813 | 1445 | `87e718dfa21ebe84…` | 3 |
| package-macos-14-arm64-py3.12 | 12771146974 | 5694338 | `bd0013461da9ddb2…` | 48 |
| package-ubuntu-24.04-x86_64-py3.10 | 12771091933 | 6197979 | `b95c2a6f6b46dd5d…` | 48 |
| catalog-inventory | 12770977366 | 7694579 | `955d8b85ec627567…` | 40 |
| python-regression-timings | 12770764459 | 3367933 | `0b89ed72542ca231…` | 2 |

合计 13 个归档、467 个成员；逐成员重新读取并核对 CRC、安全路径（无绝对路径、`..`、反斜杠、重复名）、普通文件类型、已解压字节与 members.json。完整清单：`archive-download-manifest.json`、`archive-members-verified.json`（后者还含 #274 的 2 个成员）。

### 分片与合并报告

| 分片 | 方法 | 条件 | collection | 输入指纹重算 | jsonl start/stop | bound_report |
|---|---|---|---|---|---|---|
| 0 | 818 | 1480 | valid=True cacheable=False raw_exit=1 | True | True/True | True |
| 1 | 831 | 3072 | valid=True cacheable=False raw_exit=1 | True | True/True | True |
| 2 | 823 | 1526 | valid=True cacheable=False raw_exit=1 | True | True/True | True |
| 3 | 785 | 1659 | valid=True cacheable=False raw_exit=1 | True | True/True | True |

- 四分片方法合计 3257、条件合计 7737，ID 两两不相交；可信 base 的 `run_regression.merge_reports` 对四份分片报告重算后与 `python-regression.json` **完全相等**，`validate_report` 通过，合并 collection 的计数字段全部一致。
- 合并报告 sha256 `35d74e62f8933cb10c8f8298f5a65389fa56b1cd6faadb4f8a09108f14d3fa75`；方法 3257、条件 7737（唯一 ID 7737）。
- 方法 outcome（方法级分类）：{"passed": 2617, "error": 214, "failed": 423, "expected_failure": 3}；其中非通过方法 637 个（failed+error），另有 3 个 expected_failure，二者分开；非通过方法数不等于独立缺陷数。
- 条件 outcome：{"passed": 6841, "error": 296, "failed": 597, "expected_failure": 3}（非通过条件 896 个，来自结构化结果）。
- unittest 另一套计数（subTest 级原始计数，不是方法分类）：{"failures": 597, "errors": 296, "skipped": 0, "expected_failures": 3, "unexpected_successes": 0}；`raw_successful=false`。

### 与当前 context 报告（#274，CI 40569530278）逐项比较

- 当前 context 报告：run 40569530278 attempt 1，head `5fe590c0c573c7296b30f38245f769ff2f71ab8a`，conclusion success，21 个作业全部 success（<https://github.com/BucketSran/vaEVAS/actions/runs/40569530278>）；其 `python-regression-timings` zip 已自行下载并核验 GitHub digest `e3b9c57d87ab130da0beec5b053babd48e0c2e9a669b8dc5d07b0ccd60e6ad95`；报告 sha256 `9cb0aa443f6f3d3298fa5261f554f1c58bf28819241cf756cd7103dae6b9978a`。该 CI 的检出树为 `33a1a097…`，等于可信 base 树。
- 方法：新增 0、缺失 0、outcome 变化 0；条件 ID 序列逐位相同（true）；条件 signature 变化的方法 0 个；`gate._retention_condition` 差异方法 0 个；discovered/selected/assignment 相同；fixtures 0/0；setup_skipped 空。
- 非通过方法 ID 与 expected_failure 方法 ID 均与 #274 相同；gate 计数与 unittest 计数相同；顶层唯一差异键为 `seconds`（耗时）。
- 可信 context 3（索引 3）：#274 报告与它**精确**匹配（`_matching_contexts` 唯一精确命中、无宿主差异，`compare_report` merge_allowed=true、无差异）；其展开观测与 #274 报告逐条件 outcome 与 `_retention_condition` 全部相同。PR271（CI 40507402194）报告与 #274 同 context，条件与 retention 也全部相同。E1 报告在同一 baseline 上匹配 0 个 context。
- 主控预检（e1-observations-40584762318.json）与本次独立推导一致：7737/7737 条件相同、condition2_holds=true、matched_context_index=3、报告 sha256 相同。

### criteria / DUT / kernel / collector / 构建 / 调用身份

- **criteria 身份变化**：`criteria_id` 由 `145a6118739af5c1…`（#274）变为 `7d70e5b5ab69abf4…`（E1），**不能写成与旧 criteria 相同**。清单 3610 项，变化路径恰为 PR6 的 4 个文档：`evas/validation/METHOD_QUALIFICATION.md`、`evas/validation/PROTOCOL.md`、`evas/validation/README.md`、`experiments/README.md`。每一项都对 fa5556de 的 Git blob 与源码导出 S 的实际字节核对一致（含变化前后 sha256，见 `source-identity-field-bindings.json`）。这 4 个文档中没有任何条件 site（`changed_criteria_documents_with_condition_sites=[]`）。
- **collector 变化**：`collector_sha256` 由 `e48ade34c276c578…` 变为 `fb887b59bb92063d…`；四个来源文件中只有 `scripts/ci_evidence.py`（environment_policy）变化，具体是 `rustc`/`cargo` 调用去掉 `+stable`；其余三个（run_regression.py、regression_reason_identity.py、regression_observation_policy.json）字节相同。metadata 变化键恰为 `collector_sha256`、`criteria_id`。
- **DUT**：327 个文件与 #274 逐项相同，清单 sha256 `5e9bf28ad121569a6975811f0b5ea9e60423e676e6dfcf88048948bfd19ba056`（在 842bde71、4d6ebc71、fa5556de 三处重算相同）。
- **kernel**：四个分片的 `evas-kernel` 字节相同，sha256 `b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe`（105862328 字节），与报告/identity 一致，与 #274 相同；**与 PR5 bundle 的 kernel 原字节完全相同**（直接重算两个文件的 sha256 与长度得到），主控可复用既有 schema2 压缩件。未执行。
- selector 变量（24 个 `EVAS_*_KERNEL` 等）在四个分片中全部为 null；构建设置 `CARGO_PROFILE_DEV_OPT_LEVEL=1`、`DEBUG_ASSERTIONS=true`、`OVERFLOW_CHECKS=true`；语言 profile `cb96d837943af90db29d359f57cc6e3a2f6f37fcf3956ed8163486f33d6111c1`；调用 `{"modules": [], "pattern": "test*.py"}`；runtime profile 与 #274 逐字节相同；环境键与变量相对 #274 变化 0 项。
- 工具链（四分片一致）：Python 3.12.15、rustc 1.99.1、cargo 1.99.1、Linux-6.17.0-1022-azure x86_64 glibc2.39；报告里的 `ImageVersion` 变量为 `20261023.334.3`。
- **runner 池事实（主控记录，本 worker 未下载作业日志）**：rerun-log.json 记录四个回归分片日志头 `Version 20261012.334.1`（provisioner），与 context 里的 ImageVersion `20261023.334.3` 不同；两份报告的 runtime profile 仍完全相同，所以对 gate 匹配无影响。

### inventory 与执行输入

- inventory 49608 路径、mode、OID 与 fa5556de 树逐项一致；25599 个唯一 blob **全部**从 Git 实际读取（463666274 字节），Git SHA-1 与 sha256 逐个核对，无缺失、无不一致；源码导出 S 的 49608 个文件字节全部与 inventory 一致。没有复用旧运行的行（`reused_from_other_run=0`），原因是全量读取只需数秒。
- 执行输入 49598 条（排除 10 个审计文档路径），按 `git ls-tree` 次序保留，次序与 Path 排序**不同**；该次序重现四个分片的 identity key，输入清单 sha256 `a5297be72fd6359418b064063588604fa6abd161a15dcc6dbbd29c12405adc96`；未绑定路径 0。
- 来源链：source capture（merge `797a2116…`）的 assets.json 与最终 head 比较，匹配 49571 项、capture→final 差异 37 项（均为再生成的 catalog/data 文件）、意外 0 项；final-candidate.json 与 derive-acceptance.json 的文件 sha256 全部与 inventory 及 Git blob 相符；相对 base 变化 153 个路径，与 precheck 和 final-candidate 的路径表一致。源码导出的私有 .git HEAD 为 `fa5556de20de4fecbf9db4e3630cd5d6754b07c2`。

### admission / loader / bootstrap / bundle-source / baseline

- admission 原件：valid=true，raw_successful=false，merge_allowed=false，semantic_qualification=false，differences=`expected exactly one matching trusted baseline context`；用可信 base gate 对 E1 报告重算 `compare_report`，与 artifact 里的 `trusted_comparison` **完全相同**。
- 信任绑定：trusted_commit=`4d6ebc71efea35822a28f2861f2b0a2a6db17e59`（来源 event.pull_request.base.sha）；`code_sha256` 与可信 gate blob 一致；`baseline_sha256` 与可信 baseline blob 一致；候选 baseline `is_authority=false`、`evaluated=false`。
- bootstrap：pin 提交 `72f1c2e4c22d8a2f743da8ec23101d022a3096d5`、路径 `scripts/run_trusted_regression_gate.py`；loader 字节 sha256 `30cb19e469db4ea26b00ca4959e68c4aa1196be15a9051452ff491210619aa63` 与 workflow pin、原 loader 收据、tree 条目（mode 100644、blob f89e5471）一致；bootstrap_exit=1 是 loader 如实报告预期的 gate 拒绝，不是 loader 故障。
- bundle-source：requested=false，materialized=false（本次没有构造 bundle，符合预期）。
- 现行基线：4 个 context、89943276 字节、sha256 `f765004c11b99673b95ddd87daabdc0c75fc6e4e3ef5b6cb2e9f31de96ae702b`、Git blob `14a5079516b3d19e8a2b2281c94d0174f2ee8f24`；在 4d6ebc71、fa5556de、02dee32b 三处**字节不变**，review 文件的 blob 也相同。

### 十角色所在原路径与摘要

| 角色 | 来源 | bundle 路径（run-r2/bundle） | 字节 | sha256 |
|---|---|---|---|---|
| artifact_manifest | 派生 | `bundle/artifact_manifest` | 1396 | `67a90613841be53eb60a54909c96090e19670a1b23b4f88496bbaa3bf9cc5cb1` |
| collector_manifest | 派生：四个 collector 来源文件的 sha256 | `bundle/collector_manifest` | 356 | `07c2295a3e878c283f6d0d1870b154303bc2038f4a3744ed3fdf27788ff25bcb` |
| composition_recipe | 派生（recipe） | `bundle/composition_recipe` | 620 | `4536d2c83a482ca519c3c00d5a030b45281e8ad3bccf05e8999ca784e7e6da9a` |
| dut_build | 派生：四分片 regression-build 记录与 identity 环境 | `bundle/dut_build` | 2057 | `0e08420cee2f2d8fa48adc08affd346cdc800df6fd895c33908a500fb6c5e9e7` |
| kernel_binary | 原件 python-regression-shard-0/regression-build/evas-kernel 字节拷贝（四份相同） | `bundle/kernel_binary` | 105862328 | `b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe` |
| report.json | 原件 python-regression-timings/python-regression.json 字节拷贝 | `bundle/report.json` | 41458228 | `35d74e62f8933cb10c8f8298f5a65389fa56b1cd6faadb4f8a09108f14d3fa75` |
| shard_reports | 四分片 regression-evidence/report.json 文本的 JSON 数组 | `bundle/shard_reports` | 44736958 | `9d831047d49defaab4bcd4a143f60d22306503bf9cd27b6b6b5e9cc32913d0bd` |
| snapshot_manifest | 派生：catalog-inventory/assets-before.json × git ls-tree 次序，49598 项 | `bundle/snapshot_manifest` | 12764289 | `61feefb5d100468cc763b49e3255d4b5554a10375e7800f25cf57442dd44d450` |
| stderr | 四分片 regression-evidence/stderr.txt 按序号串接 | `bundle/stderr` | 1667297 | `3339f28b11497b4c2b36504e7371d14199d154743b4846cb6184c2bae598f36f` |
| stdout | 四分片 regression-evidence/stdout.txt 按序号串接 | `bundle/stdout` | 11482 | `9a16bdb2b074fd1afc2bce9763b978a9060c6de504e816446848aa6cafa53f40` |

原路径索引：`raw-r5/role-original-index.json`（每个原件的路径与摘要）；缺项：无。

### 流边界

- stdout：分片字节 [0, 170, 10391, 921]，偏移 [0, 0, 170, 10561]，合计 11482 字节，sha256 `9a16bdb2b074fd1afc2bce9763b978a9060c6de504e816446848aa6cafa53f40`。
- stderr：分片字节 [401495, 403111, 431739, 430952]，偏移 [0, 401495, 804606, 1236345]，合计 1667297 字节，sha256 `3339f28b11497b4c2b36504e7371d14199d154743b4846cb6184c2bae598f36f`。

### 逐条件义务映射草稿

- 来源 #274 报告 → E1 报告：方法 3257 个、条件 7737 个按 id 绑定，**全部实际验证**相同：方法 outcome、条件 ID 集合与次序、条件 outcome、`gate._retention_condition` 均无差异；未知/不相同 0 项（`unknown_or_unmapped` 全空），因此没有编造任何映射。
- classification 全部为 `preserved`（7737 条），attribution 为 null；review_reference 为 `DRAFT primary source-bound mapping; independent exact-context acceptance PENDING; not an approval, authority or baseline; see obligation-map-proof.json`
- `preserved` 的条件 outcome 分布：{"passed": 6841, "error": 296, "failed": 597, "expected_failure": 3}——**其中 failed/error/expected_failure 条件按合同也以 preserved 带入**，Astra 审阅时需明确这一点（映射只证明‘与当前 context 逐条相同’，不证明这些失败是对的）。
- 条件 ID 公式重算：新旧报告各 7728 个直接 ID、9 个重复身份 ID，全部精确，不一致 0；332 个 (module, source_sha256) 对子都解析到唯一 criteria 路径并等于 fa5556de 的实际 blob 字节。
- 同一份映射也对‘可信 baseline context 3 的展开观测’通过生产函数 `mapped_obligations`（与 #274 报告一侧映射逐条相同）。草稿文件 sha256 `9e894cd05b70aa4a3d4d7b2d049de3cf25e69c9703bca7e8f50af1aa147ecf80`，canonical 映射 sha256 `53f6cb79277a690cd132465e89954b8b0d00738c4ed6207ed288222747ea2196`。
- 生产函数 `evidence`（登记模块）对磁盘上的九个非 report 角色字节以内存假授权对象通过；输出中不存在任何授权对象。

## 已定条件（沿用主控与简报，非本 worker 新增）

- 总协调决定 B：E1 对全部 4 个可信 context 只差 `collector_sha256` 与 `criteria_id`；与匹配的可信 context 3 的 7737 个条件相同。本次独立推导结论与之相同，没有引入新的科学阈值或合法域。
- 可信 gate 对新 context 的拒绝是门禁行为，整个 CI 仍为 failure；merge_allowed 与 raw_successful 与科学资格分开，均为 false。
- 本批不写授权、不登记 baseline、不改旧 review、不发布、不委派；主控是唯一集成者，Astra 是终审门槛。

## 新建议

1. **kernel 复用**：本次 kernel 原字节（b957460310caebac…，105862328 字节）与 PR5 bundle 的 kernel 完全相同，可复用既有 schema2 压缩件，无需重新压缩。
2. **merge 对象**：`253082c4…` 现在已在本地且 parents/tree 与预期一致。请主控确认它是谁何时取回的（对象文件时间 2026-10-27T21:48:25.644335+00:00）；bundle 里的 `dut_build`/`snapshot_reference` 文本已据此写成‘locally observed … signature header present but not verified’，若主控不接受这一表述，需重做这两个角色并重算 recipe/artifact manifest 的 SHA。
3. **dut_revision**：沿用 PR5 bundle 的 `842bde71…`（DUT 清单摘要在 842bde71、4d6ebc71、fa5556de 三处相同）；换成别的不改语义，但会改变 recipe SHA。是否改由主控定。
4. **环境等同约束**：按对 `regression_context_registration.evidence` 的阅读，它要求 `current` 报告与 E1 的 `comparison_subject.environment`（含 `ImageVersion`、`platform`）逐字相同，而 `_matching_contexts` 允许宿主差异。本次 E1 与 #274 环境相同所以通过；若登记 PR 自己的‘当前’运行落在不同镜像上，这一条可能单独拒绝。这是对代码的推断，本次没有运行完整登记流程来验证。
5. **复核点**：18 个 criteria 路径变化是 PR5 的情形，本次只有 4 个文档变化且不含条件 site；collector 变化只涉及 `rustc`/`cargo` 去掉 `+stable`。请 Astra 重点审阅这两处是否足以支撑‘条件语义不变’的结论；本 worker 只验证了字节、签名与来源绑定。

## 失败与重试（全部保留，未覆盖）

- `raw-r1`：worker implementation: pipe deadlock — stream_blobs wrote ~1 MB of OIDs to git cat-file --batch stdin before reading stdout; both pipes filled (64 KB) and the process hung at stage reading-blobs (25599 unique blobs) for >10 minutes. Killed by the worker; partial outputs kept in raw-r1/, script copy kept as raw_verify.r1-deadlock.py.（记录 `raw-r1.FAILED.json`，脚本副本 `raw_verify.r1-deadlock.py`）。
- `raw-r2`：worker implementation: quadratic loop — After the blob and source-export hashing stages (which completed in seconds) the 'unbound' computation rebuilt a 49,598-element set for every one of 49,608 paths (O(n^2)); the process spun at 100% CPU for >3 minutes without writing results. Killed by the worker. Partial outputs kept in raw-r2/, script copy kept as raw_verify.r2-quadratic.py.（记录 `raw-r2.FAILED.json`，脚本副本 `raw_verify.r2-quadratic.py`）。
- `run-r1`：worker implementation: member index collision — archive-members-verified.json lists both CI 40584762318 and CI 40569530278 archives named python-regression-timings; prepare_bundle indexed members by (artifact, path) only, so the #274 row overwrote the E1 row and the first digest assertion failed. Partial output kept in run-r1/ (failure.json). Script copy: prepare_bundle.r1-index-collision.py.（记录 `run-r1.FAILED.json`，脚本副本 `prepare_bundle.r1-index-collision.py`）。
- `raw-r3`：complete pass, 0 findings; ran before the CI merge object appeared locally, so merge_checkout carried no observed parents/tree. Script: raw_verify.r3-without-merge-object.py。
- `raw-r4`：complete pass, 0 findings; merge object observed; only the expectation.status wording and the source-export private HEAD field were improved afterwards。
- 最终采用：`raw-r5`（原始证据核验）→ `run-r2`（bundle）→ `verify-r1`（独立复验，43 项检查）。以上均不是科学失败。

## 运行信息

- 实际模型：tclaude/claude-sonnet-5-5，options [{"id": "effort", "value": "high"}]；任务 ID unknown (delegation record not visible to the worker)；开始 2026-10-27T21:34:53.741801+00:00，完成 2026-10-27T22:07:14.915815+00:00；排队时间 unknown。
- 守卫：真实工作区 HEAD 前后均 `168a9d7a4305e7ce21d1577b4ca1dda65beae4ce`；index sha256 `a2e18b66fd9b3e29093343793d45781c11a717c05c35103d4e9b1da8eec87d71`；共享 config sha256 `de2b08ef3ba66e96be8b70c87346ff4a96f905e1272934ddd86c218dba501ea8`（等于已接受基准 de2b08ef…，没有新增行）；18 tracked + 2 untracked 旧候选文件的状态与 20 个文件哈希前后相同。
- 所有 Git 调用使用明确的真实 git-dir/work-tree、`--no-lazy-fetch`，并清除继承的 GIT_*；代理只对 gh 子进程设置（HTTPS_PROXY=http://127.0.0.1:12639）。

## 交付清单（D 顶层）

- `REPORT.md`、`receipt.json`、`raw-verification.json`（汇总，含 raw-r5 全部结构化结果）、`archive-download-manifest.json`（13+1 个 zip 的 id/字节/sha256）、`archive-members-verified.json`（469 个成员的路径/字节/sha256/原路径）。
- `guard-before.json`、`guard-after.json`、`output-refusal-verification.json`、`context-digests.json`（context 与 baseline 的规范摘要，仅为数据点）。
- `run-r2/bundle/`（十角色）、`run-r2/{bundle-byte-binding,stream-boundaries,obligation-map-draft,obligation-map-proof,receipt}.json`、`verify-r1/verification.json`。
- 可重放脚本：`raw_verify.py`、`prepare_bundle.py`、`verify.py`（辅助：`common.py`、`intake.py`、`finalize.py`）。

## 重放

```
python3 -B raw_verify.py --output NEW-DIR                      # 原始证据核验（只读）
python3 -B prepare_bundle.py --raw raw-r5 --output NEW-DIR     # 十角色 bundle + 义务映射草稿
python3 -B verify.py --prepared run-r2 --output NEW-DIR        # 独立复验（含篡改与路径拒绝探针）
```

脚本只接受 D 内尚不存在的普通目录，拒绝已有目录/文件、符号链接、`..` 与目录外路径（`output-refusal-verification.json`；verify-r1 另含 prepare_bundle 的六项拒绝探针）。

## 原始来源链接

- PR6：<https://github.com/BucketSran/vaEVAS/pull/269>；E1 运行：<https://github.com/BucketSran/vaEVAS/actions/runs/40584762318>；当前 context 运行（#274）：<https://github.com/BucketSran/vaEVAS/actions/runs/40569530278>。
- 主控保存的元数据：`pr6/rebind-r7-20261027/ci-40584762318/{run,jobs,artifacts,pr}-initial.json`、`regression-admission.txt`、`rerun-log.json`；预检 `pr6/e1-precheck-20261027/`；源码导出 `pr6/rebind-r7-20261027/source`。
- 本批产物：`raw-r5/`（核验）、`run-r2/`（bundle 与证明）、`verify-r1/`（复验）、`zips/`、`artifacts/`、`zips-274/`、`artifacts-274/`、`ci-40569530278/`（#274 元数据）。
- 模板：PR5 `raw-intake-sol/` 与 `bundle-preparation-sonnet/`（同一构造思路；PR6 偏离处：ci_evidence.py 在候选与 base 之间不同，因此 bundle 的 ci_evidence 取候选版本，gate/登记取 base 版本并断言三处相同）。
