# 真实源电路与适用条件

[JKU analog-circuit-design](https://github.com/iic-jku/analog-circuit-design/tree/5635f2f5bb52968ed6c5d6896b2243d023af7edc) 固定在 `5635f2f5bb52968ed6c5d6896b2243d023af7edc`，Apache-2.0，作者 Harald Pretl 及合作者。原理图与许可在 `source/`。`netlist_schematic.py` 按原符号端口几何转译全部 34 只 MOS 与 3 个零伏电流探针，保留四管偏置栈、MOS 去耦、电气连接、W/L/ng/m 和 symbol 默认 `mm_ok=1`。改编的 `.subckt ota` 顺序是 vinp、vinn、vout、d_ena、ibias_5u、vdd、vss，与原 xschem symbol 顺序不同；调用同步改变，没有电路简化。

源工艺是 [IHP SG13CMOS5L](https://github.com/IHP-GmbH/ihp-sg13cmos5l/tree/597570eec556a473d1eedb22c055545d4522f442)，固定 `597570eec556a473d1eedb22c055545d4522f442`。其 MOS model 文件通过相对符号链接引用 [IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK/tree/5e6d592e4002946a4616f798c357f0f3c06cf3b6)，固定 `5e6d592e4002946a4616f798c357f0f3c06cf3b6`。模型链为 `cornerMOSlv.lib` 的 mos_tt、`sg13g2_moslv_mod.lib`、`sg13g2_moslv_parm.lib`。工艺文件 Apache-2.0，PSP103 的来源/许可声明留在相应原文件。运行使用 ngspice 47、[OpenVAF Reloaded v24.0.2mob](https://github.com/OpenVAF/OpenVAF-Reloaded/releases/tag/v24.0.2mob) 生成的本机 arm64 PSP103 和 PSP103 NQS OSDI。原台架 res_typ 未引用任何电阻模型，改编中省去该无效依赖；不把 50 fF 理想外部负载改成工艺电容。

固定 1.5 V、27°C、tt、50 fF、5 µA 偏置，偏置在 1.1 至 1.2 µs 爬升。输入工作区限定 0.33 至 1.44 V，包含真实高端限幅。低于此范围的微秒漂移没有纳入首题，不主张任意输入共模、PVT 或外部网络适用性。初始 uic 会产生很短的电容数值冲击，全部观察保留，公开误差合同只从 10 ns 开始评分。

`observations/` 是三条完整训练实验，`heldout/` 是三条新输入幅度/方向组合的完整留出实验。它们都是晶体管仿真数据，不是实测数据，也不是 A1 合成真值。候选执行时只获得 vin 和 enable，不获得真实输出前缀或源仿真反馈。静态插值与拟合偏置状态属于作者参考的一种结构，题面不要求采用它。

`source-manifest.json` 绑定实际 deck、原始输出、模型文件和导出观察的 SHA-256；完整 deck/日志/OSDI/波形留在本地 ignored runs。`source-convergence.json` 保存 0.5 ns 与 0.25 ns 实际 source 对照，六条记录最大输出差不超过 1.176 mV，RMS 不超过 0.103 mV。它说明已观察的数值精度，不证明所有 PDK 实例或 Spectre 源移植。
