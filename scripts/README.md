# 仓库维护脚本

本目录保存跨模块的维护工具。仿真器实现和开发测试在 [evas/](../evas/README.md)，
具体实验的运行器与分析器在 [experiments/](../experiments/README.md)。
以下命令均从仓库根目录执行，使用 Python 3.10+。

## EVAS 本地检查政策

[evas_check_policy.py](evas_check_policy.py) 定义本地迭代与交付检查、选择理由、
缺失测试阻断和待验收项。Harness 从冻结源码执行该政策；检查命令、预算、进程结果与证据保全归 Harness。
已有检查标识和范围保持不变，CI lane 仍由下方 `ci_selection.py` 决定。

政策使用版本 1 的 JSON 请求和响应。`--request` 接收请求文件：`plan` 使用 `paths`、`stage`，
`acceptance` 使用原 `plan` 与执行器提供的 `results`，每项结果只含 `check` 和布尔 `passed`。
两种请求都带 `protocol_version: 1` 和 `operation`；响应含同版本标识及 `result`。
政策不执行测试，也不核销 CI、Spectre 或原请求的外部验收。旧源码没有政策或协议不兼容时，
自动计划明确失败，仍可使用该版本原有验证入口和历史证据。

`python3 -B scripts/evas_check_policy.py --write-docs` 更新现有
[验证技能](../.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks)中的自动规则表；
`--check-docs` 只检查同步并由 CI 执行。表格外的语义解释和人工验收要求保留原文。

<a id="development-records"></a>

### 子任务进入共享基线前的快检

`python3 -B scripts/evas_check_policy.py --early-checks --report runs/early-integration.json`
检查当前源码的两个小Select兼容案例，以及实际存在的整数计费、初始化证明预算机制。
同一命令在现有CI fast-checks阶段执行。新增机制尚不存在会明确记为不适用，不会算作已验证；
显式选择缺失的检查会阻断。需要实际数值消费者时加`--kernel`指定匹配内核。
小表达式执行路径变化时先返回2，表示需要消费者验证；CI仅在此时先构建内核，
运行小消费者再决定是否继续宽回归。合法的新表示可以通过实际消费者验收，不强求IR相同。

`--plan runs/ci-plan.json` 按已确认的改动范围选择快检；纯文档或工作流改动跳过仿真，未知源码保守保留快检。
复核历史冻结副本可使用`--source-root`和`--python-root`，每次使用独立Python进程。
收据区分编译结构检查、实际内核执行和未覆盖范围。初始化检查只拦独立额度分配者增加及耗尽后恢复，
累计调用和所有循环的收费仍须相应测试与审查。完整等待、后台和复用边界统一见
[early integration checks](../docs/contributing/validation.md#early-integration-checks)，不再另开一套验收流程。

## 精简审查与阶段计时

[development_records.py](development_records.py) 检查本轮唯一的人读摘要。无问题上限 300 字，
有问题上限 800 字。按去空白后的字符计数，Markdown 链接只计标签；正文、代码块和哈希均计入。
多份摘要、空摘要或超长均返回非零状态。检查不会改写、截断或删除报告。
所有发现和详细证据保留在原任务的结构化记录中，短摘要必须说明未解决数量及读取位置。

```bash
python3 -B scripts/development_records.py check-review runs/<task>/review.md --findings 0
python3 -B scripts/development_records.py time-start runs/<task>/timing.jsonl --id check-1 --phase validation
python3 -B scripts/development_records.py time-stop runs/<task>/timing.jsonl --id check-1 --status complete --evidence runs/<task>/checks.json
python3 -B scripts/development_records.py time-summary runs/<task>/timing.jsonl
```

`review.md` 是 PR 或任务记录中摘要的本地草稿，不是另一份审查报告。交付只呈现一个入口。
检查只约束传入的草稿；不会自动抓取聊天或判断文风。审查技能和提交技能要求在交付前运行它。
检查器测试纳入现有维护 CI，不新增仿真检查，也不扫描或重判旧报告。

计时器追加 UTC 起止时间和单调时钟耗时。阶段包括调研、实现、验证、审查、返工、CI 等待与发布。
失败用 `--status failed`，返工或等待可附 `--reason`。不同 worker 用 `--actor` 区分；协调者统一写入。
汇总分别显示参与者阶段用时、区间并集和跨度，未结束及时间跳变单列。漏记时间保持未知。
规则见[耗时记录](../docs/contributing/evidence.md#development-time)。

<a id="compact-tool-output"></a>

### 默认摘要与完整证据

工作区检查、CI 选取和阶段记录默认显示紧凑状态、失败项与证据位置。
`time-summary` 会保留失败和取消阶段的 ID、原因与证据，未结束和计时未知项单列。
三个入口均可用 `--json` 展开完整结果，或用 `--report runs/<task>/<name>.json`
保存一次完整结果再返回摘要。工作区的原详细文本用 `--verbose` 查看。
没有指定 `--report` 时，工作区和 CI 选择器不写文件，摘要提示展开方式；计时原始记录仍追加到传入的 JSONL。

```sh
python3 -B scripts/check_workspaces.py --report runs/<task>/workspaces.json
python3 -B scripts/development_records.py time-summary runs/<task>/timing.jsonl --report runs/<task>/timing-summary.json
python3 -B scripts/ci_selection.py select --event-name push --event-path runs/<task>/event.json --report runs/<task>/selection.json
```

后续状态读取优先报告变化、失败和原证据路径，完整结果按具体问题展开。
JSON 协议消费者使用 `--json`；CI 保留原布尔字段编码，并增加阶段、相关模块及计划版本输出。
这只缩减显示内容，不减少工作区检查范围、检查项目或错误记录。

## CI 按改动选择检查

CI 先选择最终验收义务，再按阶段决定本次执行范围。草稿 PR 的日常更新使用迭代阶段；
已映射的修改只执行相关回归，保留完整交付义务。草稿推送在 `before` 是当前 head 的祖先时，
按本次推送差异选择迭代模块；最终义务仍按完整 PR 差异记录。非草稿 PR、`ready_for_review`、main 推送
和每周完整检查使用交付阶段。手动 `workflow_dispatch` 默认完整交付；显式选择 `iteration` 并提供
有效的前序提交 `base` 可运行快速检查，缺失或无效身份回退完整交付。草稿可手动完成完整验收，
无需改变 PR 状态。CI 配置、选择器、未知路径和缺少映射的共享修改保守回退到完整检查。

快速任务先对改动的 EVAS Python 源码、直接开发测试和 scripts 文件检查 Ruff 基本错误规则 `E9,F63,F7,F82`，再检查 Rust 格式、
Clippy 与生成清单；该任务通过后才启动昂贵任务。冻结题包、参考模型和故意失败的夹具不自动加入源码 lint。Python 风格格式化和 mypy 尚未启用。
本地可执行 `python3 -B scripts/ci_lint.py --paths <改动路径...>`，先安装固定的 `ruff==0.14.1`。
本地迭代／交付模块由 [evas_check_policy.py](evas_check_policy.py) 及其生成表维护。

下表描述完整交付的检查义务。草稿阶段未执行的项目保持待验收，不报告为通过。

| 改动内容 | 执行的检查 |
| --- | --- |
| 普通 README、贡献指南 | 改动行空白、CI 路由自检 |
| 能力对比表、论文或支持范围文档 | 上述快速检查，以及论文判据、表格来源校准 |
| 评测标准、数学或验证契约文档 | 对应数学与 checker 校准；对比评测标准同时检查表格来源 |
| 开发追溯文档、已登记的维护脚本 | 追溯矩阵、诊断清单、冻结身份与维护工具测试 |
| 已登记的后端 checker、结果分析工具 | 数学、checker 与表格来源校准 |
| 已逐项核对的历史结果收据 | 数学、checker 与表格来源校准，不运行仿真回归 |
| `evas/tests/` 的 Python 开发测试、Rust `tests/` 下的 `.rs` 测试 | 维护检查、来源校准、完整 Rust 与 Python 回归 |
| 验证模型、参数等共享输入 | 完整 Rust 与 Python 回归、相关静态检查 |
| Rust `src/`、`ir/src/` 下的 `.rs` 实现 | 完整回归、维护与来源校准、ngspice 对照、fuzz；仅已核对且内容身份完整的数值修改可免安装，并检查新 release 核 |
| Python 前端、依赖、构建文件及其他未细分 EVAS 输入 | 完整回归、静态检查、ngspice 对照、fuzz、两平台安装测试 |
| ngspice 对照工具 | 对照测试、相关静态检查 |
| 安装验收脚本 | 维护工具测试、两平台安装测试 |
| Benchmark 材料与规范文档、题目、checker、登记工具 | Benchmark 登记与索引、阶段静态检查、身份与独立判据回归 |
| CI 配置、检查选择器或未登记的非文档路径 | 全部检查 |

有完整 base/head 文件内容时，选择器额外识别以下已核对的边界：

- `scripts/ci_selection.py` 只有 `MAINTENANCE_FILES` 字面集合变化，且变化项已在当前选择器核对为独立维护路径时，只选维护检查。其余 Python 语法树必须相同。新路径、调度语义变化和 CI 配置仍全选；选择器回归自身选维护检查。
- `evas/docs/COMPARISON.md` 只有唯一 `ci:progress:start` / `ci:progress:end` 注释块内的进度文字变化，块外文本完全一致时，只做快速检查。该块只记录推进进度，不放能力、成绩或验收规则；表格、标题、代码块和嵌套注释不适用。新增、删除标记或文件仍选来源校准。
- `ci_selection.py` 的 `ALGORITHM_PATHS` 中现有数值模块，前后原件均为普通文件，且无安装相关内容或未知宏时，保留行为回归但免完整安装。入口、IR、依赖、构建、资源、平台、未核对路径、文件新增／删除和身份缺失仍保守安装。该判定不能替代消费者与风险审查，见[安装边界](../evas/docs/reference/install.md#源码交付与安装检查边界)。

仅有路径的本地政策请求不能证明这些边界，继续保守选取。逐路径理由保存在完整选取结果中。
登记独立维护路径前仍须核对消费者；共享依赖不能登记成独立维护来绕开验收。

“已登记”指 [ci_selection.py](ci_selection.py) 中明确列出的路径。不能笼统地跳过实验目录：
论文输入生成器和部分后端夹具也被 EVAS 回归读取，修改它们仍跑完整回归。
历史收据目前只登记 `experiments/backends/sample-edge-filter/rea-boundary-receipt.json`：
它保存 IR19 的既有诊断结果，代码与回归夹具不读取它。其他 JSON 文件不继承这项规则。
若新增代码开始读取该收据，必须同时更新路由及其测试；混合修改仍取所有路径的检查并集。
smoke 模型同时触发 ngspice 对照，源码包要求的 fuzz seed 同时触发安装验收。
Benchmark 下的来源说明、规范、模板和题面均触发 Benchmark 检查；来源说明新增或删除会改变生成索引。
对应维护脚本及测试也触发同一检查，不因 Markdown 扩展名或脚本目录而漏选。
静态校准通过不代表重新完成了 Spectre 对照。

混合修改取检查的并集，删除和重命名也参与选择。PR 使用分叉点至最新提交的完整 Git 差异，
main 推送使用推送前后的提交差异，不使用有文件数量上限的路径过滤。
差异身份缺失、首次推送或默认手动 `workflow_dispatch` 时全跑。每周一北京时间02:23的完整检查重新执行回归，fuzz每个目标由普通检查的45秒延长到300秒；400模型和外部参考矩阵仍只按专项授权运行。

[numerical-assurance.yml](../.github/workflows/numerical-assurance.yml) 是唯一调度入口，
选择任务记录完整差异；快速任务在自己的 checkout 重建同一计划。安装和 Benchmark 工作流保留各自文件，由入口按需调用。
统一的 `ci-result` 检查每个被选中的任务和子工作流完成记录；失败、取消、缺失或意外跳过
都不能通过。需要设置分支必需检查时使用 `ci-result`，它替代原来的三个 `*-result` 检查。
草稿迭代只产生 `iteration-result`，不产生可供合并门禁使用的 `ci-result`；转为非草稿会触发完整验收。完整阶段的 `ci-result` 额外要求 `regression-coverage` 通过。本次没有修改 GitHub 分支保护配置。

同一 PR 的新推送会取消该 PR 的过期 CI。main 推送和手动运行互相独立，不自动取消，
避免后来的文档推送取消前一版代码尚未完成的回归。
CI 针对固定提交后台执行。主对话按[等待边界](../CONTRIBUTING.md#keep-iteration-feedback-short)
继续独立授权工作，在检查点收取结果；选中的最终任务未完成时保持待验收，合并前收齐。

未选择安装的完整回归，在第 0 组先构建新 release 核，并用
`scripts/check_source_kernel.py` 经公开 API 检查独立仿射与积分答案，记录实际路径与 SHA256。
这一步检查源码核，不声明新 wheel 或另一平台已安装通过。完整安装已选择时沿用其 release 构建与运行检查。

Rust 缓存按操作系统、架构、实际编译器、依赖清单和任务区分，保存 Cargo 下载与开发构建结果。
缓存命中后仍执行 Cargo 构建和全部选中的测试，不缓存“通过”结论。
`cargo-fuzz` 单独缓存固定版本的工具。安装测试仅复用依赖下载，仍从源码包构建新的原生 wheel，
并在 checkout 外执行 Linux x86_64、macOS arm64 的安装验收。
缓存为空也必须能完成检查；首次运行的耗时不能用来推算缓存命中后的收益。

```sh
python3 -B -m unittest discover -s scripts/tests -p test_ci_selection.py -v
```

路由回归使用真实临时 Git 仓库，覆盖文档分类、共享夹具、混合修改、删除、重命名、分叉点
和身份缺失，也检查被选任务及子工作流意外跳过时是否拒绝通过。
检查调度和缓存不改变仿真器判据与历史成绩。

### 本轮缩减的依据与边界

2026-10-16 核对了三轮 Actions 的实际步骤耗时，单位为秒：

| 运行 | Python 回归 | 数学与 checker 校准 | 论文契约与来源校准 |
| --- | ---: | ---: | ---: |
| [main，969b1b88](https://github.com/BucketSran/vaEVAS/actions/runs/38750014225) | 261 | 47 | 188 |
| [#188，5ac25198](https://github.com/BucketSran/vaEVAS/actions/runs/38767462283) | 406 | 36 | 140 |
| [#189，ab752520](https://github.com/BucketSran/vaEVAS/actions/runs/38769351568) | 416 | 48 | 192 |

只修改上述开发测试或 Rust 实现时，取消数学与 checker 校准。
实际执行这组 14 条命令并记录文件读取，未读取开发测试或 Rust 文件。
来源校准仍读取生产源码与测试文件，继续保留。例如
[原语输入冻结器](../experiments/backends/support/primitives_run.py)会将 Python 测试写入源码身份清单，
[论文输入冻结器](../experiments/backends/paper/inputs.py)会将 Rust 测试写入运行时身份清单。
前端改动仍保留两组，因为校准中有真实编译器调用，例如
[回调记录校准](../experiments/backends/support/test_root_callback_evidence.py)。
构建输入、共享验证夹具、混合改动和未知路径继续按完整依赖选取。
数学校准组若开始读取开发测试或 Rust 实现，必须同时更新选择器与路由回归。

这减少符合条件的改动所消耗的 runner 时间，不代表整个 CI 等待时间按同样幅度下降。
上述三个原始 diff 均需按完整路径重新判断，不能把静态步骤耗时直接算作其加速收益。
Python 回归仍是这些运行的最长路径，完整功能回归、测试分母与精度门槛均未缩减。
调度语义修改仍触发全部检查；上文所列的独立维护登记例外需要完整文件内容核对。

### 同一观察记录的多档校准

旧整链正控仍检查 12 个条件和 Q1、Q2、Q3 三档，共 36 次判定。
`legacy_chain_precision.assess_tiers` 在一次调用内保存输入快照，复用同一回调历史在各观察点的
Decimal80 参考包络。各档的输入预算、回调检查、离散相位选择、误差累计和通过判定仍分别执行。
缓存随本次调用结束而释放，条目数最多等于本次波形的观察点数。

这个入口用于把**同一份观察记录**按三档判据校准。实际后端的三档配置会产生各自的波形和回调，
`legacy_chain_run` 继续分别调用 `assess`，不能用一次仿真代替三个配置的实际运行。
独立单档调用、错误波形、非零回调时间区间和跨调用输入变化均保留回归覆盖。

2026-10-16 在 macOS arm64、Python 3.14.6 上做了五组交错 A/B；基线为 `fa59e4c6`。
每次生成相同的 24,561 个观察点并完成 36 次判定，全部结果字段的序列化字节一致。
机器有 10 个逻辑核，采样时一分钟负载约 5.6–9.5；这些本地观测不代表空闲机或 Actions runner。

| 完整正控校准路径（含夹具生成） | 五次耗时，秒 | 中位数 | 进程峰值内存范围 |
| --- | --- | ---: | ---: |
| 原逐档调用 | 67.92、67.59、64.70、77.82、62.86 | 67.59 秒 | 33.3–45.0 MiB |
| 同次调用内复用参考包络 | 39.31、33.05、32.36、32.55、33.32 | 33.05 秒 | 66.4–76.6 MiB |

这条路径的中位耗时下降约 51%，代价是保存观察点包络的内存。它不是仿真器加速，
也不是完整测试模块或整体 CI 的加速比例；本次还新增了两项跨档等价与错误输入检查。

### 将完整回归分组并复用相同输入的成功结果

`run_regression.py` 按模块分组，保留同一模块的 fixture 与测试顺序。四个 CI worker 使用独立
checkout 和构建目录。`regression-weights.json` 中的历史模块耗时只影响分配，不改变测试或阈值；
新模块按测试数量分配默认权重。汇总任务验证四份完整清单一致、实际执行与显式的夹具级跳过逐项对应计划，集合不重叠且没有遗漏；跳过不计为执行。
Rust 全工作区测试由第0组执行；其他组只执行各自 Python 集合。新版本工具或输入自动使
[成功证据缓存](../docs/contributing/evidence.md#reuse-ci-regression-evidence)失效。

```sh
PYTHONPATH=evas/src python3 -B scripts/run_regression.py --shard-count 4 --shard-index 0 --weights scripts/regression-weights.json --report runs/<task>/shard0.json
PYTHONPATH=evas/src python3 -B scripts/run_regression.py --modules test_transition test_timer --report runs/<task>/focused.json
python3 -B scripts/run_regression.py --merge runs/<task>/shard0.json runs/<task>/shard1.json runs/<task>/shard2.json runs/<task>/shard3.json --report runs/<task>/complete.json
```

单组成功不是完整回归通过。开发迭代只跑相关模块；稳定候选再执行四组及覆盖核对。
计时报告的各组耗时之和不是并行墙钟耗时，不从一次运行推断提速比例。参考
[分阶段持续集成](https://martinfowler.com/articles/continuousIntegration.html#KeepTheBuildFast)与
[测试范围和隔离](https://testing.googleblog.com/2010/12/test-sizes.html)。

### 找出回归慢在哪里

Python 回归在 Actions 摘要列出最慢的 20 个测试，并保留 `python-regression-timings` 附件。
JSON 记录每个测试的耗时和结果；JSONL 在测试开始、结束时立即写入。
如果进程被终止，最后一条开始记录可以定位尚未结束的测试。报告是否完整会单独标明，
缺少最终报告不能解释为通过。硬终止时附件上传仍取决于 Actions runner 是否可用。

本地使用相同入口：

```sh
PYTHONPATH=evas/src python3 -B scripts/run_regression.py --report runs/python-regression.json
```

这仍执行完整 unittest 回归。失败、错误、意外成功、空测试集和中断均返回非零状态。
论文电路按 12 张卡分别计时，仍保留每张卡的稀疏与加密查询、原精度要求和历史一致性检查。
耗时是定位线索，单次 CI 数字不能当作可复现的性能提升。

`regression` 使用 Cargo 开发配置的 `opt-level=1`，明确保留 `debug-assertions=true`
和 `overflow-checks=true`，缓存单独使用 `regression-opt1`。这减少未优化代码的执行成本，
不改变模型、精度参数或误差门槛。配置含义见 [Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html)。
需要复现 CI 构建时，在 Cargo 命令前设置对应环境变量：

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=1 CARGO_PROFILE_DEV_DEBUG_ASSERTIONS=true CARGO_PROFILE_DEV_OVERFLOW_CHECKS=true \
  cargo +stable build --locked --manifest-path evas/rust_core/Cargo.toml
```

数值拒绝测试必须核对预期的错误类型。`kernel_timeout`、进程启动失败或协议错误
不能证明求解器正确拒绝了模型；相关防退化检查见
[拒绝测试校准](../evas/tests/test_rejection_contracts.py)。

## 本地工作区检查

```sh
python3 -B scripts/check_workspaces.py
python3 -B scripts/check_workspaces.py --json
python3 -B scripts/check_workspaces.py --repo /path/to/checkout --base main
```

检查器从 `git worktree list` 找到主 checkout，并检查其同级 `worktrees/README.md`。
每个临时 checkout 都要在该目录下有可见入口，并由索引中的相对链接指向它；入口可以是
真实目录或指向 Codex 托管目录的符号链接。项目外层 README 必须链接这个索引。
只在索引里写一个隐藏目录的绝对路径，不满足可见入口要求。普通单 checkout 无需索引。

导航使用普通 Markdown 行内链接，例如 `[任务](task)`；含空格的路径可以百分号编码或
放在尖括号中。检查器排除 HTML 注释和代码中的示例链接，不解析完整 Markdown 或 HTML；
引用式链接不属于索引格式。索引可附带指向现有草稿文件的链接，已消失的本地目标会报错，
包括不带尾斜杠的旧目录链接。`worktrees/` 内的目录链接用于活动工作区入口；
草稿材料使用文件链接，目录外的日常入口与归档导航不按工作区入口判定。

开始或恢复编辑、新建工作区以及交接时运行同一个命令。返回值 `0` 表示可见性检查通过，
`1` 表示入口缺失或失效，`2` 表示 Git 或文件检查未完成。命令只读，不创建、移动、提交、
合并或删除工作区，也不访问网络。只有显式 `--report` 会保存结果文件。JSON 包含每个 checkout 的分支、HEAD、未提交及未跟踪
条目、忽略路径和不在比较基准中的提交数；目录条目数不是文件数。

基准默认选本地 `origin/main`，其次是本地 `main`，并记录实际 SHA；也可用 `--base` 指定。
没有可用默认基准时将比较记为未知，显式指定无效基准则失败。没有自动 fetch，本地引用可能
滞后；squash/cherry-pick 后提交的不可达性也不能直接等同于“成果未合入”。脏文件和未纳入
基准的提交用于交接，不使正常开发的可见工作区失败。忽略路径需人工判断哪些材料必须保留。

索引还应写明用途、交接状态和下一步，这些内容的准确性由交接审查负责。检查器不证明
任务已经完成、目标分支已更新或清理已获授权，也不会验证是否仍有程序在使用工作区。
规则和收尾要求见 [CONTRIBUTING](../docs/contributing/workspaces.md#workspace-visibility-and-handoff)。
`local/` 历史快照通过目录索引查找，不作为活动 worktree 递归扫描。

机制回归使用真实临时 Git 仓库，覆盖隐藏入口被拒绝、可见入口修复、过期链接、改动与
忽略材料报告。CI 选中维护检查时，`scripts/tests` 步骤会执行这些回归，
但远端 CI 不检查开发者电脑上的工作区。没有安装全局 hook；agent 必须实际调用检查器。

### 只读资产报告

准备复用或退出工作区时，增加 `--assets`。普通可见性检查不扫描文件内容或目录体积。
报告输出到标准输出；需要保存时，由调用者重定向到现有任务的 `runs/` 目录。

```sh
python3 -B scripts/check_workspaces.py --assets
python3 -B scripts/check_workspaces.py --assets --json > runs/workspace-assets.json
```

报告列出每个工作区未提交和未跟踪的文件、未纳入基准的提交，以及从分叉点产生的改动路径。
暂存区与工作文件分别记录，即使工作文件已恢复原文，也保留暂存区修改。
内容哈希只读取这些改动文件，忽略目录另按磁盘类别统计。
`assume-unchanged` 或 `skip-worktree` 索引标记可能隐藏修改；报告列出仍存在的隐藏路径并读取内容。
本地不存在的隐藏路径只记数量，避免稀疏检出的大量缺席文件淹没改动列表；普通 Git 删除仍逐项保留。
存在隐藏标记时仍将覆盖标为未完成，不生成完整源码匹配或退出候选结论。
`--verbose` 文本限制文件和匹配组展示数量，完整清单和匹配组保留在 `--json` 或 `--report` 中。

| 报告项 | 可以据此判断什么 |
| --- | --- |
| `matching_source_states` | HEAD 文件树、暂存及工作区差异、未跟踪内容相同的候选；不包含忽略资产和提交历史 |
| `matching_changed_files` | 不同工作区中，同路径、类型、权限和内容哈希相同的改动文件 |
| `matching_branch_patches`、`patch_equivalent_in_base` | Git patch-id 相同的补丁候选；patch-id 忽略空白，不证明行为等价或已经交付 |
| `overlapping_paths` | 多个工作区正在保留同一路径的改动，供负责人检查重复开发或冲突 |

“未纳入基准”和“未找到匹配”都不是独有成果的最终结论。报告不替代验收，也不检查其他机器、
未登记目录或历史归档。文件和 Git 状态在检查中变化时，会保留未知状态，抑制完整源码匹配结论。
这些观察不是整个文件系统的原子快照。

磁盘分为 `build`（`evas/rust_core/target`）、`runs` 和 `other`。报告文件逻辑大小和文件系统
返回的已分配字节数；不进入符号链接，不扫描 `.git`，同一 checkout 内硬链接只计一次。
目录通过禁止跟随链接的文件描述符读取；平台不支持这种读取方式时明确报告未完成。
类别按路径划分，目录中仍可能有需要留证的二进制。跨 checkout 的硬链接、APFS 共享块等
不能由这些数字确定独占空间，因此不能将它们直接相加作为可回收容量。

每个工作区的每类目录默认扫描最多 2 秒，改动文件默认最多哈希 64 MiB。
使用 `--scan-seconds 10` 或 `--hash-limit-mib 128` 可以扩大一次检查的范围。
扫描时限是元数据操作之间检查的软上限；单次文件系统调用可能更慢。
超时、权限错误、子模块或内容超限会明确标为未完成；未完成的体积只是下界，未知值不是零。
资产报告未完成时退出码为 `2`，可见性结果另行保留。只有需要资产分析时才使用此模式。

处置建议包括保留日常入口、保存未提交修改、审查未合入提交、补查未完成项，以及核对退出条件。
即使 checkout 干净且没有独有提交，也需确认负责人、活动进程和忽略证据，再按
[退出清单](../docs/contributing/workspaces.md#retiring-work)处理。脚本只观察，不创建快照、修改索引、
移动、清理或删除资产，也不自动读取远端 PR 状态。

## 生成和检查追溯矩阵

```sh
python3 -B scripts/traceability.py
python3 -B scripts/traceability.py --check
python3 -B -m unittest discover -s scripts/tests -v
```

`traceability.py` 读取测试 GUARDS 标签、[能力 ID 与证据索引](../evas/docs/development/capability-evidence.md)和 DUT 目录，生成
[追溯矩阵](../evas/docs/development/TRACEABILITY.md)。`--check` 不写文件，拒绝无效标签、
失效本地目标和过期矩阵。它不执行测试，也不证明完整覆盖或验证资格。
维护工具的回归在 `scripts/tests/`，不计入 EVAS 测试或原矩阵分母。

## Benchmark 题卡与 review 索引

使用 Python 3.11+；任务元数据由标准库 `tomllib` 读取。

```sh
python3 -B scripts/benchmark_workbench.py --write
python3 -B scripts/benchmark_workbench.py --check
python3 -B -m unittest scripts.tests.test_benchmark_workbench scripts.tests.test_benchmark_package -v
```

`benchmark_workbench.py` 读取 [workbench](../benchmark/material/draftbench/README.md) 的 `catalog.json` 与
逐题 `case.json`，维护历史卡索引与摘要；读取 `tasks.json` 的功能组与卡片关联，
以及各题 `task.toml` 的类别和来源组，生成任务计数、定位链接与设计卡的实现关联。
`--write` 先验证所有元数据与摘要标记，再更新生成内容；`--check` 只读，拒绝重复 ID、
失效来源/电路/证据引用、错误分类路径、旧版本的设计认可和过期索引。
对现有 `vN-*`（N ≥ 2）任务，还拒绝漏登记、缺少题面/来源/元数据及无效任务关联。
旧首批和早期 VA 题包不加入该分母。Benchmark evidence CI 执行 `--check` 与登记回归；
CI 接线不代表每次检查都已执行，实际结果仍按具体作业报告。
题目迁移后，`--write` 删除不再需要且带完整生成标记的类别/家族索引页，保留手写说明。
可用 `--root` 指定另一处同结构目录；其中运行证据路径相对该目录上两级的仓库根目录。
新题包的 `metadata.stage` 决定静态检查层级；单题可加 `--package <task-directory>`，
用 `--stage implementation` 等选项提前核对更高阶段。文件和结果的具体检查边界见
[题包静态检查](../benchmark/material/draftbench/docs/evaluation.md#题包静态检查)。
旧 v2/v3 登记兼容与新格式结果分别报告；静态通过不证明仿真通过、checker 正确或题目达到发布条件。

## 核验冻结的验证集

```sh
python3 -B scripts/verify_validation_version.py
```

`verify_validation_version.py` 默认核验 `validation-v1` 的 Git 对象、快照清单和
原始输入哈希。它只读已有材料，不调用仿真器，也不把当前文件重新登记为旧版证据。
冻结版本的内容与已知问题见 [validation v1](../evas/validation/versions/v1/README.md)。

## 从原始模型重编译 IR

```sh
python3 -B scripts/recompile_evas_manifests.py --output runs/recompile-ir16
python3 -B scripts/recompile_evas_manifests.py \
  --output runs/recompile-selected evas/validation/smoke/idt.json
```

`recompile_evas_manifests.py` 读取 manifest、原始 VA 与实例参数，生成当前版本的 IR
及逐项来源/失败记录。第一条命令默认处理 `evas/validation/smoke/`；第二条只处理指定 manifest。
输出目录必须不存在，便于保留原 IR 和历史结果。

旧 IR 不能通过修改 `schema_version` 迁移；没有对应 VA/manifest 的文件无法由此工具重编译。
脚本不会启动 Rust 内核。部分模型失败时返回非零状态，成功项仍保留在新输出目录中。
兼容性与错误分类见 [IR 版本与迁移](../evas/README.md#ir-v8-migration)。

## 诊断源码清单

```sh
python3 -B scripts/diagnostic_inventory.py --write
python3 -B scripts/diagnostic_inventory.py --check
```

生成 [diagnostic-inventory.json](../evas/docs/development/diagnostic-inventory.json)，记录 Python/Rust
生产源码的诊断构造、包装、转换和处理器。条目都是源码观察，不能作为实际触发覆盖率；
维护范围、动态原因与消费者兼容边界见 [诊断来源](../evas/docs/development/diagnostic-sources.md)。
修改相关源码或登记后重新生成；CI 拒绝旧清单。
