```json
{
  "scope": "对固定提交 5fce77d6926794331a5beebfa16151cf18485e06 的 core/foundation/composition 数学与资格判定增量做独立只读静态复审，完整依据本消息提供的文件：precision_breadth.py、precision_breadth_composition.py、precision_breadth_foundation.py、precision_reference.py、precision-v2.json、test_precision_breadth_{core,composition,foundation,runner}.py、precision_breadth_run.py、precision_run.py（节选）、precision_report.py、inputs.py、observations.py、runner.py（节选）、SPEC.md、INTERFACE.md、COMPARISON-METHODOLOGY.md 与 math/events.md 节选，以及先前采集的真实 Spectre 工件摘录。重点复审修订 934cd1fa/db36c834/a6a6c71e/f17face9 的集成结果：相位/输入拓扑资格、元数据与校准、F14 初始化时间盒、raw 相位与完整 transition 负控制、logic_out 保留字修复。未执行任何代码、测试或仿真。",
  "standards": "SPEC.md 第 7-17、31、35 行（固定组分母、事件/时间不确定盒保守包含、raw 相位独立义务、单一公共回调历史、正负校准控制、边界与单向义务不可静默跳过、未决语义保持可见）；INTERFACE.md 第 5-11 行卡/reference API 与第 14-25 行预冻结澄清（cross 双容差法定窗口且不裁剪实测括号、L1 输入增益、idtmod 半开精确点、计数阶段仅在整段历史验证后可信、16*ulp(stop) 时间盒与 time_uncertainty_included）；COMPARISON-METHODOLOGY.md L204-206 与 math/events.md L260-283 的 cross 容差契约。",
  "spec": "对照结论：(1) cross 法定窗口按 INTERFACE.md L7 显式定义为 nominal-early 至 min(nominal+late, expr_tol/|slope|)（precision_breadth.py:187-189），实测括号由计数器行导出且从不裁剪（:179-200），非法窗口外为 behavior_error、部分重叠为 unknown；(2) 单一全局 event_bounds_s 深拷贝传给每个 reference 调用（:284-305），stage 仅在 behavior['errors'] 为空后由当前行计数器值构建（:299-304），符合 INTERFACE L25；(3) reference_time_uncertainty_s 注入副本卡（:289-291），未声明 time_uncertainty_included 时核心追加 slope*ut（:359-360）；(4) 未知原生相位/输入拓扑/精确输入证据分别以 unqualified_observations 记录并使 numerical 变 unknown，而任何已合格输出的确认失败仍产生 numerical_error（:362-394），满足'未知保持未知、他处确认失败仍为 numerical_error'；(5) composition 参考对折返相位用 _phase_serialization 在跨折返时保留整个半开区间（composition:523-534），对 EC16 t=0 序列化盒做 DC/瞬态 hull（:659-665），对非末位 transition 窗口事件在 else 分支返回已累积 hull 而非仅新状态（:466-472），并有 test_nonlast_transition_keeps_old_branch_across_query_time_box、test_nonlast_transition_window_contains_independent_rational_replay（独立 Fraction 状态机）与 test_transition_completion_uncertainty_contains_both_history_branches 三个新负/正控制；(6) foundation F14 在序列化盒触及零时显式并入 DC 值 0（foundation:350-354），折点邻域返回两侧 hull，time_uncertainty_included=True 为真；(7) logic_out 保留字修复（foundation:59 与测试 :60-67）保持 F03 组数与 logic 语义校准；(8) F20 raw 相位负控制改用真实 grader 路径 assess 并验证 phase+1 整周期偏移被拒（foundation 测试 :222-231），替代了先前退化的链式比较断言。",
  "findings": [
    {
      "id": "G1",
      "severity": "low",
      "classification": "semantic_visibility_gap",
      "file": "evas/validation/paper/precision_breadth_composition.py",
      "line": "221-227",
      "trigger": "EC21 使用 @(timer(next,0,TT))，next 在 0.125T 事件中由 0.625T 改写为 0.375T；参考冻结为在 0.375T 触发并给出闭式解 1/(4/3-2r+t)。卡片未设置 support_probe_only，也未携带 qualification_note 说明'timer 参数在离散变更后按新值调度'这一语义假设；SPEC L31 仅把 EC05/22/23/24 列为待支持组，EC21 不在其列。",
      "impact": "若某后端在 initial_step 即按 0.625T 调度且不重评估 timer 参数，该组将按冻结参考被判 numerical_error（不会错误通过，方向保守）；但该未证语义假设在卡片元数据层面不可见，违反 SPEC L31'record explicit current behavior and independent equations, do not silently redesign'所体现的显性化要求，也不同于同文件 EC05/22/23/24 的显式标注惯例。",
      "requirement": "SPEC.md:31；SPEC.md:7（语义未决组保持可见）。",
      "classification_note": "非数学错误；属元数据/可见性缺口。"
    },
    {
      "id": "G2",
      "severity": "low",
      "classification": "test_gap",
      "file": "evas/tests/test_precision_breadth_foundation.py",
      "line": "49-67",
      "trigger": "F03 的三元链输出 tern（源码 foundation:59，dc_rows 特意构造 (a,b,c) 全组合）与 F10-common-mode 必测变体（foundation:89-93，inputs 整体 +0.125V）均无手写锚点断言：test_dc_equality... 只校验 lt/le/gt/ge 与 F04 的 y；test_logical_expression... 只锚定 logic_out；test_pure_relations... 的 self.card('F10') 取首个匹配即 F10-base，common-mode 变体无任何独立期望。",
      "impact": "三元链优先级与共模输入下参考-输出一致性这两项特性缺少独立校准；SPEC L17 的手写锚点/正负控制要求在冻结卡范围内未完全覆盖。共享 core 的通用负控制（缺行/NaN/超差）不针对这两个特性。",
      "requirement": "SPEC.md:17 'Include handwritten anchors and positive/negative calibration controls'。"
    }
  ],
  "prior_findings_disposition": {
    "core_F1_紧急尝试上限": "超出本次冻结范围：scope 明确 runner 文件仅为 caller context 且 runner 配置变更被排除；precision_breadth_run.py 全文已供，确认仍无 1000/2000 次尝试累计计数，但该义务属执行资源治理而非数学资格门，按审查指令不列为当前缺陷。",
    "core_F2_cross窗口收窄": "驳回：INTERFACE.md L7 与 COMPARISON-METHODOLOGY.md L204-206、math/events.md L270-275 明确把 expression_tolerance_V/|slope| 并入法定 late 界且'never clips the measured callback bracket'；precision_breadth.py:188-189 与 composition _event:33 的实现与契约一致，实测括号未裁剪。",
    "core_F3_边界未定义点": "驳回（当前范围无触发）：全部冻结卡的 undefined_points 均为内部点（F14 在 T、2T）；0<=left<time<right<=stop 的不变式对现有案例可满足。",
    "core_F4_校验缺口": "大部分驳回：counter 引用已校验（:58-63），undefined_points 结构已校验（:64-70）；critical_times_s 非有限值会被 critical_points 的 0<=t<=stop 过滤排除，无实际影响。",
    "core_F5_early_s>nominal": "驳回：precision_breadth.py:56 已强制 nominal_s-early_s>=0。",
    "core_F6_测试覆盖": "大部分驳回：起止覆盖/观测间隔/输入电压偏差负控制（core 测试 :260-274）、cross 双容差（:120-128）、NaN 输出（foundation :244-247）、F19 错误沿（foundation :233-242）均已存在；残余缺口收敛为本报告 G2。",
    "core_F7_open后端runtime_control未知": "维持为显式未决证据（非缺陷），与'未知保持未知'一致。",
    "foundation_F-1_F14丢弃t=0样本": "驳回：foundation:354-357 对 t==0 显式追加 DC 值，时间盒 [0,high] 的两侧值均进入 hull。",
    "foundation_F-2_t>=hi右连续分类": "驳回：右连续语义为文档化意图并有专门校准（test_callback_point_is_right_continuous_at_upper_bound）；核心 _event_history 由行间计数变化导出括号，不受该单点影响。",
    "foundation_F-3/R1_退化断言": "驳回：该断言已删除，替换为经真实 assess 的 phase+1 整周期负控制（foundation :222-231），且确认 sin 仍 pass、raw phase error_lower>.99、全 tier numerical_error。",
    "foundation_R2_F03/F04无界增益": "驳回为已缓解：卡片携带 input_exact_evidence_required=True，core 使相关输出全部 unqualified、numerical=unknown（core :344-372），数值增益仅进入 conditional 指标，不影响 pass 判定；test_real_threshold_and_case_branch_need_actual_exact_input 提供负控制。",
    "foundation_R3_timing_evidence_required整卡设置": "驳回：core 仅在'timing_evidence_required 且无 events'时追加 issue（:221-222），对可观测事件无副作用，F07/F19 可正常取得计数器括号。",
    "foundation_R5_硬编码两个slew追赶点": "维持为信息级维护提示，冻结输入下无错误，不列为缺陷。",
    "composition_F1_transition非末位窗口丢旧分支": "驳回：当前 _transition（composition:438-474）在 else 分支返回已含旧分支的累积 hull，straddle 分支 hull(旧,新)；新增三个独立测试（含精确 Fraction 标量状态机重放与 .5 错误状态排除控制）覆盖该路径。注：test_nonlast_transition_window_contains_independent_rational_replay 属同实现语义的重放校验，不构成独立数学证明，但其与 test_transition_completion_uncertainty 的端点枚举共同提供了合理证据。",
    "composition_F2_EC16_t=0点值": "驳回：composition:659-665 已对 ts.lo==0 做 hull(_i(0), 瞬态右值)，test_dc_derivative_boundary_encloses_positive_serialization_times 验证。",
    "composition_F3_EC17_out增益7": "驳回（前次推导有误）：输入扰动经积分路径 δphase<=0.25*ε*4T=ε，sine 全局增益 2π，总增益 <=2π≈6.28<7；da/du 的 1.5 是对时间的瞬时频率斜率而非输入电压增益，卡片注释与 test_vco_input_gain_bounds_integrated_voltage_perturbation 一致。",
    "composition_F4_零增益编码": "驳回为已缓解：core 对 input_gain_evidence_required 命中的输出强制 unqualified/numerical unknown（:342-372），0.0 值不进入任何 pass 路径，仅在 conditional 指标中出现，与注释声明一致。",
    "composition_F5_测试缺口": "驳回：冻结次序负控制（composition 测试 :89-107）、order evidence（core :293-307）、非末位 transition 负控制均已补齐。",
    "composition_F6_EC21语义": "维持并收敛为本报告 G1（降级为元数据可见性缺口）。"
  },
  "missing_context": [
    "precision_query.py、settings_readback.py、process.py、observations 的底层 dvs2 解析器（analyze.py/suite.py）与 evas 前端/内核源（compile_sources、transient、continuous.rs）未提供：EC05/22/23/24 的支持性结论、Issue #70/#131 历史、strobe_evidence 的 origins 语义只能按卡片 qualification_note 与 precision_report.py 文本采信。",
    "composition-inventory.md 与 foundation-inventory.md 未提供：手写锚点与义务清单只能按测试文件内嵌锚点核对（本复审独立重推导抽查 EC01 采样保持、EC02 中断反转、EC06/EC07 复位面积、EC11/EC12 滤波直通项、EC16 直通项 1/2、EC18 负频相位、EC20 近时钟面积、F01-F20 初始值与 L1 增益表，均一致）。",
    "四后端实际运行产物（T5 执行矩阵）不在本次范围：提供的 Spectre 工件（LP-IDT--deep_bound，accepted steps 21614，strobetimes 267 项，precision=%.17g、annotate=steps/annotatedigits=16/skipcount=1/compression=no）仅用于确认 runner 的 native_observation_evidence 匹配配方与真实日志格式一致（log L86 'precision = %.17g' 与 deck L5-6 选项均匹配 spectre_accepted_rows 的检查 token），不构成对任何组通过与否的判定。",
    "precision-v2.json 已提供并核对：tiers 因子 10/1/0.1、time_serialization_ulps=16、count_V=1e-6、global_gap_units=0.0625、boundary_distance_s=2.1e-12、各 fraction 与 observation 常量，与 core/测试中使用的常量一致。"
  ],
  "limitations": [
    "纯静态只读评审：未执行任何代码、测试、仿真或文件系统/仓库访问；不声称任何运行结果。测试文件中的断言仅作线索，作者公式经本复审独立重推导抽查（非穷举形式证明）。",
    "Decimal 区间算术（_I/_exp/Interval）的外向舍入按 Python decimal 语义采信；_sin_cycles 的 1e-15 折返/PI 舍入项与 _sin_phase 的 Taylor 余项做了量级合理性核对，未做严格证明。",
    "runner 相关（尝试上限、容器清理、设置读回的正确性）按 scope 仅作 caller context，未评审其变更；提供的 Spectre 工件为先前采集的真实文件摘录，非本次新运行。",
    "EC05/22/23/24 为 support_probe_only，reference 抛 NotImplementedError 且 core 强制 evidence_insufficient（core:334-336），其底层语义争议（transition 作积分依赖、同刻 OR 合并、自换向 cross 历史、隐式 DAE）超出可判定范围，保持显式未决。",
    "G1 的最终定性依赖后端 timer 参数重评估的实际语义证据；G2 为校准覆盖缺口，均不阻塞当前数学参考的保守性结论。"
  ]
}
```
