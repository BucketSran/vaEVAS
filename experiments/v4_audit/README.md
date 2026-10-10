# benchmarkv4 静态设计审核

按电路家族整理旧 v4 的 DUT、Testbench、Bugfix，再用 Claude Code 的 `glm-5.3`
通道生成待复核建议。此工具不执行候选、不调用仿真器、不修改原资产，也不把模型意见变成正式题目准入。

## 范围与输入

输入是 `benchmark/reference/v4/release/benchmarkv4-r53/tasks/` 的400家族、1200包，
以及相应 provenance 的 derivation、mutation、认证和任务记录。每家族一请求。
任务包全部文本入包，完全相同的文件按 SHA256 合并展示，同时列出全部原路径和原行号。
重复网表行用已展示的原行引用；重复JSON字段值用已展示的相同值引用，允许对象键顺序不同。
原位置及哈希仍保留，VA源码完整展开。另按实际 VA 字节比较 Bugfix starter 与同家族 TB 负例，
将实际匹配和旧 manifest 所称 seed 分开保存。

审核要求见 [audit_prompt.md](audit_prompt.md)。报告分别判断电路含义、规格、参考实现、
故障身份和验收，再建议进入五类中的哪些方向。不能假设原私有 checker 已提供或可运行，
不能把人工 mutation 说成真实工程故障，不沿用旧语言子集、统一后端或三形态配额。

## 执行与恢复

在仓库根目录执行；需 Python 3.10+、已配置 GLM 通道的 Claude Code 和 tmux。
凭据只由 CLI 从用户配置读取，不进入 prompt。CLI 在临时空目录中运行，关闭工具、
自定义指令、插件和 MCP；审核者不能读取环境变量或修改仓库。

```bash
python3 -B experiments/v4_audit/run.py prepare --run-dir runs/v4-audit-20261010-r3
python3 -B experiments/v4_audit/run.py run --run-dir runs/v4-audit-20261010-r3 --families 001,024,102,249 --workers 4
python3 -B experiments/v4_audit/run.py status --run-dir runs/v4-audit-20261010-r3
```

先核对试审的模型身份、报告内容和最大输入，再省略 `--families` 展开全量。
2026-10-10 的 r3 审核已完成400家族，首轮8路、补跑4路；原会话已结束。
运行日志仍保存在本地 `runs/v4-audit-20261010-r3/full.log`。
完整结论见[优先清单](../../benchmark/workbench/migration/v4-migration-priorities.md)，
调用统计与恢复例外见[紧凑摘要](../../benchmark/workbench/migration/v4-audit-summary.json)。
默认每次调用上限 USD 5、15分钟、32000输出token；模型思考使用 high。
首轮最多400次正常调用，失败不自动重试。限额是 CLI 护栏，CLI 成本估计不等于供应商账单。
预算或输出截断失败须保留响应、调整对应资源后再明确重试。不能仅因退出码为0认定完成。

`run` 跳过已通过结构校验的草稿；失败尝试保存为 `attempt-01/` 等独立目录。
同一 run 的监督进程用排他锁防止重复派发。SIGTERM/SIGINT 会停止派发并回收 CLI。
SIGKILL 或系统崩溃无法捕获；此时须核对锁中的 supervisor PID，以及执行记录中的
`child_pid` / `child_process_group`，确认监督进程和所有仍运行的 CLI 进程组都已结束，
再处理遗留锁。创建 run 目录中的 `STOP` 文件会停止新派发并终止运行中的子进程组；
恢复须显式移除 STOP。不要删除失败日志。

## Review 入口

run 目录的 `INDEX.md` 按400个家族展示 pending、running、failed、accepted_draft 等状态，
链接逐家族 `review.md`。同目录 `status.json` 记录覆盖分母和 CLI 用量；
`reviews.tsv` 保留全部1200个任务的状态、模型建议、工程价值和下一步，未完成的条目留空；
`families/<id>/input.json` 保存所有输入路径、哈希、行数；`prompt.md` 保存实发内容；
每次尝试的 `stdout.json`、`stderr.log`、`execution.json`、`response.txt` 保存原响应及执行身份。

`accepted_draft` 仅表示身份、三形态、必读资产声明、引用路径/行号和字段校验通过。
它不能证明模型确实理解所有材料，也不能证明发现正确。须抽查具体反例、对照原文件，
再把核实结论写回设计卡。缺参考工程、缺 checker 或需要仿真的事项继续保留为未知。
400个家族有草稿与1200道题已具备可信验收是不同交付。

本轮运行与审核结论入口见[迁移讨论记录](../../benchmark/workbench/migration/README.md)。
大体积输入和原响应仅保留在 ignored `runs/`，进入仓库的结论应经过复核并保留来源身份。
