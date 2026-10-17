# 有界物理源曲线与事件组合

IR24 为有限连续 PWL 提供原始有理角点。内核验证物理曲线始终位于名义 PWL 的原非零电压误差带内，再用物理曲线求值、导数及完整 cross 分区；转浮点的舍入界仍进入下游验收。有限采样算术、无环 transition 条件和中断直线证明的范围见[数学合同](../../../../evas/docs/math/events.md#causal-transition-composition)，字段及资源边界见[源曲线合同](../../../../evas/docs/math/events.md#physical-source-shape)。仅有幅度界时，原动态拒绝边界保持。候选未合并，包版本沿用 0.19.0；IR1–23须从原 VA 重编译。

七项机制对照覆盖 pulse 到 cross/transition、反向接地与保持 timer 复位、采样乘法与数值关联、冻结 transition 网络条件、内部条件级联、相邻内部根，以及两个独立中断边沿的连续结束点。五项使用保留的实际 Spectre 原始数据，两项为新增实际执行；全部 EVAS 输出在同一最终冻结内核上重新运行。

[紧凑结果](reference.json)保留全部 403 个精确共享原生时刻、原行、设置和哈希；[完整输入](inputs.json)保留两后端的物理模型、源参数和初态。所有原生参考点另按独立 Fraction 答案检查。连续电压比较预算为原定 10 nV，最大共享点差约 0.445 nV；离散值仅在原定 1 ps 事件窗内检查相邻可能值，不移动时间轴或删去窗口。该窗口对照不证明窗口内的严格次序；EVAS 的严格根顺序另由[独立相邻查询测试](../../../../evas/tests/test_transition_event_conditions.py)检查。

参考为 Spectre 21.1.0.509.isr12，请求 reltol=1e-10、vabstol=1e-12 V、traponly，实际生效 reltol=1e-11。每例 maxstep 及请求/生效差别均见收据。执行沿用 90 s、4 GiB、32 MiB、单线程与 30 s license 等待上限。EVAS 不使用 Spectre 的积分方法、iabstol 或 preset。完整 PSF、响应、源码冻结包和运行收据为本地 `runs/evas-source-shape-20261017/` 证据，远端原件保留；未声称这些商业参考原始数据可以公开下载。

[23 条原请求结果](originals.json)保持原模型、刺激、初态、容差、checker、normalization、每例120 s内核及150 s worker预算。同一最终冻结内核完整执行23例，原checker通过22/23，23例guardian清理均确认；不增加正式Q成绩。候选的唯一原checker失败为347，具体差异及完整物理输入保留在[兼容诊断](compatibility.json)。

347 的时钟数学根约为135.05 ns，根处 enable_req 比0.45 V阈值高约4.87e-14 V；按EVAS既有 `te=tau` 合同应释放复位。checker却用首条高时钟保存行135.1 ns的enable_req=0推断该事件，从而产生本拍复位和下一拍模拟使能两处失败。实际Spectre在根后约5.8e-20 s回调，条件已翻转，原checker通过。两种行为和原判定均保留。用户选择保留现行语义并交付未合并候选，不把这一差异改写为23/23。

独立回归入口包括 `test_source_shape`、`test_causal_event_math`、`test_event_value_precision`、`test_transition_event_conditions`、`test_exact_transition_deadlines` 及 Rust 生命周期测试。它们分别检查物理角点、误差放大、关联值、候选回滚、请求级预算、observer-only数学结构拒绝和真正无法认证的期限次序。参考缺少原生 t=0 行时，初态由公共回归独立检查。
