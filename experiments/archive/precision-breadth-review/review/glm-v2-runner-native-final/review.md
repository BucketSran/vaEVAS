```json
{
  "scope": "对 commit 5f73f5016bb44808549ddfbf9b685bc192f2b2d7 下 precision_breadth_run.py 的运行证据与编排进行只读静态审查：native_observation_evidence / spectre_accepted_rows、runtime_control_evidence、原始证据与工具/来源身份、执行前 Q/profile 绑定、缺失或歧义 native 行、请求设置与有效设置、异常回执、defer-analysis 语义。simulator、core/foundation/composition 数学公式不在本次范围内（另有审查）；supplied 的 precision_breadth.assess 仅作为消费方上下文。",
  "standards": [
    "runs/evas-overnight-20261012/SPEC.md（验收：证据未知保持未知；失败/未运行槽位保留；分母不变；设置/来源/数值/观测分开记录；deep_bound=step_units 0.0004 仅用于 Spectre Q3）",
    "runs/evas-overnight-20261012/INTERFACE.md（breadth-v1 卡/参考 API、事件窗口契约、回调区间全局一致、unknown 不得变 pass）",
    "precision_breadth_run.py 自身 docstring 声明：Q 绑定不是资格；科学分级与实际设置/来源是独立记录；defer 导出是原始证据而非科学通过",
    "evas/tests/test_precision_breadth_runner.py 作为行为契约证据",
    "旧归档 Spectre 摘录仅作为解析器/版本证据，不作为新执行或通过证据"
  ],
  "spec": "重点核查：伪合格（false qualified）、证据缺口静默变 pass、弱身份/读回、跳过行或请求、分母变化、defer 原始导出被误当科学成功。明确排除：故意 unknown 的 open 后端运行时/来源资格不算缺陷；不得要求不支持的控制在支持之列；新的最终 breadth 原始结果尚不存在，不在评估内。",
  "findings": [
    {
      "id": "F1",
      "severity": "medium",
      "file": "experiments/backends/support/precision_breadth_run.py",
      "lines": "261-277（尤其 272-274）",
      "trigger": "native_observation_evidence 的 Spectre 分支完全忽略传入的 qualified（设置/来源资格）参数：只要 spectre_accepted_rows 返回 qualified，即返回 {'status':'qualified', ...}，与 precision_report.qualification 是否 evidence_insufficient 无关。",
      "impact": "单独阅读 RESULT.json 中 native_observation_evidence.status='qualified' 的回执时，可能被误读为该次 Spectre 运行整体合格，而实际上设置/来源资格可能已失败。runner 内部第 186 行的三重合取（q/provenance/runtime_control 均 qualified）阻止了最终 qualified_tiers 误判，因此这不是可触发的伪通过，但单项回执的语义与函数名中的 'qualification' 参数承诺不一致，存在下游消费者误用风险。",
      "requirement": "SPEC.md 'Numerical accuracy, behavior, evidence completeness and actual effective settings are separate results'——各分离结果应各自如实反映自身状态；docstring 'qualify only an independently checked origin path' 虽有说明，但参数 qualified 未被消费属于接口语义弱化。建议在返回体中显式记录 settings_provenance_status 以消除歧义。"
    },
    {
      "id": "F2",
      "severity": "low",
      "file": "experiments/backends/support/precision_breadth_run.py",
      "lines": "301-307, 351-364",
      "trigger": "spectre_accepted_rows 校验 tb.scs 存在及 annotate/strobe/skipcount/compression 配方 token 存在，并核对 requested_times.json 与 PSF 行的一一对应，但从不将 tb.scs 中的 strobetimes=[...] 列表与 requested_times.json 内容比对（旧归档 tb.scs 摘录第 6 行显示 strobetimes 内嵌于 deck）。",
      "impact": "若冻结输入中 deck 的 strobe 列表与 requested_times.json 不一致（例如上游 decks() 生成逻辑变更或冻结时的拼接错误），strobe 匹配仍会针对 requested_times.json 判定 qualified，而实际仿真器收到的请求是另一组时间点。当前由 MANIFEST/INPUT_IDENTITY 哈希冻结缓解（deck 与 requested_times 同源冻结、运行前 verify），故触发链很弱；但请求-证据链条上存在一处未闭合的交叉核对。",
      "requirement": "SPEC.md 'Keep start, stop, input corners, event windows, edge endpoints...' 的请求完整性；'requested strobe has no unique raw row' 检查针对的是 requested_times.json，而非 deck 实际请求。"
    },
    {
      "id": "F3",
      "severity": "low",
      "file": "experiments/backends/support/precision_breadth_run.py",
      "lines": "196, 207-212, 137-141",
      "trigger": "defer_analysis=False 且 execute_one 返回非 waveform_available 且非异常的状态（如 compile_failed / runtime_timeout，见 precision_run.execute_one 与 runner.result_state 的状态集）时，result 不含 qualification / qualified_tiers / assessment 字段，仅 status 表达失败。",
      "impact": "统一消费 EXECUTION.json 的下游若以 qualified_tiers 缺失或空字典做默认聚合，可能把执行失败槽位从分母中遗漏或误计。runner 自身在 finally 中以 not_run 补齐未达槽位、分母来自冻结 cards，未改变；这是回执 schema 不一致的健壮性问题而非现成缺陷。test_deferred_failed_invocation_retains_failure_and_unrun_slots 仅覆盖 defer_analysis=True 路径（该路径会填充 unknown qualified_tiers）。",
      "requirement": "SPEC.md 'Preserve failed and unrun slots' 与 T5 'isolate compiler/interface/configuration/numerical/evidence failures'——失败槽位应以完整 schema 呈现，避免下游以字段缺失作静默处理。"
    },
    {
      "id": "F4",
      "severity": "info",
      "file": "experiments/backends/support/precision_breadth_run.py",
      "lines": "102-110",
      "trigger": "freeze 中 spectre/openvaf_r_ngspice/gnucap_modelgen 的 deck 追加/替换补丁与 precision_binding_run.py:31-39 逐字重复；且当生成文本不含预期锚（如 ' method=trap\\n' 或 '.options numdgt=17 dtmin=1e-15'）时，str.replace 静默无效果，不抛错。",
      "impact": "若 inputs.decks 生成格式变化导致替换锚失效，open 后端将以未打补丁的 deck 运行；其后果被下游保守地拦截（gnucap 的 method readback 在 precision_report.qualification:50-53 会因 method 缺失报 issue；ngspice 的 trtol/chgtol/itl4 为记录性 extra），但 ngspice 分支替换失效时 deck 仍含 ' method=trap'，method readback 可通过，仅丢失 trtol/chgtol/itl4 附加控制而无任何告警。属可察觉性弱的重复代码漂移点。",
      "requirement": "SPEC.md 配置身份（controls 小节冻结 trtol=7, chgtol=1e-14, itl4=10）应以可验证方式写入 deck 并在 freeze 侧断言替换确实发生。"
    }
  ],
  "missing_context": [
    "precision_v2.py（observation_plan/load_contract 的真实实现）、precision_reference.py、precision_breadth_foundation/composition.py 未提供，无法核对冻结计划中的观察请求与 Q3 网格生成细节。",
    "runner.py 中被复用的 preflight/verify_tool/stage/result_state/effective_settings/directory_budget 已提供，但其上游 settings_readback 解析对六位有效数字 maxstep 的实际行为（SPEC 已声明的配置证据缺口）只能据文档确认，无法据日志验证。",
    "新 breadth 批次的实际 PROFILE_BINDINGS.json / SELECTION.json / 执行产物不存在，无法做运行侧一致性核对（按范围排除）。",
    "precision_report.py 的 qualification 中 spectre 分支引用 scoped_readback/psf_effective 的完整字段结构由 settings_readback.spectre 佐证，但无真实新日志可复核。"
  ],
  "limitations": [
    "纯静态文本审查：未执行任何代码、未访问文件系统或仓库；所有结论仅基于所供固定源文本与旧归档摘要。",
    "旧 Spectre 摘录（21.1.0.509.isr12、binary sha、precision='%.17g'、annotate=steps 配方、accepted tran steps 计数行）仅证明 spectre_accepted_rows 的解析锚与版本门限与历史真实日志格式一致，不构成新执行或通过证据；新运行必须自行产生这些回执。",
    "core/foundation/composition 数学参考、模拟器语义及 production simulator 已有独立审查，本审查未重评 precision_breadth.assess 的数学正确性，仅确认 runner 对其输出的消费门（第 186 行三重合取）不产生伪合格。",
    "open 后端（openvaf_r_ngspice/gnucap_modelgen）在 runtime_control_evidence 与 native_observation_evidence 中恒为 unknown 属声明的故意设计，未按缺陷处理；同理，Spectre 深日志六位 maxstep 渲染导致的配置证据缺口按 SPEC 既定处理（deep_bound 0.0004），不算新缺陷。",
    "F1/F2 均被第 186 行合取门与哈希冻结缓解为不可触发的最终伪通过，仅列为回执语义与链路闭合性问题；未发现分母变化、静默跳过请求、或 defer 导出被标记为科学成功的路径。"
  ]
}
```
