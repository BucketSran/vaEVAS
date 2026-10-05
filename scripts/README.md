# 仓库维护脚本

本目录保存跨模块的维护工具。仿真器实现和开发测试在 [evas/](../evas/README.md)，
具体实验的运行器与分析器在 [experiments/](../experiments/README.md)。
以下命令均从仓库根目录执行，使用 Python 3.10+。

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
包括不带尾斜杠的旧目录链接。

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
规则和收尾要求见 [CONTRIBUTING](../CONTRIBUTING.md#workspace-visibility-and-handoff)。
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

`traceability.py` 读取测试 GUARDS 标签、能力表证据入口和 DUT 目录，生成
[追溯矩阵](../evas/docs/TRACEABILITY.md)。`--check` 不写文件，拒绝无效标签、
失效本地目标和过期矩阵。它不执行测试，也不证明完整覆盖或验证资格。
维护工具的回归在 `scripts/tests/`，不计入 EVAS 测试或原矩阵分母。

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
