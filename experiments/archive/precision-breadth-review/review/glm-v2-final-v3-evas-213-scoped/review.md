```json
{
  "scope": "固定 v3 EVAS 213 槽独立数据差异审（非 science 全 pass 批准）。审阅对象为用户提供的新 receipt（bb948…，声称覆盖完整 852 中的本次 213 EVAS 槽）、132 个 group cell（24 group × 3 tier 减去无 cell 项后按 schema 列出）、全部所引用表值、6 个 changed 槽（F14/F20/EC17/EC18/EC19/EC21 各 Q3）的完整前后 witness、原 RESULT+worker 诊断、请求设置/strobes/观测计划、TOOL/BUILD 身份，以及独立 program 字节审计附件文本。本轮不重复 aa7/d9 工具与 c254 数学机制的源码复审；不重算 hash/数值；仅审文本映射、关键见证与资格逻辑。其余 603 槽按声明复用旧 data review，不在本轮范围内重看。",
  "standards": [
    "用户固定审阅指令：五项 Q3 变更（F14/F20/EC17/EC18/EC19 执行失败→waveform 但最终须为 insufficient/unknown，不得当 pass）与 EC21 Q3（旧 waveform→新实际 timeout，最终 X，保留回退）",
    "计数约束：213 = 105 pass + 81 insufficient + 27 execution_failed；numeric 108 pass + 96 unknown + 9 insufficient + 0 N；0 N 不得表述为 213 precision pass",
    "完整请求固定：不得删 wrap 邻点、缩 callback bracket、改预算；reference uncertainty 不得当作实际点误差",
    "probe 不能 pass；原 deferred 未知 RESULT 不得当科学 pass；所有科学轴保留；source/build 身份限制与 local-only 不声称 public raw",
    "schema/字面量重建规则：按 object_columns 重建 $o 对象，$r 为 value_pool 准确字面量，数组保持数组；不得凭抽样宣称逐 hash 重算",
    "审实际数据而非采信作者/Astra 结论；附件独立审计文本为外部证据而非采信结论"
  ],
  "spec": "v3 EVAS 213 槽 receipt 差异审：核验 six_major_changes 前后轴迁移、聚合计数自洽性（final/numeric/original_execution/behavior/evidence 各轴前后分布与 6 个变更槽迁移的推导一致性）、EC21 timeout 见证（returncode -15、elapsed 90.01653360016644s 对 90s 限）、五槽新执行 waveform_available 但资格轴不提升的守门逻辑、请求/设置/输入身份前后一致（identical_scientific_inputs）、TOOL/BUILD 身份与 local-only 限制声明。",
  "findings": [
    {
      "id": "F1",
      "severity": "medium",
      "file": "comparison_metadata（counts before/after）与 six_major_changes/F14-base--Q3 原 RESULT",
      "location": "comparison_metadata.counts：numeric 轴 before [109,98,6] → after [108,96,9]；F14-base--Q3 原 execution_failed 见证 waveform_accuracy: cannot certify same-time forward error at y: bound 5.551137327586275e-11, budget 5.001000000005759e-11",
      "trigger": "对 6 个变更槽的 numeric 轴迁移做算术闭合：新 numeric 为 EC17=pass、EC18=evidence_insufficient、EC19=evidence_insufficient、F14=unknown、F20=evidence_insufficient、EC21=unknown；要使净变化为 pass −1 / unknown −2 / insufficient +3（其余 207 槽 numeric 不变），唯一闭合解要求旧 receipt 中 F14-Q3 的 numeric = pass（P→U），即 F14 旧 numeric 为 pass 而其旧失败恰是数值认证失败（bound 超 budget）。",
      "impact": "若该推导成立，旧 receipt 对 F14-Q3 在数值认证明确失败的执行上仍记 numeric=pass，numeric 轴语义与 waveform_accuracy 失败记录矛盾；即使闭合解不唯一（旧 EC17/18/19/F20 numeric 归属另有取值），[109,98,6]→[108,96,9] 也无法由 6 个已供审槽的自然迁移（失败执行 numeric=unknown/insufficient）推出，存在 1 pass + 1 unknown 的残余差额。",
      "violation": "违反计数自洽/轴语义一致性要求：变更槽迁移必须可推导聚合计数差异；numeric 认证失败不得在旧 receipt 中记为 numeric pass。需作者澄清旧 receipt 中 F14-Q3（及 EC17/18/19/F20-Q3）的 numeric 轴原值。"
    },
    {
      "id": "F2",
      "severity": "low",
      "file": "six_major_changes/EC21-v1--Q3 前后执行见证",
      "location": "旧执行 elapsed_seconds=89.84979362413287（status completed）；新执行 elapsed_seconds=90.01653360016644、returncode=-15、status=timeout、cleanup 判 timeout=true",
      "trigger": "旧运行距 90s 硬限仅 0.15s 余量即完成；新运行以 0.0165s 超限被 SIGTERM。新旧科学输入身份相同（同 source_sha256/settings/times/plan SHA），最终轴回退为 execution_failed。",
      "impact": "EC21-Q3 的 X 结论依赖单次运行贴边时序；虽然 receipt 已明确不据此宣称算法性能退化、并保留回退，且资格轴（final=execution_failed, behavior/config/native/runtime=unknown）与 'analysis deferred to independent local reanalysis' 未当 pass，但该槽结论对调度噪声敏感，任何复跑可能在 X 与 waveform_available 间翻转。",
      "violation": "不构成规则违反（receipt 措辞与回退处理符合约束）；作为敏感性记录提出，建议标注 'near-timeout-boundary' 限定而非缺陷修复。"
    }
  ],
  "missing_context": [
    "EC21 巨型 strobelist 与 observation_plan 仅提供 SHA/bytes 指向（requested_times 513142 bytes / observation_plan 557354 bytes），32k 时刻未逐项供模型重审；builder 声称旧新完全相同未经本轮独立验证。",
    "其余 603 槽的旧 data review 结论与旧 receipt（7e8）明细未提供，本轮无法验证 '其他 603 复用旧 data review' 的边界划分本身。",
    "独立 program 字节审计（script c767d413…）为外部附件文本，其执行与结论本轮不可复核，仅作为声明性证据记录。",
    "F1 所需的旧 receipt 中 6 个变更槽 numeric 轴原值未直接列出，只能由聚合计数反推；需作者提供旧 receipt 逐槽 numeric 值以闭合。",
    "kernel build revision 未随 build receipt 报告（仅有 source/toolchain 身份与 kernel_sha256），receipt 自身已声明该限制；历史二进制 provenance 无法由本轮文本核实。"
  ],
  "limitations": [
    "本轮为只读静态文本审：未执行任何 hash 重算、数值重跑或波形字节重审；所有 SHA 一致性依赖 builder/独立审计声明。",
    "结论范围限于 213 EVAS 槽文本映射与资格逻辑；不构成对完整 852 槽或任何 science 全 pass 的批准。",
    "计数核验基于 schema 重建对象的轴分布算术闭合，非逐槽重放；除 F1 指出的 numeric 残差外，final [105,77,31]→[105,81,27]、original_execution [182,22,9]→[186,10,17]（X 合计 31→27）、behavior [170,43]→[174,39]、evidence [105,108] 不变，均可由 6 槽迁移（5× X→waveform/最终 I、EC21 I→X）精确推出，自洽。",
    "五槽守门逻辑核验通过：F14/F20/EC17/EC18/EC19 Q3 新执行 waveform_available 且 numeric 分化（EC17 pass；EC18/19/F20 因 phase wrap/未定义单侧点等理由 insufficient/unknown，理由文本在 value pool 中在案），但 final 均保持 evidence_insufficient、evidence 不变，probe/deferred 未被提升为科学 pass；EC21 timeout 回退为 X 且未宣称性能退化。",
    "local-only、requires-backend-environment、'source revision 不证明历史二进制 provenance 或 public raw' 等限制声明在 metadata 中保留在案。"
  ]
}
```
