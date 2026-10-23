# uwb-repair-scheduler-warm-restart 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的整条发射链（串并、编码器、16 相主 RO、PG、8 支路调度器、8 个 RF 支路、2 条包络通道、合路输出），行为约定见 [ir-uwb-tx/SPEC.md 第 2–5 节](../../../../circuits/ir-uwb-tx/SPEC.md)。题面 C2–C6 是 SPEC 4.2–4.9 中判断 RF 输出和观测端口所需的部分，按内容重写，不引用文件路径；SPEC 不进入求解镜像。
- 故障对应的规则：SPEC 4.7 事件表第一行“支路 k 正在 PRECHARGE/ACTIVE/TAIL/HOLD：不另占供电，记为热请求，继续振荡（或继续预充电）”，以及 4.8“HOLD 和连续脉冲期间相位连续，不在符号边界重置”。需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）§7.2–7.3（状态机、200 ps 内保持、并发供电 ≤ 2）。
- δ₀ 格点取自主 RO 的 16 个抽头、位置递推 P[n] = (P[n−1] + D[n]) mod 8，与 Lei 等 [JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077) 的做法一致（原文 16 阶）。
- 参考解是系统资产的 9 个 gold 模块：[module/](../../../../circuits/ir-uwb-tx/module/)，其中被修复的是 [ro_scheduler8.va](../../../../circuits/ir-uwb-tx/module/ro_scheduler8.va)。题包副本只删去了注释里的“(SPEC.md 4.x)”字样，模块名、代码一字未改（模块名保持 `uwb_*`，因为台架按名字实例化）。
- 起始工程 `environment/starter/modules/` = 参考解 + 一处故障：`ro_scheduler8.va` 的 4 条热请求语句（通道 a/b × 槽 0/1）各加 `sN_st = 1;`，即热请求把支路打回 PRECHARGE。这就是系统资产校准里的 `sch_warm_restarts_precharge` 错误版本，扩展到两条通道和两个槽。
- 系统资产自己的整链检查见 [test/m4_chain/check_chain.py](../../../../circuits/ir-uwb-tx/test/m4_chain/check_chain.py)；本题的 `pg_windows`、`scheduler_replay`、`check_rf` 由它移植，改为从激励直接推出 PG 窗口（不读仿真里的抽头），并改用公开的观测节点。

## 建模选择

- **固定系统用网表连接，不用 VA 顶层。** 任务单原定 `/app/circuit.va` 放一个固定的 `uwb_tx_chain` 顶层并暴露观测端口。实测 EVAS 0.8.7 做不到（见待定项），所以改为由公开 `contract.py` 生成的网表按端口顺序连接 9 个模块，边沿记录仪直接挂在叶子节点上；交付物是目录 `/app/modules`（主会话已同意）。频率校准模块随目录编译但不实例化，主 RO 码由 10 个直流源固定为 288，PG 的 en 接 1 V。
- **交付范围。** 开放目录：9 个文件都可改，可以新增 `.va` 辅助模块（台架编译目录里全部 `.va`），不得删除或改名；接口（文件名、模块名、端口顺序、参数名和默认值）必须保持，因为台架按名字和端口顺序连接、并按参数名传 `n_pre`、`t_tail`、`t_hold`、`dpc_db*`。目录交付不套用单文件固定尾段，尾段按目录改写了三句（已有可运行候选、按目录采集、目录外文件不提交）。
- **期望值完全由规则算出。** `pg_windows` 从激励推出每个字的锁存时刻 t_L(n) 和 PG 窗口（C2–C3），`scheduler_replay` 按 C4 的两槽规则重放，得到每个支路的 pwr/pre/rel、两条 gate、conflict、nsup 的期望边沿；RF 波形按 C5–C6 用观测到的 rel/gate/clk672 过阈时刻重建。checker 不读 gold 波形，也不读仿真里的 PG 内部信号。
- **观测点。** clk672（ph0）、pwr/pre/rel ×8、gate_a、gate_b、conflict、nsup 的 0.5/1.5/2.5 V 过阈，共 32 个记录仪；outp、outn 存全部步点。`st` 状态监测电压不验收（题面已写明），求解者可以改其内部编码。
- **时间容差 2 ps。** 期望过阈时刻 = 动作时刻 + 1 ps（2 ps 线性边沿的中点）。EVAS 0.8.7 在 maxstep 10 ps 下实测参考解最差偏差 0.5 ps（全部 9 个用例），与系统资产 README 记录的“约 0.5 ps”一致；2 ps 远小于最短的有意义间隔（δ = 93 ps、t_wait 最短 14 ps）。用例设计另外保证（C8，`design_problems` 自动检查）：计时区间的结束点离任何 pre_x/rf_x 过阈至少 5 ps，同一信号两次变化至少相隔 5 ps，enc_valid 锁存离帧边沿至少 50 ps，所以仿真器误差不会改变事件先后。
- **RF 判据。** 重建误差限 2 mV（参考解 9 个用例实测最大 0.04 mV）；载频按脉冲中间一半的过零点估计，±2 %（只检查中间一半落在仿真区间内的脉冲）；脉冲及其 300 ps 尾部以外 |outp − outn| < 1 µV（参考解实测 ≤ 3e-15 V）。重建误差限与系统资产 check_chain 相同，故障造成的误差是几十 mV 到满幅。
- **每段仿真长度。** 公开 2 个用例约 28–34 ns，终评 7 个用例 25–130 ns，32 个记录仪；最长一段参考解约 13 s、峰值内存约 2.6 GB（整个 verify 进程），远低于“6 µs、60 个记录仪”被杀的情形。
- **预期难度：难（D4）。** 现象在 RF 波形和支路控制线上，根因在 9 个模块之一的 4 处对称语句里；只修通道 a 或只修槽 0 的改法在部分公开用例上能过；直接“让支路一直开着”、“请求总占新槽”或“热请求直接进 ACTIVE”都会破坏终评中的保持超时、抢占、丢弃或 PRECHARGE 中的热请求。

验收对应（C 编号为题面条款；“热请求”= C4(a)）：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| C4(a) 热请求：ACTIVE/TAIL 中、通道 b | hold（7→0、6→0、4→0 三对） | random_a、random_b、long_precharge | faulty_starter、fix_lane_a_only、warm_path_removed |
| C4(a) 热请求：槽 1 | conflict（3 次） | preempt、long_precharge、busy | fix_slot0_only |
| C4(a) 热请求：空闲 HOLD 中，取消超时 | — | hold_idle（n_pre=1，107 ps 窗口）、preempt、busy | warm_no_pending |
| C4(a) 热请求：PRECHARGE 中，不提前释放 | — | busy（n_pre=15，3 次） | warm_goes_active、warm_excludes_precharge |
| C4 TAIL 后保持与超时，t_wait = max(0, t_hold − n_pre·δ) | hold（3→0、2→0 关断后冷启动） | hold_idle、long_precharge（T_pre > t_hold）、random_b（t_tail=100 ps、t_hold=300 ps）、cold_cycle | never_off、hold_ignores_tpre |
| C4(c) 抢占空闲 HOLD，两个都空闲时先槽 0 | — | preempt（t_hold=2 ns，5 次，其中 2 次两槽都空闲）、busy | no_preempt |
| C4(d) 丢弃与 conflict，供电 ≤ 2 | conflict（两条通道各丢 1 个） | busy（丢 4 个） | always_take_slot |
| 修复不能改动无关行为（全冷启动） | — | cold_cycle（载频轮转，48 字无热请求） | never_off、hold_ignores_tpre |
| C2–C3 收字、帧、通道交替、预充电提前量 | 全部 | random_b（另一个 bit 时钟相位 t_d = 700 ps、n_pre=3） | （由所有边沿比较覆盖） |
| C5–C6 起振、相位连续、包络、极性、DPC | hold（极性、DPC） | random_a（随机 DPC ±6 dB）、全部 | faulty_starter（重建误差 55 mV、载频为 0） |

终评用例的“路径计数下限”写在 `tests/final_cases.py` 的 `need` 中，每次运行先核对期望序列确实走到了这些分支（结果表第一行）。

校准（EVAS 0.8.7，2026-10-23，`results/calibration.json`）：参考解与替代实现（`tests/calibration/alternative.va`，不用待发计数，改由通道指针和门控推出“有待发脉冲”）均为 1 分，324 项检查全过，最差过阈偏差 0.5 ps；起始工程和 10 个错误修复均为 0 分。只有终评用例能检出的有 3 个：warm_goes_active、warm_excludes_precharge（只有 busy）、no_preempt（preempt、busy）；fix_slot0_only 和 always_take_slot 在公开用例中只被 conflict 检出。每个样本完整终评 50–87 s，单个用例 3–12 s。

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了这些模块（[#229](https://github.com/BucketSran/vaEVAS/issues/229)）。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），结果见 `results/`。EVAS 补齐后需要重跑参考解、替代实现、起始工程和全部错误版本，再更新 `results/`。
- EVAS 0.8.7 的两个层次化限制（决定了上面“网表连接”的选择），探针在 `runs/uwb-tx-vabench-20261022/tasks/uwb-repair-scheduler-warm-restart/probe/`：
  1. VA 层次里整条总线端口按子模块的端口名解析成全局节点，而不经过父模块的映射：子模块写 `y[k]` 会写到全局 `y[k]`。所以 `uwb_tx_chain` 把调度器 `pwr[7:0]` 接到顶层端口 `pwr[7:0]` 再接网表 `pwr0…pwr7` 时，网表节点恒为 0 V（`probe/bus/child*.va`、`probe/out/gold`；`system/tx_seed.va` 能用是因为每个子模块端口名都恰好等于父模块线名）。
  2. 纯拷贝 `V(y) <+ V(x)`（在叶子模块或顶层）保存的波形正确，但边沿记录仪漏记过阈：40 个时钟边只记到 27 个（`probe/bus/tb4.scs`、`sim4/`）。所以观测拷贝不可靠，记录仪必须挂在产生边沿的节点上。
  Spectre 上这两点应不存在；届时可以恢复固定 VA 顶层的写法，但公开合同（接口按端口顺序连接）不变。
- 抢占顺序（两个槽都是空闲 HOLD 时先抢槽 0）是 gold 的实现选择，SPEC 4.7 没写；题面 C4(c) 把它写成了规则，preempt 用例有 2 次依赖它。需要人工确认是否保留为验收要求。
- Docker 镜像没有构建，EVAS 安装方式待定；目录交付的收集与在独立终评环境中恢复基线未验证。
- Spectre 未运行。
