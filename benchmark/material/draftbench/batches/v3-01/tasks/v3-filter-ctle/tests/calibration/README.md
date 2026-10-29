# 校准候选（first30-calib-r1）

2026-10-29 新建。未仿真：下面的矩阵是按 checker 推导、经合成控制核对的期望，待 D2 Spectre 校准。同日 first30-fix-r4 加了端点用例 `ctle-endpoints`，各节已同步，改动见末节“first30-fix-r4 修正”。

`mutants.py` 由 `solution/circuit.va` 生成 VA 候选：`wrong/` 应被拒，`correct/` 应被接受，都用 `../cases.json` 的私有用例和 `../../environment/starter/testbench/cases.json` 的公开用例、同一 checker 判定。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新建或空目录>`，输出目录必须是新的或空的；两次生成逐字节相同。

`expected.json` 是同一被拒矩阵的机器可读形式：私有用例写在 `cases` 和各候选的 `must_reject`/`must_accept`；公开用例写在 `public_cases`（`same_as_private` 指出与之完全相同的私有用例，没有则为 null）和各候选的 `public_must_reject`/`public_must_accept`。`author_synthetic_control` 是对应的候选模型合成控制名。

checker（`tests/v2_next_filter.py:55-66`）有两类失败：任一保存行上 y 与 checker 按保存的 u 用 RK4 积分得到的状态解相差超过 6 mV；或 t ≥ stop/2 的稳态里 500 Hz、2 kHz、8 kHz、16 kHz 任一频点的复响应误差超过 0.03·max(1,|H|)。

## 用例

| 用例 | 集合 | 内容 |
| --- | --- | --- |
| `ctle-0` | 私有 | 缺省参数（fz 1 kHz、fp1 4 kHz、fp2 12 kHz、gain 1），零初态；u = 30 mV 直流 + 500 Hz、2/8/16 kHz 各 35 mV；12 ms |
| `ctle-1` | 私有 | 全部参数覆盖（1.5/6/18 kHz、gain 1.3）与初态 x1init 0.07、x2init -0.03；u 直流 50 mV |
| `ctle-endpoints` | 私有 | first30-fix-r4 新加：参数取合法域端点 fz 2000 Hz、fp1 2000 Hz、fp2 24000 Hz、gain 0.5、x1init 0.1、x2init -0.1；u = 40 mV 直流 + 500 Hz、2/8/16 kHz 各 35 mV；12 ms |
| `ctle-0` | 公开 | 与私有 `ctle-0` 完全相同 |

## 被拒矩阵

“拒”为应被拒，“过”为应通过。

| 候选 | 组 | 失败类别 | `ctle-0` | `ctle-1` | `ctle-endpoints` | 公开 `ctle-0` |
| --- | --- | --- | --- | --- | --- | --- |
| `hz_as_radians` | wrong | 单位错（Hz 当 rad/s，漏 2π） | 拒 | 拒 | 拒 | 拒 |
| `zero_initval` | wrong | 初态不读覆盖值（x1init、x2init 写死为 0） | 过 | 拒 | 拒 | 过 |
| `corner_frequencies_hardcoded` | wrong | 参数写死不读覆盖值（fz、fp1、fp2 固定为缺省） | 过 | 拒 | 拒 | 过 |
| `zero_normalized_to_first_pole` | wrong | 零点归一化错（fp1/fz 代替 fp2/fz） | 拒 | 拒 | 拒 | 拒 |
| `alt_difference_state` | correct | 正确替代（差分状态 d = x1 - x2） | 过 | 过 | 过 | 过 |

## 候选说明

- `hz_as_radians`（wrong，仓库内历史候选，逐字节相同）：极点落在 fp/(2π)：时域与频响都错。合成控制 `model-hz_as_radians`。
- `zero_initval`（wrong，仓库内历史候选，逐字节相同）：ctle-1 的初态 0.07/-0.03 被忽略，开头的恢复段错。合成控制 `model-zero_initval`。
- `corner_frequencies_hardcoded`（wrong，新写）：ctle-1 覆盖 1.5/6/18 kHz 后仍按 1/4/12 kHz 响应。合成控制 `model-corner_frequencies_hardcoded`。
- `zero_normalized_to_first_pole`（wrong，新写）：零点落到 fz*fp2/fp1，高频峰化不足。合成控制 `model-zero_normalized_to_first_pole`。
- `alt_difference_state`（correct，仓库内历史候选，逐字节相同）：第二个状态改用 x1-x2。合成控制 `model-alt_difference_state`。

## 后端条件（`conditions`）

无。所列候选的判决不依赖后端的特定语义；依赖与参考解相同的，不另列。

## F01 核对

连续输出，逐点比较加稳态频响，没有事件后的评分起点。不适用。

## 样板 r2.18–r2.24 各条核对

| 条目 | 结果 |
| --- | --- |
| 零边沿 transition()（r2.18，r2.23 细化） | 没有 `transition()`。不适用。 |
| 实数 ==、!=（r2.18，r2.23 细化） | 没有实数 `==`、`!=`。已核对。 |
| 直流工作点与 initial_step 读值（r2.18，r2.23 更正） | 参考解没有 `initial_step`；a、b 由 `idt(…, x1init/x2init)` 的电压贡献驱动，t = 0 可能偏 1e-14 量级，6 mV 容差盖得住。已核对。 |
| PWL 折点平局（r2.19，平局规则 v2.1） | 激励是 sine 源，没有 `cross()`。不适用。 |
| 台架余量：间隔在合同下界、保存行在穿越或评分起点上（r2.20，U17 先例） | 不适用（连续激励）。 |
| 定义域错误（r2.23） | 参考解的除法 `fp2/fz` 中 fz 在合法域 500–2000 Hz 内，不为零；候选 `fp1/fz` 同理；没有其他定义域风险。旧版不能运行（见下），没有定义域证据。 |
| 内部量观察（r2.23） | 用例只 save u、y；a、b 不保存。已核对。 |
| pulse 角点（r2.23） | 没有 pulse。不适用。 |
| 最后一行与 stop（r2.23） | checker 用全部行积分、用 stop/2 之后的行求相量，不要求最后一行恰为 stop；`validate_rows` 带容差。已核对。 |
| 字面量与常量（r2.23） | 用 `M_PI` 与 4000.0、12000.0 等字面量，不依赖逐位值。已核对。 |
| 不含电路未知量的 ddt（r2.24） | 没有 `ddt`。不适用。 |
| strobetimes 第一个值（r2.24） | 不用 strobe。不适用。 |
| 峰值在折点上碰门限（r2.24） | 没有门限比较。不适用。 |
| TIE-RULE 平局类别 | 连续模型，没有事件。无平局。 |
| 旧版零点处理掩盖与两类旧版限制（r2.16、r2.20） | 旧版 EVAS 不认 sine 源（`missing_waveform_metadata`），参考解与全部候选都跑不了；不涉及零点掩盖。 |

## 旧版 EVAS 开发检查

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。用 `runs/t3-harbor30-20261027/tools/legacy_case.py`（标签 first30-calib）逐例运行参考解与全部候选、全部私有与公开用例，判决与上表逐项比较；“全部行”和“只用网格行”分开计。

参考解与 5 个候选在旧版都报 `ERROR [rust_lowering]: source:u:missing_waveform_metadata`（sine 源），没有判决；预期依据合成控制（候选输出由 checker 自己的 RK4 积分器按候选系数推出），待 Spectre 核实。

统计：18 个运行。全部行：0 个出判决，其中与期望一致 0 个；只用网格行：0 个出判决，其中与期望一致 0 个；其余运行没有判决（旧版仿真失败或证据错误，原因见上）。

## 合成控制（未仿真）

D1 交回的执行身份：私有包 `spectre-D1-private-v2（结果包 sha256 7ec4fbda83b6db84…）`（118 个作业），公开包 `spectre-D1-public-v2（结果包 sha256 87f515d69aa668a9…）`（29 个作业）。Spectre 线 2026-10-29 正式核收（suite v1.8 加 r8 两项未结 P1 的一次性核对，证据 clean）。核收报告是 `Spectre 线核收报告（私有）`（sha256 `66844d7b…`）与同目录的 `结果包（私有）`（`0701a701…`）；登记文件是 `runs/spectre-returns-20261028/accepted/REGISTER.json`（主控转达时 sha256 `3764e9af…`，之后又追加了别的批次，D1 两条不变）。合成控制读的是 `runs/t3-spectre-batchD-20261028/returns-preread-…/` 下解开的同一结果包，两个 tar.gz 的 sha256 与登记相同。

D1 Spectre 21.1 交回（2026-10-29 已正式核收，执行身份见上）里参考解的波形，在内存中按判据改写，或换成候选按同一激励应输出的理想波形，再由本题未改动的 checker 判定（`runs/t3-harbor30-20261027/first30-calib-r1/scripts/synthetic_controls.py`）。

| 控制 | 改写 | `ctle-0` | `ctle-1` |
| --- | --- | --- | --- |
| `y-offset-+5mV` | offset 0.005 | 过 | 过 |
| `y-offset-+7mV` | offset 0.007 | 拒 | 拒 |
| `tone-500Hz-0.5mV` | tone 0.0005 | 过 | 过 |
| `tone-500Hz-2mV` | tone 0.002 | 拒 | 拒 |

500 Hz 误差音调 2 mV 只让该频点的复响应误差超限（约 0.057），时域误差仍小于 6 mV；0.5 mV 时两个判据都不超。

候选模型（含参考解模型）在私有与公开用例上共 18 项，与上面的矩阵一致 18 项；D1 参考解原波形全部通过；去掉输出列的证据控制都报 evidence_error，不出判决。全部控制：私有 24/24、公开 8/8 与预期一致。

## 覆盖缺口

- 合法域端点：first30-fix-r4 已按建议加 `ctle-endpoints`（fz 2000、fp1 2000、fp2 24000、gain 0.5、x1init 0.1、x2init -0.1）。fz = fp1 时 H(s) 里零点与第一极点相消，但初态合同里 x1 仍按 fp1 从 x1init 恢复，所以时域响应不是单极点滤波；`zero_normalized_to_first_pole` 在这里给出 y = gain·x1，被拒。其余端点（fz 500、fp1 8000、fp2 8000、gain 2）仍没有用例。题面写范围用“500–2000”与“lies in ±0.1”，没有写明是否含端点；按惯常读法含端点，参考解不声明 `from` 范围，端点在参考解上合法；要不要在题面写明“含端点”，交主控。

## 记忆污染

本题是 benchmark_next 新建题（规格 #149，同源组 verilogalib-ctle），不是 v4 迁移题；historyref 里的 v4 CTLE 题（329 自适应环、352 时钟化均衡器宏）端口与合同都不同，不作套壳候选。

## 来源声明

- 新写（本轮，由参考解按注释改写或整段新写）：`corner_frequencies_hardcoded`、`zero_normalized_to_first_pole`。
- 仓库内历史资产：`hz_as_radians`：`experiments/benchmark_next/filter/candidates/v3-filter-ctle/hz-as-radians/dut.va`（sha256 9014d78f…，逐字节相同）；`zero_initval`：`experiments/benchmark_next/filter/candidates/v3-filter-ctle/zero-initval/dut.va`（sha256 461c511e…，逐字节相同）；`alt_difference_state`：`experiments/benchmark_next/filter/candidates/v3-filter-ctle/alternative/dut.va`（sha256 3aba928f…，逐字节相同）。
- 外部许可代码：题目主题（一零二极点 CTLE）取自 Brian Li 的 verilogaLib ctle.va（https://github.com/ShabbyGayBar/verilogaLib，提交 a6cdb370，Copyright (c) 2025 Brian Li，MIT 许可证）；参考解是本仓库按公开合同改写的状态方程，候选由参考解改写，都没有复制 verilogaLib 的代码。按许可在 `mutants.py` 的文档字符串保留署名。

## 生成器与 D2 估计

生成器两次输出逐字节相同（5 个文件）；每个由参考解改写的候选与参考解的差异摘要在 `runs/t3-harbor30-20261027/first30-calib-r1/generator/diffs/`。

D2 要加 15 个作业（5 个候选 × 3 个用例，含公开用例）。按 D1 同用例参考解作业估计：一般每个约 11.5 s，最长约 21.6 s（D1 最大值的 1.5 倍），串行合计约 3 分钟；PSF 合计约 35.2 MB，单个最大约 2.5 MB。

## first30-fix-r4 修正（2026-10-29）

未仿真。改了 `tests/cases.json`（加 `ctle-endpoints`，现有两例逐字节不变）、本目录 `expected.json` 与本文件；公开用例、checker、参考解、`mutants.py` 与候选都没有改。

- `expected.json`：`cases` 加新用例，4 个 wrong 候选的 `must_reject` 与 `alt_difference_state` 的 `must_accept` 各加这一例；`semantics` 末尾补新用例一段。现有用例与公开用例的期望不变。
- 新用例的写法：实例行 `fz=2000 fp1=2000 fp2=24000 gain=0.5 x1init=0.1 x2init=-0.1`，与题面范围端点的写法相同（参考解不声明 `from` 范围）；激励与 tran 同现有用例（四个 sine 源写明 sinedc、ampl、freq，`errpreset=conservative`）。
- 新用例上各候选的依据：`hz_as_radians` 极点落在 fp/(2π)；`zero_initval` 忽略 0.1/-0.1 的初态；`corner_frequencies_hardcoded` 仍按 1/4/12 kHz；`zero_normalized_to_first_pole` 给出 y = gain·x1；`alt_difference_state` 通过。
- 合成控制（未仿真，`runs/t3-harbor30-20261027/first30-fix-r4/slot24/synthetic.json`）：按 LTI 解析解算出的参考解与 5 个候选输出，加去掉输出列的证据控制，由本题 checker 判定：私有 24/24、公开 8/8 与预期一致。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：标签 f30-fix4，新用例上参考解与 5 个候选 6 个运行都报 `ERROR [rust_lowering]: source:u:missing_waveform_metadata`（sine 源），没有判决；新用例的期望只依据合成控制，待 Spectre 核实。
- Spectre 补跑：新用例 × （参考解、默认容差对照、5 个候选），7 个作业，PSF 约 15.9 MB，单个最大约 2.49 MB，串行约 1 分钟；清单在 `runs/t3-harbor30-20261027/first30-fix-r4/spectre-jobs/`。
