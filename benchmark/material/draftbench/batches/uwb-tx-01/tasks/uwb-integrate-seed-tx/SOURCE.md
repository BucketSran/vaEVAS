# uwb-integrate-seed-tx 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的系统顶层 [system/tx_seed.va](../../../../circuits/ir-uwb-tx/system/tx_seed.va)，架构见 [SPEC.md 第 3 节](../../../../circuits/ir-uwb-tx/SPEC.md#3-架构)，各模块行为见同页第 4 节。需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）：§6.1–6.2 的链路与模块划分，§6.3–6.4 的 48 MHz 参考比 14 校准和“校准 done 后才发送、使能只在帧边界生效”，§7.2–7.3 的预充电、释放和两路供电调度。
- δ₀ 格点取主 RO 的 16 个相位、绝对位置按差分递推，与 Lei 等 [JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077) 式 (1) 的做法一致。
- 固定模块库 `environment/starter/modules/*.va` 是 [module/](../../../../circuits/ir-uwb-tx/module/) 下 9 个 gold 模块的逐字节副本，模块名不变。参考解与 `tx_seed.va` 相同，只把 9 行 include 的路径从 `../module/` 改成 `modules/`（库在题目环境里的位置不同），模块名 `uwb_tx_seed`、端口、参数和连接都没改。
- 检查从系统资产的独立检查移植：校准重放来自 [check_m2.py](../../../../circuits/ir-uwb-tx/test/m2_clock/check_m2.py) 的 `replay_cal`；接收机式解码来自 [check_system.py](../../../../circuits/ir-uwb-tx/test/system/check_system.py)；PG 窗口与两路供电重放来自 [check_chain.py](../../../../circuits/ir-uwb-tx/test/m4_chain/check_chain.py) 的 `pg_replay`、`scheduler_replay`，波形相关性用其 `check_rf` 的公式。区别是这里只看顶层引脚：帧边沿和抽头时刻从 `clk672` 推出，字到达 PG 的时刻从 `bclk` 推出。

## 建模选择

- **预期难度：中～难。** 求解者不写行为模型，只做集成，但要从 Spec 和库说明里读出几处容易接错的关系：PG 使能接 done（帧边界采样）、包络通道和 `clk672` 用帧时钟 ph[0]、n_pre 要同时进 PG 和调度器、两条通道 a/b 从调度器到包络和输出级一一对应、支路 k 用 f_k、pol 接 PG、conflict/nsup 取调度器输出。工作量主要是 9 个模块、30 多个网络的接线和参数直通。
- **CDC 测试条件。** 没有用题目简报里的 n_win = 192（44.5 µs 校准，旧 EVAS 每个用例 4–5 分钟，且旧 EVAS 内存随 strobe 数 × 时间点数增长）。改用测试台的 VA 比特源 [bit_source.va](environment/starter/testbench/bit_source.va)：它在 `clk672` 每个上升沿测上一周期 T，在该帧内按 (j + 0.25)·T/6 发 6 个 bclk 脉冲，din 在 bclk 下降沿换位，所以比特时钟总与校准后的 RO 同频，比特时刻不需要预先算。各用例 n_win 取 1–3，校准约 0.6–1.2 µs，RO 落在 677–700 MHz（不是 672 MHz），数据链照常工作。符号用 64 个整数参数传入（旧 EVAS 不支持动态数组下标）。整条链的单例仿真 21–47 s。代价：n_win = 192 收敛到码 288 的路径没有在本题里跑（系统资产的 `check_system.py` 已覆盖），n_win 直通由 `n_win_not_passed` 错误版本检验。
- **从保存波形取过阈时刻，不用边沿记录仪。** 协调会话的探针显示旧 EVAS 的记录仪会漏掉“纯复制节点”（`V(y) <+ V(x)`，正是 `clk672`）的过阈，而且内存随 `$strobe` 数增长。改为保存 8 个节点的波形、线性插值求过阈。本题探针（git 忽略的运行目录 `runs/uwb-tx-vabench-20261022/tasks/uwb-integrate-seed-tx/probe/`）：maxstep 10 ps 时波形求得的 `clk672` 上升沿相对直线拟合的残差 5e-8 ps，与记录仪相差 ≤ 0.5 ps，且记录仪漏了 9 个下降沿而波形不漏；maxstep 25 ps 残差 6.7 ps、100 ps 残差 17.7 ps，所以固定 maxstep = 10 ps，每例内存约 0.33 GB。
- **总线网络同名规则（旧 EVAS 缺陷的规避）。** 协调会话发现、本题探针（`probe/bus2`）复现：VA 层次里整条总线端口按子模块的端口名接到全局网络，不经父模块映射。结果是：改名的总线网络在父模块里读不到值（b3 = b4 = 0），同一顶层的两个实例共用这些网络（X1、X2 都得 64.2）。正确的种子链里，凡是相连的总线端口名字都相同（sym、pos、fcode、code、ph、sel_a、sel_b），所以题面要求“库模块的总线端口接同名总线网络”，公开检查和终评都在预检里执行，违反者记 0 分。这是充分条件而非必要条件：只改 `code` 网络名而两端端口都叫 `code` 的设计在旧 EVAS 上也对（`probe/renamed_bus` 的 reset 用例全部通过）。EVAS 或 Spectre 能跑后应放宽或删除这条。
- **没有双实例用例。** 同一原因，两个 `uwb_tx_seed` 实例在旧 EVAS 上会互相串扰，所以终评只变参数、序列、参考和数据相位，不加双实例。
- **公开与终评用例。** 公开：`decode`（n_win = 2，48 个随机字，done 之后发送）、`early_conflict`（n_win = 1、n_pre = 15、pol = 1，done 前 12 帧开始送数据，再用 P = 7, x, 0 三个不同载频制造 3 次丢弃）。终评追加：`params_hold`（n_pre = 1、n_win = 3、code_init = 100、g_pa = 0.6、vcm = 0.65、载频降序 7.6–4.45 GHz；同频字对 ΔP = −4 落在 107 ps 空闲保持窗口内、−5 在尾部内、−7 首尾相接、−3 和 0 冷启动）、`params_permuted`（n_pre = 3、code_init = 1023、g_pa = 1.5、vcm = 0.35、载频乱序 3.8–7.4 GHz、pol = 1，60 个随机字）、`ref_lost`（搜索中参考停掉 → fail，此后送数据也不发射）、`reset`（code_init = 700，在第 10 个字的脉冲窗口中间复位）。复位时刻按一次参考解运行的帧时刻选定；正确实现的 RO 时序与参考解相同，所以它对所有正确实现都落在脉冲中间。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S1/S3 code_init 直通（校准前 clk672 频率） | 两例（512） | params_hold 100、params_permuted 1023、ref_lost 300、reset 700 | code_init_not_passed |
| S1/S3 n_win 直通、逐次逼近、done 时刻 | decode 2、early_conflict 1 | params_hold 3 | n_win_not_passed |
| S2/S3 校准驱动 RO、`clk672` 为 ph[0] | 两例（每个试探码区间的频率） | reset（复位回 code_init） | clk672_from_tap8 |
| S3 done/fail 引脚 | 两例 | ref_lost（fail） | done_fail_swapped |
| S2/S4 PG 使能为 done，帧边界生效 | early_conflict（done 前已有 12 个字） | ref_lost（从不 done） | pg_enable_tied_high |
| S4 帧内位置、差分间隔、格点、按时到达 | 两例 | params_hold、params_permuted | lane_gates_swapped、clk672_from_tap8 |
| S2/S4 支路 k 用 f_k | 两例 | 降序与乱序载频 | carriers_swapped |
| S2/S4 pol 接 PG | decode pol = 0、early_conflict pol = 1 | params_permuted pol = 1 | pol_not_connected |
| S2/S4 包络窗口为帧周期的 9/16 | 两例 | 全部 | envelope_clocked_by_bclk |
| S1/S4 g_pa、vcm | 默认值 | params_hold、params_permuted | g_pa_not_passed |
| S2/S5 n_pre 同时进 PG 和调度器 | early_conflict 15 | params_hold 1、params_permuted 3 | scheduler_without_n_pre |
| S5 丢弃与 conflict | early_conflict（3 次） | — | conflict_from_overrun |
| S5 nsup ≤ 2 V、按供电规则变化 | 两例 | 全部 | scheduler_without_n_pre、lane_gates_swapped |
| S4/S5 复位立即停止 RF、done 清零 | — | reset | — |

作者校准（2026-10-23，EVAS 0.8.7，`tests/calibration/mutants.py`，结果见 `results/`）：参考解 1 分（6 例 120 项全过，仿真合计 215 s），替代实现 [alternative.va](tests/calibration/alternative.va)（RF 后端包成辅助模块、实例倒序、n_pre 经 localparam 传给调度器）1 分，上表 12 个错误版本全部 0 分。每个样本约 3.5–6 分钟。

容差依据（参考解实测值见 `results/reference.json`）：

- `clk672` 频率 ±0.1 MHz：码步 0.25 MHz；参考解每个区间误差 < 1 kHz。
- done、fail、conflict、nsup 过阈 ±5 ps：库输出都是 2 ps 线性边沿，插值得到的过阈与重放一致到 0.001 ps；5 ps 也容纳正确实现给 `clk672` 加小缓冲带来的帧边沿偏移。
- 脉冲起点 ±10 ps：用能量质心减 T_w/2 和 10.9 ps，按库公式数值计算的偏差冷启动 ≤ 1 ps、热启动 ≤ 0.05 ps；参考解最大 0.82 ps；抽头间隔 85–93 ps。
- 检测门限 0.2 × g_pa、合并间隔 180 ps：脉冲内载波峰值每半个载波周期出现一次（f ≥ 3.5 GHz 时 < 143 ps）；首尾相接的两个窗口之间包络低于 0.2 的区间约 240 ps。原 `check_system.py` 用 50 mV、100 ps，在低载频脉冲边沿会把一个脉冲拆开、在首尾相接处会把两个合并（开发中实测）。
- 载频 ±2 %、相关 ≥ 0.9、峰值 0.85–1.01 × g_pa：参考解分别为 ≤ 0.09 %、1.000、0.948–0.997（峰值受采样步长 1/(20 f) 影响）。载频之间至少差 5 %，最近载频判决不会混淆。

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了模块库（[#229](https://github.com/BucketSran/vaEVAS/issues/229)）。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），结果见 `results/`。EVAS 补齐后需要重跑参考解、正确替代实现和全部错误版本，再更新 `results/`；届时重新评估总线同名规则和双实例用例。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。比特源依赖 `clk672` 的上升沿测周期，在 Spectre 上需要确认 `clk672` 的过阈事件可靠。
