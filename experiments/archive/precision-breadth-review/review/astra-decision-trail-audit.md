# 决策日志独立证据审计

审计对象为 `decisions.tsv`，本次读取范围从 2026-10-11T17:19:59Z 至 2026-10-11T19:06:26Z，共 18 行决策。读取时 SHA256 为 `0f45d2b155fc489064193e097a7d9af68039a394f3e7f3ee6cf8b349685ecae4`。按 vaevas-review-pr 和 show-me-your-work 的审查要求核对可访问文件、固定提交及已执行的独立探针。本次没有写 tracked 文件、没有修改 canonical log、没有远端调用，也没有获得协调者完整会话记录，因此不称为完整 transcript 审计。

## 需追加更正的证据指针

1. 18:41:52Z 的 GLM 事故行引用 `review/mixed-stream-result-audit.json`，该路径不存在。实际文件为 `review/glm-v2-foundation/mixed-stream-result-audit.json`。这是确定的断链，应由日志唯一写者追加 superseding 行修正，原行保留。影响是读者无法从日志直接核验两个 session 的混合流恢复过程；不表示恢复文件丢失。
2. 18:04:50Z 的 `astra-composition-followup.md` 实际位于 `review/astra-composition-followup.md`；18:15:04Z 的 `events.rs447-470` 没有完整路径或修订身份，`worktrees/precision-event-array` 相对 current/ 也不是实际位置。建议补为固定提交 `4448253a:evas/rust_core/src/events.rs` 的相关保护条件，以及 `../worktrees/precision-event-array`。17:55:07Z 的 `Astra EC01锚点反馈` 是描述，不是可跟随证据路径，宜同时补指向已保存的审查报告。上述为可追溯性缺口，不是新的数学/生产 P1/P2。
3. 17:34:52Z 的历史 6 项校准及 18:04:50Z 的历史 77 项校准，仅由提交/报告间接指向。本次未取得这些历史执行的原始输出，不能独立认证当时恰好运行了该数量。可补原始输出路径；若没有保存，则明确历史执行来自协调者当时记录。不能用当前 113 项测试通过倒推历史调用。

## 已核实的保留与身份

- 原冻结 preflight 为 68 变体、44 组，即 816 个四后端三档计划槽；修订旧批次及 batch-v2 均为 71 变体、44 组、852 槽。三份 preflight 的资源限制相同：单阶段 90 秒、license 30 秒、内存 4 GiB、单文件 32 MiB、单条件 256 MiB、单线程。这些是计划/限制身份，不是成功运行数。
- batch-v2/SOURCE_MANIFEST.json 中全部 149 个源码文件的 SHA256 都与固定提交 `5f73f5016bb44808549ddfbf9b685bc192f2b2d7` 的 git 对象匹配。最新 freeze 行中的源码数量和 commit 有证据支持。
- 首次 deployment 与 build-dispatch 的 stderr 分别表明父目录不存在、remote_control.py 不存在；返回码为 1 和 2。随后部署 receipt 返回 0。失败 receipt 和 stderr 仍保留，失败阶段没有进入仿真命令。
- old foundation-evas-part1 收集目录确有 93 个 RESULT.json。F07 Q1/Q2/Q3 均保存原 unsupported_cross 拒绝，未用修复结果覆写。
- SPEC 固定的 20 基础组加 24 工程组、Q 目标和未知项保留原则，与日志相符。PLAN 是旧提案，日志已标为 superseded；独立读取 PLAN 中“未启动”的文字不应解释为当前状态。后续交付应优先链接 SPEC 与最新冻结身份。

## GLM 调用与失败证据

独立核对 `review/glm-v2-index.md` 内 45 个带 SHA256 的文件引用，全部存在且匹配。两份 first-preserved manifest 各 10 个文件也全部匹配。会计文件中的 12 次 actual calls 包括 9 次带成功终止 JSON 的完成调用、3 次 timeout；完成调用合计报告 10 turns，已知报告费用 USD 7.119545。逐份核验完成 JSON 的 session、num_turns、费用与成功状态。三个 timeout 没有终止用量凭证，费用和 turns 继续记 unknown，不能当零。

`glm-spec-math`、`glm-foundation`、`glm-composition` 的超时 receipt 与收到的流仍存在；未形成完整 review.md，不能记为审查通过。日志“保留失败全响应”只能指保留收到的原始内容，不能读成取得完整终止响应。

重复启动事故的限制也保留了：core/foundation 的 first-preserved 终止 JSON 可用，但完整单次原流不可恢复；started.json 属于第二次启动。foundation 普通 receipt 选择过第一 session 的迟到终止结果，真正第二 session 为 `recovered-result-0.json`。应依赖 nested mixed-stream 审计和该恢复 JSON，不能把普通 receipt 当成第二次干净调用。原 glm-core 实际完成，索引已修正早期“超时”口头判断。

最终 delta GLM 固定审查 `4288e9225e8d201a70a589156ed2811c6f975d48` 的三个数学模块；runner 不在它的覆盖范围。生产双审、数学增量审查和 runner 本地/直接读审应分别声明。

## 必须保留的结论边界

此前独立审查在 `review/astra-final-breadth-delta.md` 保存 transition clamp 的真实反例、修复后的 40,176 个 Fraction 包围检查，以及 F07 假重复的来源和修正。它们支持 checker 修复与新身份冻结，不证明新远端科学结果。

旧实际 Spectre F07 的数值观测与解析状态序列一致，但完整 callback bracket 跨合法窗口边缘，仍为 behavior unknown / I。旧 Q1/Q2 请求覆盖有伪重复，旧 Q3 有超过固定 16 ulp(stop) 的请求差距；原 RESULT 的资格不得直接沿用到新分析。新 batch-v2 的 deferred-analysis 原始结果也不提供数值或资格通过结论。

本次没有发现日志把上述关键 unknown、旧失败或三次 GLM timeout 排除出历史的证据。确定的问题是证据断链；历史 6/77 校准调用和授权/分派细节因完整 transcript 不可用仍属审计覆盖缺口。该结论不构成 merge 授权，也不替代随后对新 F07 实际运行和最终表格的审查。
