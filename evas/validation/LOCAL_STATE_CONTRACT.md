# 普通 analog 局部量与事件状态

本切片处理 #65 的 65-L 阻塞，属于 LANG、TIMER、EVENT-ORDER 和 DYNAMICS。
这是开发分支行为，Spectre 配对待执行，不表示原始 VCO 或 #65 全部完成。

声明中的 real 变量不会因为另一变量有事件就自动变成持久状态。
`initial_step` 或事件体写入的目标是持久状态，包括条件和静态循环体中的写目标。
每个持久状态仍须恰好一次显式初始化。其余变量按普通 analog 局部量处理，
仅支持 real，读取前必须已有普通赋值。同一目标既有事件写入又有普通写入仍拒绝。
这项分类按写入职责处理，不根据名字或是否恰好初始化进行猜测。

普通赋值按源程序顺序展开，贡献捕获它所在位置的表达式。
对于 `a=u; V(y)<+a+q; a=2*a; V(y)<+a;`，结果为 `y=3u+q`。
`q` 保持为既有 StateRef，事件后读取新状态；局部量不增加 IR 状态槽。
事件可以直接读取输入电压和合法的持久状态表达式。
事件触发器或赋值读取普通 analog 局部量仍拒绝，
即使该局部赋值出现在事件之前，因为当前事件 IR 没有源语句位置的局部快照。
初始化表达式、事件条件、数组和自换向范围沿用原合同。

调用点历史属于实例化的源调用，不属于接收变量。
`a=idt(1,0)` 与稍后的 `a=idt(2,.25)` 保留两个历史槽，
独立积分为 `t` 和 `2t+.25`。改变输出查询集合不改变事件记录或共同查询值。
这不扩大持久状态驱动积分、反馈复位或自换向的接受边界。

实现入口为 `src/evas/instance_compiler.py` 的 `compile`、`local_symbol` 和
`execute_analog`。变量分类在数组标量化后进行；事件目标仍通过既有状态 ID 下发。
已查 Python model 生产/消费、数组与节点展开、静态循环、前端结构判断、IR 序列化、
protocol 状态名验证及 Rust 状态/历史消费。Model、Program、IR18 和 Rust 均未改变。

[公开回归](../tests/test_local_state.py)提供手推预期，覆盖 timer 后的 ramp、
贡献顺序、输入参考方向、实例参数/状态隔离、未赋值量与双重写入负控、
事件合法输入读取和局部别名拒绝，以及积分调用点/实例历史和查询不变性。
[冻结 VA](cases/local_state/dut.va)、[Spectre deck](cases/local_state/table.scs)和
[手写 manifest](cases/local_state/manifest.json)分别保存输入、独立公式及电压/事件容差。
冻结模型同时观察状态，禁止把精确事件时刻的不同前后 stage 当成电压偏差。
必须保留实际原生记录和观察资格证据；仅本地回归通过不能声明 Spectre 对齐。

原 `benchmark/tasks/va05-dynamic-vco/solution/dut.va` 原字节保留。
本切片移除将 `freq/triangle` 错当作未初始化持久状态的首失败，
随后 `cross(triangle-.5,1)` 的局部量读取会明确拒绝。
未来还需定义源顺序局部快照、持久方向驱动 idt、反馈事件未来根和
自换向不确定根窗口的完整合同及实际配对，不能关闭原 VCO 验收。
