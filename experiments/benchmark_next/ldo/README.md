# 真实 LDO 启动与响应实验

本路线实现规格 #148 的两个工程目标。B1 是只读测量模块，B2 驱动规定的供电和负载命令，并根据实际输出决定实验进度。两题使用同一个真实 OTA5 LDO，同源组为 `adb-ldo-ota5`，每题权重 1。

最终 r7 作者校准已完成：17 个实现、51 个实际条件全部编译并仿真成功，四个正确实现的 12 个条件全部通过，13 个语义错版各有至少一个条件被拒绝。交付证据见[作者报告](author-calibration.md)；这是分支证据，不能据此宣称已合并支持。

| 任务 | 交付差异 | 独立验收 |
| --- | --- | --- |
| [B1 启动测量](../../../benchmark/material/draftbench/batches/v3-01/tasks/v3-ldo-startup-measurement/instruction.md) | 固定激励下开发只读 VA 测量模块 | 从实际输出的固定采样点重算 t90、过冲和有限窗口建立，包括不足目标和末尾资格不足 |
| [B2 响应实验](../../../benchmark/material/draftbench/batches/v3-01/tasks/v3-ldo-response-experiment/instruction.md) | 开发可驱动允许命令的完整 VA 测试台 | 验证真实 line 和 load 扰动、阶段顺序、实际资格或超时，以及每阶段重置后的峰值、偏移和恢复 |

两题没有合并。B1 的激励完全固定，测量必须等待完整窗口才能确认此后全部样本入带。B2 的下一阶段发生时间由实际连续入带资格或超时决定，候选承担实验组织职责。原始 341、372、340 是后续软启动、PWM 和热保护素材，本批没有据此新增任务。

## 测量准确性与 DUT 合格性分别判断

目标来自公开规格 1.2V。B1 的 t90 是最早满足 90% 且此后到观察末端都不再低于门限的采样时刻。建立从供电斜坡结束计算，要求此后全部样本在目标 ±2%，并明确要求末 20 个样本的资格。若输出一直只有 1V，正确结果是未达目标和未建立。checker 接受正确报告，不要求 DUT 强行合格。

B2 每次扰动独立积累实际偏差。连续入带 20 个样本、完成最短观察窗口后才允许推进，超时则给出明确失败状态并继续规定实验。比如输出先进入带内又振铃出带，资格和恢复起点会重新开始。独立 checker 直接使用实际波形重建流程，候选的状态端或 PASS 文本都不能代替判据。

本题明确使用离散采样定义，采样间隔 50ns。时间报告容差 75ns 覆盖一个采样格及波形数值重建差异。峰值和偏移容差 0.3mV，状态容差 2mV，供电命令与实际供电误差 1mV。状态和报告边沿允许 5ns 过渡，命令边沿为 1ns。固定零压探针保存候选每个只读端的实际电流，绝对值上限 0.1nA。不同正确实现包含 1TΩ 极小输入负载，可验证上限允许合理观测形式。1MΩ 负载和直接电压驱动是独立作弊负例。算法校准与实际候选校准见[作者报告](author-calibration.md)。

## 来源、适配与许可

原电路来自 [Analog Design Bench 固定提交](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ldo-ota5-robust-pvt-mc)。[ldo_ota5.spi](source/ldo_ota5.spi) 为原参考电路字节，仍然包含输入差分对、镜像负载、尾电流与偏置管和 PMOS pass 管。反馈保持 300kΩ/600kΩ，参考输入 0.8V，偏置 50µA，输出网络保留 ESR 和实际电容。B1 在公开范围改变固定斜坡、负载、电容和供电高值。B2 增加命令到供电电压的固定受控源，以及命令到实际额外负载电流的固定 VA 适配器。候选只驱动命令，不承担电流负载模型。

电路与原始测试台是 CC-BY-NC-4.0 内容，原作者为 Analog Design Bench contributors。任务公开目录保留[上游许可说明](source/UPSTREAM-LICENSE)和[完整许可正文](source/CC-BY-NC-4.0.txt)。自有测量模块和 checker 没有复制上游 Python 评分实现。SKY130 依赖来自 [google/skywater-pdk-libs-sky130_fd_pr](https://github.com/google/skywater-pdk-libs-sky130_fd_pr/tree/f62031a1be9aefe902d6d54cddd6f59b57627436)，固定提交 `f62031a1be9aefe902d6d54cddd6f59b57627436`，单独保留 [Apache-2.0 许可](source/PDK-LICENSE)及模型文件原版权说明。

[raw_models.spice](source/raw_models.spice) 由既有源数据生成器递归展开 lod、nfet 和 pfet 的 TT 与 mismatch 文件，参数不改。Spectre SPICE 导入需要两处格式适配。`prepare_models.py` 先核实确定性 TT 的随机 slope 为 0，化简对应的零贡献项，再将花括号表达式转成单引号表达式。数值参数和器件拓扑保持，变化数及字节身份见[翻译记录](source/model-translation.json)。[实际 ngspice 复核](source-calibration.json)包含原始与适配模型的三种完整启动仿真；它验证源适配，不代表候选 VA 已通过 ngspice。

两题固定 Spectre，属于商业仿真器扩展集。没有用理想斜坡或虚构二阶 DUT 替代实际电路，也没有宣称 VA 配套模型已经具有开源等价性。源电路可在 ngspice 运行，候选测量和电流环境的开源执行资格仍未建立。本题没有 EN、shutdown 或 PG，也不增加休眠唤醒行为。

## 重建与作者校准

在仓库根目录执行下列命令。模型试做不在这些命令中。

```sh
python3 -B experiments/benchmark_next/ldo/prepare_models.py
python3 -B experiments/benchmark_next/ldo/build_tasks.py
python3 -B -m unittest discover -s experiments/benchmark_next/ldo -p 'test_*.py' -v
python3 -B experiments/benchmark_next/ldo/generate_source.py --output runs/ldo-source-reproduction
```

`manifest.json` 登记参考、不同的正确实现及可编译的语义错版。`calibrate.py` 使用现有 `v2_runtime.py` 与 circuit harness，原参考先在固定 Python Docker 镜像执行 `solution/solve.sh`，再封存其实际产出的 VA。远端配置仅由操作者传入，不入库。协调者分配一个 Spectre 槽后执行：

```sh
python3 -B experiments/benchmark_next/ldo/calibrate.py \
  --config /absolute/private/operator.json \
  --output runs/ldo-author-calibration
```

完整原始波形与所有失败尝试保留在忽略的 `runs/ldo-calibration/`，精简证据绑定候选、判据、源文件、后端和归档摘要。数值容差仅限定上述公开采样合同，校准不能证明所有可能错误都能被识别。公开自测材料与私有条件分别封装，候选解题包不含参考、checker、错版或隐藏实例。
