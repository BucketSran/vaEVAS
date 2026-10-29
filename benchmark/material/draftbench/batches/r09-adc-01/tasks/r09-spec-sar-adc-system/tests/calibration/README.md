# 校准候选

Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

每个候选都是完整的五模块文件。checker 只有一类失败：某个评分点上一个输出与期望值相差超过 2 mV。顶层用例检查 `code_3..code_0`、`done`、`sample_dbg`、`dac_dbg`；模块用例 `modules-default`、`modules-override` 分别检查单独实例化的 DAC、比较器、采样保持和控制器的全部输出，`modules-initial` 只实例化 DAC 和比较器，从与输入相关的初态起步。失败记录里的 `node`、`change_time` 和 `cause` 指出它属于哪次输出变化：第几次转换的采样沿、哪一位的判决沿、start 请求、复位，或模块输入的哪次穿越。输出形状、容差边界和参数端点由作者证据中的 Python 合成轨迹覆盖。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、4.5.8 `transition`、5.10.3.3 `timer` 写出。参考解的 `cross` 时间容差设为 1 ps，派生候选沿用这一设置。合同要求控制输入的穿越离 `clk` 上升沿至少 100 ps（顶层的 start 至少 `2*tr`），顶层中 `rst` 放行的时钟沿离此前的 `rst` 上升穿越至少 `2*tr`（2026-10-28 p0-fix-b 增加；已定（用户 2026-10-29，决定单第 5 项）），采样前后 100 ps 内 `vin` 变化小于 0.25 mV，样本离每个 DAC 电平至少 3 mV，所以事件定位误差在几 ps 内时判决不变。

参考解的比较器按电平判定（2026-10-29 p0-fix-e 换入）：`cmp_o` 在每个时间点取 `V(sample_i) >= V(dac_i)`，`cross()` 只在过零处放时间点。换入前的比较器靠 `cross()` 锁存状态，现在是错误候选 `comparator_cross_latch`。

列中用例简称：
- 顶层五例：`base`、`sweep`、`busy-reset`、`vss-override`、`reset-recovery-long-tr`；
- 全模块两例：`modules-default`、`modules-override`，四个模块都单独实例化；`modules-initial` 只有 DAC 和比较器；
- 时序七例：前八例中除 `modules-initial` 外的七例，即 p0-fix-e 之前含控制器或采样保持的用例；
- 参数两例：`vss-override`、`modules-override`；
- 复位六例：`base`、`busy-reset`、`vss-override`、`reset-recovery-long-tr` 与全模块两例；
- 零平台三例（p0-fix-e 加，顶层，默认参数）：`zero-plateau-vss`、`zero-plateau-from-below`、`zero-plateau-from-above`。顶层内部比较器两输入之差停在 0 的平台之后，前两例差值走向负侧（下一个样本为 `vss`），后一例从正侧回到 0 后再走向正侧（样本 0.60 V）；
- 两个复位零平台例：`zero-plateau-from-below`、`zero-plateau-from-above`，零平台由转换中或武装中的复位造成；
- 全部：十一个用例。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `dac_span_reading` | DAC 为 `vss + vref*c/16`（按跨度理解，用户未选的读法） | 参数两例 | `dac_dbg`、码 |
| `dac_old_public_formula` | DAC 为 `vref*c/16`（旧公开公式） | 参数两例 | `dac_dbg`、码 |
| `dac_divisor_15` | DAC 步长为量程的 1/15（v4:842 neg_002） | 全部 | `dac_dbg`、码 |
| `cdac_bit_order_reversed` | DAC 把 `bit_0` 当最高位 | 全部 | `dac_dbg`、码 |
| `cdac_initial_bits_zero` | DAC 在 t = 0 把四个位记成 0，之后的穿越照常更新 | `modules-initial` | `cdac_o`（t = 0 起） |
| `comparator_polarity` | 样本低于 DAC 时输出 1：电平判定取反（v4:1342 的故障、v4:842 neg_003） | 全部 | 码、`cmp_o` |
| `comparator_reads_live_vin` | 顶层把比较器接到实时 `vin`，不接保持的样本；采样保持和 `sample_dbg` 照常 | 顶层五例 | 码 |
| `comparator_initial_high` | 比较器在 t = 0 一律输出 1，之后靠 `cross()` 锁存更新（保留换入前的锁存写法） | `modules-initial`、零平台三例（后者条件见下） | `cmp_o`（t = 0 起）；零平台三例为码 |
| `comparator_cross_latch` | 换入前参考解的比较器：`initial_step` 按电平取初值，之后只在 `cross()` 事件更新 | 零平台三例（条件见下） | 码：`zero-plateau-vss`、`zero-plateau-from-below` 得 15（合同 0），`zero-plateau-from-above` 第二次转换得 0（合同 10） |
| `sh_ignores_sample_en` | 采样保持在每个时钟沿都采样 | 时序七例、两个复位零平台例 | `sample_dbg`、码 |
| `sh_samples_in_reset` | `rst` 为高时也采样 | 全模块两例、`reset-recovery-long-tr` | `sh_o`、`sample_dbg` |
| `sh_samples_at_sample_en_rise` | 在 `sample_en` 上升时采样，不等时钟沿 | 时序七例、两个复位零平台例 | `sample_dbg`、码 |
| `sample_clamped_at_vss` | 保持值低于 `vss` 时取 `vss` | `base`、`sweep`、`vss-override`、全模块两例 | `sample_dbg` |
| `sh_reset_does_not_clear` | 复位不清采样保持的值 | 复位六例、两个复位零平台例 | `sample_dbg` |
| `sample_one_edge_late` | start 后第二个时钟沿才采样 | 时序七例、零平台三例 | 时序 |
| `first_decision_at_sample_edge` | 采样沿就判决最高位 | 时序七例、零平台三例 | 时序、码 |
| `idle_edge_before_decisions` | 采样后空一个沿再判决 | 时序七例、零平台三例 | 时序 |
| `keep_every_trial_bit` | 比较失败也保留试位 | 时序七例、零平台三例 | 码 |
| `next_trial_from_trial` | 下一个试位建在旧试位上，不建在已判定的 `R` 上 | 时序七例、零平台三例 | 码、`dac_dbg` |
| `decided_bits_lost` | 下一个试位只含新的一位 | 时序七例、两个复位零平台例 | 码、`dac_dbg` |
| `code_only_at_done` | 码输出只在 done 时更新，start 不清 | 时序七例、两个复位零平台例 | 码 |
| `done_kept_at_start` | start 不清 `done` | 时序七例、`zero-plateau-from-above` | `done` |
| `done_one_clock` | `done` 只高一个时钟周期 | 时序七例中除 `sweep` 外、`zero-plateau-vss` | `done` |
| `dac_keeps_final_at_start` | start 不把试位码清零 | 时序七例、`zero-plateau-from-above` | `dac_dbg` |
| `dac_shows_last_trial_after_done` | done 后试位码保持最后一次试位 | 时序七例、零平台三例 | `dac_dbg` |
| `trial_lags_one_edge` | 试位输出晚一个时钟沿 | 时序七例、零平台三例 | `dac_dbg`、码 |
| `busy_start_ignored` | 转换中的 start 被忽略（另一种读法） | `base`、`busy-reset`、全模块两例 | 码、`done` |
| `level_sensitive_start` | 空闲时 start 为高就开始转换 | `base`、全模块两例 | 码、`done` |
| `falling_edge_clock` | 用 `clk` 下降沿 | 时序七例、零平台三例 | 时序 |
| `synchronous_reset` | 复位只在 `rst` 为高的时钟沿生效 | 复位六例、两个复位零平台例 | 码、`done`、`sample_dbg` |
| `reset_keeps_conversion` | 复位只清码和 `done`，转换继续 | 复位六例、两个复位零平台例 | 码、`done` |
| `start_latched_in_reset` | 复位期间的 start 被记住，释放后开始转换 | `base`、全模块两例 | 码、`sample_dbg` |
| `sample_en_cleared_at_next_edge` | 复位不拉低 `sample_en`，到下一个时钟沿才清；武装中复位后，采样保持在那个沿仍读到高电平而采样 | `reset-recovery-long-tr`、`zero-plateau-from-above` | `sample_dbg`（多出的一次采样） |
| `slow_output_1p3tr` | 过渡时间 1.3·tr，到达晚于评分起点 1.25·tr | 全部 | 评分起点后第一个点 |
| `hardcoded_vss_0` | 低电平和下端点写死 0 V | 参数两例 | 电平、码 |
| `hardcoded_vref_0p9` | 上端点写死 0.9 V | `modules-override` | `cdac_o` |
| `hardcoded_vdd_0p9` | 高电平写死 0.9 V | 参数两例 | 电平 |
| `hardcoded_vth_0p45` | 门限写死 0.45 V | 参数两例 | 时序、码 |
| `hardcoded_tr_200p` | 过渡时间写死 200 ps | 参数两例 | 1.25·tr 时未到达 |
| `original_v4_342_gold` | 原 v4:342 五个 gold 模块原样提交 | 参数两例 | `dac_dbg`、码 |
| `alt_gold_style_continuous`（正确） | 比较器与 DAC 连续求值（gold 写法，比较器不放 `cross()` 时间点），DAC 按端点公式 | 无（条件见下） | 无 |
| `alt_mask_pointer_controller`（正确） | 控制器用单热掩码记位置 | 无 | 无 |
| `alt_fast_output`（正确） | 过渡时间 0.2·tr | 无 | 无 |
| `alt_delayed_within_tr`（正确） | 延迟 0.2·tr 后用 0.8·tr 过渡，正好在 tr 到达 | 无 | 无 |
| `alt_fast_sample_en`（正确） | 只把控制器的 `sample_en` 改为 0.1·tr 过渡 | 无 | 无 |
| `margin_arrival_1p2tr`（用户已接受的余量） | 过渡时间 1.2·tr：晚于期限 tr，早于评分起点 1.25·tr | 无 | 无 |

`hardcoded_tr_200p` 在 `reset-recovery-long-tr`（`tr = 1 ns`）中不被拒：200 ps 的过渡早于期限到达，合同允许。

零平台三例各自能区分的候选：
- `zero-plateau-vss`：样本恰为 `vss`，每次判决都不保留，`R` 始终为 0，`sample_dbg` 不变。所以只改 `R` 的显示或在 `R = 0` 时等价的候选（`decided_bits_lost`、`code_only_at_done` 等）在这一例不被拒；完成后还有一个空闲时钟沿，`done_one_clock` 在零平台三例中只在这一例被拒。
- `zero-plateau-from-below`：第一次转换在判完一位后被复位放弃，第二次转换的样本为 `vss`。
- `zero-plateau-from-above`：完成后的 start（`done` 为高、试位为最终码），以及 start 后 3 ns 的武装中复位，所以 `done_kept_at_start`、`dac_keeps_final_at_start`、`sample_en_cleared_at_next_edge` 在这一例被拒。
- 两个复位零平台例里 `vin` 在 4.045 ns 的空闲时钟沿已是 0.60 V，`sh_ignores_sample_en` 在那里多采一次样；`zero-plateau-vss` 的 `vin` 一直是 `vss`，看不出。

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- 全部条目：假定 `cross()` 事件定位在穿越后几 ps 内，并假定一个模块在时钟事件读取另一个模块 `transition()` 输出节点时，读到的是该事件之前的值（LRM 4.5.8，同一事件启动的过渡在该时刻还没有移动）。参考解本身也依赖这一点：采样沿上控制器拉低 `sample_en`，采样保持仍读到高电平。Spectre 上要记录。
- `alt_gold_style_continuous`：连续求值的比较器和 DAC 在输入穿越后的下一个时间点才翻转。模块用例在穿越后 0.1·g 处放了 PWL 拐点，顶层的判决在 4 ns 后才读取，所以按预期应被接受。Spectre 上要确认时间点。
- `alt_delayed_within_tr`：用了 0.2·tr 的传输延迟，属于待发过渡。改变输出的事件至少相隔 100 ps，不会出现待发过渡被新变化覆盖。
- `margin_arrival_1p2tr`：不是正确模型，它晚于期限 tr 到达。按用户已确认的观察规则（F01 选 A，2026-10-28），评分起点前到达的输出不判错，这是已接受的余量。
- `original_v4_342_gold`：模块名与端口和本题相同，原样使用；它的 DAC 是 `vss + vref*code/16`，即用户未选的跨度读法；`mutants.py` 只在仓库内运行时从 `benchmark/material/historyref` 读取生成。
- `sample_en_cleared_at_next_edge`：被拒依赖上面同刻读取的假定：清 `sample_en` 的那个时钟沿上，采样保持仍读到高电平。`reset-recovery-long-tr` 中武装后的复位在下一个时钟沿前 `2*tr` 加 9.375 ps，即复位恢复间隔的下限加设计余量（p0u17-fix-r4：间隔恰在下限是平局）；`zero-plateau-from-above` 中武装后的复位在下一个时钟沿前 3 ns。
- 复位恢复间隔（`reset_recovery`）：顶层用例里 `rst` 放行的时钟沿离此前的 `rst` 上升穿越至少 `2*tr`。控制器的 `sample_en` 在期限 `tr` 内拉低，所以满足各模块期限的组合在该沿不会再采样。这条合法域是 2026-10-28 p0-fix-b 加的，已定（用户 2026-10-29，决定单第 5 项）；`reset-recovery-long-tr`（`tr = 1 ns`）有三次在时钟沿前 `2*tr` 加 9.375 ps 的复位（p0u17-fix-r4 的设计余量）。
- `comparator_cross_latch`：它被拒取决于仿真器在内部差值离开零平台时不触发 `cross()`（归档 Spectre 的到达规则：到达 0 时按到达方向记一次事件，离开 0 不记）。Spectre 21.1 探针 `spectre-P0probe-C109-v1` 的结果已证实（2026-10-29 已正式核收，执行身份 `spectre-P0probe-C109-v1（结果包 sha256 2c4e79eb7fa60d24…）`）：换入前的参考解（比较器代码与本候选相同，只差比较器上方的注释）在同样的激励上得码 15、15 与 10 后 0，checker 判失败。若仿真器只在变号时记事件，只有 `zero-plateau-vss` 拒绝它。旧版 EVAS 0.8.7 上它在零平台三例都通过，这是旧版零点处理的掩盖（样板 r2.16 第 4 节第 4 条：旧版对离开零点的处理相当于电平判定），不能当它正确的证据。前八例的零平台都向正侧离开或延续到记录结束，所以它在前八例都通过。
- `comparator_initial_high`：在 `modules-initial` 因初值被拒，与语义无关。它保留换入前的 `cross()` 锁存，所以在零平台三例按 `comparator_cross_latch` 的同一条件被拒；顶层 t = 0 时差值为 0，`initial_step` 置 1 与电平判定相同，被拒只来自锁存。
- 零平台三例（`zero_plateau`）：参考解和其余候选的比较器按电平判定或连续求值，判决沿读到的就是 `x - DAC(T)` 的符号，判决与仿真器的零点语义无关；依赖零点语义的只有上面两个锁存候选。

合成控制的对应范围：
- `expected.json` 的 `author_synthetic_control` 是作者证据中对应的 Python 合成控制。
- 带 `author_synthetic_control_cases` 的条目，合成控制只在所列用例上模拟了 VA 候选的行为：`sh_ignores_sample_en`、`sh_samples_in_reset` 只改了模块分支，只在全模块两例；`comparator_initial_high` 的控制在顶层按电平判定，只在前八例与 VA 的锁存一致（p0-fix-e）。其余用例上的拒绝只由 VA 矩阵、旧版观测和下一条的精确模型支持。
- `comparator_cross_latch` 的控制 `comparator-cross-latch/甲` 不是合同层的 Python 模型，而是精确事件模型（p0-fix-d 的 `c109_model.py`，比较器按语义甲）在用例网格上的波形；同一模型按语义乙给出的被拒范围只有 `zero-plateau-vss`。顶层用例里它同样模拟 `comparator_initial_high`。
- `comparator_reads_live_vin` 改用忠实的控制 `comparator-reads-live-vin`（p0-fix-e）：判决读实时 `vin`，采样保持与 `sample_dbg` 照常。原控制 `no-sample-hold-live-vin` 让 `sample_dbg` 也跟随 `vin`，在两个复位零平台例上会多拒；新控制在前八例的判决与原控制相同。
- `cdac_bit_order_reversed` 的合成控制在全部用例上都模拟 VA 候选（p0-fix-c，审核 R2-03）：位状态照输入记录，只在 DAC 电平公式里反转权重，t = 0 的初态与每次更新都按同一映射。p0-fix-b 的版本初态按正常位序、更新按反序，`modules-initial` 从 t = 0 起与 VA 不同（码 11 读成 0.61875 V，VA 为 0.73125 V），顶层用例也没有模拟。修正后，它在前八例的全部稳定评分行上与旧版存档的 VA 波形一致（最大差 2.2e-16 V，只是浮点舍入），所以去掉了该条目的 `author_synthetic_control_cases`。这是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- `sh_samples_at_sample_en_rise` 的合成控制是 `sh-samples-at-sample-en-rise`：
  - 顶层在控制器 `sample_en` 上升穿越 `vth` 时立即取样并更新保持值，时钟沿不再取样，判决用这个保持值；
  - 独立的采样保持在 `sh_en` 上升穿越时取样。
  它在时序七例与两个复位零平台例都被拒，与 VA 矩阵一致。原先关联的 `sample-at-start-crossing` 在 start 请求时读 `vin`、到采样沿才更新，只是相关故障，不再作为它的对应控制。

参考解没有待发事件：它的 `transition()` 延迟为 0，也没有定时器。上面的待发事件只属于校准候选，与参考解分别判断。

旧版 EVAS 0.8.7 上的运行结果记在作者证据中，不改变这张表。`comparator_cross_latch` 与 `comparator_initial_high` 在零平台三例上旧版通过、本表要求拒绝，原因见上面的条件：旧版的零点处理掩盖了锁存的问题。
