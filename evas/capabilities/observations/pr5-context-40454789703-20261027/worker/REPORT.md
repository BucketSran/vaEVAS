# PR266 固定候选 983b：十角色 bundle 与逐条件义务映射草案

只做数据组合与证明。没有审查、授权、登记、baseline 写入、合入判断，也没有运行测试 body、kernel、compiler、backend、Spectre、SSH、Harbor 或联网。科学资格 false，未新增科学阈值或合法域。

## 先看结论（四项分列）

| 项 | 结果 |
| --- | --- |
| 执行成功 | 是。`prepare_bundle.py` 写出 `run-r3`，`verify.py` 写出 `verify-r2`，40 项检查全部通过。 |
| 结构完整 | 是。十个角色文件齐全，生产函数 `regression_context_registration.evidence` 与 `mapped_obligations` 在磁盘字节上通过（用内存里的测试用授权对象，没有写出任何授权）。 |
| 预期拒绝 | 已复现。在 e10 的未改 baseline 上，新 report 的具体拒绝原文仍是 `expected exactly one matching trusted baseline context`（valid=true，merge_allowed=false）。同一 baseline 接受 C0 旧 report。另有 7 项篡改/漏映射必须被拒绝的探针和 6 项输出路径拒绝探针，全部按预期拒绝。 |
| 语义资格 | false。`raw_successful=false`，独立精确 context 验收未做，映射为 DRAFT。 |

## 来源事实

- 身份：run 40454789703 attempt 1，conclusion failure；固定 head `983b1ef6a4804c29483279ca34a7a92fce56a858`，tree `7a99e40b4a58e00c138e4c721f3deaab1bdb2ba6`，可信 base `e10e1af5796f0cc7af3b6b5f5d26c420c0c03325`，源码捕获 `d9495c77…`。真实工作区 HEAD 前后均 `168a9d7a…`，20 个候选文件与 HEAD/index/config/packed-refs 的 SHA 前后一致（`run-r3/guard-*.json`、`verify-r2/guard-*.json`）。
- 新 report：`python-regression.json` 原字节，SHA `531016ba…c995`，3257 方法、7737 条件；方法 passed 2617 / failed 423 / error 214 / expected_failure 3。criteria `145a6118…`（18 个路径字节相对 C0 变化），collector `e48ade34…`，DUT 327 文件与 kernel `b9574603…` 与 C0 相同。
- C0 旧 report：`ci-40429826545/raw-intake-grok/.../python-regression.json`，SHA `9097c8dc…d981`，criteria `f54a2eac…`；用的是当前已登记 context，没有用更早的旧 criteria。
- 映射实测：3257 个方法 ID 的集合与顺序在新旧两份 report 中相同，方法 outcome 全部相同；7737 个条件 ID 逐项一一对应，outcome 相同；`gate._retention_condition` 逐条完全相同（7737/7737），无需任何 remap。无 fixture、无 setup skip。条件 ID 用收集器公式重算：7728 条直接一致，9 条 `repeated_identity` 按出现序号形式一致，旧新各 0 个不一致。332 个（模块，源码 SHA）对子各自解析到唯一 criteria 路径，且等于新 criteria、旧 criteria、snapshot 条目和 983b 的实际 Git blob 字节；行号均在文件范围内。
- 与 C0 的差别只有输入集合：全输入比较主体 49560（旧 49554）。7737 条件保留签名相同，不等于测试 body 以外的 18 个 criteria 路径变化“没有影响”；这点留给精确 context 审查。
- snapshot 49562 条目保持 `git ls-files` 原次序：该次序重现 4 个 shard 的 identity key 与输入列表 SHA `d6079c1e…`；按 Path 或字符串重排会让生产函数拒绝（已测）。collector 的 DUT 清单次序是“先 `evas/src` 再 `evas/rust_core`，各自 Path 排序”，首次实现把它全局排序而失败（见下）。
- 三个仓库版本的 `regression_gate.py`、`regression_context_registration.py`、`ci_evidence.py`（e10、983b、`source/`）字节相同；bundle 用的是 e10 blob 的拷贝（`run-r3/code/trusted/`）。DUT 清单摘要在 `842bde71`、e10、983b 三处都等于 D0 `5e9bf28a…`。
- 复用已核的 13 个 zip / 467 成员，未重新下载或全量重验；本次只重新哈希实际消耗的 32 个输入（`receipt.json` 的 `consumed_inputs`），并读取 332 个测试源码 blob。

## 十个文件

目录：`run-r3/bundle/`（`kernel_binary` 仅拷贝，无执行位，未执行）。

| 角色 | 字节 | SHA256 |
| --- | ---: | --- |
| report.json | 41,458,076 | `531016babc8a288fd130f3af99364dbcaf20f25c225201d1f35e73e6b0a6c995` |
| composition_recipe | 620 | `a0abe35c10fa5e97f1b80c29e83e99db1099826a118a2d29dbf4f43a811fa38b` |
| snapshot_manifest | 12,758,265 | `908fc15264c92586d8014a7b94f71b7176440b92ce2836d9fd9f59c21435d607` |
| dut_build | 1,860 | `ae1774af226e22ebf62cd590f1c3243d43f9d06089a902307718aae9fed49f2d` |
| kernel_binary | 105,862,328 | `b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe` |
| collector_manifest | 356 | `225b9b80d905436696a410e2a312cf1a4d415fe2b4771427f38ae4d93b602179` |
| artifact_manifest | 1,394 | `5cc042c0a33607906f8eee3cc6f4f45657b13bf13ed0b02133275ba9ec8d6e43` |
| stdout | 11,482 | `231f69ab48e18e4b01251a1f46b4e4bfea54b86539695b66be2648c3501c47de` |
| stderr | 1,667,281 | `7ba285e31505468a43c81bcc5cd2aef0bda8025ba19ddaacd5463f2bf9b23843` |
| shard_reports | 44,736,807 | `42fa7bb25445a1c0784144a7b43af79b6c982dc7a3269e446492f9d947785aca` |

- `stdout`/`stderr` 按 shard 0→3 精确串接，边界、长度、SHA 在 `run-r3/stream-boundaries.json`（stdout 0+170+10391+921；stderr 401481+403111+431739+430950）。
- `shard_reports` 是四份原 `regression-evidence/report.json` 文本的 JSON 数组，解码再编码字节完全相等，次序 0→3。
- `dut_build` 把 CI 页面、四 shard 的 identity/build 记录哈希、kernel SHA、DUT 清单与 CI merge 检出写入引用文本；明确写出 merge 对象“NOT locally verified”。
- `entry_provenance_preview`（`bundle-byte-binding.json`）：recipe `a0abe35c…`，artifact manifest `5cc042c0…`，snapshot revision 为 983b。仅为预览，不是 entry。

## 映射草案

- `run-r3/obligation-map-draft.json`：7737 项，6,717,320 字节，SHA `9e894cd05b70aa4a3d4d7b2d049de3cf25e69c9703bca7e8f50af1aa147ecf80`；规范化映射摘要（授权里的 `mapping_sha256` 将绑定的值）`53f6cb79277a690cd132465e89954b8b0d00738c4ed6207ed288222747ea2196`。
- 全部 `classification: preserved`、`attribution: null`；这是现有合同允许且实测吻合的唯一分类。`review_reference` 写明 DRAFT / independent exact-context acceptance PENDING，不是批准、权威或 baseline。
- 证明：`obligation-map-proof.json`（计数、逐项对比结果、ID 重算、332 个源码绑定、生产函数结果）。没有未知、不相同或需要编造的映射。

## 已定条件

- 输出只能写入 D 内尚不存在的普通目录，拒绝已有目录/文件、符号链接（含经由符号链接的父目录）、D 外和 `..`；`verify-r2/verification.json` 的 `output_path_refusals` 实测 6 种情形（`verify-*/refusal-probe/link` 是该探针留下的指向 `/tmp` 的符号链接，无副作用）。
- `dut_revision` 取 `842bde71…`（与上一轮约定一致）；三处 DUT 摘要相同，所以换成 e10 或 983b 不改变语义，但会改变 recipe SHA。
- 时间：prepare 2026-10-27T05:53:49Z–05:54:31Z；verify-r2 05:57:06Z–05:57:27Z；排队时间 unknown。模型 tclaude / claude-sonnet-5-5，effort high。

## 保留的首轮失败

- `run-r1`：我把 `source/` 目录写成了 `ci-40454789703/source`（实际在上一级），读不到 `source/scripts`，在 import 前失败。输出 `failure.json`、`stages.jsonl` 保留。属脚本路径错误。
- `run-r2`：DUT 清单摘要断言失败。我把 327 个路径全局排序，收集器实际是 `evas/src` 与 `evas/rust_core` 两个目录依次、各自 Path 排序。属脚本实现错误，不是证据问题；`failure.json` 保留。
- `verify-r1`：40 项中 3 项失败。两项是我的篡改探针写错（篡改 kernel 末字节恰为 0 等于没改；snapshot 用字符串重排而 git 次序本身就是字符串序，等于没改），一项是变量 `before` 被循环覆盖导致 guard 文件写错。三项均为校验器自身缺陷；`verification.json` 与残留文件保留。`verify-r2` 修正后全通过。
- 上述修复是在原文件上直接改的，旧版脚本本身没有留存；当前脚本 SHA：`prepare_bundle.py` `42cd347f…`、`verify.py` `abc77b57…`。结论以 `run-r3`/`verify-r2` 为准。

## 新建议（需主控/Astra 决定）

1. 主控取回 CI merge 对象 `33ed0fa1…`，核对 parents `[e10e1af5…, 983b1ef6…]` 与 tree `7a99e40b…`。目前这只是预期，bundle 里的引用文本也如实写成“未验证”。若实测不符，`dut_build`/`snapshot_reference` 文本需重做并重新计算 recipe 与 artifact manifest 的 SHA。
2. 由主控决定是否发布这十个文件并处理既有 schema2 压缩；写授权里的 `locator` 需要可检索位置。本目录只给本地路径。
3. 下一步才是 C0 授权提案、entry 与 review 对象；这些我没有做。Astra 需要精确审阅的对象是：entry、本 bundle 十文件 SHA、映射 SHA `53f6cb79…`，以及“18 个 criteria 路径变化但 7737 条件保留签名相同”这一点。
4. 不要把 `successful=false` 的 report 或本草案当作资格依据；失败的 637 个非通过方法（423 failed + 214 error）仍是未解释的既有失败，与 C0 完全相同。

## 复现

```text
/opt/homebrew/opt/python@3.14/bin/python3.14 -B prepare_bundle.py --output NEW-UNUSED-DIRECTORY
/opt/homebrew/opt/python@3.14/bin/python3.14 -B verify.py --prepared run-r3 --output NEW-UNUSED-DIRECTORY
```

目录：`/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/pr-review-20261025/grill-vams-2023/pr5/context-registration-20261027/bundle-preparation-sonnet`（实际路径为 `/Volumes/vaEVAS-runs/...`）。prepare 约 42 秒，verify 约 21 秒。

## 来源链接（均只读）

- 固定输入根：`…/pr5/comparison-continuation-fix-20261027/fixture-root-finalization/ci-40454789703`；raw 接收：`raw-intake-sol/{receipt.json,raw-verification.json,artifact-download-receipt.json,REPORT.md}`，`raw-intake-sol/verification-r3/{role-original-index.json,source-identity-field-bindings.json,archive-members-verified.json,inventory-verification.json,admission-verification.json}`。
- 新 report：`raw-intake-sol/artifacts/python-regression-timings/python-regression.json`；shards、build、identity、assets：`raw-intake-sol/artifacts/{python-regression-shard-0..3,catalog-inventory}/`。
- C0 旧 report：`…/pr4/post-review-integration-20261027/catalog-index-recovery-20261027/ci-40429826545/raw-intake-grok/artifacts/python-regression-timings/python-regression.json`。
- 旧构造器思路：`…/pr4/detector-integration-20261027/ci-40384473617/{prepare_bundle.py,prepare_obligation_map.py,bundle-byte-binding.json}`。
- 可信代码：e10 的 `scripts/{regression_gate,regression_context_registration,ci_evidence}.py`（本轮副本 `run-r3/code/trusted/`）。
- CI 页面：https://github.com/BucketSran/vaEVAS/actions/runs/40454789703
- 机器回执：`run-r3/{receipt.json,stream-boundaries.json,bundle-byte-binding.json,obligation-map-draft.json,obligation-map-proof.json}`、`verify-r2/verification.json`。
