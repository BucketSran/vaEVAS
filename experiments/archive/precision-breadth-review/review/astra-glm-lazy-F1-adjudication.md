# Astra：GLM lazy F1 独立裁决

固定生产 c2542e5b499060db1f047fdb4e9f5de32ced58da，现有生命周期测试 fd79b59fa90070ef536c812d5b0aa20d918c5a11。阅读 GLM `glm-v2-numerical-lazy-evidence/review.md` 后独立追踪调用者并运行本地探针；未改 tracked 文件，未跑远端。

结论：GLM 所述“同帧代表值不相等”观察成立，fd79 原测试不能证明该相等性。但在当前准入与消费路径下，没有复现其声称的同刻 guard/expression_tolerance 错误接受或拒绝；不将该观察单独定为已证 P2 行为 bug。这个结论依赖下列具体条件，不是对未来 phase-root 支持的保证，也不解除最终实际矩阵验收。

## 直接观察

独立审查快照给 fd79 测试仅加打印（生产无变化），在 4.5 us 得到已提交 solution.y=-7.657137397853899e-16，同刻 ordinary operator sin=+1.2246467991473532e-16，ordinary phase=0.5。精化后的实际输出 phase 为 0.5000000000000001。两种表示的差异约 8.88e-16 V；普通 sine 包围 [-1.1990408665951705e-14,9.325873406851329e-15] 包含两者。精化输出使用自身的原预算证书，不能把后一次 ordinary 名义值解释为精化数学值错误。

fd79 只要求宽包围恢复、门控和回滚，确实没有要求同刻 nominal values 相等。因此不能用原 fd79 声称该事实已被排除。

## 当前调用路径为何没有沿用错误证明

1. lazy 入口仅有空 events、空 fired_roots、点窗口。event_conditions::select_at_roots 在空 events 下产生空 actions；events::apply 从 before 拷贝，只有 actions 才写状态。因此这一 ordinary 精化不会把新的算子代表值写入事件保持状态。未来的事件写状态仍要重新 settlement。
2. transient 主循环在模型有 operators 时，每一步都重新 prepare_root_window；settlement::prepare_impl 重建 joint/circuit、当前 RHS、代表值及包围认证。accepted.circuit 只供 reuse_affine_factor_from 复用完全一致的数值矩阵因子，旧 RHS 和旧电压不代替新求解。新名义近似若不再满足预算，会再次拒绝或走符合条件的完整精化。
3. GLM 点名的 prepare_batch_until 先调用 prepare_root_window 构造本次 next，然后才将 next.solution/next.states/next.operators.values 传给 guard。该调用包含事件或 fired roots，不能启用 ordinary refinement；它不是把先前普通精化 frame 的 solution 原样与新算子值拼接。
4. events 的 guard_operators 从结构依赖经节点关联传播；GuardTrajectory::new_held 调 Operators::check_guard。IdtMod 不在支持集合，Sin(Operator) 递归检查父算子，所以 phase/sin-phase cross 及经节点投影的相关 guard 均拒绝；系数抵消也不能绕过结构检查。允许的独立输入 guard 不读这两个相位近似的差异。
5. 连续网络 select_operator_dependencies 只接受 Idt/LaplaceNd/Ddt 动态依赖，不能将 phase/sine 的新代表值偷偷用作未来连续历史的初值或强迫源。IdtMod/Sin 的 advance 本身不写历史。普通返回 frame 的输出收集直接消费已经认证的 solution；没有给后来变宽的普通 operator bounds 冒充同一精细证书。
6. 非点事件观察包括全部算子，其 IdtMod 路径仍没有合法事件窗证书，按现合同返回 event_resolution。更宽 ordinary bounds 导致后续拒绝时，未绕过最终 certify。代码中未找到把 accepted 精细 solution 证书直接授予后来 ordinary 代表值的消费者。

## 独立公开接口探针

使用 c254 独立 debug kernel（SHA c6c60ae5647ea702981cc93a630c4b09e95f430221c0c43b6e9a3b61efdf7cf7），DUT 为 idtmod(750000,.125,1,0)→sin(2πphase)，输出 phase/y/n，额外输入 u 与 cross 更新整数计数。原预算 absolute=1e-14、relative=1e-10，max_step=5 us，stop=5 us。探针与结果在 `astra-fixed-c2542e5b/independent_f1_guards_binary.py/json`。

- u=[(0,0),(2^-17,1)]，先在 4.5 us 取得精化输出，再在精确 4.76837158203125 us 处理 cross(u-.625)：实际 guard_value=0，计数 0→1；4.8 us、5 us 后续输出通过。
- 改为 cross(u-.589824)，事件恰在 4.5 us：原 same-time waveform_accuracy 拒绝，bound=1.2112873345866442e-14、budget=1.0000000000012245e-14。没有拿普通点的精细证明替事件取得通过。
- cross(phase-.5)、cross(y)、cross(u-.95+phase-phase) 均 unsupported_cross。最后一项验证代数抵消没有放开相位结构依赖。
- 另用十进制 PWL [(0,0),(5e-6,1)] 的相关输入 root，非点事件窗口仍 event_resolution。此失败记录保留于 independent_f1_guards.json。

探针初版曾错取响应顶层 events，产生本地 KeyError；正确字段为 transient.events，修正报告脚本后重跑得到上述实际结果。不是模拟器失败，也不据其断言事件缺失。

## 裁决边界与后续触发

当前无需为了 nominal 值按位相等而盲目增加缓存。建议文档明确：精化绑定本次已认证输出，ordinary 查询仍可返回另一个保守包围内的代表值；它不能继承旧输出的精细证书。若未来支持 phase/sine cross、相位驱动连续历史、同刻增量提交而不重新 settlement，或新增直接组合 accepted.solution 与重查算子 nominal 的消费者，应重新审查并建立同帧绑定机制。若出现具体合法 DUT 的错误事件/输出或误用证书，应以该反例修复，而不是依赖本次有条件裁决。

GLM F4 的生命周期证据缺口由 fd79 的独立通过补齐，不能抹去 GLM 当时只见 c254 的范围限制。F2 消息前缀耦合和 F3 无可精化算子时重复失败工作属于保守维护/效率问题，本次未证实为 P1/P2；不得把 VCO 单例恢复外推为普遍性能保证。


## 固定文档与公共回归补核

再次只读审查文档 519d5e2805c40f2534a781e7dce4b78fbfde01b9、公共测试 6986959e35cf97eeae46d33992239c3cac092b85 与 a8446fcc0cfddb254f523a938e66ff5d671ef722。无新增 P1/P2。

519d 文档准确说明已认证输出与后续 ordinary 代表值不保证逐位相等；列出无事件赋值、phase/sine guard 与连续依赖不开放、后续重新求解与原预算认证，并明确开放依赖或改变复用方式时必须重审。它没有将 F1 的观察否认，也没有承诺任意未来消费者安全。

6986/a844 公共回归保留 4.5 us 普通精化点、精确后续输入 cross 和 0→1 计数，按原 binary64 系数的 Fraction/Decimal 独立参考检查电压；同刻 cross 仍要求 waveform_accuracy，phase/sine/结构抵消 guard 仍要求 unsupported_cross。独立将固定 a844 的 test_phase.py 放入审查快照，使用原 c254 独立内核运行唯一新增测试：1 passed（0.076 s）。没有重跑整矩阵或全部旧测试。

本人的 c254 固定生产增量审核在上述范围内可闭合。实际 GLM 对完整 transient 与全部 callers 的重裁仍待其返回；前一次误切 test helper 的报告和缺上下文限制保持保存，不能据它提前宣称双审完结。`discarded_trials=1` 是调度舍弃计数，不能作为 lazy retry 触发证明；真正触发证据来自 fd79 的 ordinary impl 拒绝→wrapper 成功及独立观察到的精化值。
