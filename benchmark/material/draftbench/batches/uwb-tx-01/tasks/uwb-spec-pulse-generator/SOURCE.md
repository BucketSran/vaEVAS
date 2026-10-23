# uwb-spec-pulse-generator 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的脉冲发生器（PG），行为约定见 [ir-uwb-tx/SPEC.md 第 4.6 节](../../../../circuits/ir-uwb-tx/SPEC.md#46-脉冲发生器-pguwb_pulse_generator)，系统常量和几何见第 2、3 节。需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）：§6.3、§6.5 规定 encoded_valid 上升沿供后级锁存；“预留一 symbol 准备时间”对应排进下一帧；§6.4 规定使能（校准 done）只在帧边界起作用、不与原始时钟相与；§3 和 §5.1 给出 Tp = 9δ₀、Δ = δ₀；§7.2 给出预充电公式但没有给 T_precharge 数值，T_launch_lead 首版取 0。
- δ₀ 格点取自 16 相主 RO 的抽头，与主参考论文同组前作的做法一致：Lei 等，[JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077)。该文用多相 RO 产生位置格点，本题是 8 位置种子。
- 参考解与系统资产中的 [pulse_generator.va](../../../../circuits/ir-uwb-tx/module/pulse_generator.va) 相同，只把模块名 `uwb_pulse_generator` 改为 `pulse_generator`，并改了头部注释。公开固定模型 `master_ro16.va` 是系统资产 [master_ro16.va](../../../../circuits/ir-uwb-tx/module/master_ro16.va) 改名而来（`uwb_master_ro16` → `master_ro16`）。系统资产的独立检查见 [test/m3_pulse/check_pg.py](../../../../circuits/ir-uwb-tx/test/m3_pulse/check_pg.py)，本题 checker 由它移植而来。

## 建模选择

- 预期难度：中。考点有五项：
  - 按抽头边沿计数（而不是按绝对时间）定位窗口；
  - 排进下一帧；
  - 两通道按已排程的符号交替；
  - en 只在帧边界采样，en 低时待发字保留；
  - 异步复位清空待发字和通道，但保留 sel/pol。
  比编码器多了“观测时钟边沿计数”和两条并行通道的状态。
- 题面用抽头边沿序号表达 SPEC 的“抽头 A+P”，s = 16 + P，从排程帧边界之后数起；帧边界本身也是抽头边沿。这样不依赖 RO 频率，换码（final 用 340）后 δ 变化，按固定 δ₀ 计时的实现会失败。
- SPEC 4.6 写“rst 上升：清空待发字和两个通道”，没有说 sel/pol 和 overrun。参考解在复位时保留 sel_x、pol_x 和正在进行的 overrun 脉冲。题面 S6、S7 把这一点写明，S7 的复位用例（R5）专门在 overrun 高时复位。
- n_width 的范围取 1–9，参考解的参数声明是 1–16。理由：同一通道最早在 32 个抽头边沿后再次排程，窗口结束于 16 + P + n_width，要求 P + n_width ≤ 16 才不会在窗口进行中被改写；n_width > 9 时参考解会延长旧窗口并在窗口中改 sel。
- 定域排除（S8）：
  - enc_valid 与 ph0 同刻：题面不规定先后，改为要求 enc_valid 上升和 en 跳变距帧边界至少 30 ps；
  - rst 跳变距任何抽头边沿和 enc_valid 上升至少 30 ps；
  - 相邻 enc_valid 上升至少相隔 t_ovr + 100 ps，避免两个 overrun 脉冲重叠，否则参考解会合并成一个。
  用例实测最小间距：enc_valid–ph0 46 ps，en–ph0 436 ps，rst–抽头 44 ps，rst–enc_valid 121 ps，间距余量 126 ps。作者用 `contract.domain_margins` 核对，不计分。
- 时间容差 2 ps，与代表题相同。EVAS 0.8.7 在 maxstep 10 ps 下的过阈定位误差约为 tr/4。参考解实测最大误差：tr = 2 ps 时 0.5 ps，tr = 5 ps（params 用例实例 a）时 1.03 ps。因此 tr 允许范围上限取 5 ps（代表题是 10 ps）：tr = 10 ps 时误差约 2.5 ps，会超出容差。
- 期望窗口按同一次仿真中实际观测到的抽头过阈时刻（在实例自己的 vth 上）计算，不用 RO 名义周期。名义抽头网格只用来摆放激励。
- 旧 EVAS 启动时 transition 输出从 0 V 爬升：t ≈ 1 ps 时，初始为高的抽头会产生假上升沿。checker 丢弃 5 ps 前的过阈记录；参考解按帧边界重置绝对序号，而且 rst 在开始时为高，所以不受影响。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S2、S5 抽头计数、下一帧、窗口长度 n_width | positions（全部 P，7→0，0→7，同 F 首尾相接） | params_two_instances（n_width 7 和 1、phase0 0.2、vth 0.4、vdd 0.9、tr 5 ps），random_code340（code 340） | no_frame_delay、width_ignores_parameter |
| S5 预充电 n_pre（含 0 和 15） | positions | pre15_pre0（同一组抽头上两个实例，n_pre 15 与 0），params（n_pre 4、1），reset_activity 实例 b（n_pre 6） | precharge_ignores_parameter |
| S3 在 enc_valid 上升沿锁存；overrun 脉冲宽 t_ovr | late_enable（en 低时 3 次 overrun 和 en 高时 1 次） | random_code340（输入在锁存后 40 ps 翻转，9 次 overrun），params（t_ovr 350 ps、60 ps） | no_overrun、descriptor_read_at_frame_edge |
| S4 按已排程符号交替通道；被覆盖的字不占通道 | positions、late_enable（空帧，被覆盖的字） | random_code340（空帧与 overrun 混合） | lane_per_latch、lane_by_frame_parity |
| S4 en 只在帧边界采样；en 低时保留待发字并继续锁存 | late_enable（帧中间使能） | random_code340（en 在帧 12 中间拉低，跨 4 个帧边界，窗口进行中） | en_blocks_latch、en_low_cancels_windows |
| S6 sel/pol 在排程时改变并保持 | 全部 | 全部；reset_activity（复位不改 sel/pol） | descriptor_read_at_frame_edge |
| S7 复位：清待发字、清两通道、下一字回到通道 a；不影响 overrun | — | reset_activity（R1 只有待发字；R2 预充电中；R3 rf_a 和 pre_b 同时为高且跨帧边界，期间锁存被忽略；R4 RF 窗口中；R5 overrun 高、已排程未开始） | reset_keeps_pending、reset_keeps_lane、reset_keeps_windows |

校准结果（EVAS 0.8.7，2026-10-23，见 `results/calibration.json`）：参考解和正确替代实现（逐通道计数、打包描述符、不同事件组织）在全部 6 个用例上都是 1 分；12 个错误版本全部为 0 分。其中 en_low_cancels_windows 和 descriptor_read_at_frame_edge 只被 random_code340 判出，3 个复位错误只被 reset_activity 判出，都是终评用例。

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了参考解，见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），本地构建在 `runs/legacy-evas-0.8.7`，结果见 `results/`，原始运行在 `runs/uwb-tx-vabench-20261022/tasks/uwb-spec-pulse-generator/`。EVAS 补齐后需要重跑参考解、正确替代实现和全部错误版本，再更新 `results/`。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。另外两项也待 Spectre 观察：enc_valid 与 ph0 同刻的事件顺序（SPEC 4.6 的“先锁存再排程”），以及 Spectre 中输出从直流工作点起步时，启动阶段的抽头沿是否与 EVAS 0.8.7 一致。
