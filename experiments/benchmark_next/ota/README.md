# OTA 连续动态任务

这条路线把规格 #147 的三种工程动作建成三道独立题。A1 根据连续状态方程建立固定负载的电压模型；A2 用真实 JKU OTA 的完整晶体管仿真轨迹建立自由运行模型；A3 编写双向阶跃与有限窗口测量模块。三题共享来源组 `jku-ota-dynamics`，每题权重 1，参数变化不增加题数。

| 任务 | 交付与独立验收 |
| --- | --- |
| `v3-ota-continuous` | VA 电压放大模块。解析压摆加指数建立判据检查全部输入、关闭、限幅与恢复历史。 |
| `v3-ota-data-model` | VA 自由运行模型。独立新完整源电路实验分别验收启动、小阶跃、大阶跃、高端限幅、恢复、重启和长尾。 |
| `v3-ota-step-measurement` | VA 激励与在线报告。实际输入和 enable 必须满足整个实验协议，指标由真实 vout 波形独立重算。健康、慢响应和限幅 DUT 都有明确报告状态。 |

与既有离散 gain-settling 的差别是，A1/A2 没有采样时钟或每拍递推，输出是随时间持续演化的状态。A3 测量双向连续阶跃、采样压摆和最后入带时刻，不能用 DUT 内部的资格位代替波形。即使 DUT 在窗口内未建立，正确报告 timeout 仍能通过。

## 真实源电路与适用条件

[JKU analog-circuit-design](https://github.com/iic-jku/analog-circuit-design/tree/5635f2f5bb52968ed6c5d6896b2243d023af7edc) 固定在 `5635f2f5bb52968ed6c5d6896b2243d023af7edc`，Apache-2.0，作者 Harald Pretl 及合作者。原理图与许可在 `source/`。`netlist_schematic.py` 按原符号端口几何转译全部 34 只 MOS 与 3 个零伏电流探针，保留四管偏置栈、MOS 去耦、电气连接、W/L/ng/m 和 symbol 默认 `mm_ok=1`。改编的 `.subckt ota` 顺序是 vinp、vinn、vout、d_ena、ibias_5u、vdd、vss，与原 xschem symbol 顺序不同；调用同步改变，没有电路简化。

源工艺是 [IHP SG13CMOS5L](https://github.com/IHP-GmbH/ihp-sg13cmos5l/tree/597570eec556a473d1eedb22c055545d4522f442)，固定 `597570eec556a473d1eedb22c055545d4522f442`。其 MOS model 文件通过相对符号链接引用 [IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK/tree/5e6d592e4002946a4616f798c357f0f3c06cf3b6)，固定 `5e6d592e4002946a4616f798c357f0f3c06cf3b6`。模型链为 `cornerMOSlv.lib` 的 mos_tt、`sg13g2_moslv_mod.lib`、`sg13g2_moslv_parm.lib`。工艺文件 Apache-2.0，PSP103 的来源/许可声明留在相应原文件。运行使用 ngspice 47、[OpenVAF Reloaded v24.0.2mob](https://github.com/OpenVAF/OpenVAF-Reloaded/releases/tag/v24.0.2mob) 生成的本机 arm64 PSP103 和 PSP103 NQS OSDI。原台架 res_typ 未引用任何电阻模型，改编中省去该无效依赖；不把 50 fF 理想外部负载改成工艺电容。

固定 1.5 V、27°C、tt、50 fF、5 µA 偏置，偏置在 1.1 至 1.2 µs 爬升。输入工作区限定 0.33 至 1.44 V，包含真实高端限幅。低于此范围的微秒漂移没有纳入首题，不主张任意输入共模、PVT 或外部网络适用性。初始 uic 会产生很短的电容数值冲击，全部观察保留，公开误差合同只从 10 ns 开始评分。

`observations/` 是三条完整训练实验，`heldout/` 是三条新输入幅度/方向组合的完整留出实验。它们都是晶体管仿真数据，不是实测数据，也不是 A1 合成真值。候选执行时只获得 vin 和 enable，不获得真实输出前缀或源仿真反馈。静态插值与拟合偏置状态属于作者参考的一种结构，题面不要求采用它。

`source-manifest.json` 绑定实际 deck、原始输出、模型文件和导出观察的 SHA-256；完整 deck/日志/OSDI/波形留在本地 ignored runs。`source-convergence.json` 保存 0.5 ns 与 0.25 ns 实际 source 对照，六条记录最大输出差不超过 1.176 mV，RMS 不超过 0.103 mV。它说明已观察的数值精度，不证明所有 PDK 实例或 Spectre 源移植。

## 作者实现与校准

`build_tasks.py` 生成 Harbor 任务、公开材料和正负变体；`calibration-plan.json` 登记完整分母。参考与不同正确实现都必须在固定 Spectre 后端通过，错误版本必须实际编译执行后由语义判据拒绝。编译故障和缺波形保持未评分，不能计为拒绝负例。

原 `solve.sh` 经 Harbor Docker 执行后产生原候选字节，A1/A3 的六个留出参考条件与 A2 的三个留出参考条件已实际 Spectre 通过。首次编译故障（`Meg` 后缀、`slew`/`current` 保留字）保留为未评分证据。随后已完成最终全变体实际校准，结果和身份见 [final-calibration.json](final-calibration.json)。

早期原脚本入口使用 Python 镜像 tag，未保存实际镜像 receipt，因此当时的镜像身份未知。补充入口验证使用三题 Dockerfile 固定 digest、关闭容器网络，重新执行原 `solve.sh`。三份产物与最终实际 Spectre 参考候选字节完全一致，见 [reference-entry-receipt.json](reference-entry-receipt.json)，其中记录实际 image ID、RepoDigest、命令、脚本与产物 SHA-256 和时间。该验证是后续补充执行，不倒填旧校准的执行身份，也没有重新运行科学矩阵。`verify_reference_entries.py` 可重复此检查；`calibrate.py` 后续参考入口使用同一固定镜像与 receipt 路径。

连续模型用 `idt`，合法替代用电容电流方程 `ddt`。数据模型从完整训练轨迹辨识静态曲线、非线性二阶响应与偏置启动状态；替代模型使用 `ddt` 实现同一已拟合自由运行状态。测量模块的参考实现保存数组后计算指标，替代实现在线累积压摆而后扫描末窗。负例覆盖静态跟随、错误单极点、正负压摆混同、关闭错误清状态、漏启动、恢复清状态、单向测量、first-entry、沿用旧 valid、参数冒充测量和 pulse-only 刺激。

最终选定 19 个变体、57 个条件全部实际成功评分：6 个正确实现的 18 条件全通过；13 个语义负变体均在可区分条件被检出，39 个负例条件中 38 个拒绝。A3 old-valid 在慢 DUT 上通过，因为前五轮 valid 都为 0，第六轮首次为 1 后没有下一次 launch；该通过保留，不计拒绝。

初版恢复负例只把状态从约 1.34 V 推到 1.3 V，其三个条件仍符合公开近似误差预算，不能算 checker 失败或负例检出。该候选字节和完整通过结果保留于 `candidates-superseded/`、[initial-calibration.json](initial-calibration.json)。最终负例在退出高端区时错误地把输出与速度清到初态；它造成公开恢复窗口的输出误差，追加三条件全部实际拒绝。包含初版的实际作者校准总分母为 60，没有删除其通过结果或扩大误差限。

A1 判据的 25 ps 与 12.5 ps 网格对照最大差 3.08 µV，见 [checker-convergence.json](checker-convergence.json)。误差容差按公开用途固定，小阶跃使用较小绝对误差，大阶跃和启动允许近似模型误差。独立 checker 对每一动态窗口单独计算 RMS 和峰值，静态段不能稀释错误。数据真值身份固定在 checker 中；修改真值记录会成为环境错误。A3 的启动、每轮刺激全段、报告清零与完成后保持也独立检查。

A1 原题面写 −0.2 至 1.8 V，而固定留出含 −0.213/1.813 V。交付题面已纠正为 −0.22 至 1.82 V。规格身份因此改变，已有执行身份保留；方程、实现、实际台架和 checker 均未改变。另将解题包的 source README 限定为来源说明，移除作者校准叙述。原、新 instruction SHA-256、精确 diff 与执行复用映射见 [criteria-update.json](criteria-update.json)。`calibration-material-manifest.json` 与 `replacement-material-manifest.json` 保存两次实际执行准备版本；`material-manifest.json` 是最终交付版本，不能混称同一个包。

本路线不运行模型解题实验。作者校准、Harbor 原参考脚本入口和正式发布分别记录，不以目录存在表示完成。当前候选固定 Spectre；原源电路能在 ngspice 运行，不等于候选 VA 已获得同题开源复验资格。

## 重建入口

先取得上述固定工艺版本及本机 PSP OSDI，再运行：

```sh
python3 -B experiments/benchmark_next/ota/source/netlist_schematic.py
python3 -B experiments/benchmark_next/ota/source/generate.py \
  --pdk /absolute/ihp-sg13cmos5l --osdi /absolute/psp103.osdi \
  --output /absolute/new/source-run --step 5e-10
python3 -B experiments/benchmark_next/ota/build_tasks.py
python3 -B experiments/benchmark_next/ota/test_contract.py
```

实际作者校准入口：

```sh
python3 -B experiments/benchmark_next/ota/calibrate.py \
  --operator /absolute/private/operator.json --harness /absolute/circuit-harness \
  --revision new-calibration
```

历史 final-r1 与 final-r2 的合并分析可用 `collect_calibration.py --revision final-r1 --replacement-revision final-r2 --output /absolute/report.json` 重建。最终 manifest 绑定当前交付字节，新校准直接运行当前 19 个变体。

该入口顺序执行，每次最多一个在途；没有资源授权时不要运行。`--slug` 与 `--variant` 可限制单组，失败必须保留并按原 job ID 恢复，编译修复才生成新的候选身份。

拟合脚本需要 NumPy 与 SciPy；任务 verifier 只依赖标准 Python。固定源输出用于训练和独立留出评分，终评不重新查询源电路。生成新源记录或修改合同后必须更新冻结身份并重做有关实际作者校准，不能只重放旧分数。
