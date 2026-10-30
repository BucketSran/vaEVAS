# 校准候选

Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

checker 只有一类失败：某个评分点上 `code_3..code_0`、`valid_o` 或 `residue_dbg` 与期望值相差超过 2 mV。失败记录里的 `output_change`、`change_time` 和 `cause` 指出它属于哪一次输出变化，`cause` 写明该时钟沿发布的是第几个样本、它在哪个沿被采入，或是复位清零。`tr` 内的输出形状、容差边界和参数端点由作者证据中的 Python 合成轨迹覆盖。修正 r7a 起，期望 `residue_dbg` 变化超过 δ 才算变化（δ = 0.25 mV：修正 r7a 定为 0.1 mV，修正 r8 改为 0.25 mV），δ 以内的变化不开不评分窗，期望值保持原值；码与 `valid_o` 照旧精确比较。台架义务不满足时 checker 抛出异常，记 checker_error，不判分；修正 r7a 加了一条：同一控制输入相邻两次穿越之间离 `vth` 不足 49 mV（合同写 50 mV）。这一条与控制输入的起点、停留、碰到都按用例网表的激励定义判（2026-10-30 修正 v417），碰到报台架错误。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、5.10.3.3 `timer`、4.5.8 `transition` 与 4.2 `floor` 写出。参考解的 `cross` 时间容差设为 1 ps，派生候选沿用这一设置。合同要求每个 `clk` 上升穿越前后 100 ps 内 `vin` 变化小于 0.25 mV，`valid_i` 与 `rst` 的穿越离它至少 100 ps，所以事件定位误差在几 ps 内时判决不变。

列中"全部"指 `base`、`stream-irregular`、`reset-recovery`、`param-override` 四个用例；"越界三例"指 `base`、`stream-irregular`、`param-override`，这三例有低于 `vss`、高于 `vref` 或正好等于 `vref` 的样本；"复位三例"指 `base`、`reset-recovery`、`param-override`，这三例有落在两个时钟沿之间的 `rst` 脉冲。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `center_residue_no_midscale` | 残差 `vss + 4*(x - c)` 再限幅，不加中值偏移（v4:096 D1 的字面读法） | 全部 | 码、`residue_dbg` |
| `edge_residue_midscale_offset` | 残差相对箱沿再加中值偏移，`(vss+vref)/2 + 4*(x - 箱沿)` | 全部 | 码、`residue_dbg` |
| `residue_gain_2` | 残差增益 2 | 全部 | 码、`residue_dbg` |
| `rounded_coarse_thresholds` | 粗量化门限在 1/8、3/8、5/8 量程（四舍五入） | 全部 | 码、`residue_dbg` |
| `rounded_fine_thresholds` | 第二级门限在 1/8、3/8、5/8 量程 | 全部 | 码 |
| `stage_order_swapped` | 码为 `4*f + k` | 全部 | 码 |
| `low_bits_swapped` | `code_1` 与 `code_0` 互换（v4:343 的覆盖缺口） | 全部 | 码 |
| `no_input_limit_wraps` | 不限幅，粗码可为 -1 或 4，码按 4 位回绕 | 越界三例 | 码 |
| `residue_from_unlimited_input` | 粗码用限幅后的样本，残差用未限幅的 `V(vin)` | 越界三例 | `residue_dbg` |
| `top_bin_floor_at_vref` | 粗码取 `floor(4*(x - vss)/span)`，`x = vref` 得 4 | 越界三例 | 码 |
| `live_input_residue` | 残差由实时 `vin` 与保持的粗码算出，第二级判决读实时残差（v4:343 gold 的行为） | 全部 | 码、`residue_dbg` |
| `track_while_clock_high` | 采样沿后 `clk` 为高时第一级跟踪 `vin`，下降沿才保持 | 全部 | 码、`residue_dbg` |
| `residue_one_cycle_then_vss` | 没有新样本的时钟沿把 `residue_dbg` 置为 `vss` | 全部 | `residue_dbg` |
| `stage2_takes_new_sample` | 同一沿先采新样本、再做第二级判决，连续样本时细码取自下一个样本 | 全部 | 码 |
| `aligner_takes_new_coarse` | 发布时取第一级当前保持的粗码，连续样本时粗码取自下一个样本 | 全部 | 码 |
| `latency_one_edge` | 采样后的第一个沿就发布（v4:343 D1 字面变体） | 全部 | 码、`valid_o` |
| `latency_three_edges` | 采样后的第三个沿才发布 | 全部 | 码、`valid_o` |
| `sticky_valid` | `valid_o` 置高后保持到复位 | 全部 | `valid_o` |
| `valid_5ns_pulse` | `valid_o` 是发布后 5 ns 的定宽脉冲 | 全部 | `valid_o` |
| `advance_only_on_valid` | 流水线只在 `valid_i` 为高的沿推进（弹性流水） | 全部 | 码、`valid_o` |
| `ignores_valid_i` | 每个时钟沿都采样 | 全部 | 码、`valid_o`、`residue_dbg` |
| `valid_not_pipelined` | `valid_o` 直接取本沿的 `valid_i` | 全部 | `valid_o` |
| `code_zero_between_results` | 不发布结果的沿把码清零 | 全部 | 码 |
| `falling_edge_clock` | 用 `clk` 下降沿 | 全部 | 全部输出 |
| `synchronous_reset` | 复位只在 `rst` 为高的时钟沿生效 | 复位三例 | 码、`valid_o`、`residue_dbg` |
| `reset_keeps_pipeline` | 复位清输出，但在途样本照常发布 | 复位三例 | 码、`valid_o` |
| `reset_keeps_residue` | 复位不清第一级样本，`residue_dbg` 保持 | 复位三例 | `residue_dbg` |
| `reset_keeps_code` | 复位只清 `valid_o`，码保持 | 复位三例 | 码 |
| `samples_while_rst_high` | `rst` 为高时时钟沿照常采样推进，只有上升穿越清零 | `base`、`reset-recovery` | 码、`valid_o` |
| `slow_output_1p3tr` | 过渡时间 1.3·tr，到达晚于评分起点 1.25·tr | 全部 | 评分起点后第一个点 |
| `hardcoded_vss_0` | 低电平和量程下端写死 0 V | `param-override` | 电平、码 |
| `hardcoded_vref_0p9` | 量程上端写死 0.9 V | `param-override` | 码、`residue_dbg` |
| `hardcoded_vdd_0p9` | 高电平写死 0.9 V | `param-override` | 电平 |
| `hardcoded_vth_0p45` | 门限写死 0.45 V | `param-override` | 码、`valid_o` |
| `hardcoded_tr_200p` | 过渡时间写死 200 ps | `param-override` | 1.25·tr 时未到达 |
| `original_v4_343_gold` | 原 v4:343 五个 gold 模块加新模块名外壳 | 全部 | `residue_dbg`、码 |
| `alt_compute_then_delay`（正确） | 采样沿一次算出 `floor(16*(x - vss)/span)` 和箱沿式残差，再经两级寄存器发布 | 无 | 无 |
| `alt_three_module_hierarchy`（正确） | 三个模块：第一级、第二级、对齐器，经电气节点相连 | 无（条件见下） | 无 |
| `alt_fast_output`（正确） | 过渡时间 0.2·tr | 无 | 无 |
| `alt_delayed_within_tr`（正确） | 延迟 0.2·tr 后用 0.8·tr 过渡，正好在 tr 到达 | 无 | 无 |

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- `alt_three_module_hierarchy`：第二级与对齐器在时钟沿读取第一级的 `transition()` 输出节点。按 LRM 4.5.8，同一事件启动的过渡在该时刻还没有移动，所以读到的是该沿之前保持的值。Spectre 上要记录这一点。
- `alt_delayed_within_tr`：用了 0.2·tr 的传输延迟，属于待发过渡。用例中改变输出的事件至少相隔 100 ps，所以不会出现待发过渡被新变化覆盖的情形。
- `valid_5ns_pulse`：用了起点会移动的 `@(timer)`。无论被替换的定时事件是否仍然触发，它都应被拒。
- `original_v4_343_gold`：需要带 `#()` 参数改写的层次实例；`mutants.py` 只在仓库内运行时从 `benchmark/material/historyref` 读取原 gold 生成它。

参考解没有待发事件：它的 `transition()` 延迟为 0，也没有定时器。上面两项待发事件只属于校准候选，与参考解分别判断。

旧版 EVAS 0.8.7 上的运行结果记在作者证据中，不改变这张表。

## 修正 r7a（2026-10-29）

- `stream-irregular` 里 13 对恰为 4 ns 的相邻上升沿改为 4.05 ns；`reset-recovery` 的复位离发布沿 101.875 ps，原为恰好 100 ps。详见 `SOURCE.md` 的“2026-10-29 修正 r7a”一节。
- 码序列与码边界余量都不变；被拒矩阵不变。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：
  - 参考解与 40 个候选在改后的两例上重跑，参考解另跑公开 `base`，共 83 次；
  - 判决与 `expected.json` 逐项一致，只用网格行重判的结论相同。
- `base`、`param-override` 与公开 `base` 的激励没改，已跑的 P0PC 结果（包 `spectre-P0PC-must-01-v1`，结果包 sha256 `56bb45dd…`）用新 checker 重判即可。

## 修正 r8（2026-10-29）

- `residue_dbg` 的变化门限 δ 由 0.1 mV 改为 0.25 mV，题面与两份 checker 同改。依据与算式见 `SOURCE.md` 的“2026-10-29 修正 r8”一节：按合同最宽参数，第 20 条的下界是 0.2008 mV。
- 被拒矩阵与 `expected.json` 不变；`expected.json` 与 `mutants.py` 都没有写到 δ。
- 判决不变（未仿真）：P0PC 已交回的本题 210 个作业、已存档的 166 次旧版波形（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）用改前、改后两版 checker 重判，判决逐个相同；建题的合成模型判决也相同。
