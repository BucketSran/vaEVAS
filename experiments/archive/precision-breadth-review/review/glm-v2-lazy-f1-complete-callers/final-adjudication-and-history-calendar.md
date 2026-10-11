# F1 最终裁决与 history-calendar 只读补核

生产固定 `c2542e5b499060db1f047fdb4e9f5de32ced58da`；供审 Frame 测试固定 `fd79b59fa90070ef536c812d5b0aa20d918c5a11`。实际 GLM 完整调用者复审见 `review.md`；原 medium finding、缺 context 的第一复审及所有收据都保留。

结论：同刻已认证输出与恢复普通路径后的算子名义值不同是事实。完整 GLM 复审未找到当前可达的错误接受/拒绝，将 F1 降为条件性文档缺口。当前重算、guard 准入与连续依赖限制，加上 519d5e28 的显式说明、fd79 生命周期回归和 6986959e/a8446fcc 实际公开负控，满足本次固定生产修复的双审义务。该结论不代替后续正式 213 条复验或实际矩阵验收，也不保证未来扩展仍安全。

## history-calendar 补核

本 reviewer 逐行读取 `transient_history_calendar.rs` 全文，当前字节与 fd79 固定源完全相同，副本保存为 `history-calendar-fixed.rs`。该模块未在最后实际 GLM prompt 中提供；以下是 Codex 只读调用路径核验，不能归属为 GLM 的执行或覆盖。

- `initialize`（6–36）只构造 Operators 与 calendar，不构造 Frame、不精化。
- `accept_history_events`（40–51）转入已供审 `accept_changed_events(...Strategy::History)`；该路径通过 `prepare_changed_batch → prepare_batch_until → prepare_root_window` 构造事件帧。
- `prepare_physical_history`（54–136）使用传入候选的 state bounds/operator history，必要时经 GuardTrajectory 准入建立 local epoch；不读取 accepted.solution，不设置 ordinary 精化。
- `prepare_history_future`（138–329）对 before/after/continuous_after 构造 GuardTrajectory，在 `keeps_guard_value` 与区间符号判定后重排 calendar；不构造 Frame、不复用旧 RHS/认证电压、不授予后来 ordinary nominal 精细证书。IdtMod 与其正弦的相关 guard 仍由已审 check_guard 递归拒绝。

该模块无新绕过路径或反例。此核验不是穷举全系统的证明；未来放开 phase/sine guard、连续依赖、同刻增量提交或混用旧解/新 nominal 时必须重审。

## 明确纠正模型辅助推断

两份增量 GLM 报告把 `discarded_trials=1` 当作 lazy retry 触发佐证。这不成立：retry wrapper 本身没有增加该计数，不能从该值单独归因到精化。有效触发证据是 fd79 的普通 impl 拒绝、wrapper 成功，以及独立探针的名义值差异。原模型报告不改写，仅在此纠正归因。

GLM F2 称前缀文案变化不会被 fd79 报警也过强：fd79 要求 ordinary impl 失败后 wrapper 成功，文案改变而禁用 retry 会令 unwrap 失败。仍保留错误消息文字耦合的低维护建议。F3 无可精化算子也重算是低效率建议，方向保守。F5 无专用 retry 计数属于可选诊断，不能据此否认已有直接 Frame 证据。

## 后续纯文档与测试

519d5e28 四行文档明确输出绑定已认证解、内部 nominal 不保证逐位同，当前依赖拒绝与后步重求解，以及未来重审条件。6986959e 把供审独立输入 cross/Decimal 原预算/相关 guard 拒绝加入公开 tests；a8446fcc 增加同点事件 waveform_accuracy 负控。这些纯文档/测试提交在 GLM 运行中到达，已独立对比来源，未宣称进入该 prompt。两份 postfreeze consistency JSON 保留精确文件 hash。Astra 的实际独立新公共测试通过记录在其固定裁决报告；本 reviewer 未执行模拟器。
