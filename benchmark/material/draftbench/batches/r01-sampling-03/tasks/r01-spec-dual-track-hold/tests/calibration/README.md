# 校准候选

未仿真：本题尚无 Spectre 运行，Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。这些是作者校准样本，不计入终评，也不进入求解环境。在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本，本页的表由它生成。

## checker 的失败类别

两类，都是电压误差：一是评分点上 `V(vout) - V(vss)` 离预期的输出级值 `b` 超过 2 mV，二是评分点上 `phase` 离它应显示的轨（时钟高时 `vdd`，低时 `vss`）超过 2 mV。失败记录里的 `tick`、`b`、`a` 和 `crossing` 给出它属于哪一次更新或哪一次穿越。使 `b` 变化超过 0.1 mV（题面写明的门限 δ）的 tick 之后、以及每次穿越之后 `1.25*tedge` 内的点不评分，不超过 0.1 mV 的变化不开窗；t = 0 那一点总按 `vinit` 评分（`initial_state` 标出这一行）。`tedge` 内的输出形状由作者证据里的 Python 合成轨迹覆盖。台架义务不满足（分辨率、参数、轨、`vin` 范围、时钟起点、穿越间距、相邻两次穿越之间离 `vth` 不到 50 mV（按保存行判，2026-10-29 修正 r2）、穿越与 tick 的间距）时，checker 抛出异常，不判分。

## 语义依据

被拒预期按 Verilog-A LRM 2.4 的 5.10.3.3（timer）、5.10.3.1（cross）、5.10.2（initial_step）和 4.5.8（transition）写成，是预期，不是结果，每个条目都待 Spectre 校准。只在某种后端语义下成立的条目写在 `expected.json` 的 `conditions` 里，下文“条件”一节逐条转述。

## 候选与应拒用例

“所有用例”指 `base`、`grid-phase`、`start-high`、`rails-offset`、`rail-droop`、`param-override`、`param-endpoints-low`、`param-endpoints-high` 共 8 个。

| 候选 | 行为 | 应拒用例 | 预期失败的输出 | 对应的历史变异 |
| --- | --- | --- | --- | --- |
| `alphas_swapped` | 两级的 alpha 互换：输入级用 `alpha_out`，输出级用 `alpha_in` | `base`、`grid-phase`、`start-high`、`rails-offset`、`rail-droop`、`param-override`、`param-endpoints-low` | `vout` | 新增 |
| `clamp_fixed_0p9` | 限幅上界固定为 0.9 V，不读轨间电压 | `rails-offset`、`rail-droop`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `clamp_input_first` | 先把输入限在 `[0, s]` 再采集，输入级的采集结果不再限幅 | `base`、`rails-offset`、`param-endpoints-low` | `vout` | 新增 |
| `clamp_lower_only` | 只限下界 0 V | `base`、`rails-offset`、`rail-droop`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `clamp_output_only` | 存储值不限幅，只把 `vout` 连续限在 `[0, s]` | `base`、`rails-offset`、`rail-droop`、`param-endpoints-low` | `vout` | 新增 |
| `clamp_rails_at_start` | 轨间电压只在 t = 0 读一次 | `rail-droop` | `vout` | 新增 |
| `clamp_updated_stage_only` | 只给本 tick 更新的那一级限幅，保持的那一级不随轨收缩 | `rail-droop` | `vout` | 新增 |
| `clamp_upper_only` | 只限上界 `s` | `base`、`rails-offset`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `edge_extra_update` | 每次时钟穿越时，对转入跟踪的那一级多做一次更新 | 所有用例 | `vout` | 新增 |
| `fixed_alpha_in` | `alpha_in` 在 analog 块内写死为 0.45 | `param-override`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `fixed_alpha_out` | `alpha_out` 写死为 0.55 | `param-override`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `fixed_tedge` | `tedge` 写死为 50 ps | `param-endpoints-low` | `phase`、`vout` | 新增 |
| `fixed_tick` | `tick` 写死为 0.5 ns | `param-override`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `fixed_vinit` | `vinit` 写死为 0 V | `start-high`、`param-override`、`param-endpoints-high` | `vout` | 新增 |
| `fixed_vth` | `vth` 写死为 0.45 V | `param-override`、`param-endpoints-low`、`param-endpoints-high` | `phase`、`vout` | 新增 |
| `grid_half_offset` | tick 落在 `(k + 1/2)*tick` | 所有用例 | `vout` | 新增 |
| `grid_restart_at_edges` | 每次时钟穿越后从穿越时刻重新起算 tick | 所有用例 | `vout` | 新增 |
| `ground_referenced` | 忽略 `vss`，所有电压对地 | `rails-offset`、`rail-droop`、`param-endpoints-low`、`param-endpoints-high` | `phase`、`vout` | 新增 |
| `initial_from_vin` | 两级初值都取 t = 0 的输入 | `base`、`grid-phase`、`start-high`、`rails-offset`、`rail-droop`、`param-override`、`param-endpoints-low` | `vout` | 新增 |
| `initial_input_vin` | 输入级初值取 t = 0 的输入 | `base`、`grid-phase`、`start-high`、`rails-offset`、`param-override`、`param-endpoints-low` | `vout` | 新增 |
| `initial_output_zero` | 输出级初值为 0 V | `start-high`、`param-override`、`param-endpoints-high` | `vout` | 新增 |
| `input_sample_at_rising_edge` | 输入级不做 tick 采集，在上升穿越时理想采样输入 | `base`、`grid-phase`、`start-high`、`rails-offset`、`param-override`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `input_stage_ideal` | 输入级在低相 tick 直接复制输入（相当于 `alpha_in = 1`） | `base`、`grid-phase`、`start-high`、`rails-offset`、`param-override`、`param-endpoints-low` | `vout` | 新增 |
| `input_tracks_both_phases` | 输入级在高相也继续采集 | 所有用例 | `vout` | 新增 |
| `late_arrival_1p3tedge` | 两个输出的过渡都用 `1.3*tedge`，在评分起点之后才到达 | `param-override`、`param-endpoints-high` | `phase`、`vout` | 新增 |
| `no_clamp` | 不限幅 | `base`、`rails-offset`、`rail-droop`、`param-endpoints-low`、`param-endpoints-high` | `vout` | 新增 |
| `no_output_hold` | 输出级在每个 tick 都更新，低相不保持 | 所有用例 | `vout` | v4:736 `neg_004_no_output_hold` |
| `no_tick_at_zero` | 第一个 tick 在 t = `tick`，没有 t = 0 的 tick | `base`、`grid-phase`、`rails-offset`、`param-override`、`param-endpoints-low` | `vout` | 新增 |
| `output_copy_at_rising_edge` | 输出级不做 tick 采集，在上升穿越时直接复制输入级 | 所有用例 | `vout` | 新增 |
| `output_reads_vin` | 输出级跟踪 `vin`，而不是输入级 | 所有用例 | `vout` | 新增 |
| `output_stage_ideal` | 输出级在高相 tick 直接复制输入级（相当于 `alpha_out = 1`） | `base`、`grid-phase`、`start-high`、`rails-offset`、`rail-droop`、`param-override`、`param-endpoints-low` | `vout` | 新增 |
| `phase_fixed_levels` | `phase` 用对地的固定 0.9 V / 0 V | `rails-offset`、`rail-droop`、`param-endpoints-low`、`param-endpoints-high` | `phase` | 新增 |
| `phase_from_ticks` | `phase` 只在 tick 改变 | 所有用例 | `phase` | 新增 |
| `phase_inverted` | `phase` 极性相反 | 所有用例 | `phase` | v4:736 `neg_005_phase_monitor_wrong` |
| `single_edge_sampler` | 单级理想采样：上升穿越时把输入复制到输出，没有 tick | 所有用例 | `vout` | v4:736 `neg_002_single_edge_sampler`（v4:1236 修复题的错误包同此） |
| `transparent_output` | 输出在每个 tick 复制当前输入，低相不保持 | 所有用例 | `vout` | v4:736 `neg_001_transparent_output` |
| `vss_at_start` | `vss` 只在 t = 0 读一次 | `rail-droop` | `phase`、`vout` | 新增 |
| `wrong_track_phase` | 两级的跟踪相位互换 | 所有用例 | `vout` | v4:736 `neg_003_wrong_track_phase` |

## 应接受的候选

| 候选 | 行为 | 应接受用例 | 条件 |
| --- | --- | --- | --- |
| `alt_fast_transition` | 输出过渡用 `0.5*tedge` | 所有用例 | 无 |
| `alt_latched_span_phase` | `phase` 的高电平取最近一次 tick 读到的轨间电压 | 所有用例 | 见下 |
| `alt_level_at_tick` | 在 tick 读取时钟电平决定相位，不用穿越事件维护的状态；`phase` 仍由穿越驱动 | 所有用例 | 无 |
| `alt_limit_then_update` | 每个 tick 先按本 tick 的轨限幅，再更新，再限幅 | 所有用例 | 无 |
| `alt_two_modules` | 输入级、输出级拆成两个辅助模块，经内部节点相连 | 所有用例 | 见下 |
| `margin_arrival_1p2tedge` | 输出过渡用 `1.2*tedge`：晚于 `tedge` 期限、早于 `1.25*tedge` 评分起点 | 所有用例 | 见下 |
| `original_v4_236_gold` | 原 v4:236 gold，生成时从 historyref 原样读取，题包里不存 | 所有用例 | 见下 |

## 条件

- `alt_latched_span_phase`、`original_v4_236_gold`：`phase` 取 tick 时锁存的轨间电压，轨移动时每个 tick 都把正在进行的 `phase` 过渡改到一个相差不到 1 mV 的新目标。按 LRM 2.4 4.5.8，被打断的过渡沿“从起点到新目标在过渡时间内走完”的斜率继续，仍在 `tedge` 内到达；若后端在改目标时从当前值重走满 `tedge`，`rail-droop` 中离穿越不到 `tedge` 的 tick 会让 `phase` 晚到，该用例被拒（合成控制 `latched_span_phase_restart`）。待 Spectre 记录。
- `alt_two_modules`：两个实例在同一时刻 tick。输出级只在高相 tick 读内部节点，此时输入级只做限幅，在合法域内每 tick 最多改变 1 mV；低相更新后节点 1 ps 内到位，远小于 50 ps 的穿越间距。另一前提：`start-high` 的时钟在 t = 0 为高，输出级在 t = 0 的 tick 读节点，要求 t = 0 的直流工作点已经按 `initial_step` 的值给出 `vinit`。旧版 EVAS 0.8.7 在那里读到 0 V，`vout` 在 t = 0 为 0.135 V，拒绝 `start-high`。待 Spectre 记录。
- `margin_arrival_1p2tedge` 不是正确模型：它晚于 `tedge` 期限、早于 `1.25*tedge` 评分起点到达。按用户已确认的观察规则（F01，2026-10-28）应被接受，这是用户已接受的余量。
- `late_arrival_1p3tedge` 只要求在 `param-override` 和 `param-endpoints-high` 被拒：这两个用例在事件后 `(1.25*tedge, 1.3*tedge)` 内有评分行（`param-override` 每个改变 `b` 的 tick 后 70 ps、每个穿越后 69.5 ps；`param-endpoints-high` 6 个上升穿越后 1611 ps）。其余用例的 10 ps、20 ps、2 ps、250 ps 网格在这个窗内没有行，也没有行正好落在 `1.25*tedge` 上，迟到在那里看不到，按构造不设预期（`rail-droop` 的 vss 斜坡把 2 个穿越移出网格，那里能看到，不作要求）。
- `initial_from_vin` 不要求在 `param-endpoints-high` 被拒：那里 `vin(0) - vss` 为 1.9 V，高于 1.5 V 的轨间电压，t = 0 的 tick 把两级都限到 `vinit` = 1.5 V，只有 t = 0 这一行不同。这一行显示 `initial_step` 的值还是 tick 之后的值，取决于后端如何处理 t = 0 改写的 transition 目标（旧版 EVAS 0.8.7 显示 1.5 V，判通过）。参考解在 t = 0 不改写任何 transition 目标，因为 `vinit` 在轨内。
- `fixed_tedge` 只在 `param-endpoints-low`（`tedge` = 10 ps）被拒：其余用例的 `tedge` 不小于 50 ps，更快的过渡是允许的。
- `clamp_rails_at_start`、`clamp_updated_stage_only`、`vss_at_start` 只在 `rail-droop` 被拒，它是唯一有轨移动的用例。
- `no_tick_at_zero`：缺 t = 0 的 tick 只在时钟从低开始、第一个低相很短时可见；`start-high` 时钟从高开始，`rail-droop` 的第一个低相长，`param-endpoints-high` 的 alpha 为 1。
- 被打断的过渡不在参考解的合法域内：tick 间距不小于 `4*tedge`（`tedge <= tick/4`），穿越间距不小于 `4*tedge`；只有锁存轨电压的 `phase` 会在过渡中改目标（上面第一条）。

## 来源

除 `original_v4_236_gold` 外，全部候选都由作者按本题合同新写，通过对 `solution/circuit.va` 的文本替换或整段重写生成，没有复制外部代码。`original_v4_236_gold` 是仓库内历史资产的原样读取：`mutants.py` 只在仓库内运行时读取 `benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/236-dual-track-sample-hold/evaluator/solution/dual_track_sample_hold.va`（sha256 `edf53017…`），题包里不存这段文本；在仓库外运行时不生成这个候选。它与历史变异的对应按各变异包相对原 gold 的实际改动核对，见 SOURCE。

## 旧版 EVAS

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。逐例结果和与本表的比对在作者证据 `runs/t3-p1-build-20261029/r01-fix-r1/c061/legacy-vs-expected.json`：`param-endpoints-low` 的 47 次运行是 2026-10-29 修正 r1（r01-fix-r1）后重跑的，其余 7 个用例沿用建题时的运行、用修正后的 checker 重判（只重判，不重跑，判决与建题时相同）。旧版只给点值，不做可信证明，结果可能不准也不报错。2026-10-29 修正 r2（r01-fix-r2）给 checker 加了上述“相邻两次穿越之间离 `vth` 至少 50 mV”的台架检查，用改后的 checker 对同一批旧版输出（建题时的 378 次运行与修正 r1 的 47 次）重判，判决无一变化，本页的计数不变（`runs/t3-p1-build-20261029/r01-fix-r2/c061/legacy-regrade.json`）。

38 个 VA 错误候选与 7 个应接受的候选各 8 个用例，共 360 个条目。其中有预期的 254 个：249 个与旧版结果一致，1 个不一致，4 个旧版没有判决；未列预期的 106 个：102 个有判决，4 个没有判决。只用 strobe 网格行重判，计数相同（一致 249、不一致 1）。不一致的是 `alt_two_modules` 在 `start-high`，原因见上文“条件”一节：旧版在 t = 0 的 tick 读内部节点得到 0 V。

旧版跑不了的候选：`clamp_output_only`。它把 `transition()` 包在 `min`/`max` 里，旧版报 `continuous_body_not_lowered`，8 个用例都没有判决（其中 4 个有预期、4 个未列预期）。作者另做了在 tick 时限幅输出的探针（存储值不限幅，不进题包），单独记账：它在 `base`、`rails-offset`、`rail-droop`、`param-endpoints-low` 被拒，与 `clamp_output_only` 的应拒用例相同。

作者证据里的 Python 合成控制另有 39 个错误模型（比 VA 错误候选多一个 `early_start_0p3tedge`，它没有对应的 VA 候选）和 7 个正确模型，与上面的 VA 候选分开计数。

参考解在 8 个私有用例与公开用例上都通过，最大误差 0.0 mV；只用 strobe 网格行复判，结论不变。引用这些通过之前已核对旧版的零点处理：参考解与全部候选只对外部驱动的时钟用 `cross()`，时钟不停在门限上，不涉及检出离开零点。
