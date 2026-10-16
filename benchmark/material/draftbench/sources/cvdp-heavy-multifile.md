# CVDP heavy 1.1 的交付约定与验收质量

2026-10-15 静态核对官方说明、执行代码与真实数据。此笔记支持多文件题包约定与验收设计讨论，没有审核或修改本项目具体题目，没有运行模型、Docker 或仿真。

## 固定来源

- 官方 runner 仓库 `NVlabs/cvdp_benchmark`，读取版本 `8e894cf74414ab1eaea1e2b4e80a02f123df07b6`。这是读取时的 HEAD，并非声称它是最初发布 v1.1.0 时的代码。
- [README_AGENTIC](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/README_AGENTIC.md)、[heavy 使用说明](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/README.md#context-heavy-agentic-datasets)。README 的一般 docs/rtl/verif 示例不能替代 heavy 分支代码。
- 官方 HF 数据集 `nvidia/cvdp-benchmark-dataset`，revision `5b807d945f6a99aa645f7e43a64a2115e281b4bf`。实读 [v1.1.0 heavy no_commercial JSONL](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl)，以及[公开 repo bundle 清单](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/tree/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_public)。多文件交付约定部分未读取设计 bundle；下方质量分析另复用本地 RVX bundle。所有分析均未运行设计。

## 工作区如何准备

每条 heavy 数据有 `context.repo` 与 `context.commit`。runner 通过 `CVDP_HEAVY_REPOS_PATH` 找同名目录或 `.bundle`，两者同时存在时优先目录。它从 mirror fetch 并 checkout 指定 commit，再把需要的树复制进 Docker workspace volume。对于名称匹配 CVDP 且不是 `_ext_` 的 repo，代码选 `external/` 的内容；`_ext_` 等情况选 repo 根。原 repo 的目录结构由这一步决定，不能由 heavy 标签推出统一的 RTL 子目录。[repo 解析](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/git_utils.py#L74-L101)、[checkout 与复制](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/git_utils.py#L457-L501)、[heavy 准备分支](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2816-L2865)。

agent 容器的工作目录为 `/code`。workspace volume 挂 `/code`；题面文件另挂 `/code/prompt.json`，内容只有 `prompt`；运行目录另挂 `/code/rundir`。普通 agent run 不应用参考解 patch；golden run 才按条件应用。[prompt 内容](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L1445-L1446)、[agent 挂载](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L1984-L2007)、[参考 patch 条件](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2844-L2855)。

## 题面如何区分修改目标与材料

实读例子来自上面的固定 JSONL。行号是文件的一基行号，ID 是更稳定的定位键。

| 例子 | 题面明确给出的路径和动作 | 能确认的边界 |
| --- | --- | --- |
| 第 1 行 `cvdp_agentic_heavy_rvx_0004`，context commit `941d71dd5c96c64379abd8485c4ba6bc70429415` | 在 `/code/hardware/rvx.v` 实现顶层，集成各子模块，并明确要求不修改子模块内部功能 | 有明确目标文件与依赖功能限制。不能把子模块存在解释为可任意改写 |
| 第 15 行 `cvdp_agentic_heavy_axis_0001`，context commit `8f6b683798cf4367cb0522415a85f2cd9a312db0` | 列出 `/code/src/axis_switch.v`、`arbiter.v`、`priority_encoder.v` 与 supporting `axis_register.v`；要求修复前三个模块 | 真实多文件目标，repo 的 `src/` 是设计代码；不能将 heavy 的 `/code/src/` 统一当作测试基础设施 |
| 第 69 行 `cvdp_agentic_heavy_pulpino_0004`，context commit `f0aa3cf681e2e8fc39d630b5e30b66026ebb73d0` | 要求修改 `axi2mem.sv`、`core2axi.sv`，阅读 related modules；`patch` keys 为 `rtl/axi2mem.sv`、`rtl/core2axi.sv` | 此题题面只给文件名，没有另一题那样的绝对路径格式 |

这些例子说明题面可以直接描述“修改哪些模块、其余文件起什么作用”。没有证据表明所有 heavy 题都有统一的 editable 文件清单。JSON 的 `patch` 是参考解数据；例如 axis 题的 keys 还包含 `tb/test_axis_switch_4x4.v`，题面却指定三个 RTL 模块。没有找到 heavy 分支将 `patch` keys 作为 agent 修改白名单的实现，不能拿它当权限合同。[heavy agent 处理](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2414-L2445)。

## 最终收集什么

agent 的任务是修改挂载文件并正常退出。它无需把完整文件、patch 或答案代码打印到最终消息中。runner 在 agent 前复制 workspace 为 before snapshot；结束后执行 `diff -ruN before after`，将结果保存为 `agent_changes.patch`。因此 agent 的实质交付是修改后的文件树，patch 是 runner 生成的记录。[官方要求](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/README_AGENTIC.md#agent-requirements)、[snapshot](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2764-L2793)、[diff](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2706-L2744)。

该差分不调用 `git diff`，也不按 tracked/untracked 过滤。按代码推断，工作树中的普通新文本文件不需 `git add` 就会进入差分，删除与修改同样记录。不过它排除匹配 `.*` 的文件和目录、`prompt.json`、`rundir`。这不是“任意新增文件都能提交”的合同：隐藏新文件会遗漏；二进制文件、权限变化、符号链接等也不能据此保证可由该文本 patch 完整复原。此处只读实现，没有运行实验验证这些边界。

## 终评与固定测试

正常 heavy 流程开始时根据 context commit 准备基线；agent 运行后保留同一个 workspace volume 给测试使用。`AgenticRepository.docker_cmd` 把它挂到测试容器 `/code`，另把数据集 harness 恢复出的 host `src` 挂到 `/src`、运行目录挂 `/rundir`。所读流程没有在 agent 完成后重新 checkout 干净基线再应用 `agent_changes.patch` 的步骤，不能把这种更强的重建流程归为 CVDP 已有保证。[测试材料恢复与挂载](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/repository.py#L1079-L1117)、[volume 保留说明](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2219-L2239)。

默认 `include_harness=False`。只有显式开关才把 host `./src` 与 compose 挂到 agent 的 `/code/src` 等位置。此选项与 repo 自身的 `src/` 路径不能混为一谈。harness 的源内容来自每条数据的 `harness` 字段，runner 还会做镜像占位符、网络等配置处理；不是整个 host harness 目录都以不可写挂载运行。已查看 pulpino 题使用 `/src/:ro`，axis 题的 `/src` 则没有 `:ro`。固定材料应理解为来源与角色固定，不能泛化为所有容器挂载都有强制只读权限。[默认设置](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L1797-L1805)、[可选暴露](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/dataset_processor.py#L2035-L2052)、[harness 恢复处理](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/src/repository.py#L230-L258)。

对本项目可借鉴的事实是“题面给目标路径与依赖说明、agent 留下文件树、外部测试读取它”。本项目的修改范围、文件收集和独立终评恢复要求属于自己的明确合同，不能声称 CVDP heavy 已统一规定。2026-10-15 用户确认后的规则见[多文件交付约定](../docs/task-package.md#多文件工程的交付约定)。

## 工程目标与验收质量

2026-10-16 从已有本地材料复核下面三个样例的题面与 harness，来源仍为上述固定 revision 的 no_commercial JSONL。`harness` 文件名是数据对象中的键。此处是三个样例的静态审查，不是全题集质量统计；没有运行模型或仿真。工程目标、修改范围和验收有效性需要分别检查，不能由文件数或 `hard` 标签判断。

| 样例与固定上下文 | 工程目标 | 已有验收与缺口 |
| --- | --- | --- |
| [ENSO 0003，第 23 行](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L23)，`7253c1db09d8a345705bd9b600e817ae4fecb80d` | 只修改 `flow_director`，增加 fallback round-robin，保留 hash 路径并处理零队列丢包。单模块也涉及状态、配置切换和 ready/valid 兼容 | `test_flow_director.py` 与 `harness_library.py` 逐周期比较 15 项输出，包含元数据和握手信号。但队列选择使用 `nb_fallback_qs - 1` 掩码，随机队列数不限于 2 的幂，不能据此证明任意队列数均匀轮询 |
| [EDMA 0008，第 52 行](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L52)，`3db01f510dbb2e9bcc34b5729a1c6e930343c7a6` | 新增安全 checker、寄存器地址 8/9、controller 违规停止和恢复，并连接顶层配置及 IRQ。交付必须从配置入口到系统反馈形成完整路径 | 测试地址宽度 32/64，各重复五次，覆盖 IRQ、安全关闭与 packet 比较。但 `expect_transfer` 立即读取 `packet_out`，部分回读循环没有超时失败断言，不能由测试数量推出事务和违规停止均已验证 |
| [RVX 0002，第 42 行](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L42)，`44d5040e26bd2da5d3ccbe9c6a5b15d2d37e8ad9` | 修复既有顶层互连，题面描述事务无应答、外设无活动、中断不触发。需要对照实际接口和信号流定位 | `test_rvx.py` 驱动请求、打印读回及 IRQ；AST 中 assert、if、raise 均为 0，没有等待应答并比较预期。运行完成和日志不能证明故障已修复 |

ENSO 和 EDMA 仅核对 JSONL 中的题面与 harness，没有检查对应设计 bundle 或独立运行 testbench。RVX 另静态读取已有[官方 bundle](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_public/cvdp_agentic_heavy_rvx.bundle) 在指定 commit 的 `external/hardware/rvx.v`：`NUM_DEVICES=4` 却定义 `D4_SPI=4`，缺少 SPI 实例和 timer 地址区间赋值，UART IRQ 没有接回固定为零的 `irq_fast`。这些是静态代码问题；没有复现死锁、检查全部子模块或确定必要且充分的修复，不能作为实际故障根因结论。

对本项目的启示是：题面先说明交付后的行为变化和必须保留的旧行为，再提供解决它所需的接口、调用关系和失败证据。验收应直接检查承诺，例如等待事务应答并核对数据、检查违规窗口内的总线活动、保留旧路径场景；每个等待都必须能在限定时间后失败。这些是选题与验收设计建议，不是 CVDP 官方定义，也不新增本项目的正式评分题。
