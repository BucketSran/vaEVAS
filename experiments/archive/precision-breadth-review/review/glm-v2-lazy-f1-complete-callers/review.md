```json
{
  "scope": "基于本次补全的完整 transient.rs（含 prepare_root_window 包装 288-313、prepare_root_window_impl 315-460、prepare_batch_until 513-633、run_inner 702-1066、run_stateless_transient 1068-1127）对先前 F1（lazy 普通相位精化提交帧内精化解与非精化算子历史代表值不一致）的独立重裁；同时复核 fd79 测试对 Frame 生命周期回归的覆盖，并给出 F2/F3/F4/F5 处置。评审对象为 supplied 全文（transient.rs、operators.rs、idtmod.rs、settlement.rs、settlement_bounds.rs、event_conditions.rs、events.rs、guard_trajectory.rs、schedule.rs、strobe.rs、transient_event_acceptance.rs、transient_root_refinement.rs、continuous.rs、solver.rs、operators.md）、fd79 测试 delta，及 Astra 保留探针（仅作可复现声明，非权威）。仅静态审阅，未执行任何代码。",
  "standards": "1) F1 裁决：仅当提交帧内精化解与复位后 ordinary 算子代表值的不一致被某个当前存在的消费者直接消费并导致违背原预算的错误接受/拒绝时，才构成实际行为缺陷；若被整体重算/结构拒绝/最终认证拦截，则降级为一致性文档缺口。2) fd79 回归评审：必须区分“宽包围恢复”与“名义值相等”，不得以 bounds 相等宣称 nominal 一致；须覆盖回滚不变、门控拒绝与标志复位。3) 历史发现保留，只做基于完整调用者证据的重定级。4) Astra 探针按可复现声明对待，其 kernel 二进制与执行环境未经本审阅者验证，仅作方向性佐证。",
  "spec": "完整调用路径独立推导：prepare_root_window（transient.rs:288-313）首次以 refine=false 调 impl，仅当错误 kind=waveform_accuracy、消息前缀 \"cannot certify same-time forward error at \"（与 settlement_bounds.rs:345-346 的 format! 输出一致）、点窗口、events 空、fired_roots 空时，从同一 accepted Frame 以 refine=true 整体重算。impl（315-460）在克隆的 operators 上置标志（333），settle/observed_after/advanced_until 全程使用精化代表值与包围，返回前 operators.refine_ordinary_phase(false) 复位（451）。IdtMod 的 advance 为 no-op（operators.rs:1859），IdtMod 无可变历史，值由 integral+certificate 标志即时求出，故提交帧的算子状态与 ordinary 路径完全一致，不对称仅表现为“已认证 solution 基于精化代表值，而事后 operators.values/bounds 同刻查询返回 ordinary 代表值”。全部 Frame 构造调用方（run_inner:979 普通步进、prepare_batch_until:530、preflight_root_consumer:122、PreparedEvents 输出相位查询 transient_event_acceptance.rs:185）均经包装；含 events/fired_roots/非点窗口的调用被门控拒绝精化，其 guard 检查（prepare_batch_until:549/564 的 next.operators.values）消费的是本次新鲜构造帧自身的值，不拼接旧解。run_inner 提交后同刻仅执行 check_deadline_order（只查 transition deadlines，operators.rs:1733-1771）与直接输出 accepted.solution；下一步/下一事件均从 accepted 整体重算 settlement（settlement.rs:65-154 重建电路与 RHS，accepted.circuit 仅 reuse_affine_factor_from 复用数值因子）。phase/sin 相位 cross 及代数抵消形式被 check_guard/事件结构依赖拒绝（operators.rs:1463-1492、events.rs:638-784）；非点事件窗口 IdtMod 无 event_bounds 证书（operators.rs:1086-1091）返回 event_resolution；连续网络 select_operator_dependencies 只接纳 Idt/LaplaceNd/Ddt（continuous.rs:909-936）。",
  "findings": [
    {
      "id": "F1-重裁",
      "severity": "low",
      "file": "evas/rust_core/src/transient.rs",
      "line": "288-313（包装）、451（标志复位）、975-1000（run_inner 提交）",
      "trigger": "重试成功提交的 Frame 中，solution/states 由精化后的 IdtMod 代表值与精化包围求解并认证，但返回前 operators.refine_ordinary_phase(false)（451 行）复位，此后同刻 operators.values/bounds 返回未精化区间路径代表值。Astra 探针实证该不对称真实存在：4.5us 提交 phase=0.5000000000000001 与同刻 ordinary 查询 0.5 并存，差约 8.88e-16 V，包含于 ordinary sine 包围 [-1.20e-14, 9.33e-15] 内。",
      "impact": "在当前完整调用者下未发现错误接受或错误拒绝：(a) run_inner 每个后续步进/输出点/事件批均从 accepted 帧整体重算 settlement 并按原预算重新认证，旧精化解不替代新求解（accepted.circuit 仅因子复用，solver.rs:728-750 要求矩阵逐位一致）；(b) prepare_batch_until:549/564 的同刻 guard 消费者先经包装构造本次 next 再取值，该调用含 events/fired_roots，精化被门控关闭，帧内自洽；(c) phase/sine 驱动的 cross 及其代数抵消形式被结构性拒绝（unsupported_cross），不消费该差异；(d) 非点事件窗口 IdtMod 无观察证书，返回 event_resolution；(e) 同刻事件失败仍被 same-time 预算正确拒绝（探针 same_input 反例：bound 1.211e-14 > budget 1.000e-14）。另确认 IdtMod 的 advance 为 no-op，提交帧算子历史无“陈旧精化状态”残留——不对称纯粹是解向量与事后查询代表值的表示差异。原 F1 担心的同刻检查错代表值在完整调用者下不成立，降级为一致性文档/审计缺口：同帧两套代表值缺显式绑定或声明，正确性依赖“每消费者整体重算”的隐式契约。",
      "requirement": "原要求 3 的延伸条款在提交帧层面未满足“显式一致性”，但未形成可达行为违规。重新触发条件（未来任一成立须重审）：(a) 支持 phase/sine 驱动 cross guard；(b) 相位进入连续网络历史初值；(c) 同刻增量提交而不整体重算 settlement；(d) 新增直接组合 accepted.solution 与重查 ordinary nominal 的消费者。",
      "suggestion": "保留历史 F1 记录并附本重裁；在 operators.md 补一句显式声明：精化绑定本次已认证输出，ordinary 查询可返回同一保守包围内另一代表值，不继承旧输出的精细证书（现有 596-604 段已部分覆盖）。",
      "disposition": "降级 medium→low，定性为条件性一致性缺口，非已证行为 bug。本次基于完整调用者文本独立确认，不再沿用先前报告的行号推断。"
    },
    {
      "id": "F2-维持",
      "severity": "low",
      "file": "evas/rust_core/src/transient.rs",
      "line": "298-304（前缀判定）；settlement_bounds.rs:345-346（消息生成）",
      "trigger": "重试判定依赖 error.message.starts_with(\"cannot certify same-time forward error at \")，该字符串由 settlement_bounds.rs:345 的 format! 生成，无共享常量或结构化 reason 字段。本次完整文本确认两处一致，但耦合仍在。",
      "impact": "消息文案改动会静默禁用重试（退回保守失败，方向安全）；同前缀非预算错误会触发一次无效重算。fd79 测试只断言 error.kind==\"waveform_accuracy\"，不锁消息前缀，无法报警此类静默失效。本批未修复。",
      "requirement": "要求 1 的可维护性/健壮性。",
      "suggestion": "提取共享常量或为 Error 增加结构化 kind/reason 判别字段供重试判定。",
      "disposition": "维持 low，未变化。"
    },
    {
      "id": "F3-维持",
      "severity": "low",
      "file": "evas/rust_core/src/transient.rs",
      "line": "295-311",
      "trigger": "任何点时刻、无事件、无 fired roots 的 waveform_accuracy 失败都触发第二次完整 settlement 重算（克隆、闭包迭代、两次求解），即使模型无可精化 IdtMod（exact_source=None 时 certificate 直接走原路径，idtmod.rs:80-88）或失败与相位无关。完整文本确认无任何“存在可精化 IdtMod”前置判断。",
      "impact": "失败步成本翻倍，纯性能冗余，方向保守正确。Astra 探针 discarded_trials=1 佐证该路径实际可达且生效（同时部分回应 F5），但失败密集路径的冗余双算仍在。",
      "requirement": "针对 eager 版 VCO 性能回退的 lazy 化修复目标在失败路径的残留成本。",
      "suggestion": "重试前检查 model.program.operators 中存在 IdtMod 且其 exact_source 为 Some。",
      "disposition": "维持 low，未变化。"
    },
    {
      "id": "F4-关闭",
      "severity": "info",
      "file": "evas/rust_core/src/transient.rs（测试模块，fd79 新增）",
      "line": "ordinary_phase_retry_preserves_frames_and_does_not_refine_events_or_roots",
      "trigger": "先前 F4 指出重试路径无端到端回归。fd79 测试补齐：impl 首次失败（kind=waveform_accuracy）→ 包装重试成功且 retried.solution.voltages/state_bounds 与干净路径 clean 逐位相等；before 帧 time/states/state_bounds/whole operators.bounds 在多次失败（含极紧容差 1e-20 整体失败）后保持不变（历史回滚）；带 events &[0]、fired_roots &[0] 确认 waveform_accuracy 直接失败、非点 4ps 窗口确认 event_resolution（对应 operators.rs:1086-1091 IdtMod 无非点观察证书），三者均不触发重试；成功帧 operators.bounds(time) 与 ordinary_bounds 相等且后续 4.500002e-6 步 prepare_root_window 通过（标志复位后未来帧可继续推进）。测试正确地未把 bounds 相等当作名义值相等断言，符合评审标准 2。",
      "impact": "门控条件（点时刻、events 空、fired_roots 空，消息前缀经 kind 间接锁定）与历史不变性在真实调用点被回归锁定，F4 主要缺口闭合。残余限制：测试为函数级（直接调 prepare_root_window/impl）而非完整 run_inner 控制器级场景；事件/fired-root 失败仅断言 kind，无法从外部区分“未重试”与“重试后仍失败”，但二者行为等价、方向保守，不构成缺口。",
      "requirement": "要求 1、4、5 的直接回归证据。",
      "suggestion": "可选增强：加 diagnostics 计数断言区分“未重试”与“重试后仍失败”，同时服务 F3/F5。",
      "disposition": "按新证据关闭（历史记录保留；GLM 当时只见 c254 的范围限制不被抹除）。"
    },
    {
      "id": "F5-部分关闭",
      "severity": "info",
      "file": "astra-fixed-c2542e5b/independent_f1_guards_binary.py/.json（保留探针）",
      "line": "n/a",
      "trigger": "先前 F5 指出保留日志无一展示重试路径实际触发并改变结果。Astra 探针（c254 kernel，idtmod(750000,.125,1,0)→sin(2πp)，vabstol=1e-14）显示 4.5us 提交 phase=0.5000000000000001（≠ordinary 的 0.5）且 transient.discarded_trials=1，共同表明精化重试在该类场景确实执行、按原预算重新验收并改变提交输出；same_input 反例（事件恰在 4.5us 的输入 cross 被 same-time 预算拒绝）佐证普通路径在该预算下确实失败、重试是实际生效路径。",
      "impact": "功能生效性证据缺口在“idtmod→sin 点时刻、紧预算”场景类下由保留探针补上；但代码中仍无重试触发计数/trace 诊断（F3 建议未做），探针属单一模型类别且其 kernel 二进制（SHA c6c60ae5…）与执行环境未经本审阅者验证，不外推为普遍生效性，也不作为权威事实。",
      "requirement": "交付证据完整性。",
      "suggestion": "在重试路径增加 diagnostics::counter（触发次数与前后误差界），使生产日志自带 F5 类证据。",
      "disposition": "部分关闭：生效性方向佐证已获（作为可复现声明），生产诊断缺口仍在。"
    }
  ],
  "missing_context": [
    "transient_history_calendar.rs（history_calendar::initialize、accept_history_events）全文未随批提供，history-calendar 分支下 Frame 构造是否全部经 prepare_root_window 包装未能逐行确认；就 supplied 可见部分，accept 路径经 prepare_changed_batch→prepare_batch_until→prepare_root_window，未发现绕过者。",
    "exact_source.rs（Curve.wrapped、Budget/turn 上限）与 idt.rs（value_minus_linear_boundary_sign、Idt::enclosed）全文未提供，IdtMod 精化数学正确性沿用既有 81a 报告结论，本次未重证。",
    "Astra 探针的 kernel 二进制与执行环境不可验证；其 JSON 结果按可复现声明对待，未由本审阅者执行确认。",
    "全仓调用图未提供，无法穷举是否存在绕过包装、直接以精化状态构造 Frame 的其他调用方（就 supplied 文本，run_inner、prepare_batch_until、preflight_root_consumer、PreparedEvents 输出查询均经包装）。",
    "无重试路径的运行时计数/trace 诊断，生产日志仍无法区分“从未触发”与“触发后仍失败”。"
  ],
  "limitations": "只读静态复审 supplied 完整源、fd79 测试 delta 与 Astra 保留探针；未执行、未构建、未复现任何 Spectre、私有对照或探针脚本；探针 JSON 仅作方向性佐证而非独立验证事实。F1 重裁限于当前可达行为：事件写状态强制重新 settlement、相位/sine cross 结构性拒绝、非点窗口 IdtMod 无观察证书、连续网络不接纳相位依赖——任一前提在未来放开即需重审并建立同帧名义值绑定机制，本结论不是对假想未来支持的保证。fd79 测试为函数级且仅覆盖单一模型形状，不据此宣称控制器全路径或 VCO 以外场景的普遍正确性/性能。数学基础（Taylor/F14、exact_source 有理运算）沿用在既有范围内视为有效，不因本复审关闭。未运行任何 simulator/private Spectre grid/remote proof/scientificpass。"
}
```
