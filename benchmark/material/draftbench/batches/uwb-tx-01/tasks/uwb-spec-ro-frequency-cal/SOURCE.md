# uwb-spec-ro-frequency-cal 作者记录

## 行为依据

- 电路来源：IR-UWB 发射机种子链的主 RO 频率校准，行为约定见 [ir-uwb-tx/SPEC.md 第 4.5 节](../../../../circuits/ir-uwb-tx/SPEC.md#45-ro-频率校准uwb_ro_frequency_cal)，系统常量见同页第 2 节：48 MHz 参考，目标 672 MHz = 14 × f_ref，主 RO 调谐 f = 600 MHz + code × 0.25 MHz，10 bit，理论目标码 288。需求出自用户提供的工程 SPEC《IR-UWB TX 调制与低功耗架构筛选 SPEC V1.0》（2026-10-22）§6.3–6.4：48 MHz 参考比 14 的测量搜索、校准过程不承载数据、done 只表示频率达标；§10.1 要求测参考缺失、RO 过快、RO 过慢和再次校准。
- 校准 RO 频率即同时校准 16 个抽头和 δ₀ 位置格点，这与主参考论文同组前作 Lei 等，[JSSC 2024，DOI 10.1109/JSSC.2023.3349077](https://doi.org/10.1109/JSSC.2023.3349077) 的做法相同（见 SPEC.md 第 3 节）。题面只把调谐律作为背景，被测对象是校准块本身。
- 参考解与系统资产中的 [ro_frequency_cal.va](../../../../circuits/ir-uwb-tx/module/ro_frequency_cal.va) 相同，只把模块名 `uwb_ro_frequency_cal` 改为 `ro_frequency_cal`，并改了头注释。公开台架中的 `master_ro16.va` 是 [master_ro16.va](../../../../circuits/ir-uwb-tx/module/master_ro16.va)（`uwb_master_ro16`）改名为 `master_ro16`，同样只改模块名和头注释，只用 ph[0] 作 `roclk`。
- checker 移植自作者检查 [check_m2.py](../../../../circuits/ir-uwb-tx/test/m2_clock/check_m2.py) 的 `replay_cal` 和 `check_cal`：从观测到的参考沿和 RO 沿重放搜索，自己数 RO 沿，不用调谐律预测计数。移植时补了复位、忙时重新开始、多次校准、事件间距检查和逐位边沿的一一比较。

## 建模选择

- 预期难度：中（D2–D3）。考点是逐次逼近状态机的窗口边界（第 n_settle 个参考沿开窗、再过 n_win 个沿关窗、只数严格位于两沿之间的 RO 沿）、count ≤ target 保留位、最终验证与 tol、done/fail 后保持、忙时重新开始、看门狗的计数起点和 fail 时显示已保留的码、复位与上电显示 code_init、输出延迟 t_cq。
- 题面相对 SPEC 4.5 补充的规则都取自 gold 的行为：
  - cal_start 在校准中途到来时重新开始（S5）。SPEC 只写了 done/fail 之后再次开始。
  - 看门狗从“开始或最近一个参考沿中较晚者”数起（S6），gold 在 cal_start 时清零计数。
  - 复位期间的 cal_start 被忽略（S7），gold 在 cal_start 上升沿检查 rst。
  - `n_settle` 的允许范围从 1 开始。gold 的 n_settle = 0 与 1 行为相同（都在第 1 个参考沿开窗），SPEC 的“第 n_settle 个参考沿开窗”对 0 没有定义，所以题面不开放 0。
  - 工作域要求改变输出的事件相距至少 1 ns（S9）。gold 只有一个输出定时器，两个事件相距小于 t_cq 时，后一个会覆盖前一个的输出更新，按事件排队的实现会多出一次更新；题面用间距条件避开这个差别，checker 也检查用例满足它。
  - `t_cq` 范围定为 5 ps 到 500 ps，远小于 1 ns 的事件间距。
- 起始电平：EVAS 0.8.7 把普通 `transition()` 输出在 t = 0 从 0 V 拉起，过阈记录在 5 ps 前、被 kit 当作起始电平；但带延迟参数的 `transition()`（正确替代实现就这样写）直接从直流值开始，没有过阈记录，kit 的 `Edges` 会把起始为高的位当成低。为此台架加了一个单 `$strobe` 的 `output_probe.va`，在第一个开始或复位前 5 ns 读出全部输出电平，之后的电平由边沿推出。
- 仿真内存与用例长度：EVAS 0.8.7 的内存占用（`footprint`）约为“网表中 `$strobe` 语句数 × tstop/maxstep × 2.1 KB”，与实例数和事件数无关。kit 的边沿监测器每个有 2 条 `$strobe`，本题每个实例 15 个监测器加 1 个探针共 31 条。实测：2.35 µs、43 条 `$strobe` 时，maxstep 100p/50p/20p 分别为 2.2/4.4/11 GB；不接监测器时 145 MB。完整默认校准（n_win = 192，约 44.7 µs）在 maxstep 20p 下 40 s 内涨过 63 GB 后被系统杀掉；11.7 µs、maxstep 10p 的用例同样被杀。task.toml 给验证环境 4 GB，所以：
  - 题包不跑完整默认校准，改为 `default_first_window`：默认参数只跑第一个窗口（192 个参考周期，target 2688，code 512 → 256），然后复位。完整 44.5 µs 校准由系统资产的 [check_system.py](../../../../circuits/ir-uwb-tx/test/system/check_system.py) 覆盖，它只接 4 个监测器、maxstep 200p。
  - 公开用例 `normal` 用 n_win = 16（任务说明建议 48；48 时一次校准 11.7 µs，约 7.6 GB）。终评用例的 n_win 取 4–24，双实例用例控制在约 2.8 µs。参考解各用例实测峰值 0.8–3.8 GB，见下表。
  - 本批其他题同样受这条规律影响；已报告 main，kit 暂不改。
- maxstep 与时间容差：内存决定 maxstep 只能取 100p。参考解在 100p 下各输出边沿与期望之差最大 5.6 ps（`ref_lost` 的 code[6]：由 RO 沿触发的定时器晚 3.6 ps，code 位又整体晚 2 ps），其余用例不超过 2.8 ps；正确替代实现不超过 1.0 ps。maxstep 10p 时同一用例误差 0.5 ps，但内存是 100p 的 10 倍。容差取 20 ps，约为参考解最大误差的 3.5 倍，又远小于 20.8 ns 的参考周期，足以判定哪个参考沿决定了输出。代价是默认 t_cq（10 ps）落在容差内，零延迟的错误只能由 `params_two_instances` 的 t_cq = 150 ps 检出（错误版本 `fixed_output_delay`）。
- 事件顺序：RO 沿与开窗/关窗参考沿、开始的距离小于 3 ps 时判为顺序不明（S9）。EVAS 0.8.7 对两个固定源的 2 ps 斜坡定位准确（maxstep 100p 下参考沿观测误差为 0），3 ps 足够区分。各用例的参考沿延迟逐个调过，参考解的最小距离见下表。

验收对应：

| 要求 | 公开用例 | 终评追加 | 典型错误（校准用错误版本） |
| --- | --- | --- | --- |
| S2 开始、settle 与窗口 | normal（n_win 16） | default_first_window（默认 n_win 192、n_settle 2）、params_two_instances（n_settle 4、n_win 6） | window_one_period_short、settle_ignores_n_settle |
| S3 count ≤ target 保留位 | normal（5 个窗口 count 恰等于 target） | ro_limits（RO 过快全清为 0、过慢全保留为 1023）、params_two_instances（ratio 13） | inverted_decision、equal_count_clears_bit、target_ignores_ratio |
| S4 最终验证与 tol | normal（done） | ro_limits（两个实例都 fail）、recal、params_two_instances（tol 2） | verify_ignores_tol |
| S5 保持与重新开始 | — | recal（done 后保持，再次校准）、reset_restart（忙时 cal_start 重新开始） | done_kept_on_restart、no_restart_while_busy |
| S6 参考缺失看门狗 | ref_lost（第 4 个窗口中参考停止，显示已保留的 256） | ref_lost_before_start（参考在开始前已停，从开始数起；n_lost 40 和 100，code 0） | no_lost_watchdog、lost_shows_trial_code、watchdog_not_cleared_by_ref |
| S7 上电与复位 | normal、ref_lost（开始前为 512） | reset_restart（code_init 77，搜索中复位、复位期间开始被忽略）、params_two_instances（rst 一直为低，code_init 700）、default_first_window、recal（空闲时复位） | reset_keeps_code、cal_start_during_reset、no_code_init_at_start |
| S8 输出边沿 | 全部 | params_two_instances（t_cq 150 ps、tr 4 ps、vdd 0.9 V、vth 0.4 V、VIN 0.9 V） | fixed_output_delay |
| S9 事件顺序与间距 | 全部 | 全部 | 不针对候选，检查用例本身 |

校准结果（`tests/calibration/mutants.py`，2026-10-23，EVAS 0.8.7，每个样本跑完整终评 179 项检查，参考解 102 s）：参考解 1 分，正确替代实现 1 分，15 个错误版本全部 0 分。明细见 [results/calibration.json](results/calibration.json) 与 [results/reference.json](results/reference.json)。

| 样本 | 违反条款 | 期望 | 实得 | 通过检查 | 首个失败 | 用时 |
| --- | --- | --- | --- | --- | --- | --- |
| reference | — | 1 | 1 | 179/179 | — | 102 s |
| alternative | — | 1 | 1 | 179/179 | — | 102 s |
| inverted_decision | S3 a count above the target clears the trial bit | 0 | 0 | 97/179 | normal/a: code[0] edges (S2-S8) | 129 s |
| equal_count_clears_bit | S3 a count equal to the target keeps the trial bit | 0 | 0 | 152/179 | normal/a: code[0] edges (S2-S8) | 105 s |
| window_one_period_short | S2 the window lasts n_win reference periods | 0 | 0 | 82/179 | normal/a: code[0] edges (S2-S8) | 108 s |
| settle_ignores_n_settle | S2 the window opens at the n_settle-th reference edge | 0 | 0 | 84/179 | normal/a: code[0] edges (S2-S8) | 108 s |
| target_ignores_ratio | S3 target = n_win * ratio | 0 | 0 | 172/179 | params_two_instances/a: code[0] edges (S2-S8) | 98 s |
| verify_ignores_tol | S4 done when \|count − target\| <= tol | 0 | 0 | 174/179 | recal/a: done edges (S2-S8) | 86 s |
| no_lost_watchdog | S6 lost-reference watchdog | 0 | 0 | 167/179 | ref_lost/a: code[6] edges (S2-S8) | 126 s |
| lost_shows_trial_code | S6 a watchdog fail shows the last kept code, not the untested trial code | 0 | 0 | 173/179 | ref_lost/a: code[6] edges (S2-S8) | 76 s |
| watchdog_not_cleared_by_ref | S6 roclk edges are counted since the last reference edge | 0 | 0 | 86/179 | normal/a: code[0] edges (S2-S8) | 71 s |
| reset_keeps_code | S7 reset shows code_init | 0 | 0 | 167/179 | default_first_window/a: code[9] edges (S2-S8) | 76 s |
| cal_start_during_reset | S7 cal_start is ignored while rst is high | 0 | 0 | 171/179 | reset_restart/a: code[0] edges (S2-S8) | 83 s |
| no_restart_while_busy | S5 a cal_start during a search restarts it | 0 | 0 | 165/179 | reset_restart/a: event order is unambiguous (S9) | 73 s |
| done_kept_on_restart | S5 a new cal_start clears done | 0 | 0 | 178/179 | recal/a: done edges (S2-S8) | 89 s |
| fixed_output_delay | S8 outputs change t_cq after the deciding edge | 0 | 0 | 167/179 | params_two_instances/a: code[0] edges (S2-S8) | 98 s |
| no_code_init_at_start | S7 code_init is shown before calibration | 0 | 0 | 138/179 | normal/a: event order is unambiguous (S9) | 75 s |

参考解各用例（maxstep 100 ps，EVAS 0.8.7）：

| 用例 | 时长 | 实例 | 检查 | 用时 | 仿真器峰值内存 |
| --- | --- | --- | --- | --- | --- |
| normal | 4.38 µs | 1 | 16/16 | 10 s | 2.9 GB |
| ref_lost | 2.35 µs | 1 | 16/16 | 10 s | 1.6 GB |
| default_first_window | 4.33 µs | 1 | 16/16 | 19 s | 2.9 GB |
| ro_limits | 2.54 µs | 2 | 32/32 | 13 s | 3.3 GB |
| recal | 3.70 µs | 1 | 17/17 | 15 s | 2.4 GB |
| reset_restart | 3.00 µs | 1 | 18/18 | 8 s | 2.0 GB |
| params_two_instances | 2.79 µs | 2 | 32/32 | 22 s | 3.7 GB |
| ref_lost_before_start | 0.60 µs | 2 | 32/32 | 5 s | 0.8 GB |

gold 的一处发现：看门狗分支里的 `trial = code_q;` 是死代码。那一刻 `busy_q` 已经置 0，输出定时器走
`else out_code = code_q;`，所以删掉这一行行为不变（第一轮校准时用它做的错误版本被判 1 分，已换成
`code_q = trial;`，即 fail 时显示未测完的试探码）。gold 的行为本身符合 SPEC 4.5“fail 时输出已经保留的码”，
不需要改；这一行可以在系统资产里清理，但清理会改变 gold 文件，不在本题范围内。

## 待定项

- `runtime`：声明的后端是当前 EVAS，但它还跑不了参考解（见 [#229](https://github.com/BucketSran/vaEVAS/issues/229)）。作者运行暂用 EVAS 0.8.7（`UWB_BACKEND=legacy`），结果见 `results/`。EVAS 补齐后需要重跑参考解、正确替代实现和全部错误版本，再更新 `results/`，并重新确认内存、maxstep 与 20 ps 容差。
- 完整默认校准（44.5 µs）不在题包内，原因见“建模选择”。若 kit 改用单 `$strobe` 监测器或换后端后内存允许，可以把它加回终评。
- Docker 镜像没有构建，EVAS 安装方式待定。
- Spectre 未运行。
