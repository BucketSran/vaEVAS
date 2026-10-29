# 校准候选（first30-calib-r1）

2026-10-29 新建。未仿真：下面的矩阵是按 checker 推导、经合成控制核对的期望，待 D2 Spectre 校准。同日 first30-fix-r4 按 F01 用户决定改了题面的观察时刻与清零期限，加了用例 `param-vdd-vth-sample-read-reset`、`reset-high-across-clock-edge` 与三个候选，各节已同步，改动见末节“first30-fix-r4 修正”。

`mutants.py` 由 `solution/circuit.va` 生成 VA 候选：`wrong/` 应被拒，`correct/` 应被接受，都用 `../cases.json` 的私有用例和 `../../environment/starter/testbench/cases.json` 的公开用例、同一 checker 判定。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新建或空目录>`，输出目录必须是新的或空的；两次生成逐字节相同。`original_v4_349_gold` 是原 gold 套壳：只在本仓库内运行时从 `benchmark/material/historyref` 读取，题包里不存 gold 文本，在仓库外运行时不写这个候选。

`expected.json` 是同一被拒矩阵的机器可读形式：私有用例写在 `cases` 和各候选的 `must_reject`/`must_accept`；公开用例写在 `public_cases`（`same_as_private` 指出与之完全相同的私有用例，没有则为 null）和各候选的 `public_must_reject`/`public_must_accept`。`author_synthetic_control` 是对应的候选模型合成控制名。

checker（`tests/v2_integration.py:139-152`）只有一类失败：在 `tests/cases.json` 冻结的检查时刻，`out`、`ch_sel_1`、`ch_sel_0` 或 `valid` 与期望值相差超过 3 mV，或在列出的保持窗里 `out` 的某一行相差超过 3 mV。

## 用例

| 用例 | 集合 | 内容 |
| --- | --- | --- |
| `sample-read-reset` | 私有 | 15/75/135 ns 采样（75、135 ns 同时读），25–55、75–95、115–155 ns 读，65、165 ns 暂停，101 ns 复位；检查点在各事件后 0.95–0.99 ns，另有 60–70 ns、160–173 ns 两个 out 保持窗 |
| `reset-during-sample-high` | 私有 | 15 ns 采样后适配时钟仍为高时 rst 在 16.01 ns 上升；17 ns 与 26–56 ns 检查帧已清零 |
| `architecture-gain-0.75-sample-read-reset` | 私有 | sample-read-reset 换成增益 0.75 的诊断 sample_hold |
| `architecture-gain-0.6-sample-read-reset` | 私有 | sample-read-reset 换成增益 0.6 的诊断 sample_hold |
| `param-vdd-vth-sample-read-reset` | 私有 | first30-fix-r4 新加：sample-read-reset 的时序，实例写 `vdd=1.0 vth=0.5`；clk、rst、sample、read 0 到 1.0 V，四通道输入每帧都不同（最高 0.98 V）；检查点与保持窗同 sample-read-reset |
| `reset-high-across-clock-edge` | 私有 | first30-fix-r4 新加：rst 在 41.05 ns 上升、47.05 ns 下降，高电平跨过 45.01 ns 的 clk 上升沿，该沿 sample（42–48 ns）与 read（42–58 ns）都为高，应清零而不读、不采；之后 55.01 ns 读、65.01 ns 采样、75–95 ns 读出新帧；检查点在各事件后 0.95–0.99 ns，另有 60–74 ns 的 out 保持窗；105 ns |
| `sample-read-reset` | 公开 | 与私有 `sample-read-reset` 完全相同 |

## 被拒矩阵

“拒”为应被拒，“过”为应通过。

| 候选 | 组 | 失败类别 | `sample-read-reset` | `reset-during-sample-high` | `architecture-gain-0.75-sample-read-reset` | `architecture-gain-0.6-sample-read-reset` | `param-vdd-vth-sample-read-reset` | `reset-high-across-clock-edge` | 公开 `sample-read-reset` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `read_pause_advance` | wrong | 暂停时仍推进读指针 | 拒 | 拒 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `valid_sticky` | wrong | read 低时不清 valid | 拒 | 过 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `reset_output_stale` | wrong | 复位不清 out | 拒 | 过 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `reset_clock_high_bank_stale` | wrong | 漏掉复位适配（适配时钟已高时复位不清帧） | 过 | 拒 | 过 | 过 | 过 | 过 | 过 |
| `channel0_only` | wrong | 连线错（四个部件都采通道 0） | 拒 | 过 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `read_after_capture` | wrong | 状态更新顺序错（先采新帧再读） | 拒 | 过 | 拒 | 拒 | 拒 | 过 | 拒 |
| `continuous_mux_output` | wrong | out 连续跟随所选保持节点（sample 改变正在保持的 out） | 拒 | 过 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `architecture_bypass` | wrong | 架构旁路（帧存在变量里，部件不参与） | 过 | 过 | 拒 | 拒 | 过 | 过 | 过 |
| `original_v4_349_gold` | wrong | 原 gold 套壳（v4:349 四文件合一） | 拒 | 过 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `rst_high_clk_as_normal_edge` | wrong | 漏掉 rst 为高时的 clk 沿清零（当普通沿处理） | 过 | 过 | 过 | 过 | 过 | 拒 | 过 |
| `late_clear_after_check` | wrong | 迟到负例（清零在 rst 穿越后 1.04 ns 完成，晚于 0.95 ns 检查点） | 拒 | 过 | 拒 | 拒 | 拒 | 拒 | 拒 |
| `alt_one_hot_token` | correct | 正确替代（独热读令牌） | 过 | 过 | 过 | 过 | 过 | 过 | 过 |
| `inwindow_clear_before_check` | correct | 窗内对照（清零在 0.92 ns 完成：晚于 0.9 ns 期限、早于 0.95 ns 检查点） | 过 | 过 | 过 | 过 | 过 | 过 | 过 |

## 候选说明

- `read_pause_advance`（wrong，仓库内历史候选，逐字节相同）：复位外每个 clk 沿都先推进指针，读沿再推进一次：首个读沿就读到通道 1/3，sel 与 out 都错。合成控制 `model-read_pause_advance`。
- `valid_sticky`（wrong，新写）：read 低的 clk 沿不把 valid 拉低，只有复位清它：65/165 ns 的暂停沿后 valid 仍为高。合成控制 `model-valid_sticky`。
- `reset_output_stale`（wrong，仓库内历史候选，逐字节相同）：rst 上升清指针、sel、valid，但 out 保持 0.22 V（或乘诊断增益）直到下一次读。合成控制 `model-reset_output_stale`。
- `reset_clock_high_bank_stale`（wrong，仓库内历史候选，逐字节相同）：没有延迟复位时钟与输入钳位：复位时适配时钟若已为高，部件看不到新上升沿，四个帧保留旧值。合成控制 `model-reset_clock_high_bank_stale`。
- `channel0_only`（wrong，仓库内历史候选，逐字节相同）：三处实例输入改成 a0；帧四个值都等于 ch0。合成控制 `model-channel0_only`。
- `read_after_capture`（wrong，新写）：读数推迟到 clk 沿后 150 ps，部件已采下新帧：sample 与 read 同高的 75/135 ns 沿读出新帧而不是旧帧。合成控制 `model-read_after_capture`。
- `continuous_mux_output`（wrong，新写）：out 直接接所选部件输出：15 ns 采样后、首次读之前 out 已变为 ch0，75 ns 同高沿读出新帧。合成控制 `model-continuous_mux_output`。
- `architecture_bypass`（wrong，仓库内历史候选，逐字节相同）：健康部件下行为与参考解相同；换成诊断部件后仍输出未乘增益的输入。合成控制 `model-architecture_bypass`。
- `original_v4_349_gold`（wrong，原 gold 套壳，生成时从 historyref 读取）：自带采样器、不用固定部件（架构用例不乘增益）；输出驱动在 read 高时连续读保持节点，75 ns 同高沿读出新帧。只在 reset-during-sample-high 上通过：记忆污染低。合成控制 `model-original_v4_349_gold`。
- `rst_high_clk_as_normal_edge`（wrong，新写，first30-fix-r4）：clk 事件里 rst 为高的分支改成普通沿处理：`reset-high-across-clock-edge` 的 45.01 ns 沿把 valid 拉高并推进指针，46 ns、56 ns 的检查点被拒；其余用例的 rst 高电平段不含 clk 上升沿，都通过。合成控制 `model-rst_high_clk_as_normal_edge`。
- `late_clear_after_check`（wrong，新写，first30-fix-r4）：rst 上升事件照常清指针、排适配时钟、开输入钳位，但 out、sel、valid 的清零推迟到 0.94 ns 后的 timer，在 rst 穿越后 1.04 ns 才完成，晚于 0.9 ns 的期限，也晚于 0.95 ns 的检查点：凡复位前 out、sel 或 valid 非零的用例都在复位后的检查点被拒（误差约 0.08–0.33 V）；reset-during-sample-high 复位前这三路都为 0，通过。合成控制 `model-late_clear_after_check`。
- `alt_one_hot_token`（correct，仓库内历史候选，逐字节相同）：读指针写成独热令牌 1、2、4、8。合成控制 `model-alt_one_hot_token`。
- `inwindow_clear_before_check`（correct，新写，first30-fix-r4）：同样推迟清零，但只推迟 0.82 ns，在 0.92 ns 完成：晚于题面 0.9 ns 的期限、早于 0.95 ns 的检查点，属 F01 下 checker 接受的窗内余量，全部用例通过。合成控制 `model-inwindow_clear_before_check`。

## 后端条件（`conditions`）

无。所列候选的判决不依赖后端的特定语义；依赖与参考解相同的，不另列。

## F01 核对

按 F01 用户决定执行（2026-10-28 决定单第 6 项，选 A：题面写明 checker 实际的观察时刻，checker 不改）。first30-calib-r1 时检查点在 clk 或 rst 穿越后 0.95–0.99 ns，早于题面“事件完成后 1 ns 测量”，题面又允许清零在 rst 上升后 1 ns 内完成，合法的慢清零会被误判。first30-fix-r4 把题面改为：观察在“引起事件的 clk 或 rst 上升沿穿越 vth 后 0.95 ns 到 1 ns”（冻结的检查时刻是 rst 引起的事件后 0.95 ns、clk 引起的事件后 0.99 ns 的 binary64 值，个别比 0.99 ns 多约 1e-15 ns，所以写成“0.95 ns 到 1 ns”）；清零期限改为“清零沿穿越 vth 后 0.9 ns 内”，在观察点之前。期限 0.9 ns 与 0.95 ns 的检查点之间是不评分的窗口：迟到负例 `late_clear_after_check`（1.04 ns 完成）的期限与到达之间有 0.95 ns 的检查点，被拒；窗内对照 `inwindow_clear_before_check`（0.92 ns 完成）通过。参考解在 rst 穿越后约 0.16 ns 清完（out、sel、valid 用 tr = 100 ps 过渡；帧在 +50 ps 的适配时钟后 100 ps 内清零）。其余候选的被拒都来自远离这段窗口的检查点，误差在几十 mV 以上。

## 样板 r2.18–r2.24 各条核对

| 条目 | 结果 |
| --- | --- |
| 零边沿 transition()（r2.18，r2.23 细化） | 参考解 `transition(gate*vdd,0,10p)` 省略 fall，按 LRM 等于 rise（10 ps），其余 `transition(x,0,tr)` 同理；固定部件写明 rise、fall。候选 `continuous_mux_output` 是直接贡献。不依赖零边沿。已核对。 |
| 实数 ==、!=（r2.18，r2.23 细化） | 参考解与候选只有整数 `==`（指针、令牌、选择号）；原 gold 的 `!=` 也是整数。已核对。 |
| 直流工作点与 initial_step 读值（r2.18，r2.23 更正） | 参考解 `initial_step` 只给变量赋值，不读节点；保持节点与 `gnd` 由 Verilog-A 电压贡献驱动，t = 0 可能偏 1e-14 量级，3 mV 容差盖得住。已核对。 |
| PWL 折点平局（r2.19，平局规则 v2.1） | clk 事件里比较 V(rst)、V(read)、V(sample) 与 vth，这些信号在 clk 穿越前后至少 1 ns 处于平台；rst 穿越在线段中间（101.05、16.01 ns；新用例 101.05、41.05、47.05 ns）。没有折点平局。 |
| 台架余量：间隔在合同下界、保存行在穿越或评分起点上（r2.20，U17 先例） | 采样适配延迟在参考解里恰为 50 ps，正好等于合同上限（SOURCE 已列未决）；输入在采样沿前后稳定 ≥ 2.9 ns（两个新用例 2.99 ns）；检查点与清零期限见 F01 一栏（first30-fix-r4 已按 F01 用户决定改题面）；新用例的控制信号斜坡离 clk 沿至少 1.91 ns，rst 后的两个 timer 离 clk 沿至少 3.76 ns。其余间隔不在下界上。 |
| 定义域错误（r2.23） | 参考解只有取模 `%4`、`%2` 与整数除 `/2`，除数是常量；没有其他定义域风险。旧版运行没有定义域诊断。已核对。 |
| 内部量观察（r2.23） | 用例只 save 顶层节点。已核对。 |
| pulse 角点（r2.23） | clk pulse 的穿越在上升中点，检查点在 x6.0 ns，离角点（x5.0、x5.02、x9.02、x9.04 ns）至少 0.98 ns。已核对。 |
| 最后一行与 stop（r2.23） | checker 按固定时刻插值，最后检查点 173 ns 早于 stop 175 ns；`validate_rows` 带容差。已核对。 |
| 字面量与常量（r2.23） | 参考解只用 50p、200p、10p、0.9 等字面量，不依赖 17 位字面量。已核对。 |
| 不含电路未知量的 ddt（r2.24） | 没有 `ddt`。不适用。 |
| strobetimes 第一个值（r2.24） | 不用 strobe。不适用。 |
| 峰值在折点上碰门限（r2.24） | 控制信号峰值是 0.9 V 平台。没有这种情形。 |
| TIE-RULE 平局类别 | rst 后的两个 timer（+50 ps、+200 ps）与最近的 clk 事件相隔 ≥ 2.8 ns；没有同刻事件或改写进行中过渡的事件。无平局。 |
| 旧版零点处理掩盖与两类旧版限制（r2.16、r2.20） | 没有在恰为零或恰在门限上的信号上用 `cross()` 检出离开；参考解在 t = 0 不跨实例读内部节点（帧初值来自部件的 held = 0），不用 min/max 包 transition。旧版判决可作开发证据。 |

## 旧版 EVAS 开发检查

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。用 `runs/t3-harbor30-20261027/tools/legacy_case.py`（标签 first30-calib）逐例运行参考解与全部候选、全部私有与公开用例，判决与上表逐项比较；“全部行”和“只用网格行”分开计。

参考解与 10 个候选在 5 个用例上都能运行。除 `architecture_bypass` 外，全部行判决与矩阵逐项一致；`architecture_bypass` 的 5 个运行在全部行上都是 evidence_error（旧版 13 位时间打印造成 13 个重复时间行，`non-increasing waveform times`），只用网格行与去重诊断的判决都与矩阵一致（健康部件两例通过、诊断部件两例被拒、公开例通过）。只用网格行复判没有改变其余运行的判决。

统计：55 个运行。全部行：50 个出判决，其中与期望一致 50 个；只用网格行：55 个出判决，其中与期望一致 55 个；其余运行没有判决（旧版仿真失败或证据错误，原因见上）。

## 合成控制（未仿真）

D1 交回的执行身份：私有包 `spectre-D1-private-v2（结果包 sha256 7ec4fbda83b6db84…）`（118 个作业），公开包 `spectre-D1-public-v2（结果包 sha256 87f515d69aa668a9…）`（29 个作业）。Spectre 线 2026-10-29 正式核收（suite v1.8 加 r8 两项未结 P1 的一次性核对，证据 clean）。核收报告是 `Spectre 线核收报告（私有）`（sha256 `66844d7b…`）与同目录的 `结果包（私有）`（`0701a701…`）；登记文件是 `runs/spectre-returns-20261028/accepted/REGISTER.json`（主控转达时 sha256 `3764e9af…`，之后又追加了别的批次，D1 两条不变）。合成控制读的是 `runs/t3-spectre-batchD-20261028/returns-preread-…/` 下解开的同一结果包，两个 tar.gz 的 sha256 与登记相同。

D1 Spectre 21.1 交回（2026-10-29 已正式核收，执行身份见上）里参考解的波形，在内存中按判据改写，或换成候选按同一激励应输出的理想波形，再由本题未改动的 checker 判定（`runs/t3-harbor30-20261027/first30-calib-r1/scripts/synthetic_controls.py`）。

| 控制 | 改写 | `sample-read-reset` | `reset-during-sample-high` | `architecture-gain-0.75-sample-read-reset` | `architecture-gain-0.6-sample-read-reset` |
| --- | --- | --- | --- | --- | --- |
| `out-offset-+2.5mV` | offset 0.0025 | 过 | 过 | 过 | 过 |
| `out-offset-+3.5mV` | offset 0.0035 | 拒 | 拒 | 拒 | 拒 |
| `valid-offset-+3.5mV` | offset_valid 0.0035 | 拒 | 拒 | 拒 | 拒 |
| `hold-window-glitch-2.5mV` | glitch 0.0025 | 过 | 过 | 过 | 过 |
| `hold-window-glitch-5mV` | glitch 0.005 | 拒 | 过 | 拒 | 拒 |

保持窗毛刺加在 63 ns（60–70 ns 保持窗内，离 56、66 ns 检查点各 3 ns 以上）；`reset-during-sample-high` 没有保持窗，所以 5 mV 毛刺在该例通过。

候选模型（含参考解模型）在私有与公开用例上共 55 项，与上面的矩阵一致 55 项；D1 参考解原波形全部通过；去掉输出列的证据控制都报 evidence_error，不出判决。全部控制：私有 72/72、公开 13/13 与预期一致。

## 覆盖缺口

- “rst 为高时的 clk 上升沿清零”：first30-fix-r4 已加 `reset-high-across-clock-edge`（rst 高电平跨过 45.01 ns 的 clk 上升沿，该沿 read 与 sample 都为高）和只错在这一分支的候选 `rst_high_clk_as_normal_edge`。
- 参数覆盖：first30-fix-r4 已加 `param-vdd-vth-sample-read-reset`（vdd 1.0 V、vth 0.5 V）：sel、valid 电平写死为 0.9 V 的实现差 0.1 V，被拒。vth 写死为 0.45 V 的实现仍分不开：控制沿 20 ps（rst 100 ps）满摆，门限差 0.05 V 只让事件早 1–5 ps，检查点在 0.95 ns 之后；tr 也看不到（过渡在检查点前结束即可）。要评 vth 需要慢边沿或停在门限附近的电平，交主控。

## 记忆污染

原 v4:349 gold（四文件合一）自带采样器、不用固定部件，输出驱动在 read 高时连续读保持节点，只在 reset-during-sample-high 上通过、其余三个私有用例与公开用例都被拒：记忆污染低。

## 来源声明

- 新写（本轮，由参考解按注释改写或整段新写）：`valid_sticky`、`read_after_capture`、`continuous_mux_output`。
- 仓库内历史资产：`read_pause_advance`：`experiments/benchmark_v2/extension_integration/candidates/v2-integrate-349-multichannel-readout/read-pause-advance/dut.va`（sha256 3db97e9c…，逐字节相同）；`reset_output_stale`：`experiments/benchmark_v2/extension_integration/candidates/v2-integrate-349-multichannel-readout/reset-output-stale/dut.va`（sha256 bd5929a8…，逐字节相同）；`reset_clock_high_bank_stale`：`experiments/benchmark_v2/extension_integration/candidates/v2-integrate-349-multichannel-readout/reset-clock-high-bank-stale/dut.va`（sha256 c7931399…，逐字节相同）；`channel0_only`：`experiments/benchmark_v2/extension_integration/candidates/v2-integrate-349-multichannel-readout/channel0-only/dut.va`（sha256 db6228a7…，逐字节相同）；`architecture_bypass`：`experiments/benchmark_v2/extension_integration/candidates/v2-integrate-349-multichannel-readout/architecture-bypass/dut.va`（sha256 8f9d8e31…，逐字节相同）；`original_v4_349_gold`：`benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/349-multichannel-sample-readout/evaluator/solution/`（四个文件的 sha256 见 generator/history-comparison.json，生成时原样读取（题包不存文本））；`alt_one_hot_token`：`experiments/benchmark_v2/extension_integration/candidates/v2-integrate-349-multichannel-readout/alternative/dut.va`（sha256 14a4e221…，逐字节相同）。
- first30-fix-r4 新写（由参考解按注释改写）：`rst_high_clk_as_normal_edge`、`late_clear_after_check`、`inwindow_clear_before_check`。
- 外部许可代码：无外部许可代码。

## 生成器与 D2 估计

生成器两次输出逐字节相同（10 个文件）；每个由参考解改写的候选与参考解的差异摘要在 `runs/t3-harbor30-20261027/first30-calib-r1/generator/diffs/`。

D2 要加 50 个作业（10 个候选 × 5 个用例，含公开用例）。按 D1 同用例参考解作业估计：一般每个约 25.5 s，最长约 40.5 s（D1 最大值的 1.5 倍），串行合计约 21 分钟；PSF 合计约 51.5 MB，单个最大约 1.0 MB。

## first30-fix-r4 修正（2026-10-29）

未仿真。按 F01 用户决定执行。改了 `instruction.md`（观察时刻与清零期限两句）、`tests/cases.json`（加两例，现有四例逐字节不变）、本目录 `mutants.py`（加三个候选）、`expected.json` 与本文件；公开用例、checker、参考解与现有候选都没有改。

- `expected.json`：`cases` 加 `param-vdd-vth-sample-read-reset`、`reset-high-across-clock-edge`；10 个现有候选各按上表加这两例；在 `alt_one_hot_token` 之前加 `rst_high_clk_as_normal_edge`、`late_clear_after_check`（wrong），末尾加 `inwindow_clear_before_check`（correct），三者都写了公开用例的期望；`semantics` 改写（观察时刻、期限、新用例）。
- `mutants.py`：加常量 `RST_HIGH_BRANCH`、函数 `late_clear(gold, delay)` 与三个候选；生成器两次输出逐字节相同（13 个文件）。
- 合成控制（未仿真，`runs/t3-harbor30-20261027/first30-fix-r4/slot03/synthetic.json`）：精确激励的事件模型，参考解与 13 个候选在 6 个私有用例、1 个公开用例上，加去掉输出列的证据控制，私有 90/90、公开 15/15 与预期一致。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：标签 f30-fix4，参考解与 13 个候选在两个新用例上、三个新候选在 4 个旧私有用例与公开用例上，共 43 个运行：全部行 42 个出判决、42 个与矩阵一致；只用网格行 43 个出判决、43 个一致。`architecture_bypass` 在 `reset-high-across-clock-edge` 上全部行是 evidence_error（旧版 13 位时间打印造成重复时间行），只用网格行通过，与矩阵一致；其余运行只用网格行复判没有改变判决。
- Spectre 补跑：两个新用例 × （参考解、默认容差对照、13 个候选），30 个作业，PSF 约 25.1 MB，单个最大约 1.05 MB，串行约 13 分钟；另建议附加三个新候选在 4 个旧私有用例与公开用例上的作业，15 个作业，PSF 约 15.7 MB，单个最大约 1.05 MB，串行约 6 分钟；清单在 `runs/t3-harbor30-20261027/first30-fix-r4/spectre-jobs/`。
