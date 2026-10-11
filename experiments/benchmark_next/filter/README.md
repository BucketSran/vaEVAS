# 连续滤波、RF变频与测量

本目录实现已批准规格 #149：5道实际VA任务，覆盖C1–C4；C3拆成独立I/Q变频和包络动态。公开题面给出连续状态、频率单位、LO极性、窗口与容差，固定健康材料均可读。当前checkpoint：[参考smoke](reference-smoke.json)的五参考11个实际Spectre条件通过（最终窗末报告保持检查补充之前）；最终26候选58条件的完整作者矩阵仍pending，独立审查尚未完成。历史预检及保留字编译错误已保留；当前未达到spec关闭条件。完整作者校准完成后由 `calibration.json` 绑定最终材料身份。题目文件存在不代表校准成功。本轮不开展模型实验。

| 任务 | 工程动作 | 验收重点 |
| --- | --- | --- |
| `v3-filter-ctle` | 规格建模 | 单零双极归一化、完整幅相、非零初态 |
| `v3-filter-programmable-lp` | 扩展集成 | 原码基线、动态码频映射、连续状态和复位 |
| `v3-filter-iq-conversion` | 规格建模 | 实际输入与LO相乘、和频侧带、下变频低通、使能 |
| `v3-filter-envelope` | 规格建模 | 能量低通、瞬态、禁用衰减与复位 |
| `v3-filter-sweep-measurement` | 测试表征 | 实际扫频、实际输入输出同步积分、低幅及不足窗口无效 |

前四题各两个私有合法条件，测量题三个（包括未稳态）。每题有参考、不同正确实现和三个语义错误版本，测量题另有提前报告负例，共26候选、58个条件位置。完整分母由 `manifest.json` 与 `run-plan.json` 固定。不同参数与工况不增加题数。来源及所有334/364/400/336去向见 [SOURCES](SOURCES.md)。

`build.py` 确定性生成题包和作者候选；不调用模拟器或模型API。`benchmark/checkers/v2_next_filter.py` 是唯一判据源，题包保存执行副本。独立checker从真实波形重建连续状态（分段线性输入与RK4）；CTLE额外计算解析复数频响，I/Q额外核对实际和频分量，测量题对真实波形同步检波。阈值按公开合同固定，随后用作者正负校准报告数值裕量。没有参考波形回放，也不解析候选源码选择评分。

运行命令：

```sh
python3 -B experiments/benchmark_next/filter/build.py
python3 -B -m unittest discover -s experiments/benchmark_next/filter -p test_checker.py
```

实际运行由仓库现有 `experiments/benchmark_first_batch/runtime.py` prepare/execute 和 `batch.py --workers 1` 执行，协调者分配Spectre槽与私有配置。单个候选按条件串行，未知作业恢复原ID。`prepared_only`不算运行；编译、许可、传输或报告失败保留未知，不当成语义错误检出。原始运行放在忽略的 `runs/filter-next-*`，本目录只保留绑定身份的精简报告。

本轮是Spectre扩展集，尚无ngspice候选复验资格。没有模拟噪声、非线性限幅、相噪、镜像抑制或完整接收机性能。FFE/DFE训练、PAM4串并与完整CDR仍属后续方向，不计入本规格完成项。
