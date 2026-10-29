# 校准候选

Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

checker 只有一类失败：某个评分点上 `code_7..code_0`、`valid` 或 `overflow` 与期望电平相差超过 10 mV。失败记录里的 `output_change`、`change_time`、`cause` 和 `expected_code` 指出它属于哪一次输出变化（哪次测量的 stop、溢出、清零或复位）。`tr` 内的输出形状由作者证据中的 Python 合成轨迹覆盖。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、5.10.3.3 `timer`、4.5.8 `transition` 与 4.2 `floor` 写出。参考解的 `cross` 时间容差设为 1 ps；候选沿用这一设置。合同要求每个 start、stop 事件离任何细码边界至少 20 ps，台架实际留了 30 ps 以上，所以事件定位误差在几 ps 内时判决不变。

用例为 `base`、`phase-sweep`、`reset-warmup`、`param-override` 和 `two-ref-short`，表中"全部"指这五例。`two-ref-short` 是 2026-10-28 p0-fix-b 加的：记录里只有两个参考上升沿，第二个沿后完成一次同周期测量，结果 11，没有借位、跨周期、清零、复位或溢出，只在这些情形出错的候选在该例不被拒。同一轮 `reset-warmup` 与 `param-override` 的事件相位改为网格的 0.9 倍（含参考上升沿），细码与结果不变。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `stop_phase_only` | 只用 stop 细码，`D = 16*N + q_e`（v4 原题的代理量） | 全部 | 码 |
| `concatenated_no_borrow` | 粗码与细码差直接拼接，`q_e < q_s` 时不借位，多算一周期 | 除 `two-ref-short` 外 | 码 |
| `clamped_fine_difference` | 细码差小于 0 时取 0 | 除 `two-ref-short` 外 | 码 |
| `time_based_coarse_count` | 粗计数取 `floor((t_stop - t_start)/T_ref)`，不数参考沿 | 除 `two-ref-short` 外 | 码（少算一周期） |
| `rounded_fine_codes` | 细码四舍五入 | 除 `two-ref-short` 外 | 码 |
| `next_edge_sign_error` | 细时间量到下一个参考沿，却按"上一沿"的符号组合 | 全部 | 码 |
| `extra_coarse_edge` | 把 start 之前的参考沿也计入 `N` | 全部 | 码 |
| `fixed_period_4ns` | 细码按固定 4 ns 归一 | `reset-warmup`、`param-override`、`two-ref-short` | 码 |
| `no_warm_up` | 只有一个参考沿就接受 start | `base`、`reset-warmup`、`two-ref-short` | 码、`valid` |
| `warm_up_survives_reset` | 复位不重新预热，复位期间的参考沿也计数 | `reset-warmup` | 码、`valid` |
| `overflow_only_at_stop` | 不在第 16 个参考沿结束，等到 stop 才饱和 | `base`、`reset-warmup`、`param-override` | 码、`valid`、`overflow` |
| `overflow_code_zero` | 溢出时码为 0 | `base`、`reset-warmup`、`param-override` | 码 |
| `overflow_flag_missing` | 溢出时不置 `overflow` | `base`、`reset-warmup`、`param-override` | `overflow` |
| `restart_ignored` | 测量中的 start 被忽略 | `base`、`reset-warmup` | 码 |
| `stop_keeps_measurement` | stop 发布结果后仍在测量，后来的 stop 再次发布 | `base` | 码 |
| `start_keeps_result` | 被接受的 start 不清除旧结果 | 除 `two-ref-short` 外 | 码、`valid` |
| `reset_keeps_measurement` | 复位只清输出，不结束测量 | `reset-warmup` | 码、`valid` |
| `ref_falling_edges` | 用参考时钟下降沿计数和量相位 | 全部 | 码 |
| `bit_order_reversed` | `code_7` 接最低位 | 全部 | 码 |
| `hardcoded_vth_045` | 门限写死 0.45 V | `param-override` | 码、`valid` |
| `hardcoded_vdd_09` | 高电平写死 0.9 V | `param-override` | 电平 |
| `hardcoded_tr_200p` | 过渡时间写死 200 ps | `param-override` | 1.25·tr 时未到达 |
| `slow_output_1p3tr` | 过渡时间 1.3·tr，到达晚于评分起点 1.25·tr | 全部 | 评分起点后第一个点 |
| `alt_nutt_complement`（正确） | Nutt 写法：细时间量到下一个参考沿，`D = 16*N + t1 - t2` | 无 | 无 |
| `alt_timestamp_overflow_timer`（正确） | 粗计数由两端最近参考沿的时间戳求出，溢出用定时器 | 无（条件见下） | 无 |
| `alt_fast_output`（正确） | 过渡时间 0.2·tr | 无 | 无 |
| `alt_delayed_within_tr`（正确） | 延迟 0.2·tr 后用 0.8·tr 过渡，正好在 tr 到达 | 无 | 无 |

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- `alt_timestamp_overflow_timer`：接受的前提是定时器在算出的第 16 个参考沿时刻触发，误差小于 20 ps 的细码余量。
- 全部条目都假定 `cross()` 事件定位在阈值穿越后几 ps 内；Spectre 的实际事件精度待记录。

旧版 EVAS 0.8.7 上 27 个候选都能运行，判决与上表逐项一致，结果见作者证据；p0-fix-b 在改动的 `reset-warmup`、`param-override` 和新的 `two-ref-short` 上重跑了全部候选，也与上表一致。旧版结果不改本表。只用标量状态、不用 `absdelay` 和数组的正确实现：参考解与全部 4 个 `correct/` 候选。
