```json
{
  "scope": "仅裁决固定v3六条科学轴迁移（EC17/EC18/EC19/EC21/F14/F20 的前后comparison、new aggregate slot、原RESULT/worker诊断/请求/身份）及F1假设；不重复213/852全包，不审新源码，不颁发科学pass。",
  "standards": [
    "六条前后记录中逐slot明列numeric before→after，禁止推断未列出的旧值",
    "净变化须与comparison_counts聚合(109/98/6→108/96/9)对账",
    "原RESULT/worker为deferred/unknown时不授予numeric=pass",
    "内部waveform_accuracy预算与官方reference误差budget为不同门，不得混用",
    "wrap参考包围内命中应记indeterminate(I)，不得判为实际点值错误",
    "单次90s上限附近timeout(90.0165 vs 89.8498)不能单独判算法退化"
  ],
  "spec": "GLM增量裁决：独立读取六条记录，直接列出六numeric before→after，求净变化，判断F1（'109/98/6→108/96/9不能由六处迁移解释、推断旧F14 numeric=pass'）是否成立；若先前medium finding错误须明确纠正并保留初报不覆写。",
  "findings": [
    {
      "id": "ADJ-1",
      "severity": "correction",
      "title": "F1假设不成立：聚合numeric变化完全由六条迁移解释，旧值均可由明列记录读出，无需任何推断",
      "trigger": "六条full_comparison_record的before/after与changed_axes字段",
      "file": "six_full_records（用户消息内平铺JSON）",
      "line": "各记录full_comparison_record.before.numeric / after.numeric / changed_axes.numeric",
      "detail": "六条numeric明列：EC17-v1--Q3: unknown→unknown（changed_axes不含numeric轴）；EC18-v1--Q3: unknown→evidence_insufficient；EC19-v1--Q3: unknown→evidence_insufficient；EC21-v1--Q3: pass→unknown；F14-base--Q3: unknown→unknown（changed_axes不含numeric轴）；F20-base--Q3: unknown→evidence_insufficient。净变化：pass −1（EC21）；unknown −2（三条离开unknown，EC21一条进入unknown）；evidence_insufficient +3。对账：109−1=108，98−2=96，6+3=9，与after聚合完全一致。其余207条numeric不变由fixedCOMPARISON asserted及213core上一包供审，不在本次范围。",
      "impact": "先前报告的medium finding（'109/98/6→108/96/9不能由六处迁移解释，推断旧F14 numeric=pass'）不成立，须明确纠正：F14-base--Q3的before.numeric在记录中明列为unknown（其before original_execution=execution_failed，RESULT qualification=unknown），不可能是pass；真正由pass降级的唯一slot是EC21-v1--Q3（pass→unknown），而非EC17。EC17新numeric=unknown（非pass），与该先前声称'EC17新numeric=pass'也不符——after.numeric与新aggregate slot的numeric字段均明列unknown。初报保留不覆写，本条为纠正记录。",
      "violated_requirement": "先前报告违反'不推断未提供的旧值、以明列字段为准'的裁决准则"
    },
    {
      "id": "ADJ-2",
      "severity": "info",
      "title": "EC21 timeout为X而非算法退化结论；waveform内部预算与官方reference budget属不同门",
      "trigger": "EC21-v1--Q3 before elapsed 89.8498s (status completed) vs after 90.0165s (returncode -15, timeout=true, 90s上限)",
      "file": "six_full_records[EC21].original_raw.before/after RESULT.json stages[0]",
      "line": "elapsed_seconds: 89.84979362413287 / 90.01653360016644",
      "detail": "89.85s→90.02s处于90s上限±0.2%区间，仅能表明运行贴近上限的实际回退/敏感性；单次结果不能判定算法退化，裁决为X（runtime_timeout，numeric/behavior等轴按明列降为unknown，final=execution_failed）。同时EC17/EC18/EC19/F14/F20的before失败reason均为kind=waveform_accuracy的内部同刻前向误差预算（如F14 bound 5.551e-11 vs budget 5.001e-11），这是执行侧内部预算门，与after分析中的官方reference误差budget（voltage_budget≈1.01e-7）是不同判据，二者不可混淆比较，故before execution_failed→after waveform_available不构成数值精度结论。",
      "impact": "防止把内部预算失败史当作科学精度证据，也防止把单次timeout升格为性能退化结论。",
      "violated_requirement": "无（确认性核对，非违规）"
    },
    {
      "id": "ADJ-3",
      "severity": "info",
      "title": "F20/EC18/EC19 phase wrap误差≈1.0为参考包围命中，应保持I，不得判实际点值错误",
      "trigger": "F20 phase worst actual=0.9999999999999999, reference=[0.0,1.0]；EC18 phase worst actual=-0.5, reference=[-0.5000000000000001,0.5000000000000001]；EC19 phase_a/phase_b reference=[-5e-324,1.0000000000000002]",
      "file": "six_full_records[F20/EC18/EC19].after.output_witnesses.phase*",
      "line": "error_upper_V≈1.0000000000000027/1.0000000000000038, unresolved_uncertainty_V≈0.5",
      "detail": "wrap时刻raw half-open端点使参考区间跨整周期，实际值落入包围内属不确定性不足（indeterminate），三条numeric均明列为evidence_insufficient且evidence_issues含'timing or export uncertainty exceeds B/10'，与condition.json的phase_rule/qualification_note（raw half-open endpoint, circular diagnostics never replace scalar error; Full wrap-side observations required）一致。维持I裁决正确。",
      "impact": "无翻案；确认不将这些≈1.0的误差当作数值错误或授予pass。",
      "violated_requirement": "无（确认性核对）"
    },
    {
      "id": "ADJ-4",
      "severity": "info",
      "title": "F14/EC17新numeric=unknown，RESULT仍deferred/unknown，不授予科学pass",
      "trigger": "F14-base--Q3 after.numeric=unknown（105条unqualified_observations，evidence_issues含'no qualified defined reference observations: y'）；EC17-v1--Q3 after.numeric=unknown（phase 143条unqualified_observations，'no qualified defined reference observations: phase'）；两after RESULT.json qualification.status=unknown, reason=analysis deferred",
      "file": "six_full_records[F14/EC17].after 与 new_full_aggregate_slot",
      "line": "numeric: unknown; evidence: evidence_insufficient; final: evidence_insufficient",
      "detail": "两slot虽有waveform与behavior=pass/config/native/runtime=qualified，但numeric/evidence明列非pass，final=evidence_insufficient。本次裁决不为其颁发任何科学pass，符合'原RESULT deferred/unknown不颁发科学pass'。",
      "impact": "无违规；确认门控未被绕过。",
      "violated_requirement": "无（确认性核对）"
    }
  ],
  "missing_context": [
    "六条之外的207条numeric轴不变性本次未逐条验证，依赖fixedCOMPARISON asserted与213core上一包（用户声明已供审），属本裁决范围外。",
    "build/raw字节hash不重算（fixedREADY及独立audit职责），本裁决采信记录内hash字段。"
  ],
  "limitations": [
    "静态只读裁决，无工具执行、无文件系统核验；所有结论仅基于用户消息内平铺文本。",
    "初报保留未覆写；ADJ-1为对先前medium finding的明确纠正（correction），非历史改写。"
  ]
}
```
