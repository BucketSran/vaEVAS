# 仓库维护脚本

本目录保存跨模块的维护工具。仿真器实现和开发测试在 [evas/](../evas/README.md)，
具体实验的运行器与分析器在 [experiments/](../experiments/README.md)。
以下命令均从仓库根目录执行，使用 Python 3.10+。

## CI 按改动选择检查

普通 Markdown / reStructuredText 文档修改只跑静态检查：改动行的空白、追溯矩阵、
冻结输入身份、数学与 checker 校准、论文表的证据规则。不编译 Rust、不运行仿真器、
不构建安装包。静态通过不代表重新完成了 Spectre 对照。

| 改动内容 | 追加检查 |
| --- | --- |
| EVAS 实现、开发测试、VA / JSON 等测试输入、后端实验代码 | 完整 Rust / Python 回归、ngspice 对照、fuzz smoke |
| 安装包中的 Python / Rust 源码、依赖或构建文件 | Linux x86_64 与 macOS arm64 安装测试 |
| Benchmark 输入、checker 或实验工具 | Benchmark 身份、独立判据和题目来源检查 |
| CI 配置、检查选择器或未知的非文档路径 | 全部检查 |

题目的 Markdown 指令属于 Benchmark 输入，不能当成普通说明文档跳过。
混合修改取所需检查的并集；删除、重命名同样参与选择。PR 按分叉点至最新提交的完整 Git
差异选择，main 推送按推送前后的提交选择；不使用有文件数量上限的路径过滤。
差异身份缺失、首次推送或手动 `workflow_dispatch` 时运行全部相关检查。

规则集中在 [ci_selection.py](ci_selection.py)，三个工作流通过
[select-checks.yml](../.github/workflows/select-checks.yml) 调用。
每个工作流始终提供一个结果检查，只允许明确未选中的任务跳过；选中的任务失败、取消
或意外跳过均不能通过。需要设置分支必需检查时，选 `numerical-result`、`package-result`
和 `benchmark-result`，不要把会按需跳过的编译或安装任务设为必需检查。
同一 PR 的新推送会取消该 PR 的过期 CI。main 推送和手动运行互相独立，不自动取消：
后来的文档推送不能取消前一版代码尚未完成的回归。

```sh
python3 -B -m unittest discover -s scripts/tests -p test_ci_selection.py -v
```

回归使用真实临时 Git 仓库，检查纯文档、混合修改、删除、重命名、分叉点和身份缺失，
并验证必需任务失败或跳过时结果检查会拒绝。这里不修改模拟器判据或历史成绩。

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

导航使用普通 Markdown 行内链接，例如 `[任务](task/)`；含空格的路径可以百分号编码或
放在尖括号中。检查器排除 HTML 注释和代码中的示例链接，不解析完整 Markdown 或 HTML；
引用式链接不属于索引格式。索引可附带指向现有草稿文件的链接，已消失的本地目标会报错，
包括不带尾斜杠的旧目录链接。`worktrees/` 内的目录链接用于活动工作区入口；
草稿材料使用文件链接，目录外的日常入口与归档导航不按工作区入口判定。

开始或恢复编辑、新建工作区以及交接时运行同一个命令。返回值 `0` 表示可见性检查通过，
`1` 表示入口缺失或失效，`2` 表示 Git 或文件检查未完成。命令只读，不创建、移动、提交、
合并或删除工作区，也不访问网络。JSON 包含每个 checkout 的分支、HEAD、未提交及未跟踪
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
忽略材料报告。现有 Numerical assurance CI 的 `scripts/tests` 步骤会执行这些回归，
但远端 CI 不检查开发者电脑上的工作区。没有安装全局 hook；agent 必须实际调用检查器。

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

```sh
python3 -B scripts/benchmark_workbench.py --write
python3 -B scripts/benchmark_workbench.py --check
python3 -B -m unittest discover -s scripts/tests -p test_benchmark_workbench.py -v
```

`benchmark_workbench.py` 读取 [workbench](../benchmark/workbench/README.md) 的 `catalog.json` 与
逐题 `case.json`，维护总览、类别/家族索引、review 队列、同源分组及题卡摘要。
`--write` 先验证所有元数据与摘要标记，再更新生成内容；`--check` 只读，拒绝重复 ID、
失效来源/电路/证据引用、错误分类路径、旧版本的设计认可和过期索引。
题目迁移后，`--write` 删除不再需要且带完整生成标记的类别/家族索引页，保留手写说明。
可用 `--root` 指定另一处同结构目录；其中运行证据路径相对该目录上两级的仓库根目录。
静态通过只说明登记与索引一致，不证明仿真通过、checker 正确或题目达到发布条件。

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
