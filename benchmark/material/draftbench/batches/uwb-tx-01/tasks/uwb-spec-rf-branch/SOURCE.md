# uwb-spec-rf-branch 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的 RF 支路 RO，行为约定见 [ir-uwb-tx/SPEC.md 第 4.8 节](../../../../circuits/ir-uwb-tx/SPEC.md#48-rf-支路-rouwb_rf_ro_branch)。需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）：§7.2 预充电与释放（pwr 低时关断、pre 高且 rel 低时预置不振荡）；§8 种子参数“幅度、频率 99% 建立各 200 ps”（τ = 200 ps / ln 100 = 43.4 ps）和“启振额外频差约 1%”（df_start 默认 +0.01）；§5.4 要求写明局部相位（相位按释放后的局部时间累积，保持期间连续，不在符号边界重置）。
- 关断时机：调度器（SPEC 4.7）在支路 ACTIVE/TAIL/HOLD 期间保持 rel 高，转 OFF 时 rel 与 pwr 一起拉低；受控尾部由包络通道产生（SPEC 4.9），不在 RO 里。所以 rel 或 pwr 下降即停振、输出立即归零。
- 架构背景：多 RO 选频、主 RO 抽头产生位置格点的做法见 SPEC 第 3 节引用的 Lei 等，[JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077)。本模块的起振公式不出自该论文，是按原 SPEC §8 种子参数取的一阶建立模型。
- 参考解与系统资产中的 [rf_ro_branch.va](../../../../circuits/ir-uwb-tx/module/rf_ro_branch.va) 相同，只把模块名 `uwb_rf_ro_branch` 改为 `rf_ro_branch` 并改注释。系统资产的独立检查是 `circuits/ir-uwb-tx/test/m3_pulse/check_rf.py` 的 `scenario_branch`，本题 checker 由它移植扩展。

## 建模选择

- 预期难度：中。考点是相位要写成频率的积分（不是 f(u)·u）、τ = t99/ln 100、相位按释放局部时间计并在每次冷启动从 phi0 重来、只有 pwr 高时的 rel 上升才释放、rel 或 pwr 任一下降立即停振，以及 t99 = 0 的理想支路。
- 参数默认值取 SPEC 4.8。允许范围是本题的选择：f_rf 4–8 GHz 覆盖 8 个载频 4.5–7.5 GHz；a_ro 0.1–1.5 V；t99 0–1 ns；df_start ±5%；phi0 ±π；vth 0.2–1.0 V。
- gold 的 `pts_per_cycle` 只用于 `$bound_step`，不改变波形。题面不要求它，Deliverable 允许求解者加这类参数；采样密度由台架 `maxstep=1p` 保证（8 GHz 时每周期 125 点）。
- gold 不读 pre，预充电期间输出 0 是因为尚未释放。S5 把 pre 限制在合法时序内（释放前至少 100 ps 预充电，pre 与 rel 在同一时刻翻转，rel 高时 pre 低），所以 pre 不影响判定。没有把“释放要求 pre 先为高”写进规则，因为 pre 与 rel 的边沿重叠，这条规则在边沿内不可判定。
- S1 中“pwr 低时 rel 上升不释放”“rel 已高时 pwr 上升不释放”是 gold 的行为，SPEC 只写了“rel 上升（释放）”。本题把它写成明确规则（选择）；调度器自身不产生这两种组合，终评 stop_paths 用它们检查电平触发式的错误实现。
- 验收用逐点波形比较加过零点，期望值由 contract.py 按 S2 闭式计算。容差依据（EVAS 0.8.7 实测）：
  - 旧 EVAS 在线性 PWL 输入上把 cross 事件定位到精确阈值时刻（释放时刻不在 1 ps 网格上时也如此），参考解最大电压误差约 2e-11 V，过零点误差最大 0.018 ps；
  - 门限取 5 mV 与 0.2 ps。0.2 ps 在 7.5 GHz 相当于 9.4 mrad 相位；5 mV 在 a_ro = 1 V 时相当于约 5 mrad 相位或 0.5% 幅度。忽略 df_start 一类错误的稳态相位差是 2π·f·ε·τf ≈ 16 mrad（约 0.43 ps），可以检出；其他仿真器释放时刻定位还有约 0.1 ps 的余量；
  - 控制边沿 ±3 ps 内的点不比较：输入边沿 2 ps，边沿内输出可以处于任一状态，3 ps 覆盖边沿半宽和事件定位余量；
  - 过零点窗口距释放和停止各 5 ps，并在期望过零点距窗口端点不足 1 ps 时把端点内移 2 ps，避免端点处计数歧义。
- 用例长度：每个用例 5–7.5 ns、最多 4 个实例、maxstep 1 ps，旧 EVAS 每个用例 1–2.5 s，内存远低于被杀的规模。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S1 释放条件；关断、预充电、停止后为 0 | cold_starts | stop_paths（pwr 低时 rel 上升、rel 高时 pwr 上升）、restarts（pwr 高时 pre 单独翻转） | oscillates_in_precharge、release_ignores_pwr |
| S2 幅度建立 τa = t99_amp/ln 100、a_ro | cold_starts（seed、ideal） | carriers_params（a_ro = 0.5，t99_amp = 100 ps、120 ps、0）、long_hold（300 ps） | amp_tau_is_t99、a_ro_ignored |
| S2 相位为频率积分；df_start、t99_freq、phi0 | cold_starts | carriers_params（4.5/7.5 GHz 等 4 个载频，df_start −0.02、0.03，t99_freq 300 ps、150 ps、0，phi0 1.0、−2.0、0.5）、restarts（phi0 −1.2，df_start 0.04） | phase_not_integrated、freq_settles_with_t99_amp、phi0_dropped_while_settling |
| S3 局部相位、长保持、每次冷启动从 phi0 重来 | cold_starts（两次冷启动） | long_hold（rel 高 5 ns）、restarts（4 次长短不同的冷启动，释放时刻不在 1 ps 网格上） | global_phase、no_cold_restart |
| S4 rel 或 pwr 下降立即停止 | cold_starts（pwr 与 rel 同时下降、rel 单独下降） | stop_paths（rel 高时 pwr 下降） | rel_fall_does_not_stop、pwr_fall_does_not_stop |
| S5 合法域 | 全部用例经 `contract.domain_problems` 检查 | 同左（mutants.py 运行前断言） | — |

11 个错误版本中有 5 个只在终评用例中失败（freq_settles_with_t99_amp、phi0_dropped_while_settling、a_ro_ignored、release_ignores_pwr、pwr_fall_does_not_stop），对应终评针对公开用例之外的参数与停止路径。正确替代实现（`tests/calibration/alternative.va`）用“dead”标志和分开的穿越事件组织状态、0.01^(u/t99) 写建立因子、不读 pre、不设 `$bound_step`。校准结果见 `results/calibration.json`，原始运行在 `runs/uwb-tx-vabench-20261022/tasks/uwb-spec-rf-branch/`。

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了参考解（见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)）。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），结果见 `results/`。EVAS 补齐后需要重跑参考解、正确替代实现和全部错误版本，复核 5 mV / 0.2 ps / 3 ps 三个门限，再更新 `results/`。
- 旧 EVAS 0.8.7 的 `idt()` 缺陷：同一模块有两个实例时，只有一个实例的 `idt()` 积分，另一个保持 0（最小复现 `runs/uwb-tx-vabench-20261022/tasks/uwb-spec-rf-branch/probe/idt_two.va`）。用 `idt()` 积分相位的正确实现单实例时通过，多实例用例会被误判 0 分。因此替代实现改用闭式；在暂用后端上，这类候选的失败属于环境缺陷，不是模型错误。当前 EVAS 上需要用 idt 实现复核。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。
