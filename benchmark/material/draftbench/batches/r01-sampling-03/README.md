# R01 采样第三批（P1）

本批从 PR255 规划池的 P1 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-29 起按功能族建 P1，R01（采样保持与多通道读出）族最先。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r01-spec-dual-track-hold](tasks/r01-spec-dual-track-hold/SOURCE.md) | C061-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制（7 个正确模型、1 个条件模型、39 个 Python 错误模型，其中 38 个与 VA 错误候选对应）、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 9/9 用例通过（8 个私有加公开用例）；45 个候选 × 8 个用例中，有预期的 254 个条目 249 个一致、1 个不一致（`alt_two_modules` 在 `start-high`，旧版限制）、4 个无判决，未列预期的 106 个中 102 个有判决；EVAS 02dee32b 在 9 次参考解运行中 8 次停在已知的 NF-01（建题时）。原 v4:236 的 gold 原样能通过全部用例，记忆污染风险高（决定单第 21 项：接受，分开报分）。四项选择已定（用户 2026-10-29，决定单第 20、21 项）。独立审核 R01 r1 的发现已在 r01-fix-r1 处理；r01-fix-r2 按总协调的决定在合法域补“相邻两次穿越之间离 vth 至少 50 mV”并加 checker 台架检查（合成控制与旧版重判的判决不变），待复审 |
| [r01-spec-droop-leakage-hold](tasks/r01-spec-droop-leakage-hold/SOURCE.md) | C057-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制（修正 r1 后 30 个模型 × 7 个用例 210 次判决，事先写下的 172 个预期全部相符）、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 7/7 用例通过；候选有预期的 196 个条目中 182 个一致、0 个不一致、14 个无判决：两个候选旧版不能运行，其中 `tr_floor_100p` 的替代探针 `tr_floor_100p_param` 在 7 个用例都与其预期一致，`track_while_high` 待 Spectre 验证；EVAS 02dee32b 3 例跑完并通过 checker，3 例停在已知的 NF-01（建题时）。原 v4:042 gold 只在复位上不同，记忆污染中到高。四项选择已定（用户 2026-10-29，决定单第 25–28 项，都按推荐）：泄漏相位、复位方式、捕获与泄漏同刻、参数合法域。独立审核 R01 r1 的发现已在 r01-fix-r1 处理，r01-fix-r2 同步了决定单状态与第 20 条遗留（已核对），待复审 |
| [r01-spec-droop-front-end](tasks/r01-spec-droop-front-end/SOURCE.md) | C067-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制（修正 r1 后 44 个模型 × 8 个用例 352 次判决，事先写下的 231 个预期全部相符）、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 9/9 用例通过（8 个私有加公开用例），43 个候选的 344 个有预期条目全部一致；EVAS 02dee32b 报两个新的首个诊断（建题时，已转 EVAS）。原 v4:100 gold 只差模块名和 `valid` 结束时刻，记忆污染中到高。五项选择已定（用户 2026-10-29，决定单第 29–33 项，都按推荐）。独立审核 R01 r1 的发现已在 r01-fix-r1 处理，r01-fix-r2 同步了决定单状态与第 20 条遗留（已核对），待复审 |

没有可用的 Spectre，本批检查不执行电路仿真。旧版 EVAS 0.8.7 的结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；EVAS 02dee32b 的阶段结果也只作开发证据。
