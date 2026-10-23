# uwb-spec-branch-scheduler 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的 8 支路调度器，行为约定见 [ir-uwb-tx/SPEC.md 第 4.7 节](../../../../circuits/ir-uwb-tx/SPEC.md#47-8-支路调度器uwb_ro_scheduler8)，其中的“保持条件”和事件表就是本题 S3–S5 的来源。系统常量（δ₀、9δ₀ 脉宽、帧长 16δ₀）见同页第 2 节，PG 的通道与预充电时序见第 4.6 节，第三路供电条件见附录。
- 需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）：§7.3 给出支路状态 OFF/PRECHARGE/RELEASE_SETTLE/ACTIVE/TAIL/HOLD、同时供电不超过 2 路、正在 ACTIVE/TAIL 的支路不被下一字覆盖、200 ps 内保持；§7.2 给出预充电与释放；§8 给出 t_tail = 150 ps 的依据。丢弃策略、抢占空闲 HOLD、t_hold − T_pre 的空闲等待是 SPEC.md 标为“选择”的规则，本题照用。
- 参考解与系统资产中的 [ro_scheduler8.va](../../../../circuits/ir-uwb-tx/module/ro_scheduler8.va) 相同，只改了头部注释并把模块名改为 `ro_scheduler8`。系统资产里的独立检查是 [m4_chain/check_chain.py](../../../../circuits/ir-uwb-tx/test/m4_chain/check_chain.py) 的 `scheduler_replay`，本题 checker 由它移植，改成按支路记状态，并加了路径统计和工作范围检查。
- 主参考论文 Lei 等 [JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077) 提供了 16 相 RO 定位格点的做法（SPEC.md 第 3 节）。调度器的状态机和供电上限来自原 SPEC §7.3，不来自该论文。

## 建模选择

- **只写外部可观察规则。** gold 用两个供电槽组织状态。题面只规定：最多两路供电、哪个请求得到支路（热请求 → 冷启动 → 接管空闲 HOLD → 丢弃）、支路何时进入 TAIL/HOLD/OFF、各输出与状态的对应。替代实现（`tests/calibration/alternative.va`）不用槽：它把 8 个支路的状态压进整数字，数供电支路来限两路，扫描找空闲 HOLD，截止时刻放在按支路索引的两项定时队列里。它在全部用例上得 1 分。
- **激励。** 两条通道直接用 PWL 源驱动，网表里没有 PG 和 RO。`contract.windows` 用独立的理想格点 PG 模型生成：帧 i 的描述符 (P, F) 排进帧 i+1，窗口从 t0 + (16(i+1)+P)δ₀ 开始，宽 9δ₀，请求提前 n_pre·δ₀；sel 在帧开始后 δ₀/2 改变；已排程的符号轮流走 a、b 通道，空帧不占通道。随机用例由随机 6 bit 字经编码器规则（P 累加 Gray 增量）得到，或直接随机取 (P, F)。
- **工作范围（S9）。** 有几种情形下，事件的先后由仿真器决定，或者行为取决于 gold 的内部顺序。题面把它们排除在工作范围之外，`contract.validate` 对每个用例的每个实例逐条检查：
  - 请求恰好落在 TAIL 或空闲 HOLD 结束的时刻。SPEC.md 规定按热请求处理，本题要求两者相隔至少 10 ps。
  - 接管时有两个支路都处于空闲 HOLD。gold 取槽 0，外部看不出依据。
  - 复位落在 conflict 脉冲中。gold 的复位不清 conflict。
  - 空闲等待 t_wait 在 0 到 10 ps 之间。
  - 首尾相接的两个窗口在同一时刻交接，这一点题面明确规定为保持 ACTIVE（S4）。checker 把 1 ps 内的窗口开始排在窗口结束之前，所以 rf 两个边沿的过阈先后不影响期望。
- **st 与 nsup 的阈值和计时。**
  - 阈值放在每个电平上下各 0.1 V 处：st 用 0.1、0.3、0.5、0.7、0.9、1.1 V，nsup 用 0.5、0.9、1.1、1.5、1.9、2.1 V。过阈次数一致就要求每个电平误差不超过 0.1 V。
  - 第一版 nsup 只用 0.5/1.5 V。错误版本 `nsup_scaled_by_vdd`（nsup 按 vdd 缩放）在 vdd = 0.8–1.3 的实例上照样通过，所以补了带宽阈值。
  - EVAS 0.8.7 在 maxstep 10 ps 下，若过阈点落在一个边沿的最后一个仿真步内，会把过阈时刻报到下一个步点。实测：参考解的 st 从 1.0 V 落到 0 时，0.1 V 过阈晚了 2.5 ps，而波形本身正确。因此每个期望边沿只对最靠近边沿中点的阈值计时（容差 2 ps，并列时取较早的阈值），其余阈值只比次数和方向（S10）。
  - pwr/pre/rel/gate/conflict 用 vdd/2 过阈，都在边沿中点，全部计时。
- **容差。** 过阈时刻容差 2 ps，与同批题一致。参考解在全部用例上计时误差最大 0.75 ps（tr = 3 ps 的实例），替代实现同样通过。事件间隔下限 10 ps 远大于这个误差，也大于 tr 的上限 5 ps。
- **未覆盖。** 在 PG 形状的通道下，两次丢弃间隔小于 t_conf 的情形几乎构造不出来：39 个随机种子都没有出现。conflict 脉宽“从最后一次丢弃起算”的延长规则写在 S6，但没有用例检查。“请求落在已有等待请求的 HOLD 上”（`warm_hold_waiting`）目前没有用例覆盖；它与其他热请求走同一条规则 S3 (a)。
- **预期难度：难。** 考点是热/冷/接管/丢弃的优先级、TAIL 与 HOLD 的时序、空闲 HOLD 的等待扣除 T_pre、首尾相接窗口的交接、复位取消已获准请求、多级 st/nsup 输出、两路上限。

作者校准（2026-10-23，EVAS 0.8.7，7 个用例、264 项检查）：参考解与替代实现均得 1 分，12 个典型错误版本均得 0 分，参考解计时误差最大 0.75 ps。逐项结果、命中用例与 sha256 见 `results/reference.json`、`results/calibration.json`。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S1 pre_x 上升沿请求、此刻读 sel | hold、conflict | random_words、random_dense（任意支路与位置） | 各错误版本共用 |
| S2 状态到输出的映射、st、nsup | 全部 | 非默认 vdd 与 tr（hold_idle/b、random_words/b、random_dense/b） | nsup_scaled_by_vdd、rel_during_precharge |
| S3 (a) 热请求不改状态 | hold（ACTIVE、TAIL 中的请求） | hold_idle（空闲 HOLD 中的请求）、random_dense（PRECHARGE 中的请求） | warm_restarts_precharge |
| S3 (b)(d) 冷启动与丢弃、两路上限 | conflict（a、b 通道各丢一次） | random_dense（n_pre = 15、δ₀ = 60 ps，16 次丢弃） | steal_busy_slot |
| S3 (c) 接管空闲 HOLD | — | preempt（n_pre = 8、t_hold = 2.5 ns，17 次接管）、random_dense | no_take_over |
| S4 窗口、门控、首尾相接交接 | hold（7 → 0） | 全部 | steal_busy_slot、rel_during_precharge |
| S5 TAIL、等待中的 HOLD、空闲 HOLD | hold | hold_idle（n_pre = 1 的空闲窗口）、非默认 t_tail/t_hold（含 t_hold = 0） | no_hold、hold_ignores_tpre、fixed_tail |
| S6 conflict 脉冲 | conflict | random_dense（t_conf = 790 ps 与 150 ps） | drop_without_conflict、fixed_conflict_width |
| S7 异步复位、取消请求、复位中忽略请求 | hold（起始复位） | reset_phases（预充电中、门控高、TAIL 中、请求时 rst 高、空闲 HOLD 中、rst 在已忽略请求的窗口前释放） | reset_keeps_branches、requests_during_reset |

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了参考解，见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），结果见 `results/`。EVAS 补齐后，要重跑参考解、正确替代实现和全部错误版本，再更新 `results/`。原始输出在 `runs/uwb-tx-vabench-20261022/tasks/uwb-spec-branch-scheduler/`。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。同一时刻多个事件的先后、请求恰在空闲 HOLD 结束时的处理，都要等 Spectre 确认。题面已用 10 ps 间隔把这些情形排除在工作范围外。
- SPEC.md 第 7 节的“T_pre > t_hold 时继续保持”仍待用户确认，本题按现行选择写入 S5。
